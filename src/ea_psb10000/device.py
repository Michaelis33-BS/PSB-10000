# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: High-level device facade, connection lifecycle, SCPI transactions, measurements, and safety checks.

"""High-level reusable driver for EA-PSB 10000 bidirectional supplies."""

from __future__ import annotations

import logging
import math
import time
from threading import RLock
from typing import Any, Optional, Tuple

from .exceptions import (
    PSBAlarmError,
    PSBConnectionError,
    PSBProtocolError,
    PSBRemoteControlError,
    PSBSCPIError,
    PSBUnsupportedFeatureError,
)
from .models import DeviceInfo, DeviceRatings, LimitSnapshot, Measurements
from .transports import EthernetTransport, SCPITransport, SerialTransport
from .util import parse_bool, parse_csv_numbers, parse_float, parse_int, parse_scpi_error
from .subsystems import (
    AnalogInterfaceSubsystem,
    CommunicationsSubsystem,
    DiagnosticsSubsystem,
    ErrorSubsystem,
    EventsSubsystem,
    FirmwareExtensionsSubsystem,
    FunctionGeneratorSubsystem,
    LimitsSubsystem,
    MasterSlaveSubsystem,
    OutputSubsystem,
    ProtectionSubsystem,
    SinkSubsystem,
    SourceSubsystem,
    StatusSubsystem,
    SystemSubsystem,
    WatchdogSubsystem,
)


class PSB10000:
    """EA-PSB 10000 SCPI driver.

    Design goals:
      * safe connection: connecting never energizes the DC terminal;
      * transport independence: Ethernet and serial share one high-level API;
      * thread-safe transactions;
      * explicit remote ownership;
      * model-aware range validation;
      * SCPI error queue checking without silently replaying writes;
      * raw SCPI escape hatch for future firmware commands.

    The driver does *not* automatically retry state-changing writes.  If a
    connection is lost while a write is in flight, the caller cannot know with
    certainty whether the instrument applied it, so replaying it is unsafe.
    """

    def __init__(
        self,
        transport: SCPITransport,
        *,
        check_errors_after_write: bool = True,
        raise_on_alarm_after_write: bool = True,
        write_settle_s: float = 0.02,
        strict_model: bool = True,
        output_off_on_exit: bool = False,
        release_remote_on_exit: bool = False,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.transport = transport
        self.check_errors_after_write = bool(check_errors_after_write)
        self.raise_on_alarm_after_write = bool(raise_on_alarm_after_write)
        self.write_settle_s = max(0.0, float(write_settle_s))
        self.strict_model = bool(strict_model)
        self.output_off_on_exit = bool(output_off_on_exit)
        self.release_remote_on_exit = bool(release_remote_on_exit)
        self.logger = logger or logging.getLogger("ea_psb10000")
        self._io_lock = RLock()
        self._info_cache: Optional[DeviceInfo] = None
        self._ratings_cache: Optional[DeviceRatings] = None
        self._limit_cache: Optional[LimitSnapshot] = None
        self._last_alarm_masks: Tuple[int, int] = (0, 0)

        self.source = SourceSubsystem(self)
        self.sink = SinkSubsystem(self)
        self.output = OutputSubsystem(self)
        self.protection = ProtectionSubsystem(self)
        self.limits = LimitsSubsystem(self)
        self.events = EventsSubsystem(self)
        self.status = StatusSubsystem(self)
        self.errors = ErrorSubsystem(self)
        self.system = SystemSubsystem(self)
        self.communications = CommunicationsSubsystem(self)
        self.diagnostics = DiagnosticsSubsystem(self)
        self.analog = AnalogInterfaceSubsystem(self)
        self.master_slave = MasterSlaveSubsystem(self)
        self.function_generator = FunctionGeneratorSubsystem(self)
        self.extensions = FirmwareExtensionsSubsystem(self)
        self.watchdog = WatchdogSubsystem(self)

    @classmethod
    def ethernet(
        cls,
        host: str,
        port: int = 5025,
        *,
        timeout: float = 2.0,
        connect_timeout: float = 5.0,
        **driver_options: Any,
    ) -> "PSB10000":
        """Construct a PSB10000 instance using the built-in Ethernet/TCP SCPI interface. This
        only constructs the object; use connect() or a with block to open the socket."""

        return cls(
            EthernetTransport(host, port, timeout=timeout, connect_timeout=connect_timeout),
            **driver_options,
        )

    @classmethod
    def serial(
        cls,
        port: str,
        *,
        baudrate: int = 115200,
        timeout: float = 2.0,
        **driver_options: Any,
    ) -> "PSB10000":
        """Construct a PSB10000 instance using a serial or USB-COM SCPI connection. pyserial is
        required for this transport."""

        return cls(SerialTransport(port, baudrate=baudrate, timeout=timeout), **driver_options)

    @property
    def connected(self) -> bool:
        """Return True while the underlying transport is open."""

        return self.transport.is_open

    def connect(self) -> "PSB10000":
        """Open the transport and identify the unit; never acquires remote or turns DC on."""
        self.transport.open()
        try:
            info = self._read_identity()
            if self.strict_model:
                model_upper = info.model.upper().replace("-", " ")
                if "PSB" not in model_upper or "100" not in model_upper:
                    raise PSBConnectionError(
                        f"Connected instrument identifies as {info.model!r}, not an EA-PSB 10000 family device"
                    )
            self._info_cache = info
            self._ratings_cache = self._read_ratings()
            self._limit_cache = None
            return self
        except Exception:
            self.transport.close()
            raise

    def close(self) -> None:
        # Stop the optional host heartbeat before closing the underlying socket/
        # serial handle so the background thread cannot race transport teardown.
        """Stop the optional heartbeat and close the underlying transport. This does not
        silently change the DC terminal unless context-manager cleanup options requested it."""

        try:
            self.watchdog.stop_heartbeat()
        finally:
            self.transport.close()

    def __enter__(self) -> "PSB10000":
        return self.connect()

    def __exit__(self, exc_type, exc, tb) -> None:
        cleanup_error: Optional[Exception] = None
        try:
            if self.connected and self.output_off_on_exit:
                try:
                    if self.remote_owner_raw() == "REMOTE":
                        self.output.off()
                except Exception as cleanup_exc:
                    cleanup_error = cleanup_exc
                    self.logger.exception("Failed to switch DC terminal off during context cleanup")
            if self.connected and self.release_remote_on_exit:
                try:
                    if self.remote_owner_raw() == "REMOTE":
                        self.release_remote()
                except Exception as cleanup_exc:
                    cleanup_error = cleanup_error or cleanup_exc
                    self.logger.exception("Failed to release remote control during context cleanup")
        finally:
            self.close()
        if exc is None and cleanup_error is not None:
            raise cleanup_error

    def _require_open(self) -> None:
        if not self.connected:
            raise PSBConnectionError("PSB is not connected; call connect() or use a with block")

    def query_scpi(self, command: str) -> str:
        """Send a raw SCPI query.

        Raw queries are intentionally not followed by SYST:ERR? because querying
        the error queue itself has side effects (alarm acknowledgement).  High-
        level setters use write_scpi(), which performs the configured checks.
        """
        self._require_open()
        if "?" not in command:
            self.logger.debug("query_scpi called with command not containing '?': %s", command)
        with self._io_lock:
            self.logger.debug("SCPI ? %s", command)
            response = self.transport.query(command)
            self.logger.debug("SCPI < %s", response)
            return response

    def write_scpi(self, command: str, *, check_errors: Optional[bool] = None) -> None:
        """Send a raw SCPI write and optionally verify the instrument error state.

        Before reading SYST:ERR? the driver captures current alarm condition
        registers because EA documents that reading the error queue can also
        acknowledge alarm bits whose cause has disappeared.
        """
        self._require_open()
        do_check = self.check_errors_after_write if check_errors is None else bool(check_errors)
        with self._io_lock:
            self.logger.debug("SCPI > %s", command)
            self.transport.write(command)
            if not do_check:
                return
            if self.write_settle_s:
                time.sleep(self.write_settle_s)

            q = 0
            sq = 0
            try:
                q = parse_int(self.transport.query("STAT:QUES:COND?"), name="questionable status")
                try:
                    sq = parse_int(self.transport.query("STAT:SEC:QUES:COND?"), name="secondary questionable status")
                except Exception:
                    sq = 0
                self._last_alarm_masks = (q, sq)
            except Exception:
                # An unsupported status query should not prevent us from reading
                # the error queue. The original error is preserved there if the
                # instrument supports normal SCPI status handling.
                pass

            record = parse_scpi_error(self.transport.query("SYST:ERR?"))
            if record.is_error:
                # Drain remaining command errors so callers get the full context.
                records = [record]
                for _ in range(15):
                    nxt = parse_scpi_error(self.transport.query("SYST:ERR?"))
                    if not nxt.is_error:
                        break
                    records.append(nxt)
                raise PSBSCPIError(records, command=command)

            if self.raise_on_alarm_after_write:
                alarms = self.status.decode_alarms(q, sq)
                if alarms:
                    raise PSBAlarmError(alarms, questionable=q, secondary=sq)

    def _query_float(self, command: str) -> float:
        return parse_float(self.query_scpi(command), name=command)

    def _query_int(self, command: str) -> int:
        return parse_int(self.query_scpi(command), name=command)

    def _query_bool(self, command: str) -> bool:
        return parse_bool(self.query_scpi(command))

    def _unsupported(self, message: str) -> None:
        raise PSBUnsupportedFeatureError(message)

    def _read_identity(self) -> DeviceInfo:
        raw = self.query_scpi("*IDN?")
        parts = [part.strip().strip('"') for part in raw.split(",")]
        if len(parts) < 3:
            raise PSBProtocolError(f"Unexpected *IDN? response: {raw!r}")
        manufacturer = parts[0]
        model = parts[1] if len(parts) > 1 else ""
        serial = parts[2] if len(parts) > 2 else ""
        firmware = tuple(parts[3:]) if len(parts) > 3 else ()
        return DeviceInfo(manufacturer, model, serial, firmware, raw)

    def _read_ratings(self) -> DeviceRatings:
        voltage = self._query_float("SYST:NOM:VOLT?")
        current = self._query_float("SYST:NOM:CURR?")
        power = self._query_float("SYST:NOM:POW?")
        rmin: Optional[float] = None
        rmax: Optional[float] = None
        try:
            rmin = self._query_float("SYST:NOM:RES:MIN?")
            rmax = self._query_float("SYST:NOM:RES:MAX?")
        except Exception:
            # Some firmware/model combinations can omit resistance. Preserve
            # basic operation rather than failing the whole connection.
            self.logger.debug("Resistance nominal range not available", exc_info=True)
        if voltage <= 0 or current <= 0 or power <= 0:
            raise PSBProtocolError(
                f"Invalid nominal ratings returned by device: {voltage=}, {current=}, {power=}"
            )
        return DeviceRatings(voltage, current, power, rmin, rmax)

    @property
    def info(self) -> DeviceInfo:
        """Return cached device identification information, querying *IDN? on first access."""

        if self._info_cache is None:
            self._info_cache = self._read_identity()
        return self._info_cache

    @property
    def ratings(self) -> DeviceRatings:
        """Return cached nominal voltage/current/power/resistance ratings read from the
        instrument."""

        if self._ratings_cache is None:
            self._ratings_cache = self._read_ratings()
        return self._ratings_cache

    def refresh_device_data(self) -> None:
        """Refresh identity and nominal ratings from hardware and invalidate the cached
        adjustment limits."""

        self._info_cache = self._read_identity()
        self._ratings_cache = self._read_ratings()
        self._limit_cache = None

    def acquire_remote(self) -> None:
        """Request digital remote control and verify that the instrument reports REMOTE
        ownership.
        
        Underlying SCPI used here: ``SYST:LOCK ON``."""

        self.write_scpi("SYST:LOCK ON", check_errors=True)
        owner = self.remote_owner_raw()
        if owner != "REMOTE":
            raise PSBRemoteControlError(
                f"Instrument did not grant remote ownership; SYST:LOCK:OWNER? returned {owner!r}"
            )

    def release_remote(self) -> None:
        # Leaving remote can change output state according to device setup.
        """Release digital remote control and verify that the instrument no longer reports
        REMOTE ownership. Device configuration determines what happens to the DC terminal
        after remote is released.
        
        Underlying SCPI used here: ``SYST:LOCK OFF``."""

        self.write_scpi("SYST:LOCK OFF", check_errors=True)
        owner = self.remote_owner_raw()
        if owner == "REMOTE":
            raise PSBRemoteControlError("Instrument remained in remote control after SYST:LOCK OFF")

    def remote_owner_raw(self) -> str:
        """Return the raw normalized remote-control owner token reported by the PSB.
        
        Underlying SCPI used here: ``SYST:LOCK:OWNER?``."""

        return self.query_scpi("SYST:LOCK:OWNER?").strip().upper()

    def require_remote(self) -> None:
        """Raise PSBRemoteControlError unless digital remote control is currently owned by this
        interface."""

        owner = self.remote_owner_raw()
        if owner != "REMOTE":
            raise PSBRemoteControlError(f"Operation requires digital remote control; current owner is {owner}")

    def measure(self) -> Measurements:
        """Read voltage, current, and power. MEAS:ARR? is preferred; individual measurement
        queries are used as a compatibility fallback.
        
        Underlying SCPI used here: ``MEAS:ARR?``, ``MEAS:VOLT?``, ``MEAS:CURR?``,
        ``MEAS:POW?``."""

        values = parse_csv_numbers(self.query_scpi("MEAS:ARR?"))
        if len(values) < 3:
            # Fall back to individual queries if a firmware returns an odd array.
            return Measurements(
                self._query_float("MEAS:VOLT?"),
                self._query_float("MEAS:CURR?"),
                self._query_float("MEAS:POW?"),
            )
        return Measurements(values[0], values[1], values[2])

    def source_only(self) -> None:
        """Force source-only behavior by setting the sink current setpoint to 0 A."""
        self.sink.current = 0.0

    def sink_only(self) -> None:
        """Force sink-only behavior per EA's rule by setting voltage setpoint to 0 V."""
        self.source.voltage = 0.0

    def bidirectional(self, *, voltage: float, sink_current: float) -> None:
        """Restore bidirectional operation with explicit voltage and sink-current settings."""
        self.source.voltage = voltage
        self.sink.current = sink_current

    def ping(self) -> bool:
        """Return True if a non-mutating *IDN? query succeeds; return False on
        communication/protocol failure.
        
        Underlying SCPI used here: ``*IDN?``."""

        try:
            return bool(self.query_scpi("*IDN?"))
        except Exception:
            return False

    @property
    def last_alarm_masks_before_error_check(self) -> Tuple[int, int]:
        """Return the QUESTIONABLE and secondary QUESTIONABLE condition masks captured
        immediately before the most recent automatic SCPI error-queue read."""

        return self._last_alarm_masks
