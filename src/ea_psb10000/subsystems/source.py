"""Source-mode setpoint controls."""

from __future__ import annotations

from .base import Subsystem
from ..util import ensure_range


class SourceSubsystem(Subsystem):
    @property
    def voltage(self) -> float:
        return self._query_float("VOLT?")

    @voltage.setter
    def voltage(self, value: float) -> None:
        limits = self._device.limits.snapshot()
        value = ensure_range(value, limits.voltage_min, limits.voltage_max, "source voltage")
        self._write(f"VOLT {value:.12g}")

    @property
    def current(self) -> float:
        return self._query_float("CURR?")

    @current.setter
    def current(self, value: float) -> None:
        limits = self._device.limits.snapshot()
        value = ensure_range(value, limits.source_current_min, limits.source_current_max, "source current")
        self._write(f"CURR {value:.12g}")

    @property
    def power(self) -> float:
        return self._query_float("POW?")

    @power.setter
    def power(self, value: float) -> None:
        limits = self._device.limits.snapshot()
        value = ensure_range(value, 0.0, limits.source_power_max, "source power")
        self._write(f"POW {value:.12g}")

    @property
    def resistance(self) -> float:
        return self._query_float("RES?")

    @resistance.setter
    def resistance(self, value: float) -> None:
        ratings = self._device.ratings
        limits = self._device.limits.snapshot()
        low = ratings.resistance_min if ratings.resistance_min is not None else 0.0
        high = limits.source_resistance_max
        if high is None:
            high = ratings.resistance_max
        if high is None:
            self._device._unsupported("source resistance range is not reported by this device")
        value = ensure_range(value, low, float(high), "source resistance")
        self._write(f"RES {value:.12g}")

    def configure(
        self,
        *,
        voltage: float | None = None,
        current: float | None = None,
        power: float | None = None,
        resistance: float | None = None,
    ) -> None:
        """Set multiple source values in a deterministic order.

        This is not an instrument-side transaction: if a later command fails, earlier
        values remain changed.  Callers that need rollback should snapshot first.
        """
        if voltage is not None:
            self.voltage = voltage
        if current is not None:
            self.current = current
        if power is not None:
            self.power = power
        if resistance is not None:
            self.resistance = resistance
