"""Function-generator support verified against EA's SCPI programming guide."""

from __future__ import annotations

import time
from collections.abc import Sequence

from .base import Subsystem
from ..models import ArbitrarySequence
from ..util import ensure_range


class FunctionGeneratorSubsystem(Subsystem):
    def exit(self) -> None:
        self._write("FUNC:GEN:SEL NONE")

    def select_arbitrary(self, target: str) -> None:
        token = target.upper()
        aliases = {"V": "VOLTAGE", "VOLT": "VOLTAGE", "I": "CURRENT", "CURR": "CURRENT"}
        token = aliases.get(token, token)
        if token not in {"VOLTAGE", "CURRENT"}:
            raise ValueError("arbitrary target must be VOLTAGE or CURRENT")
        self._write(f"FUNC:GEN:SEL {token}")

    def configure_arbitrary(
        self,
        sequences: Sequence[ArbitrarySequence],
        *,
        target: str,
        cycles: int = 1,
        start_sequence: int = 1,
        submit_delay_s: float = 2.0,
        verify_each_value: bool = False,
        check_each_write: bool = False,
    ) -> None:
        if not 1 <= len(sequences) <= 99:
            raise ValueError("arbitrary generator requires 1..99 sequences")
        if not 0 <= cycles <= 999:
            raise ValueError("cycles must be 0 (infinite) or 1..999")
        end_sequence = start_sequence + len(sequences) - 1
        if not 1 <= start_sequence <= 99 or end_sequence > 99:
            raise ValueError("sequence numbers must remain within 1..99")

        # EA requires leaving the previous generator mode before selecting a
        # different one. configure_arbitrary() is a destructive reconfiguration
        # anyway, so explicitly exit first.
        self.exit()
        self.select_arbitrary(target)
        self._write(f"FUNC:GEN:WAVE:STAR {start_sequence}")
        self._write(f"FUNC:GEN:WAVE:END {end_sequence}")
        self._write(f"FUNC:GEN:WAVE:NUM {cycles}")

        # EA explicitly warns that plausibility checks are not performed in
        # remote mode, so perform the range checks the guide documents.
        target_token = target.upper()
        is_voltage = target_token in {"V", "VOLT", "VOLTAGE"}
        nominal = self._device.ratings.voltage if is_voltage else self._device.ratings.current
        for seq_number, sequence in enumerate(sequences, start=start_sequence):
            values = sequence.as_values()
            ensure_range(values[0], 0.0, nominal, "start amplitude")
            ensure_range(values[1], 0.0, nominal, "end amplitude")
            ensure_range(values[2], 0.0, 10000.0, "start frequency")
            ensure_range(values[3], 0.0, 10000.0, "end frequency")
            ensure_range(values[4], 0.0, 359.0, "start angle")
            level_min = 0.0 if is_voltage else -nominal
            ensure_range(values[5], level_min, nominal, "start level")
            ensure_range(values[6], level_min, nominal, "end level")
            ensure_range(values[7], 0.0001, 36000.0, "sequence time")
            # Bulk table loading can involve hundreds of writes. By default we
            # defer SCPI error-queue inspection until SUBMIT; local validation
            # catches documented range errors before transmission. Set
            # check_each_write=True for bench debugging when per-field checking
            # is worth the substantial performance cost.
            self._write(f"FUNC:GEN:WAVE:LEV {seq_number}", check_errors=check_each_write)
            for index, value in enumerate(values):
                self._write(f"FUNC:GEN:WAVE:IND {index}", check_errors=check_each_write)
                self._write(f"FUNC:GEN:WAVE:DATA {value:.12g}", check_errors=check_each_write)
                if verify_each_value:
                    returned = self._query_float("FUNC:GEN:WAVE:DATA?")
                    if abs(returned - value) > max(1e-9, abs(value) * 1e-6):
                        raise RuntimeError(
                            f"Function-generator readback mismatch at sequence {seq_number}, index {index}: "
                            f"requested {value}, got {returned}"
                        )
        self._write("FUNC:GEN:WAVE:SUBM")
        if submit_delay_s > 0:
            time.sleep(submit_delay_s)

    def run(self) -> None:
        self._write("FUNC:GEN:WAVE:STAT RUN")

    def stop(self) -> None:
        self._write("FUNC:GEN:WAVE:STAT STOP")

    @property
    def state(self) -> str:
        return self._query("FUNC:GEN:WAVE:STAT?").strip().upper()

    def load_xy(
        self,
        mode: str,
        values: Sequence[float],
        *,
        second_table: bool = False,
        submit_delay_s: float = 2.0,
        check_each_write: bool = False,
    ) -> None:
        token = mode.upper()
        if token not in {"FC", "IUPS", "IUEL", "IU", "PV", "PVA", "PVB"}:
            raise ValueError("PSB XY mode must be FC, IUPS, IUEL, IU, PV, PVA, or PVB")
        if not 1 <= len(values) <= 4096:
            raise ValueError("XY table requires 1..4096 values")
        self.exit()
        self._write(f"FUNC:GEN:SEL {token}")
        prefix = "FUNC:GEN:XY:SEC" if second_table else "FUNC:GEN:XY"
        for index, value in enumerate(values):
            self._write(f"{prefix}:LEV {index}", check_errors=check_each_write)
            self._write(f"{prefix}:DATA {float(value):.12g}", check_errors=check_each_write)
        self._write(f"FUNC:GEN:XY:SUBM {'SECOND' if second_table else 'FIRST'}")
        if submit_delay_s > 0:
            time.sleep(submit_delay_s)
