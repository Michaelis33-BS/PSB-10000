# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: Regenerative sink-mode current, power, and resistance setpoint controls.

"""Sink-mode setpoint controls."""

from __future__ import annotations

from typing import Optional

from .base import Subsystem
from ..util import ensure_range


class SinkSubsystem(Subsystem):
    """Typed regenerative sink-mode setpoints. Writes are checked against the instrument adjustment limits before transmission."""

    @property
    def current(self) -> float:
        """Read and return the current current setpoint from the instrument or driver state.
        
        Underlying SCPI used here: ``SINK:CURR?``."""

        return self._query_float("SINK:CURR?")

    @current.setter
    def current(self, value: float) -> None:
        """Validate and write the current setpoint to the instrument.
        
        Underlying SCPI used here: ``SINK:CURR {value}``, ``SINK:CURR``."""

        limits = self._device.limits.snapshot()
        value = ensure_range(value, limits.sink_current_min, limits.sink_current_max, "sink current")
        self._write(f"SINK:CURR {value:.12g}")

    @property
    def power(self) -> float:
        """Read and return the current power setpoint from the instrument or driver state.
        
        Underlying SCPI used here: ``SINK:POW?``."""

        return self._query_float("SINK:POW?")

    @power.setter
    def power(self, value: float) -> None:
        """Validate and write the power setpoint to the instrument.
        
        Underlying SCPI used here: ``SINK:POW {value}``, ``SINK:POW``."""

        limits = self._device.limits.snapshot()
        value = ensure_range(value, 0.0, limits.sink_power_max, "sink power")
        self._write(f"SINK:POW {value:.12g}")

    @property
    def resistance(self) -> float:
        """Read and return the current resistance setpoint from the instrument or driver state.
        
        Underlying SCPI used here: ``SINK:RES?``."""

        return self._query_float("SINK:RES?")

    @resistance.setter
    def resistance(self, value: float) -> None:
        """Validate and write the resistance setpoint to the instrument.
        
        Underlying SCPI used here: ``SINK:RES {value}``, ``SINK:RES``."""

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
        current: Optional[float] = None,
        power: Optional[float] = None,
        resistance: Optional[float] = None,
    ) -> None:
        """Validate and configure configure using only the values supplied by the caller."""

        if current is not None:
            self.current = current
        if power is not None:
            self.power = power
        if resistance is not None:
            self.resistance = resistance
