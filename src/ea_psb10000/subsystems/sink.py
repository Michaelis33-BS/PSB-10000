"""Sink-mode setpoint controls."""

from __future__ import annotations

from .base import Subsystem
from ..util import ensure_range


class SinkSubsystem(Subsystem):
    @property
    def current(self) -> float:
        return self._query_float("SINK:CURR?")

    @current.setter
    def current(self, value: float) -> None:
        limits = self._device.limits.snapshot()
        value = ensure_range(value, limits.sink_current_min, limits.sink_current_max, "sink current")
        self._write(f"SINK:CURR {value:.12g}")

    @property
    def power(self) -> float:
        return self._query_float("SINK:POW?")

    @power.setter
    def power(self, value: float) -> None:
        limits = self._device.limits.snapshot()
        value = ensure_range(value, 0.0, limits.sink_power_max, "sink power")
        self._write(f"SINK:POW {value:.12g}")

    @property
    def resistance(self) -> float:
        return self._query_float("SINK:RES?")

    @resistance.setter
    def resistance(self, value: float) -> None:
        ratings = self._device.ratings
        limits = self._device.limits.snapshot()
        low = ratings.resistance_min if ratings.resistance_min is not None else 0.0
        high = limits.sink_resistance_max
        if high is None:
            high = ratings.resistance_max
        if high is None:
            self._device._unsupported("sink resistance range is not reported by this device")
        value = ensure_range(value, low, float(high), "sink resistance")
        self._write(f"SINK:RES {value:.12g}")

    def configure(
        self,
        *,
        current: float | None = None,
        power: float | None = None,
        resistance: float | None = None,
    ) -> None:
        if current is not None:
            self.current = current
        if power is not None:
            self.power = power
        if resistance is not None:
            self.resistance = resistance
