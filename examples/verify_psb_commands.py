#!/usr/bin/env python3
"""EA-PSB 10000 command/readback verification utility.

This script exercises the public command surface of the ea_psb10000 driver.
For writable settings it normally performs the following sequence:

    1. Read the original value and instrument status.
    2. Write a different, safe test value.
    3. Query the value back and capture status again.
    4. Verify that readback matches the requested value.
    5. Restore the original value and verify restoration.

The DC terminal is forced OFF before ordinary write tests. Commands that can
energize the output, disrupt Ethernet, change master/slave operation, alter an
optional interface, run the function generator, enable the watchdog, or reset
the instrument require explicit command-line flags.

Requires the ea_psb10000 package built for this project.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    from ea_psb10000 import PSB10000, ArbitrarySequence
    from ea_psb10000.subsystems.errors import KNOWN_SCPI_ERRORS
    from ea_psb10000.util import parse_scpi_error
    from ea_psb10000.exceptions import (
        PSBAlarmError,
        PSBConnectionError,
        PSBError,
        PSBSCPIError,
        PSBUnsupportedFeatureError,
    )
except ImportError as exc:  # pragma: no cover - user environment dependent
    raise SystemExit(
        "ea_psb10000 is not installed. Install the driver first, e.g.\n"
        "  python -m pip install ea_psb10000-0.2.1-py3-none-any.whl\n"
        "or from the driver source directory:\n"
        "  python -m pip install -e .\n"
    ) from exc


PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
INFO = "INFO"
ERROR = "ERROR"


@dataclass
class Result:
    index: int
    group: str
    name: str
    command: str
    result: str
    original: str = ""
    requested: str = ""
    readback: str = ""
    restored: str = ""
    status_changed: bool = False
    status_delta: str = ""
    detail: str = ""
    elapsed_ms: float = 0.0


def clean(value: Any) -> Any:
    """Convert enums/dataclasses/tuples to JSON-friendly ordinary values."""
    if hasattr(value, "value"):
        return value.value
    if is_dataclass(value):
        return {k: clean(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [clean(v) for v in value]
    return value


def text(value: Any) -> str:
    value = clean(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def value_equal(a: Any, b: Any, *, rel: float = 1e-7, abs_tol: float = 1e-6) -> bool:
    """Compare protocol values without treating strings such as "OFF" as truthy booleans."""
    a = clean(a)
    b = clean(b)
    if isinstance(a, bool) or isinstance(b, bool):
        if not (isinstance(a, bool) and isinstance(b, bool)):
            return str(a).strip().upper() == str(b).strip().upper()
        return a is b
    try:
        af = float(a)
        bf = float(b)
    except (TypeError, ValueError):
        return str(a).strip().upper() == str(b).strip().upper()
    return math.isclose(af, bf, rel_tol=rel, abs_tol=abs_tol)


def numeric_compare(abs_tol: float, *, rel_tol: float = 0.0) -> Callable[[Any, Any], bool]:
    """Return a comparator that understands the PSB's finite DAC/readback resolution."""
    def compare(a: Any, b: Any) -> bool:
        try:
            return math.isclose(float(clean(a)), float(clean(b)), rel_tol=rel_tol, abs_tol=abs_tol)
        except (TypeError, ValueError):
            return value_equal(a, b)
    return compare


def lsb_tolerance(nominal: float, *, floor: float, multiplier: float = 3.0) -> float:
    """Conservative readback tolerance based on EA's 26214-step effective resolution."""
    return max(float(floor), abs(float(nominal)) / 26214.0 * multiplier)


def choose_float(original: float, low: float, high: float) -> float | None:
    """Choose a noticeably different value inside [low, high]."""
    low = float(low)
    high = float(high)
    original = float(original)
    if not (math.isfinite(low) and math.isfinite(high) and math.isfinite(original)):
        return None
    if high < low:
        return None
    span = high - low
    if span <= max(1e-9, abs(high) * 1e-12):
        return None

    # Favor modest values rather than rail-to-rail transitions.
    candidates = [
        low + 0.25 * span,
        low + 0.50 * span,
        low + 0.75 * span,
        low + 0.10 * span,
        low + 0.90 * span,
    ]
    min_change = max(span * 0.005, abs(original) * 1e-5, 1e-6)
    for candidate in candidates:
        if abs(candidate - original) >= min_change:
            return candidate
    return None


def choose_int(original: int, low: int, high: int) -> int | None:
    for candidate in (low, high, (low + high) // 2, original + 1, original - 1):
        if low <= candidate <= high and candidate != original:
            return int(candidate)
    return None


def choose_token(original: Any, options: Iterable[Any]) -> Any | None:
    original_text = str(clean(original)).upper()
    for candidate in options:
        if str(clean(candidate)).upper() != original_text:
            return candidate
    return None


class CommandVerifier:
    def __init__(self, psb: PSB10000, args: argparse.Namespace, transport_kind: str) -> None:
        self.psb = psb
        self.args = args
        self.transport_kind = transport_kind
        self.results: list[Result] = []
        self._index = 0
        self._remote_was = ""
        self._acquired_remote = False
        self._output_was_on = False
        r = self.psb.ratings
        self.voltage_compare = numeric_compare(lsb_tolerance(r.voltage, floor=0.01))
        self.current_compare = numeric_compare(lsb_tolerance(r.current, floor=0.01))
        # The real PSB observed during checkout returns integer-watt readbacks
        # for several power commands, so 1 W is the minimum useful tolerance.
        self.power_compare = numeric_compare(lsb_tolerance(r.power, floor=1.0))
        rspan = (r.resistance_max or 0.0) - (r.resistance_min or 0.0)
        self.resistance_compare = numeric_compare(lsb_tolerance(rspan or 1.0, floor=0.01))

    # ------------------------------ reporting ------------------------------
    def _add(
        self,
        group: str,
        name: str,
        command: str,
        outcome: str,
        *,
        original: Any = "",
        requested: Any = "",
        readback: Any = "",
        restored: Any = "",
        status_before: dict[str, Any] | None = None,
        status_after: dict[str, Any] | None = None,
        detail: str = "",
        elapsed_ms: float = 0.0,
    ) -> None:
        self._index += 1
        delta = self.status_delta(status_before, status_after)
        result = Result(
            index=self._index,
            group=group,
            name=name,
            command=command,
            result=outcome,
            original=text(original) if original != "" else "",
            requested=text(requested) if requested != "" else "",
            readback=text(readback) if readback != "" else "",
            restored=text(restored) if restored != "" else "",
            status_changed=bool(delta),
            status_delta=text(delta) if delta else "",
            detail=detail,
            elapsed_ms=round(elapsed_ms, 3),
        )
        self.results.append(result)
        marker = {PASS: "+", FAIL: "!", ERROR: "X", SKIP: "-", INFO: "i"}.get(outcome, "?")
        line = f"[{marker}] {outcome:5} {group:15} {name}"
        if requested != "":
            line += f" | set={text(requested)} read={text(readback)}"
        if delta:
            line += f" | status changed: {', '.join(delta.keys())}"
        if detail and self.args.verbose:
            line += f" | {detail}"
        print(line)

    @staticmethod
    def status_delta(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
        if before is None or after is None:
            return {}
        delta: dict[str, Any] = {}
        for key in sorted(set(before) | set(after)):
            if before.get(key) != after.get(key):
                delta[key] = {"before": before.get(key), "after": after.get(key)}
        return delta

    def capture_status(self) -> dict[str, Any]:
        """Capture raw status registers plus explicit output/owner state."""
        data: dict[str, Any] = {}
        queries: list[tuple[str, Callable[[], Any]]] = [
            ("stb", self.psb.status.status_byte),
            ("questionable", self.psb.status.questionable),
            ("secondary_questionable", self.psb.status.secondary_questionable),
            ("operation", self.psb.status.operation),
            ("output", lambda: self.psb.output.enabled),
            ("owner", self.psb.remote_owner_raw),
        ]
        for key, getter in queries:
            try:
                data[key] = clean(getter())
            except Exception as exc:  # status collection must never abort a test
                data[key] = f"<{type(exc).__name__}: {exc}>"
        return data

    def _drain_errors(self) -> tuple[list[Any], str]:
        """Drain SCPI errors while preserving a useful failure string.

        The verifier disables the driver's automatic post-write error check and
        drains explicitly around each test. This prevents an error from a timed
        out/unsupported command being incorrectly blamed on the next valid
        command.
        """
        try:
            return self.psb.errors.drain(max_errors=16), ""
        except Exception as exc:
            return [], f"error-queue read failed: {type(exc).__name__}: {exc}"

    @staticmethod
    def _error_text(errors: list[Any]) -> str:
        return "; ".join(f"{getattr(e, 'code', '?')}: {getattr(e, 'message', e)}" for e in errors)

    def _discard_stale_errors(self) -> str:
        errors, problem = self._drain_errors()
        parts: list[str] = []
        if errors:
            parts.append(f"discarded stale queue before test: {self._error_text(errors)}")
        if problem:
            parts.append(problem)
        return "; ".join(parts)

    # ------------------------------ test helpers ------------------------------
    def query_test(
        self,
        group: str,
        name: str,
        command: str,
        getter: Callable[[], Any],
        *,
        check_error_queue: bool = True,
        unsupported_is_skip: bool = False,
    ) -> Any | None:
        start = time.perf_counter()
        stale = self._discard_stale_errors() if check_error_queue else ""
        before = self.capture_status()
        try:
            value = getter()
            after = self.capture_status()
            errors: list[Any] = []
            queue_problem = ""
            if check_error_queue:
                errors, queue_problem = self._drain_errors()
            detail = "; ".join(part for part in (stale, queue_problem) if part)
            if errors:
                detail = "; ".join(part for part in (detail, f"SCPI queue: {self._error_text(errors)}") if part)
                outcome = FAIL
            else:
                outcome = PASS
            self._add(
                group, name, command, outcome, readback=value,
                status_before=before, status_after=after, detail=detail,
                elapsed_ms=(time.perf_counter() - start) * 1000,
            )
            return value if outcome == PASS else None
        except PSBUnsupportedFeatureError as exc:
            outcome = SKIP
            self._add(group, name, command, outcome, detail=str(exc), elapsed_ms=(time.perf_counter() - start) * 1000)
        except Exception as exc:
            after = self.capture_status()
            errors: list[Any] = []
            queue_problem = ""
            if check_error_queue:
                errors, queue_problem = self._drain_errors()
            extra = f"; SCPI queue: {self._error_text(errors)}" if errors else ""
            if queue_problem:
                extra += f"; {queue_problem}"
            outcome = SKIP if unsupported_is_skip else FAIL
            self._add(
                group, name, command, outcome, status_before=before, status_after=after,
                detail=f"{type(exc).__name__}: {exc}{extra}",
                elapsed_ms=(time.perf_counter() - start) * 1000,
            )
        return None

    def skip(self, group: str, name: str, command: str, why: str) -> None:
        self._add(group, name, command, SKIP, detail=why)

    def rw_test(
        self,
        group: str,
        name: str,
        command: str,
        getter: Callable[[], Any],
        setter: Callable[[Any], None],
        requested: Any,
        *,
        compare: Callable[[Any, Any], bool] = value_equal,
        restore: bool = True,
        settle_s: float = 0.03,
    ) -> bool:
        """Isolated write -> readback -> error/status -> restore verification."""
        start = time.perf_counter()
        original: Any = ""
        readback: Any = ""
        restored: Any = ""
        before: dict[str, Any] | None = None
        after: dict[str, Any] | None = None
        changed_ok = False
        restore_ok = not restore
        detail_parts: list[str] = []

        stale = self._discard_stale_errors()
        if stale:
            detail_parts.append(stale)
        try:
            original = getter()
            if compare(original, requested):
                self.skip(group, name, command, "No alternate value available; requested value equals original")
                return False
            before = self.capture_status()
            setter(requested)
            if settle_s:
                time.sleep(settle_s)
            readback = getter()
            after = self.capture_status()
            errors, queue_problem = self._drain_errors()
            if queue_problem:
                detail_parts.append(queue_problem)
            if errors:
                detail_parts.append(f"SCPI queue after write/readback: {self._error_text(errors)}")
            changed_ok = compare(readback, requested) and not compare(readback, original) and not errors
            if not compare(readback, requested):
                detail_parts.append("write/readback verification failed")
            elif compare(readback, original):
                detail_parts.append("readback did not move away from original")
        except PSBUnsupportedFeatureError as exc:
            errors, queue_problem = self._drain_errors()
            details = [str(exc)]
            if errors:
                details.append(f"SCPI queue: {self._error_text(errors)}")
            if queue_problem:
                details.append(queue_problem)
            self._add(
                group, name, command, SKIP, original=original, requested=requested,
                readback=readback, status_before=before, status_after=after,
                detail="; ".join(details), elapsed_ms=(time.perf_counter() - start) * 1000,
            )
            return False
        except Exception as exc:
            errors, queue_problem = self._drain_errors()
            detail_parts.append(f"write/read exception: {type(exc).__name__}: {exc}")
            if errors:
                detail_parts.append(f"SCPI queue after failure: {self._error_text(errors)}")
            if queue_problem:
                detail_parts.append(queue_problem)
        finally:
            if restore and original != "":
                # The error queue above has already been drained, so restoration
                # is evaluated independently instead of inheriting the prior error.
                try:
                    setter(original)
                    if settle_s:
                        time.sleep(settle_s)
                    restored = getter()
                    restore_errors, restore_problem = self._drain_errors()
                    restore_ok = compare(restored, original) and not restore_errors
                    if not compare(restored, original):
                        detail_parts.append("restore verification failed")
                    if restore_errors:
                        detail_parts.append(f"SCPI queue during restore: {self._error_text(restore_errors)}")
                    if restore_problem:
                        detail_parts.append(restore_problem)
                except Exception as exc:
                    restore_ok = False
                    restore_errors, restore_problem = self._drain_errors()
                    detail_parts.append(f"restore exception: {type(exc).__name__}: {exc}")
                    if restore_errors:
                        detail_parts.append(f"SCPI queue during restore failure: {self._error_text(restore_errors)}")
                    if restore_problem:
                        detail_parts.append(restore_problem)

        outcome = PASS if changed_ok and restore_ok else FAIL
        self._add(
            group, name, command, outcome, original=original, requested=requested,
            readback=readback, restored=restored, status_before=before, status_after=after,
            detail="; ".join(dict.fromkeys(part for part in detail_parts if part)),
            elapsed_ms=(time.perf_counter() - start) * 1000,
        )
        return outcome == PASS

    def raw_rw_test(
        self,
        group: str,
        name: str,
        set_command: str,
        query_command: str,
        requested: str,
        *,
        allowed_original: set[str] | None = None,
    ) -> bool:
        """Use raw SCPI for settings lacking a typed getter."""
        try:
            original = self.psb.query_scpi(query_command).strip().strip('"').upper()
        except Exception as exc:
            self.skip(group, name, set_command, f"Cannot safely test because {query_command} is unavailable: {exc}")
            return False
        if allowed_original and original not in allowed_original:
            self.skip(group, name, set_command, f"Unexpected original readback {original!r}; refusing to overwrite it")
            return False
        target = requested.upper()
        if original == target and allowed_original:
            target = next((v for v in sorted(allowed_original) if v != original), target)
        return self.rw_test(
            group,
            name,
            set_command,
            lambda: self.psb.query_scpi(query_command).strip().strip('"').upper(),
            lambda v: self.psb.write_scpi(f"{set_command} {v}"),
            target,
        )

    # ------------------------------ lifecycle ------------------------------
    def prepare(self) -> None:
        print(f"Instrument: {self.psb.info.raw_idn}")
        print(f"Ratings: U={self.psb.ratings.voltage:g} V, I={self.psb.ratings.current:g} A, P={self.psb.ratings.power:g} W")
        self._remote_was = self.psb.remote_owner_raw()
        try:
            self._output_was_on = bool(self.psb.output.enabled)
        except Exception:
            self._output_was_on = False

        if self._remote_was != "REMOTE":
            self._discard_stale_errors()
            before = self.capture_status()
            start = time.perf_counter()
            self.psb.acquire_remote()
            owner = self.psb.remote_owner_raw()
            after = self.capture_status()
            self._acquired_remote = owner == "REMOTE"
            self._add(
                "remote", "Acquire remote", "SYST:LOCK ON", PASS if owner == "REMOTE" else FAIL,
                original=self._remote_was, requested="REMOTE", readback=owner,
                status_before=before, status_after=after,
                elapsed_ms=(time.perf_counter() - start) * 1000,
            )
        else:
            self._add("remote", "Remote already owned", "SYST:LOCK:OWNER?", INFO, readback="REMOTE")

        # All normal command mutation occurs with DC terminal off.
        self._discard_stale_errors()
        before = self.capture_status()
        start = time.perf_counter()
        self.psb.output.off()
        off_state = self.psb.output.enabled
        off = not off_state
        after = self.capture_status()
        errors, queue_problem = self._drain_errors()
        detail = ""
        if errors:
            detail = f"SCPI queue: {self._error_text(errors)}"
        if queue_problem:
            detail = "; ".join(part for part in (detail, queue_problem) if part)
        self._add(
            "output", "Force DC terminal OFF", "OUTPut OFF", PASS if off and not errors and not queue_problem else FAIL,
            requested=False, readback=off_state,
            status_before=before, status_after=after, detail=detail,
            elapsed_ms=(time.perf_counter() - start) * 1000,
        )
        if not off:
            raise RuntimeError("DC terminal did not switch off; refusing to continue with command mutation")

    def cleanup(self) -> None:
        # Never restore an originally-on output automatically: the verifier may
        # have changed setpoints during the run. Leaving it OFF is safer.
        try:
            if self.psb.connected and self.psb.remote_owner_raw() == "REMOTE":
                self._discard_stale_errors()
                self.psb.output.off()
                self._drain_errors()
        except Exception as exc:
            print(f"WARNING: cleanup could not force output OFF: {exc}", file=sys.stderr)
        if self._acquired_remote and self.args.release_remote:
            try:
                self.psb.release_remote()
                self._add("remote", "Release remote", "SYST:LOCK OFF", PASS, readback=self.psb.remote_owner_raw())
            except Exception as exc:
                self._add("remote", "Release remote", "SYST:LOCK OFF", FAIL, detail=f"{type(exc).__name__}: {exc}")

    # ------------------------------ command groups ------------------------------
    def test_identification_and_status(self) -> None:
        self.query_test("identity", "Identification", "*IDN?", lambda: self.psb.query_scpi("*IDN?"))
        self.query_test("identity", "Nominal voltage", "SYST:NOM:VOLT?", lambda: self.psb.query_scpi("SYST:NOM:VOLT?"))
        self.query_test("identity", "Nominal current", "SYST:NOM:CURR?", lambda: self.psb.query_scpi("SYST:NOM:CURR?"))
        self.query_test("identity", "Nominal power", "SYST:NOM:POW?", lambda: self.psb.query_scpi("SYST:NOM:POW?"))
        self.query_test("identity", "Nominal R min", "SYST:NOM:RES:MIN?", lambda: self.psb.query_scpi("SYST:NOM:RES:MIN?"))
        self.query_test("identity", "Nominal R max", "SYST:NOM:RES:MAX?", lambda: self.psb.query_scpi("SYST:NOM:RES:MAX?"))

        self.query_test("measurement", "Measurement array", "MEAS:ARR?", self.psb.measure)
        self.query_test("measurement", "Voltage", "MEAS:VOLT?", lambda: self.psb.query_scpi("MEAS:VOLT?"))
        self.query_test("measurement", "Current", "MEAS:CURR?", lambda: self.psb.query_scpi("MEAS:CURR?"))
        self.query_test("measurement", "Power", "MEAS:POW?", lambda: self.psb.query_scpi("MEAS:POW?"))

        self.query_test("status", "Status byte", "*STB?", self.psb.status.status_byte)
        self.query_test("status", "Questionable condition", "STATus:QUEStionable:CONDition?", self.psb.status.questionable)
        self.query_test("status", "Secondary questionable", "STATus:SECond:QUEStionable:CONDition?", self.psb.status.secondary_questionable)
        self.query_test("status", "Operation condition", "STATus:OPERation:CONDition?", self.psb.status.operation)
        self.query_test("status", "Questionable event", "STATus:QUEStionable:EVENt?", self.psb.status.questionable_event)
        self.query_test("status", "Secondary questionable event", "STATus:SECond:QUEStionable:EVENt?", self.psb.status.secondary_questionable_event, unsupported_is_skip=True)
        self.query_test("status", "Operation event", "STATus:OPERation:EVENt?", self.psb.status.operation_event)
        self.query_test("status", "Event status register", "*ESR?", self.psb.status.event_status)
        self.query_test("status", "Full status snapshot", "status.snapshot()", self.psb.status.snapshot)

        # Enable/status masks are ordinary settings. Change one bit and restore so
        # command/readback is tested without leaving service-request behavior altered.
        mask_specs = [
            ("Questionable enable", "STATus:QUEStionable:ENABle", lambda: self.psb.status.questionable_enable, lambda v: setattr(self.psb.status, "questionable_enable", v)),
            ("Operation enable", "STATus:OPERation:ENABle", lambda: self.psb.status.operation_enable, lambda v: setattr(self.psb.status, "operation_enable", v)),
            ("Secondary questionable enable", "STATus:SECond:QUEStionable:ENABle", lambda: self.psb.status.secondary_questionable_enable, lambda v: setattr(self.psb.status, "secondary_questionable_enable", v)),
            ("Event status enable", "*ESE", lambda: self.psb.status.event_status_enable, lambda v: setattr(self.psb.status, "event_status_enable", v)),
            ("Service request enable", "*SRE", lambda: self.psb.status.service_request_enable, lambda v: setattr(self.psb.status, "service_request_enable", v)),
        ]
        for name, command, getter, setter in mask_specs:
            try:
                original = int(getter())
                maximum = 255 if command in {"*ESE", "*SRE"} else 65535
                target = original ^ 1
                if target > maximum:
                    target = 0
                self.rw_test("status", name, command, getter, setter, target)
            except Exception as exc:
                errors, _ = self._drain_errors()
                detail = f"{type(exc).__name__}: {exc}"
                if errors:
                    detail += f"; SCPI queue: {self._error_text(errors)}"
                # Secondary register availability can vary by family/firmware.
                outcome = SKIP if "Secondary" in name else FAIL
                self._add("status", name, command, outcome, detail=detail)

        from ea_psb10000.subsystems.status import ALARM_COUNTER_COMMANDS
        for counter, command in ALARM_COUNTER_COMMANDS.items():
            self.query_test(
                "status", f"Alarm counter {counter}", command,
                lambda c=counter: self.psb.status.alarm_counter(c),
                unsupported_is_skip=True,
            )

        self.query_test("status", "Output state", "OUTPut?", lambda: self.psb.output.enabled)
        self.query_test("status", "Remote owner", "SYSTem:LOCK:OWNer?", self.psb.remote_owner_raw)

        # Error-queue commands are tested without the verifier recursively draining
        # the queue around them. The normal command isolation resumes afterward.
        pre_error = self.capture_status()
        self._add("error", "Status before error queries", "STATus:*", INFO, readback=pre_error)
        self.query_test("error", "Next SCPI error", "SYSTem:ERRor?", self.psb.errors.next, check_error_queue=False)
        self.query_test("error", "Explicit NEXT SCPI error", "SYSTem:ERRor:NEXT?", self.psb.errors.next_explicit, check_error_queue=False)
        self.query_test("error", "All SCPI errors", "SYSTem:ERRor:ALL?", self.psb.errors.all, check_error_queue=False)

    def test_setpoints(self) -> None:
        r = self.psb.ratings
        lim = self.psb.limits.snapshot(refresh=True)
        tests: list[tuple[str, str, Callable[[], Any], Callable[[Any], None], float, float]] = [
            ("Source voltage", "VOLT / VOLT?", lambda: self.psb.source.voltage, lambda v: setattr(self.psb.source, "voltage", v), lim.voltage_min, lim.voltage_max),
            ("Source current", "CURR / CURR?", lambda: self.psb.source.current, lambda v: setattr(self.psb.source, "current", v), lim.source_current_min, lim.source_current_max),
            ("Source power", "POW / POW?", lambda: self.psb.source.power, lambda v: setattr(self.psb.source, "power", v), 0.0, lim.source_power_max),
            ("Sink current", "SINK:CURR / ?", lambda: self.psb.sink.current, lambda v: setattr(self.psb.sink, "current", v), lim.sink_current_min, lim.sink_current_max),
            ("Sink power", "SINK:POW / ?", lambda: self.psb.sink.power, lambda v: setattr(self.psb.sink, "power", v), 0.0, lim.sink_power_max),
        ]
        if r.resistance_min is not None and (lim.source_resistance_max or r.resistance_max) is not None:
            tests.append(("Source resistance", "RES / RES?", lambda: self.psb.source.resistance, lambda v: setattr(self.psb.source, "resistance", v), r.resistance_min, float(lim.source_resistance_max or r.resistance_max)))
        if r.resistance_min is not None and (lim.sink_resistance_max or r.resistance_max) is not None:
            tests.append(("Sink resistance", "SINK:RES / ?", lambda: self.psb.sink.resistance, lambda v: setattr(self.psb.sink, "resistance", v), r.resistance_min, float(lim.sink_resistance_max or r.resistance_max)))

        for name, command, getter, setter, low, high in tests:
            try:
                original = float(getter())
                target = choose_float(original, low, high)
                if target is None:
                    self.skip("setpoint", name, command, f"No safe alternate in {low:g}..{high:g}")
                    continue
                if "power" in name.lower():
                    compare = self.power_compare
                elif "resistance" in name.lower():
                    compare = self.resistance_compare
                elif "voltage" in name.lower():
                    compare = self.voltage_compare
                else:
                    compare = self.current_compare
                self.rw_test("setpoint", name, command, getter, setter, target, compare=compare)
            except Exception as exc:
                self._add("setpoint", name, command, FAIL, detail=f"{type(exc).__name__}: {exc}")

    def test_protection(self) -> None:
        r = self.psb.ratings
        tests = [
            ("OVP", "VOLT:PROT / ?", lambda: self.psb.protection.ovp, lambda v: setattr(self.psb.protection, "ovp", v), self.psb.source.voltage, r.voltage * 1.10),
            ("Source OCP", "CURR:PROT / ?", lambda: self.psb.protection.source_ocp, lambda v: setattr(self.psb.protection, "source_ocp", v), self.psb.source.current, r.current * 1.10),
            ("Source OPP", "POW:PROT / ?", lambda: self.psb.protection.source_opp, lambda v: setattr(self.psb.protection, "source_opp", v), self.psb.source.power, r.power * 1.10),
            ("Sink OCP", "SINK:CURR:PROT / ?", lambda: self.psb.protection.sink_ocp, lambda v: setattr(self.psb.protection, "sink_ocp", v), self.psb.sink.current, r.current * 1.10),
            ("Sink OPP", "SINK:POW:PROT / ?", lambda: self.psb.protection.sink_opp, lambda v: setattr(self.psb.protection, "sink_opp", v), self.psb.sink.power, r.power * 1.10),
        ]
        for name, command, getter, setter, active_setpoint, high in tests:
            try:
                original = float(getter())
                # Keep the temporary protection level above the active setpoint
                # where possible so the instrument does not reject a valid
                # protection command merely because it conflicts with U/I/P.
                low = min(high, max(float(active_setpoint), high * 0.60))
                target = choose_float(original, low, high)
                if target is None:
                    target = choose_float(original, 0.0, high)
                if target is None:
                    self.skip("protection", name, command, "No alternate value")
                    continue
                compare = self.power_compare if "OPP" in name else (self.voltage_compare if name == "OVP" else self.current_compare)
                self.rw_test("protection", name, command, getter, setter, target, compare=compare)
            except Exception as exc:
                self._add("protection", name, command, FAIL, detail=f"{type(exc).__name__}: {exc}")

    def test_limits(self) -> None:
        r = self.psb.ratings
        snap = self.psb.limits.snapshot(refresh=True)
        source_v = self.psb.source.voltage
        source_i = self.psb.source.current
        source_p = self.psb.source.power
        sink_i = self.psb.sink.current
        sink_p = self.psb.sink.power

        # Each candidate is constrained so it cannot exclude the current setpoint.
        specs: list[tuple[str, str, Callable[[], Any], Callable[[Any], None], float, float]] = [
            ("Voltage minimum", "VOLT:LIM:LOW", lambda: self.psb.limits.snapshot(refresh=True).voltage_min, lambda v: self.psb.limits.set_voltage(minimum=v), 0.0, max(0.0, source_v)),
            ("Voltage maximum", "VOLT:LIM:HIGH", lambda: self.psb.limits.snapshot(refresh=True).voltage_max, lambda v: self.psb.limits.set_voltage(maximum=v), min(source_v, r.voltage * 1.02), r.voltage * 1.02),
            ("Source current minimum", "CURR:LIM:LOW", lambda: self.psb.limits.snapshot(refresh=True).source_current_min, lambda v: self.psb.limits.set_source_current(minimum=v), 0.0, max(0.0, source_i)),
            ("Source current maximum", "CURR:LIM:HIGH", lambda: self.psb.limits.snapshot(refresh=True).source_current_max, lambda v: self.psb.limits.set_source_current(maximum=v), min(source_i, r.current * 1.02), r.current * 1.02),
            ("Source power maximum", "POW:LIM:HIGH", lambda: self.psb.limits.snapshot(refresh=True).source_power_max, self.psb.limits.set_source_power, min(source_p, r.power * 1.02), r.power * 1.02),
            ("Sink current minimum", "SINK:CURR:LIM:LOW", lambda: self.psb.limits.snapshot(refresh=True).sink_current_min, lambda v: self.psb.limits.set_sink_current(minimum=v), 0.0, max(0.0, sink_i)),
            ("Sink current maximum", "SINK:CURR:LIM:HIGH", lambda: self.psb.limits.snapshot(refresh=True).sink_current_max, lambda v: self.psb.limits.set_sink_current(maximum=v), min(sink_i, r.current * 1.02), r.current * 1.02),
            ("Sink power maximum", "SINK:POW:LIM:HIGH", lambda: self.psb.limits.snapshot(refresh=True).sink_power_max, self.psb.limits.set_sink_power, min(sink_p, r.power * 1.02), r.power * 1.02),
        ]
        if snap.source_resistance_max is not None and r.resistance_max is not None:
            src_r = self.psb.source.resistance
            specs.append(("Source resistance maximum", "RES:LIM:HIGH", lambda: self.psb.limits.snapshot(refresh=True).source_resistance_max, self.psb.limits.set_source_resistance_max, min(src_r, r.resistance_max), r.resistance_max))
        if snap.sink_resistance_max is not None and r.resistance_max is not None:
            snk_r = self.psb.sink.resistance
            specs.append(("Sink resistance maximum", "SINK:RES:LIM:HIGH", lambda: self.psb.limits.snapshot(refresh=True).sink_resistance_max, self.psb.limits.set_sink_resistance_max, min(snk_r, r.resistance_max), r.resistance_max))

        for name, command, getter, setter, low, high in specs:
            try:
                original = float(getter())
                target = choose_float(original, low, high)
                if target is None:
                    self.skip("limits", name, command, f"No safe alternate without moving the active setpoint ({low:g}..{high:g})")
                    continue
                if "power" in name.lower():
                    compare = self.power_compare
                elif "resistance" in name.lower():
                    compare = self.resistance_compare
                elif "voltage" in name.lower():
                    compare = self.voltage_compare
                else:
                    compare = self.current_compare
                self.rw_test("limits", name, command, getter, setter, target, compare=compare)
            except Exception as exc:
                self._add("limits", name, command, FAIL, detail=f"{type(exc).__name__}: {exc}")

        self.psb.limits.invalidate()

    def test_events(self) -> None:
        r = self.psb.ratings
        event_specs = [
            (False, "UVD", r.voltage),
            (False, "OVD", r.voltage),
            (False, "UCD", r.current),
            (False, "OCD", r.current),
            (False, "OPD", r.power),
            (True, "UCD", r.current),
            (True, "OCD", r.current),
            (True, "OPD", r.power),
        ]
        for sink, event, nominal in event_specs:
            side = "Sink" if sink else "Source"
            label = f"{side} {event}"
            original_action: str | None = None
            try:
                original_action = self.psb.events.get_action(event, sink=sink)
                # Temporarily disable the action while moving the threshold. This
                # prevents an event threshold test from turning into an alarm test.
                if original_action not in {"NONE", "OFF", "0"}:
                    self.psb.events.set_action(event, "NONE", sink=sink)
                original = self.psb.events.get_threshold(event, sink=sink)
                target = choose_float(original, 0.0, nominal * 1.02)
                if target is not None:
                    self.rw_test(
                        "events", f"{label} threshold", f"{event} threshold",
                        lambda e=event, s=sink: self.psb.events.get_threshold(e, sink=s),
                        lambda v, e=event, s=sink: self.psb.events.set_threshold(e, v, sink=s),
                        target,
                        compare=(self.power_compare if event == "OPD" else (self.voltage_compare if event in {"UVD", "OVD"} else self.current_compare)),
                    )
                else:
                    self.skip("events", f"{label} threshold", event, "No alternate threshold")

                # Test action using a non-shutdown alternative, then restore.
                action_target = choose_token(original_action, ["NONE", "SIGNAL", "WARNING"])
                if action_target is None:
                    self.skip("events", f"{label} action", f"{event}:ACT", "No alternate action")
                else:
                    self.rw_test(
                        "events", f"{label} action", f"{event}:ACT",
                        lambda e=event, s=sink: self.psb.events.get_action(e, sink=s),
                        lambda v, e=event, s=sink: self.psb.events.set_action(e, v, sink=s),
                        action_target,
                    )
            except Exception as exc:
                self._add("events", label, event, FAIL, detail=f"{type(exc).__name__}: {exc}")
            finally:
                try:
                    if original_action is not None:
                        self.psb.events.set_action(event, original_action, sink=sink)
                except Exception:
                    pass

    def test_system(self) -> None:
        # User text
        try:
            original = self.psb.system.user_text
            tag = "PSB-CMD-CHECK"
            target = tag if original != tag else "PSB-CMD-CHECK-2"
            self.rw_test("system", "User text", "SYSTem:CONFig:USER:TEXT", lambda: self.psb.system.user_text, lambda v: setattr(self.psb.system, "user_text", v), target)
        except Exception as exc:
            self._add("system", "User text", "SYSTem:CONFig:USER:TEXT", FAIL, detail=f"{type(exc).__name__}: {exc}")

        enum_tests = [
            ("Resistance mode", "SYSTem:CONFig:MODe", lambda: self.psb.system.resistance_mode, lambda v: setattr(self.psb.system, "resistance_mode", v), ["UIP", "UIR"]),
            ("State after remote", "POWer:STAGe:AFTer:REMote", lambda: self.psb.system.state_after_remote, lambda v: setattr(self.psb.system, "state_after_remote", v), ["OFF", "AUTO"]),
            ("State after power-on", "SYSTem:CONFig:OUTPut:RESTore", lambda: self.psb.system.state_after_power_on, lambda v: setattr(self.psb.system, "state_after_power_on", v), ["OFF", "AUTO"]),
            ("State after PF", "SYSTem:ALARm:ACTion:PFAil", lambda: self.psb.system.state_after_pf, lambda v: setattr(self.psb.system, "state_after_pf", v), ["OFF", "AUTO"]),
            ("State after OT", "SYSTem:ALARm:ACTion:OTEMperature", lambda: self.psb.system.state_after_ot, lambda v: setattr(self.psb.system, "state_after_ot", v), ["OFF", "AUTO"]),
            ("Voltage controller speed", "SYSTem:CONFig:CONTroller:SPEed", lambda: self.psb.system.voltage_controller_speed, lambda v: setattr(self.psb.system, "voltage_controller_speed", v), ["SLOW", "NORM", "FAST"]),
        ]
        for name, command, getter, setter, options in enum_tests:
            try:
                original = getter()
                target = choose_token(original, options)
                if target is None:
                    self.skip("system", name, command, "No alternate value")
                else:
                    self.rw_test("system", name, command, getter, setter, target)
            except Exception as exc:
                self._add("system", name, command, FAIL, detail=f"{type(exc).__name__}: {exc}")

        try:
            original = self.psb.system.semi_f47
            self.rw_test("system", "SEMI F47", "SYSTem:CONFig:SEMif47", lambda: self.psb.system.semi_f47, lambda v: setattr(self.psb.system, "semi_f47", v), not original)
        except Exception as exc:
            self._add("system", "SEMI F47", "SYSTem:CONFig:SEMif47", FAIL, detail=f"{type(exc).__name__}: {exc}")

        # *CLS is state clearing, not a setting with a readback. Capture before/after.
        if self.args.clear_status:
            start = time.perf_counter()
            before = self.capture_status()
            try:
                self.psb.system.clear_status()
                after = self.capture_status()
                self._add("system", "Clear status", "*CLS", PASS, status_before=before, status_after=after, detail="Command accepted; a status change is not required when no latched status exists", elapsed_ms=(time.perf_counter() - start) * 1000)
            except Exception as exc:
                self._add("system", "Clear status", "*CLS", FAIL, detail=f"{type(exc).__name__}: {exc}")
        else:
            self.skip("system", "Clear status", "*CLS", "Use --clear-status to allow clearing latched status")

    def test_analog(self) -> None:
        tests = [
            ("Analog range", "SYSTem:CONFig:ANALog:REFerence", lambda: self.psb.analog.range_volts, lambda v: setattr(self.psb.analog, "range_volts", v), [5, 10]),
            ("Analog monitor", "SYSTem:CONFig:ANALog:MONitor", lambda: self.psb.analog.monitor_mode, lambda v: setattr(self.psb.analog, "monitor_mode", v), ["DEFAULT", "EL", "PS", "ELPS", "PSEL", "COMBINATION"]),
            ("REM-SB level", "SYSTem:CONFig:ANALog:REMSb:LEVel", lambda: self.psb.analog.rem_sb_level, lambda v: setattr(self.psb.analog, "rem_sb_level", v), ["NORMAL", "INVERTED"]),
            ("REM-SB action", "SYSTem:CONFig:ANALog:REMSb:ACTion", lambda: self.psb.analog.rem_sb_action, lambda v: setattr(self.psb.analog, "rem_sb_action", v), ["OFF", "AUTO"]),
        ]
        for name, command, getter, setter, options in tests:
            try:
                original = getter()
                target = choose_token(original, options)
                if target is None:
                    self.skip("analog", name, command, "No alternate value")
                else:
                    self.rw_test("analog", name, command, getter, setter, target)
            except Exception as exc:
                self._add("analog", name, command, FAIL, detail=f"{type(exc).__name__}: {exc}")

        # Driver intentionally exposes setters for these pins but no typed getter.
        self.raw_rw_test("analog", "Pin 6 routing", "SYSTem:CONFig:ANALog:PIN6", "SYSTem:CONFig:ANALog:PIN6?", "ALL", allowed_original={"OT", "PF", "ALL"})
        self.raw_rw_test("analog", "Pin 14 routing", "SYSTem:CONFig:ANALog:PIN14", "SYSTem:CONFig:ANALog:PIN14?", "ALL", allowed_original={"OVP", "OCP", "OPP", "OVP/OCP", "OVP/OPP", "OCP/OPP", "ALL"})
        self.raw_rw_test("analog", "Pin 15 routing", "SYSTem:CONFig:ANALog:PIN15", "SYSTem:CONFig:ANALog:PIN15?", "POW", allowed_original={"CONT", "POW"})

    def test_communications(self) -> None:
        # SYSTem:COMMunicate:TIMeout is specifically the inter-byte timeout for
        # serial transfers (USB/RS232). Do not treat it as an Ethernet setting.
        if self.transport_kind == "serial":
            try:
                orig = self.psb.communications.serial_message_timeout_ms
                target = choose_int(orig, 5, 65535)
                if target is not None:
                    self.rw_test(
                        "communication", "Serial/USB message timeout",
                        "SYSTem:COMMunicate:TIMeout",
                        lambda: self.psb.communications.serial_message_timeout_ms,
                        lambda v: setattr(self.psb.communications, "serial_message_timeout_ms", v),
                        target,
                    )
            except Exception as exc:
                errors, _ = self._drain_errors()
                detail = f"{type(exc).__name__}: {exc}"
                if errors:
                    detail += f"; SCPI queue: {self._error_text(errors)}"
                self._add("communication", "Serial/USB message timeout", "SYSTem:COMMunicate:TIMeout", FAIL, detail=detail)
        else:
            self.skip(
                "communication", "Serial/USB message timeout", "SYSTem:COMMunicate:TIMeout",
                "This setting applies to USB/RS232 inter-byte timing; Ethernet uses LAN:TIMeout",
            )

        try:
            orig = self.psb.communications.modbus_enabled
            self.rw_test(
                "communication", "ModBus protocol enable", "SYSTem:COMMunicate:PROTocol:MODBus",
                lambda: self.psb.communications.modbus_enabled,
                lambda v: setattr(self.psb.communications, "modbus_enabled", v),
                not orig,
            )
        except Exception as exc:
            errors, _ = self._drain_errors()
            detail = f"{type(exc).__name__}: {exc}"
            if errors:
                detail += f"; SCPI queue: {self._error_text(errors)}"
            self._add("communication", "ModBus protocol enable", "SYSTem:COMMunicate:PROTocol:MODBus", FAIL, detail=detail)

        interface_code = self.query_test(
            "communication", "Optional interface code", "SYSTem:COMMunicate:INTerface:CODe?",
            lambda: self.psb.communications.interface_code,
        )
        int_type: Any = None
        if interface_code is None:
            self.skip("communication", "Optional interface type", "SYSTem:COMMunicate:INTerface:TYPe?", "Interface code query failed; avoiding dependent queries")
            self.skip("communication", "Optional interface serial", "SYSTem:COMMunicate:INTerface:SERial?", "Interface code query failed; avoiding dependent queries")
        elif interface_code == 255:
            self.skip("communication", "Optional interface type", "SYSTem:COMMunicate:INTerface:TYPe?", "Interface code 255 means no optional Anybus module is installed")
            self.skip("communication", "Optional interface serial", "SYSTem:COMMunicate:INTerface:SERial?", "No optional Anybus module is installed")
        else:
            int_type = self.query_test(
                "communication", "Optional interface type", "SYSTem:COMMunicate:INTerface:TYPe?",
                lambda: self.psb.communications.interface_type, unsupported_is_skip=True,
            )
            self.query_test(
                "communication", "Optional interface serial", "SYSTem:COMMunicate:INTerface:SERial?",
                lambda: self.psb.communications.interface_serial, unsupported_is_skip=True,
            )

        if interface_code is None or interface_code == 255:
            reason = "Interface code query failed" if interface_code is None else "No optional interface module installed (CODE=255)"
            for name, cmd in [
                ("Optional interface baud", "SYSTem:COMMunicate:INTerface:BAUD"),
                ("Optional interface address", "SYSTem:COMMunicate:INTerface:ADDRess"),
                ("Profibus function tag", "SYSTem:COMMunicate:PROFibus:FTAG"),
                ("Profibus location tag", "SYSTem:COMMunicate:PROFibus:LTAG"),
                ("Profibus installation date", "SYSTem:COMMunicate:PROFibus:DATe"),
                ("Interface description", "SYSTem:COMMunicate:PROFibus:DESCription"),
                ("Station name", "SYSTem:COMMunicate:PROFibus:NAMe"),
                ("CAN configuration", "SYSTem:COMMunicate:CAN:*"),
                ("CAN cyclic reads", "SYSTem:COMMunicate:CAN:READ:*"),
            ]:
                self.skip("optional-if", name, cmd, reason)
        elif self.args.optional_interface:
            self._test_optional_interface(int_type)
        else:
            for name, cmd in [
                ("Optional interface baud", "SYSTem:COMMunicate:INTerface:BAUD"),
                ("Optional interface address", "SYSTem:COMMunicate:INTerface:ADDRess"),
                ("Profibus function tag", "SYSTem:COMMunicate:PROFibus:FTAG"),
                ("Profibus location tag", "SYSTem:COMMunicate:PROFibus:LTAG"),
                ("Profibus installation date", "SYSTem:COMMunicate:PROFibus:DATe"),
                ("Interface description", "SYSTem:COMMunicate:PROFibus:DESCription"),
                ("Station name", "SYSTem:COMMunicate:PROFibus:NAMe"),
                ("CAN configuration", "SYSTem:COMMunicate:CAN:*"),
                ("CAN cyclic reads", "SYSTem:COMMunicate:CAN:READ:*"),
            ]:
                self.skip("optional-if", name, cmd, "Use --optional-interface to permit changes to the installed option module")

        # Query the built-in LAN (index 2 on 10000-series hardware), then restore
        # which LAN's settings were selected for subsequent SCPI configuration.
        lan_orig: int | None = None
        try:
            self._discard_stale_errors()
            lan_orig = self.psb.communications.lan_index
            if lan_orig != 2:
                self.psb.communications.select_lan(2)
                errors, problem = self._drain_errors()
                if errors or problem:
                    raise RuntimeError(f"select LAN 2 failed: {self._error_text(errors)} {problem}".strip())
            self.query_test("network", "Built-in LAN index", "SYSTem:COMMunicate:LAN:INDex?", lambda: self.psb.communications.lan_index)
            self.query_test("network", "IP address", "SYSTem:COMMunicate:LAN:ADDRess?", lambda: self.psb.communications.ip_address)
            self.query_test("network", "Subnet mask", "SYSTem:COMMunicate:LAN:SMASk?", lambda: self.psb.communications.subnet_mask)
            self.query_test("network", "Gateway", "SYSTem:COMMunicate:LAN:GATeway?", lambda: self.psb.communications.gateway)
            self.query_test("network", "TCP port", "SYSTem:COMMunicate:LAN:CONTrol?", lambda: self.psb.communications.tcp_port)
            self.query_test("network", "DHCP", "SYSTem:COMMunicate:LAN:DHCP?", lambda: self.psb.communications.dhcp)
            self.query_test("network", "Keepalive", "SYSTem:COMMunicate:LAN:KEEPalive?", lambda: self.psb.communications.keepalive)
            self.query_test("network", "Ethernet socket timeout", "SYSTem:COMMunicate:LAN:TIMeout?", lambda: self.psb.communications.ethernet_timeout_s)
            self.query_test("network", "Hostname", "SYSTem:COMMunicate:LAN:HOSTname?", lambda: self.psb.communications.hostname)
            self.query_test("network", "Domain", "SYSTem:COMMunicate:LAN:DOMain?", lambda: self.psb.communications.domain)
            self.query_test("network", "MAC address", "SYSTem:COMMunicate:LAN:MAC?", lambda: self.psb.communications.mac_address)
        except Exception as exc:
            errors, _ = self._drain_errors()
            detail = f"{type(exc).__name__}: {exc}"
            if errors:
                detail += f"; SCPI queue: {self._error_text(errors)}"
            self._add("network", "LAN query block", "SYSTem:COMMunicate:LAN:*?", FAIL, detail=detail)

        if self.args.network_settings:
            if self.transport_kind == "ethernet":
                self.skip("network", "Network-setting writes", "SYSTem:COMMunicate:LAN:*", "Connected over Ethernet; changing IP/DHCP/port can break the control socket. Run this group over serial/USB.")
            else:
                self._test_network_writes()
        else:
            self.skip("network", "Network-setting writes", "SYSTem:COMMunicate:LAN:*", "Use --network-settings over serial/USB to test mutable LAN settings")

        try:
            if lan_orig in {1, 2} and self.psb.communications.lan_index != lan_orig:
                self.psb.communications.select_lan(lan_orig)
                self._drain_errors()
        except Exception:
            pass

    def _test_network_writes(self) -> None:
        # Select built-in LAN on PSB 10000.
        try:
            self.psb.communications.select_lan(2)
        except Exception as exc:
            self._add("network", "Select built-in LAN", "SYST:COMM:LAN:IND 2", FAIL, detail=str(exc))
            return

        bool_specs = [
            ("DHCP", "SYST:COMM:LAN:DHCP", lambda: self.psb.communications.dhcp, lambda v: setattr(self.psb.communications, "dhcp", v)),
            ("Keepalive", "SYST:COMM:LAN:KEEP", lambda: self.psb.communications.keepalive, lambda v: setattr(self.psb.communications, "keepalive", v)),
        ]
        for name, command, getter, setter in bool_specs:
            try:
                orig = getter()
                self.rw_test("network", name, command, getter, setter, not orig)
            except Exception as exc:
                self._add("network", name, command, FAIL, detail=f"{type(exc).__name__}: {exc}")

        try:
            orig = self.psb.communications.ethernet_timeout_s
            choices = [0, 5, 10, 30]
            target = choose_token(orig, choices)
            if target is not None:
                self.rw_test("network", "Ethernet timeout", "SYST:COMM:LAN:TIME", lambda: self.psb.communications.ethernet_timeout_s, lambda v: setattr(self.psb.communications, "ethernet_timeout_s", v), target)
        except Exception as exc:
            self._add("network", "Ethernet timeout", "SYST:COMM:LAN:TIME", FAIL, detail=f"{type(exc).__name__}: {exc}")

        for name, command, getter, setter, target in [
            ("Hostname", "SYST:COMM:LAN:HOST", lambda: self.psb.communications.hostname, lambda v: setattr(self.psb.communications, "hostname", v), "PSB-CMD-CHECK"),
            ("Domain", "SYST:COMM:LAN:DOM", lambda: self.psb.communications.domain, lambda v: setattr(self.psb.communications, "domain", v), "cmd-check.local"),
        ]:
            try:
                if str(getter()).upper() == target.upper():
                    target += "2"
                self.rw_test("network", name, command, getter, setter, target)
            except Exception as exc:
                self._add("network", name, command, FAIL, detail=f"{type(exc).__name__}: {exc}")

        # IP/mask/gateway/TCP port/DNS writes are intentionally not changed to
        # arbitrary addresses. They require user-supplied alternate values so a
        # command test cannot accidentally create an invalid plant network setup.
        requested_map = [
            ("IP address", "SYST:COMM:LAN:ADDR", self.args.test_ip, lambda: self.psb.communications.ip_address, lambda v: setattr(self.psb.communications, "ip_address", v)),
            ("Subnet mask", "SYST:COMM:LAN:SMAS", self.args.test_mask, lambda: self.psb.communications.subnet_mask, lambda v: setattr(self.psb.communications, "subnet_mask", v)),
            ("Gateway", "SYST:COMM:LAN:GAT", self.args.test_gateway, lambda: self.psb.communications.gateway, lambda v: setattr(self.psb.communications, "gateway", v)),
            ("TCP port", "SYST:COMM:LAN:CONT", self.args.test_tcp_port, lambda: self.psb.communications.tcp_port, lambda v: setattr(self.psb.communications, "tcp_port", v)),
        ]
        for name, command, requested, getter, setter in requested_map:
            if requested is None:
                self.skip("network", name, command, f"No alternate supplied; provide the matching --test-* option")
            else:
                self.rw_test("network", name, command, getter, setter, requested)

        if self.args.test_dns:
            # Raw getter because the driver only exposes DNS setters.
            primary = self.args.test_dns[0]
            secondary = self.args.test_dns[1] if len(self.args.test_dns) > 1 else None
            try:
                old1 = self.psb.query_scpi("SYST:COMM:LAN:DNS1?").strip().strip('"')
                old2 = self.psb.query_scpi("SYST:COMM:LAN:DNS2?").strip().strip('"')
                before = self.capture_status()
                self.psb.communications.set_dns(primary, secondary)
                rb1 = self.psb.query_scpi("SYST:COMM:LAN:DNS1?").strip().strip('"')
                rb2 = self.psb.query_scpi("SYST:COMM:LAN:DNS2?").strip().strip('"')
                after = self.capture_status()
                ok = rb1 == primary and (secondary is None or rb2 == secondary)
                self.psb.communications.set_dns(old1, old2)
                self._add("network", "DNS", "SYST:COMM:LAN:DNS1/2", PASS if ok else FAIL, original=[old1, old2], requested=[primary, secondary], readback=[rb1, rb2], restored=[self.psb.query_scpi("SYST:COMM:LAN:DNS1?").strip().strip('"'), self.psb.query_scpi("SYST:COMM:LAN:DNS2?").strip().strip('"')], status_before=before, status_after=after)
            except Exception as exc:
                self._add("network", "DNS", "SYST:COMM:LAN:DNS1/2", FAIL, detail=f"{type(exc).__name__}: {exc}")
        else:
            self.skip("network", "DNS", "SYST:COMM:LAN:DNS1/2", "Provide --test-dns PRIMARY [SECONDARY]")

    def _test_optional_interface(self, interface_type: Any) -> None:
        # Only mutate fields that have a query/readback. Tag and CAN fields lack
        # typed getters; raw queries are attempted before any write.
        try:
            orig = self.psb.communications.interface_baud_index
            target = choose_int(orig, 0, 9)
            if target is not None:
                self.rw_test("optional-if", "Baud index", "SYST:COMM:INT:BAUD", lambda: self.psb.communications.interface_baud_index, lambda v: setattr(self.psb.communications, "interface_baud_index", v), target)
        except Exception as exc:
            self._add("optional-if", "Baud index", "SYST:COMM:INT:BAUD", FAIL, detail=f"{type(exc).__name__}: {exc}")
        try:
            orig = self.psb.communications.interface_address
            target = choose_int(orig, 1, 127)
            if target is not None:
                self.rw_test("optional-if", "Interface address", "SYST:COMM:INT:ADDR", lambda: self.psb.communications.interface_address, self.psb.communications.set_interface_address, target)
        except Exception as exc:
            self._add("optional-if", "Interface address", "SYST:COMM:INT:ADDR", FAIL, detail=f"{type(exc).__name__}: {exc}")

        raw_fields = [
            ("Function tag", "SYST:COMM:PROF:FTAG", "CMDCHK", self.psb.communications.set_function_tag),
            ("Location tag", "SYST:COMM:PROF:LTAG", "CMDCHK", self.psb.communications.set_location_tag),
            ("Installation date", "SYST:COMM:PROF:DATE", "2000-01-01", self.psb.communications.set_installation_date),
            ("Interface description", "SYST:COMM:PROF:DESC", "PSB command check", self.psb.communications.set_interface_description),
            ("Station name", "SYST:COMM:PROF:NAME", "psb-cmd-check", self.psb.communications.set_station_name),
        ]
        for name, command, target, setter in raw_fields:
            query = command + "?"
            try:
                old = self.psb.query_scpi(query).strip().strip('"')
            except Exception as exc:
                self.skip("optional-if", name, command, f"No verified readback ({query} failed): {exc}")
                continue
            if old == target:
                target += "2"
            self.rw_test("optional-if", name, command, lambda q=query: self.psb.query_scpi(q).strip().strip('"'), setter, target)

        # CAN settings are only touched if their corresponding queries exist.
        for name, set_cmd, query_cmd, target in [
            ("CAN format", "SYST:COMM:CAN:FORM", "SYST:COMM:CAN:FORM?", "BASE"),
            ("CAN DLC", "SYST:COMM:CAN:DLC", "SYST:COMM:CAN:DLC?", "AUTO"),
            ("CAN termination", "SYST:COMM:CAN:TERM", "SYST:COMM:CAN:TERM?", "OFF"),
        ]:
            self.raw_rw_test("optional-if", name, set_cmd, query_cmd, target)

        self.skip("optional-if", "CAN cyclic-read writes", "SYST:COMM:CAN:READ:*", "Cyclic read periods have no verified query/readback in the driver; not overwritten automatically")
        self.skip("optional-if", "CAN read/send base IDs", "SYST:COMM:CAN:*:NODE", "No verified query/readback in the driver; not overwritten automatically")

    def test_watchdog(self) -> None:
        self.query_test("watchdog", "Enabled", "SYST:COMM:MON:ACT?", lambda: self.psb.watchdog.enabled)
        self.query_test("watchdog", "Timeout", "SYST:COMM:MON:TIME?", lambda: self.psb.watchdog.timeout_s)
        self.query_test("watchdog", "Ping", "*STB?", self.psb.watchdog.ping)
        if not self.args.watchdog:
            self.skip("watchdog", "Writable watchdog settings", "SYST:COMM:MON:*", "Use --watchdog to test enable/timeout with a heartbeat")
            return
        try:
            orig_enabled = self.psb.watchdog.enabled
            orig_timeout = self.psb.watchdog.timeout_s
            target_timeout = 10 if orig_timeout != 10 else 15
            self.rw_test("watchdog", "Timeout", "SYST:COMM:MON:TIME", lambda: self.psb.watchdog.timeout_s, lambda v: setattr(self.psb.watchdog, "timeout_s", v), target_timeout)

            if not orig_enabled:
                # Start the host heartbeat first, then enable monitoring, verify,
                # and restore before stopping the heartbeat.
                self.psb.watchdog.start_heartbeat(1.0)
                self.rw_test("watchdog", "Enable", "SYST:COMM:MON:ACT", lambda: self.psb.watchdog.enabled, lambda v: setattr(self.psb.watchdog, "enabled", v), True)
                self.psb.watchdog.stop_heartbeat()
            else:
                self.rw_test("watchdog", "Enable", "SYST:COMM:MON:ACT", lambda: self.psb.watchdog.enabled, lambda v: setattr(self.psb.watchdog, "enabled", v), False)
        except Exception as exc:
            self._add("watchdog", "Writable watchdog settings", "SYST:COMM:MON:*", FAIL, detail=f"{type(exc).__name__}: {exc}")
            try:
                self.psb.watchdog.stop_heartbeat()
            except Exception:
                pass

    def test_diagnostics(self) -> None:
        specs = [
            ("Device class", "SYST:DEV:CLASS?", lambda: self.psb.diagnostics.device_class),
            ("Operation hours", "DIAG:INF:DEV:OTIM?", lambda: self.psb.diagnostics.operation_hours),
            ("DC-on hours", "DIAG:INF:DEV:ONT?", lambda: self.psb.diagnostics.dc_on_hours),
            ("DC-off hours", "DIAG:INF:DEV:OFFT?", lambda: self.psb.diagnostics.dc_off_hours),
            ("Source Ah", "FETC:AHO?", lambda: self.psb.diagnostics.source_amp_hours),
            ("Source kWh", "FETC:WHO?", lambda: self.psb.diagnostics.source_kilowatt_hours),
            ("Sink Ah", "FETC:SINK:AHO?", lambda: self.psb.diagnostics.sink_amp_hours),
            ("Sink kWh", "FETC:SINK:WHO?", lambda: self.psb.diagnostics.sink_kilowatt_hours),
        ]
        for name, command, getter in specs:
            self.query_test("diagnostics", name, command, getter)

    def test_master_slave(self) -> None:
        self.query_test("master-slave", "Enabled", "SYST:MS:ENAB?", lambda: self.psb.master_slave.enabled)
        self.query_test("master-slave", "Role", "SYST:MS:LINK?", lambda: self.psb.master_slave.role)
        self.query_test("master-slave", "Termination", "SYST:MS:TERM?", lambda: self.psb.master_slave.termination)
        self.query_test("master-slave", "Bias", "SYST:MS:BIAS?", lambda: self.psb.master_slave.bias)
        condition = self.query_test("master-slave", "Condition", "SYSTem:MS:CONDition?", lambda: self.psb.master_slave.condition, unsupported_is_skip=True)
        if isinstance(condition, str) and condition.strip().upper() == "INIT":
            self.query_test("master-slave", "Units", "SYSTem:MS:UNITs?", lambda: self.psb.master_slave.units, unsupported_is_skip=True)
        else:
            self.skip("master-slave", "Units", "SYSTem:MS:UNITs?", "Unit count is meaningful after successful master/slave initialization; current condition is not INIT")
        if not self.args.master_slave:
            self.skip("master-slave", "Writable MS settings", "SYST:MS:*", "Use --master-slave to permit topology changes")
            return
        specs = [
            ("Enabled", "SYST:MS:ENAB", lambda: self.psb.master_slave.enabled, lambda v: setattr(self.psb.master_slave, "enabled", v), [False, True]),
            ("Role", "SYST:MS:LINK", lambda: self.psb.master_slave.role, lambda v: setattr(self.psb.master_slave, "role", v), ["MASTER", "SLAVE"]),
            ("Termination", "SYST:MS:TERM", lambda: self.psb.master_slave.termination, lambda v: setattr(self.psb.master_slave, "termination", v), [False, True]),
            ("Bias", "SYST:MS:BIAS", lambda: self.psb.master_slave.bias, lambda v: setattr(self.psb.master_slave, "bias", v), [False, True]),
        ]
        for name, command, getter, setter, options in specs:
            try:
                orig = getter()
                target = choose_token(orig, options)
                if target is not None:
                    self.rw_test("master-slave", name, command, getter, setter, target)
            except Exception as exc:
                self._add("master-slave", name, command, FAIL, detail=f"{type(exc).__name__}: {exc}")
        if self.args.master_slave_init:
            start = time.perf_counter()
            before = self.capture_status()
            try:
                condition = self.psb.master_slave.initialize()
                after = self.capture_status()
                self._add("master-slave", "Initialize", "SYST:MS:INIT", PASS, readback=condition, status_before=before, status_after=after, elapsed_ms=(time.perf_counter() - start) * 1000)
            except Exception as exc:
                self._add("master-slave", "Initialize", "SYST:MS:INIT", FAIL, detail=f"{type(exc).__name__}: {exc}")
        else:
            self.skip("master-slave", "Initialize", "SYST:MS:INIT", "Use --master-slave-init; this can affect every unit on an MS bus")

    def test_output_toggle(self) -> None:
        if not self.args.output_toggle:
            self.skip("output", "DC terminal ON/OFF transition", "OUTP ON/OFF", "Use --output-toggle after confirming the DC terminals are safe to energize")
            return

        # Snapshot active setpoints and make the transition as benign as possible.
        limits = self.psb.limits.snapshot(refresh=True)
        if limits.voltage_min > 1e-9 or limits.source_current_min > 1e-9 or limits.sink_current_min > 1e-9:
            self.skip(
                "output",
                "DC terminal ON/OFF transition",
                "OUTP ON/OFF",
                "Configured minimum U/I limits are nonzero; refusing to energize the terminal for a command-only check",
            )
            return

        original = {
            "voltage": self.psb.source.voltage,
            "source_current": self.psb.source.current,
            "source_power": self.psb.source.power,
            "sink_current": self.psb.sink.current,
            "sink_power": self.psb.sink.power,
        }
        before = self.capture_status()
        start = time.perf_counter()
        try:
            # Keep the unit incapable of delivering/source current or sinking
            # current during the ON-command verification.
            self.psb.source.voltage = max(self.psb.limits.snapshot().voltage_min, 0.0)
            self.psb.source.current = max(self.psb.limits.snapshot().source_current_min, 0.0)
            self.psb.source.power = 0.0
            self.psb.sink.current = max(self.psb.limits.snapshot().sink_current_min, 0.0)
            self.psb.sink.power = 0.0
            self.psb.output.on()
            on_rb = self.psb.output.enabled
            after_on = self.capture_status()
            self.psb.output.off()
            off_rb = self.psb.output.enabled
            ok = on_rb and not off_rb
            self._add("output", "DC terminal ON/OFF transition", "OUTP ON/OFF", PASS if ok else FAIL, requested="ON then OFF", readback={"on": on_rb, "off": off_rb}, status_before=before, status_after=after_on, elapsed_ms=(time.perf_counter() - start) * 1000)
        except Exception as exc:
            self._add("output", "DC terminal ON/OFF transition", "OUTP ON/OFF", FAIL, detail=f"{type(exc).__name__}: {exc}")
        finally:
            try:
                self.psb.output.off()
                self.psb.source.voltage = original["voltage"]
                self.psb.source.current = original["source_current"]
                self.psb.source.power = original["source_power"]
                self.psb.sink.current = original["sink_current"]
                self.psb.sink.power = original["sink_power"]
            except Exception as exc:
                self._add("output", "Restore setpoints after output test", "restore", FAIL, detail=f"{type(exc).__name__}: {exc}")

    def test_function_generator(self) -> None:
        self.query_test("function-gen", "State", "FUNC:GEN:WAVE:STAT?", lambda: self.psb.function_generator.state)
        if not self.args.function_generator:
            self.skip("function-gen", "Writable function-generator commands", "FUNC:GEN:*", "Use --function-generator; configuring a waveform overwrites the current FG setup")
            return
        r = self.psb.ratings
        seq = ArbitrarySequence(
            start_amplitude=0.0,
            end_amplitude=0.0,
            start_frequency_hz=0.0,
            end_frequency_hz=0.0,
            start_angle_deg=0.0,
            start_level=0.0,
            end_level=min(1.0, r.voltage * 0.01),
            sequence_time_s=0.25,
        )
        start = time.perf_counter()
        before = self.capture_status()
        try:
            self.psb.output.off()
            self.psb.function_generator.configure_arbitrary([seq], target="VOLTAGE", verify=True)
            configured_state = self.psb.function_generator.state
            self.psb.function_generator.run()
            time.sleep(0.05)
            running_state = self.psb.function_generator.state
            self.psb.function_generator.stop()
            stopped_state = self.psb.function_generator.state
            self.psb.function_generator.exit()
            after = self.capture_status()
            self._add("function-gen", "Arbitrary configure/run/stop/exit", "FUNC:GEN:*", PASS, requested="configure/run/stop/exit", readback={"configured": configured_state, "running": running_state, "stopped": stopped_state}, status_before=before, status_after=after, detail="Function-generator configuration is destructive and is not automatically restorable", elapsed_ms=(time.perf_counter() - start) * 1000)
        except Exception as exc:
            try:
                self.psb.function_generator.stop()
                self.psb.function_generator.exit()
            except Exception:
                pass
            self._add("function-gen", "Arbitrary configure/run/stop/exit", "FUNC:GEN:*", FAIL, detail=f"{type(exc).__name__}: {exc}")

        self.skip("function-gen", "XY table load", "FUNC:GEN:XY:*", "Requires application-specific 4096-point table data; use the driver's load_xy() with a controlled dataset")

    def _inject_scpi_error(
        self,
        name: str,
        command: str,
        *,
        expected: set[int] | None = None,
        restore: Callable[[], None] | None = None,
    ) -> None:
        """Send an intentionally invalid, non-energizing command and verify the queue."""
        start = time.perf_counter()
        stale = self._discard_stale_errors()
        before = self.capture_status()
        write_exc: Exception | None = None
        try:
            self.psb.write_scpi(command, check_errors=False)
            time.sleep(max(0.02, self.args.write_settle))
        except Exception as exc:
            write_exc = exc
        after = self.capture_status()
        errors, queue_problem = self._drain_errors()
        codes = [getattr(e, "code", None) for e in errors]
        documented = bool(errors) and all(code in KNOWN_SCPI_ERRORS for code in codes)
        matches_expected = expected is None or any(code in expected for code in codes)
        ok = documented and matches_expected and write_exc is None and not queue_problem
        details: list[str] = []
        if stale:
            details.append(stale)
        if expected:
            details.append(f"expected one of {sorted(expected)}")
        details.append(f"observed {codes if codes else 'no queued error'}")
        if write_exc:
            details.append(f"transport/write exception: {type(write_exc).__name__}: {write_exc}")
        if queue_problem:
            details.append(queue_problem)

        restore_ok = True
        if restore is not None:
            try:
                restore()
                restore_errors, restore_problem = self._drain_errors()
                if restore_errors or restore_problem:
                    restore_ok = False
                    if restore_errors:
                        details.append(f"restore SCPI queue: {self._error_text(restore_errors)}")
                    if restore_problem:
                        details.append(restore_problem)
            except Exception as exc:
                restore_ok = False
                details.append(f"restore exception: {type(exc).__name__}: {exc}")
        ok = ok and restore_ok
        self._add(
            "error-inject", name, command, PASS if ok else FAIL,
            requested=(sorted(expected) if expected else "documented error"),
            readback=codes, status_before=before, status_after=after,
            detail="; ".join(details),
            elapsed_ms=(time.perf_counter() - start) * 1000,
        )

    def test_error_handling(self) -> None:
        """Exercise every documented error code plus safe real-instrument injection.

        The -999 Safety OVP and other destructive/hard-to-induce conditions are
        validated through the parser/exception path only; the verifier never
        intentionally creates a physical Safety OVP fault.
        """
        for code, message in KNOWN_SCPI_ERRORS.items():
            start = time.perf_counter()
            raw = f'{code},"{message}"'
            try:
                record = parse_scpi_error(raw)
                ok = record.code == code and record.message == message and record.is_error == (code != 0)
                if code != 0:
                    exc = PSBSCPIError([record], command="VERIFIER:SOFTWARE-ERROR-TEST")
                    ok = ok and exc.errors[0].code == code and str(code) in str(exc)
                detail = "software parser + PSBSCPIError path verified"
                if code == -999:
                    detail += "; hardware Safety OVP is intentionally NOT induced"
                self._add(
                    "error-catalog", f"SCPI error {code}: {message}", "software self-test",
                    PASS if ok else FAIL, requested=code, readback=record.code, detail=detail,
                    elapsed_ms=(time.perf_counter() - start) * 1000,
                )
            except Exception as exc:
                self._add(
                    "error-catalog", f"SCPI error {code}: {message}", "software self-test", FAIL,
                    detail=f"{type(exc).__name__}: {exc}", elapsed_ms=(time.perf_counter() - start) * 1000,
                )

        if self.args.no_error_injection:
            self.skip("error-inject", "Safe hardware error probes", "intentional invalid SCPI", "Disabled by --no-error-injection")
            return

        # Keep the terminal off and verify that the instrument actually queues
        # representative protocol/parameter errors. These writes are invalid by
        # construction and should not energize or intentionally trip protection.
        try:
            self.psb.output.off()
            self._drain_errors()
        except Exception as exc:
            self._add("error-inject", "Precondition output OFF", "OUTPut OFF", FAIL, detail=f"{type(exc).__name__}: {exc}")
            return

        self._inject_scpi_error(
            "Unknown command -> Command error",
            "VERifier:THIS:COMMAND:DOES:NOT:EXIST",
            expected={-100},
        )
        self._inject_scpi_error(
            "Parameter on no-parameter command",
            "*IDN 1",
            expected={-108, -102, -100},
        )
        self._inject_scpi_error(
            "Malformed command syntax",
            "VOLTage::PROTection 1",
            expected={-102, -100, -220},
        )
        self._inject_scpi_error(
            "Illegal enum parameter",
            "SYSTem:CONFig:MODe VERIFIER_BAD",
            expected={-224, -220},
        )

        # Save/restore voltage defensively in case a firmware clamps instead of
        # rejecting an out-of-range raw value. The output remains OFF throughout.
        original_v = None
        try:
            original_v = float(self.psb.source.voltage)
        except Exception:
            pass
        restore_voltage = None
        if original_v is not None:
            restore_voltage = lambda v=original_v: setattr(self.psb.source, "voltage", v)
        self._inject_scpi_error(
            "Out-of-range voltage parameter",
            f"VOLTage {self.psb.ratings.voltage * 2.0:g}",
            expected={-222, -220},
            restore=restore_voltage,
        )
        self._inject_scpi_error(
            "Too many parameters",
            "VOLTage 0,0,0",
            expected={-223, -108, -102},
            restore=restore_voltage,
        )
        if self.args.deep_error_injection:
            self._inject_scpi_error(
                "SCPI response buffer overflow",
                "*IDN?;*IDN?;*IDN?;*IDN?;*IDN?",
                expected={-225},
            )
        else:
            self.skip(
                "error-inject",
                "SCPI response buffer overflow",
                "*IDN? x5",
                "Software path for -225 is tested; use --deep-error-injection to intentionally overflow the instrument SCPI response buffer",
            )

    def test_firmware_extensions(self) -> None:
        for name in ("Fast discharge", "Actual-value filter", "STBY zero stabilization"):
            self.skip("extensions", name, "firmware extension", "The 2025 manual documents the feature, but the verified programming-guide revision does not provide an exact SCPI spelling. Register the verified command in psb.extensions before testing it.")

    def test_reset(self) -> None:
        if not self.args.reset:
            self.skip("system", "SCPI reset", "*RST", "Use --reset to execute *RST at the very end; it is not automatically reversible")
            return
        before = self.capture_status()
        start = time.perf_counter()
        try:
            self.psb.system.reset()
            time.sleep(0.25)
            self.psb.refresh_device_data()
            after = self.capture_status()
            self._add("system", "SCPI reset", "*RST", PASS, readback=self.psb.info.raw_idn, status_before=before, status_after=after, detail="Reset is intentionally executed last and is not restored", elapsed_ms=(time.perf_counter() - start) * 1000)
        except Exception as exc:
            self._add("system", "SCPI reset", "*RST", FAIL, detail=f"{type(exc).__name__}: {exc}")

    def run(self) -> None:
        self.prepare()
        try:
            self.test_identification_and_status()
            self.test_setpoints()
            self.test_protection()
            self.test_limits()
            self.test_events()
            self.test_system()
            self.test_analog()
            self.test_communications()
            self.test_watchdog()
            self.test_diagnostics()
            self.test_master_slave()
            self.test_output_toggle()
            self.test_function_generator()
            self.test_error_handling()
            self.test_firmware_extensions()
            self.test_reset()  # destructive: intentionally last
        finally:
            self.cleanup()

    def write_reports(self) -> None:
        if self.args.csv:
            path = Path(self.args.csv)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", newline="", encoding="utf-8") as fp:
                writer = csv.DictWriter(fp, fieldnames=list(Result.__dataclass_fields__))
                writer.writeheader()
                for row in self.results:
                    writer.writerow(asdict(row))
            print(f"CSV report: {path}")
        if self.args.json:
            path = Path(self.args.json)
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "instrument": clean(self.psb.info) if self.psb.connected else None,
                "results": [asdict(r) for r in self.results],
                "summary": self.summary(),
            }
            path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            print(f"JSON report: {path}")

    def summary(self) -> dict[str, int]:
        counts = {PASS: 0, FAIL: 0, ERROR: 0, SKIP: 0, INFO: 0}
        for item in self.results:
            counts[item.result] = counts.get(item.result, 0) + 1
        return counts


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Verify EA-PSB 10000 SCPI commands by write/readback/status/restore.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    connection = p.add_mutually_exclusive_group(required=True)
    connection.add_argument("--host", help="PSB Ethernet IP/hostname")
    connection.add_argument("--serial", help="Serial/USB COM port (for example COM5 or /dev/ttyUSB0)")
    p.add_argument("--port", type=int, default=5025, help="SCPI TCP port")
    p.add_argument("--baudrate", type=int, default=115200, help="Serial baud rate")
    p.add_argument("--timeout", type=float, default=2.0, help="SCPI read timeout in seconds")
    p.add_argument("--connect-timeout", type=float, default=5.0, help="Ethernet connect timeout in seconds")
    p.add_argument("--write-settle", type=float, default=0.02, help="Driver delay before post-write error/status check")

    p.add_argument("--output-toggle", action="store_true", help="Permit an OUTP ON/OFF test; script first commands zero source/sink capability")
    p.add_argument("--network-settings", action="store_true", help="Permit mutable LAN-setting tests; disruptive settings only run on serial/USB")
    p.add_argument("--optional-interface", action="store_true", help="Permit changes to an installed optional communication module")
    p.add_argument("--watchdog", action="store_true", help="Permit interface-monitor/watchdog enable/timeout writes")
    p.add_argument("--master-slave", action="store_true", help="Permit master/slave setting changes")
    p.add_argument("--master-slave-init", action="store_true", help="Permit SYST:MS:INIT; implies --master-slave")
    p.add_argument("--function-generator", action="store_true", help="Permit destructive function-generator configuration test")
    p.add_argument("--clear-status", action="store_true", help="Permit *CLS")
    p.add_argument("--reset", action="store_true", help="Permit *RST at the end of the run")
    p.add_argument("--release-remote", action="store_true", help="Release remote ownership on exit if this script acquired it")
    p.add_argument("--no-error-injection", action="store_true", help="Disable safe invalid-command probes; software coverage for every documented error code still runs")
    p.add_argument("--deep-error-injection", action="store_true", help="Also induce documented SCPI response-buffer overflow (-225); still never induces Safety OVP (-999)")

    p.add_argument("--test-ip", help="Alternate IP address to write/read/restore during serial LAN test")
    p.add_argument("--test-mask", help="Alternate subnet mask to write/read/restore during serial LAN test")
    p.add_argument("--test-gateway", help="Alternate gateway to write/read/restore during serial LAN test")
    p.add_argument("--test-tcp-port", type=int, help="Alternate TCP port to write/read/restore during serial LAN test")
    p.add_argument("--test-dns", nargs="+", metavar=("PRIMARY", "SECONDARY"), help="One or two alternate DNS server addresses for serial LAN test")

    p.add_argument("--csv", default="psb_command_check.csv", help="CSV report path; empty string disables")
    p.add_argument("--json", default="psb_command_check.json", help="JSON report path; empty string disables")
    p.add_argument("--verbose", action="store_true", help="Print detailed failure/skip text inline")
    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.master_slave_init:
        args.master_slave = True
    transport_kind = "ethernet" if args.host else "serial"

    options = dict(
        timeout=args.timeout,
        write_settle_s=args.write_settle,
        check_errors_after_write=False,
        raise_on_alarm_after_write=False,  # record alarms/status; don't abort every write on pre-existing alarms
        output_off_on_exit=True,
        release_remote_on_exit=False,
    )
    if args.host:
        psb = PSB10000.ethernet(args.host, args.port, connect_timeout=args.connect_timeout, **options)
    else:
        psb = PSB10000.serial(args.serial, baudrate=args.baudrate, **options)

    verifier: CommandVerifier | None = None
    try:
        psb.connect()
        verifier = CommandVerifier(psb, args, transport_kind)
        verifier.run()
        summary = verifier.summary()
        print("\nSummary:")
        print("  " + "  ".join(f"{key}={summary.get(key, 0)}" for key in (PASS, FAIL, SKIP, INFO)))
        verifier.write_reports()
        return 1 if summary.get(FAIL, 0) or summary.get(ERROR, 0) else 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 130
    except (PSBConnectionError, PSBError, OSError, RuntimeError) as exc:
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    finally:
        try:
            if psb.connected:
                # The context was not used because reports need live metadata.
                try:
                    if psb.remote_owner_raw() == "REMOTE":
                        psb.output.off()
                except Exception:
                    pass
                psb.close()
        except Exception as exc:
            print(f"WARNING: close failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
