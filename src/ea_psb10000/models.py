# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: Immutable data records returned by identification, measurement, limit,
#          protection, status, and function-generator APIs.

"""Data models returned by the high-level driver.

The models are frozen dataclasses on purpose: a returned snapshot describes the
instrument at the instant it was read.  Mutating the Python object must never be
mistaken for changing the physical supply; settings are changed only through the
subsystem APIs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from .enums import PowerFlow, RegulationMode, RemoteOwner


@dataclass(frozen=True)
class DeviceInfo:
    """Identification parsed from ``*IDN?``.

    Attributes:
        manufacturer: Manufacturer string reported by the instrument.
        model: Model identifier, for example ``PSB 10060-60``.
        serial_number: Instrument serial number.
        firmware: Remaining comma-separated IDN fields as firmware/version text.
        raw_idn: Unmodified ``*IDN?`` response for traceability.
    """

    manufacturer: str
    model: str
    serial_number: str
    firmware: Tuple[str, ...]
    raw_idn: str


@dataclass(frozen=True)
class DeviceRatings:
    """Nominal electrical ratings queried from the connected unit.

    Resistance limits are optional because some firmware/model combinations do
    not report them through the same command set.
    """

    voltage: float
    current: float
    power: float
    resistance_min: Optional[float] = None
    resistance_max: Optional[float] = None


@dataclass(frozen=True)
class Measurements:
    """One voltage/current/power measurement sample.

    EA bidirectional supplies may report negative current/power while sinking,
    so callers should not discard the sign.
    """

    voltage: float
    current: float
    power: float

    @property
    def flow(self) -> PowerFlow:
        """Infer source, sink, or idle power flow from the measurement signs."""

        if self.current < 0 or self.power < 0:
            return PowerFlow.SINK
        if self.current > 0 or self.power > 0:
            return PowerFlow.SOURCE
        return PowerFlow.IDLE


@dataclass(frozen=True)
class LimitSnapshot:
    """Current programmable adjustment limits for source and sink setpoints."""

    voltage_min: float
    voltage_max: float
    source_current_min: float
    source_current_max: float
    source_power_max: float
    source_resistance_max: Optional[float]
    sink_current_min: float
    sink_current_max: float
    sink_power_max: float
    sink_resistance_max: Optional[float]


@dataclass(frozen=True)
class ProtectionSnapshot:
    """Current programmable hard-protection thresholds."""

    ovp: float
    source_ocp: float
    source_opp: float
    sink_ocp: float
    sink_opp: float


@dataclass(frozen=True)
class StatusSnapshot:
    """Decoded status-register snapshot.

    ``raw`` retains the original register/query responses so a test log can be
    diagnosed later even if a future driver version changes the decode logic.
    """

    status_byte: int
    questionable: int
    secondary_questionable: int
    operation: int
    output_on: bool
    remote_owner: RemoteOwner
    regulation_mode: RegulationMode
    power_flow: PowerFlow
    active_alarms: Tuple[str, ...]
    active_events: Tuple[str, ...]
    raw: Mapping[str, str]

    @property
    def alarm_active(self) -> bool:
        """Return ``True`` when at least one decoded alarm is active."""

        return bool(self.active_alarms)


@dataclass(frozen=True)
class ArbitrarySequence:
    """One arbitrary-function-generator sequence record.

    The fields map directly to SCPI data indexes 0..7 in the order returned by
    :meth:`as_values`.  The driver validates ranges again before upload because
    remote function-generator programming may not receive the same HMI
    plausibility checks as manual entry.
    """

    start_amplitude: float
    end_amplitude: float
    start_frequency_hz: float
    end_frequency_hz: float
    start_angle_deg: float
    start_level: float
    end_level: float
    sequence_time_s: float

    def as_values(self) -> Tuple[float, ...]:
        """Return the eight values in the instrument's required SCPI index order."""

        return (
            float(self.start_amplitude),
            float(self.end_amplitude),
            float(self.start_frequency_hz),
            float(self.end_frequency_hz),
            float(self.start_angle_deg),
            float(self.start_level),
            float(self.end_level),
            float(self.sequence_time_s),
        )
