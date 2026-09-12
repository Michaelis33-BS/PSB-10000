"""Data models for measurements, identity, status, and configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .enums import PowerFlow, RegulationMode, RemoteOwner


@dataclass(slots=True, frozen=True)
class DeviceInfo:
    manufacturer: str
    model: str
    serial_number: str
    firmware: tuple[str, ...]
    raw_idn: str


@dataclass(slots=True, frozen=True)
class DeviceRatings:
    voltage: float
    current: float
    power: float
    resistance_min: float | None = None
    resistance_max: float | None = None


@dataclass(slots=True, frozen=True)
class Measurements:
    voltage: float
    current: float
    power: float

    @property
    def flow(self) -> PowerFlow:
        if self.current < 0 or self.power < 0:
            return PowerFlow.SINK
        if self.current > 0 or self.power > 0:
            return PowerFlow.SOURCE
        return PowerFlow.IDLE


@dataclass(slots=True, frozen=True)
class LimitSnapshot:
    voltage_min: float
    voltage_max: float
    source_current_min: float
    source_current_max: float
    source_power_max: float
    source_resistance_max: float | None
    sink_current_min: float
    sink_current_max: float
    sink_power_max: float
    sink_resistance_max: float | None


@dataclass(slots=True, frozen=True)
class ProtectionSnapshot:
    ovp: float
    source_ocp: float
    source_opp: float
    sink_ocp: float
    sink_opp: float


@dataclass(slots=True, frozen=True)
class StatusSnapshot:
    status_byte: int
    questionable: int
    secondary_questionable: int
    operation: int
    output_on: bool
    remote_owner: RemoteOwner
    regulation_mode: RegulationMode
    power_flow: PowerFlow
    active_alarms: tuple[str, ...]
    active_events: tuple[str, ...]
    raw: Mapping[str, str]

    @property
    def alarm_active(self) -> bool:
        return bool(self.active_alarms)


@dataclass(slots=True, frozen=True)
class ArbitrarySequence:
    """One EA arbitrary-generator sequence (SCPI indexes 0..7)."""

    start_amplitude: float
    end_amplitude: float
    start_frequency_hz: float
    end_frequency_hz: float
    start_angle_deg: float
    start_level: float
    end_level: float
    sequence_time_s: float

    def as_values(self) -> tuple[float, ...]:
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
