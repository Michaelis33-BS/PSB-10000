"""Adjustment limit controls."""

from __future__ import annotations

from .base import Subsystem
from ..models import LimitSnapshot
from ..util import ensure_range


class LimitsSubsystem(Subsystem):
    def snapshot(self, *, refresh: bool = False) -> LimitSnapshot:
        if self._device._limit_cache is not None and not refresh:
            return self._device._limit_cache
        r = self._device.ratings
        def optional(command: str) -> float | None:
            try:
                return self._query_float(command)
            except Exception:
                return None
        snap = LimitSnapshot(
            voltage_min=self._query_float("VOLT:LIM:LOW?"),
            voltage_max=self._query_float("VOLT:LIM:HIGH?"),
            source_current_min=self._query_float("CURR:LIM:LOW?"),
            source_current_max=self._query_float("CURR:LIM:HIGH?"),
            source_power_max=self._query_float("POW:LIM:HIGH?"),
            source_resistance_max=optional("RES:LIM:HIGH?"),
            sink_current_min=self._query_float("SINK:CURR:LIM:LOW?"),
            sink_current_max=self._query_float("SINK:CURR:LIM:HIGH?"),
            sink_power_max=self._query_float("SINK:POW:LIM:HIGH?"),
            sink_resistance_max=optional("SINK:RES:LIM:HIGH?"),
        )
        # Defensive sanity checks for damaged/misparsed responses.
        if snap.voltage_max > r.voltage * 1.03 + 1e-9:
            self._device.logger.warning("Reported voltage adjustment limit exceeds expected 102%% nominal")
        self._device._limit_cache = snap
        return snap

    def invalidate(self) -> None:
        self._device._limit_cache = None

    def _set(self, command: str, value: float, low: float, high: float, name: str) -> None:
        value = ensure_range(value, low, high, name)
        self._write(f"{command} {value:.12g}")
        self.invalidate()

    def set_voltage(self, *, minimum: float | None = None, maximum: float | None = None) -> None:
        r = self._device.ratings
        if minimum is not None:
            self._set("VOLT:LIM:LOW", minimum, 0.0, r.voltage * 1.02, "voltage minimum")
        if maximum is not None:
            self._set("VOLT:LIM:HIGH", maximum, 0.0, r.voltage * 1.02, "voltage maximum")

    def set_source_current(self, *, minimum: float | None = None, maximum: float | None = None) -> None:
        r = self._device.ratings
        if minimum is not None:
            self._set("CURR:LIM:LOW", minimum, 0.0, r.current * 1.02, "source current minimum")
        if maximum is not None:
            self._set("CURR:LIM:HIGH", maximum, 0.0, r.current * 1.02, "source current maximum")

    def set_source_power(self, maximum: float) -> None:
        self._set("POW:LIM:HIGH", maximum, 0.0, self._device.ratings.power * 1.02, "source power maximum")

    def set_sink_current(self, *, minimum: float | None = None, maximum: float | None = None) -> None:
        r = self._device.ratings
        if minimum is not None:
            self._set("SINK:CURR:LIM:LOW", minimum, 0.0, r.current * 1.02, "sink current minimum")
        if maximum is not None:
            self._set("SINK:CURR:LIM:HIGH", maximum, 0.0, r.current * 1.02, "sink current maximum")

    def set_sink_power(self, maximum: float) -> None:
        self._set("SINK:POW:LIM:HIGH", maximum, 0.0, self._device.ratings.power * 1.02, "sink power maximum")

    def set_source_resistance_max(self, maximum: float) -> None:
        high = self._device.ratings.resistance_max
        if high is None:
            self._device._unsupported("resistance nominal range unavailable")
        self._set("RES:LIM:HIGH", maximum, 0.0, float(high), "source resistance maximum")

    def set_sink_resistance_max(self, maximum: float) -> None:
        high = self._device.ratings.resistance_max
        if high is None:
            self._device._unsupported("resistance nominal range unavailable")
        self._set("SINK:RES:LIM:HIGH", maximum, 0.0, float(high), "sink resistance maximum")
