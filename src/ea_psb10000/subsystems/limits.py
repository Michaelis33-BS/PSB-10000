# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: Adjustment-limit readback, validation, cache management, and writes.

"""Adjustment limit controls."""

from __future__ import annotations

from typing import Optional

from .base import Subsystem
from ..models import LimitSnapshot
from ..util import ensure_range


class LimitsSubsystem(Subsystem):
    """Adjustment-limit access with a device-side readback snapshot cached by the driver until invalidated."""

    def snapshot(self, *, refresh: bool = False) -> LimitSnapshot:
        """Read all supported adjustment limits and return a LimitSnapshot. Unless
        refresh=True, a previously cached snapshot may be returned.
        
        Underlying SCPI used here: ``VOLT:LIM:LOW?``, ``VOLT:LIM:HIGH?``, ``CURR:LIM:LOW?``,
        ``CURR:LIM:HIGH?``, ``POW:LIM:HIGH?``, ``RES:LIM:HIGH?``, ``SINK:CURR:LIM:LOW?``,
        ``SINK:CURR:LIM:HIGH?``."""

        if self._device._limit_cache is not None and not refresh:
            return self._device._limit_cache
        r = self._device.ratings
        def optional(command: str) -> Optional[float]:
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
        """Discard the cached adjustment-limit snapshot so the next read obtains current
        hardware values."""

        self._device._limit_cache = None

    def _set(self, command: str, value: float, low: float, high: float, name: str) -> None:
        value = ensure_range(value, low, high, name)
        self._write(f"{command} {value:.12g}")
        self.invalidate()

    def set_voltage(self, *, minimum: Optional[float] = None, maximum: Optional[float] = None) -> None:
        """Validate and write voltage.
        
        Underlying SCPI used here: ``VOLT:LIM:LOW``, ``VOLT:LIM:HIGH``."""

        r = self._device.ratings
        if minimum is not None:
            self._set("VOLT:LIM:LOW", minimum, 0.0, r.voltage * 1.02, "voltage minimum")
        if maximum is not None:
            self._set("VOLT:LIM:HIGH", maximum, 0.0, r.voltage * 1.02, "voltage maximum")

    def set_source_current(self, *, minimum: Optional[float] = None, maximum: Optional[float] = None) -> None:
        """Validate and write source current.
        
        Underlying SCPI used here: ``CURR:LIM:LOW``, ``CURR:LIM:HIGH``."""

        r = self._device.ratings
        if minimum is not None:
            self._set("CURR:LIM:LOW", minimum, 0.0, r.current * 1.02, "source current minimum")
        if maximum is not None:
            self._set("CURR:LIM:HIGH", maximum, 0.0, r.current * 1.02, "source current maximum")

    def set_source_power(self, maximum: float) -> None:
        """Validate and write source power.
        
        Underlying SCPI used here: ``POW:LIM:HIGH``."""

        self._set("POW:LIM:HIGH", maximum, 0.0, self._device.ratings.power * 1.02, "source power maximum")

    def set_sink_current(self, *, minimum: Optional[float] = None, maximum: Optional[float] = None) -> None:
        """Validate and write sink current.
        
        Underlying SCPI used here: ``SINK:CURR:LIM:LOW``, ``SINK:CURR:LIM:HIGH``."""

        r = self._device.ratings
        if minimum is not None:
            self._set("SINK:CURR:LIM:LOW", minimum, 0.0, r.current * 1.02, "sink current minimum")
        if maximum is not None:
            self._set("SINK:CURR:LIM:HIGH", maximum, 0.0, r.current * 1.02, "sink current maximum")

    def set_sink_power(self, maximum: float) -> None:
        """Validate and write sink power.
        
        Underlying SCPI used here: ``SINK:POW:LIM:HIGH``."""

        self._set("SINK:POW:LIM:HIGH", maximum, 0.0, self._device.ratings.power * 1.02, "sink power maximum")

    def set_source_resistance_max(self, maximum: float) -> None:
        """Validate and write source resistance max.
        
        Underlying SCPI used here: ``RES:LIM:HIGH``."""

        high = self._device.ratings.resistance_max
        if high is None:
            self._device._unsupported("resistance nominal range unavailable")
        self._set("RES:LIM:HIGH", maximum, 0.0, float(high), "source resistance maximum")

    def set_sink_resistance_max(self, maximum: float) -> None:
        """Validate and write sink resistance max.
        
        Underlying SCPI used here: ``SINK:RES:LIM:HIGH``."""

        high = self._device.ratings.resistance_max
        if high is None:
            self._device._unsupported("resistance nominal range unavailable")
        self._set("SINK:RES:LIM:HIGH", maximum, 0.0, float(high), "sink resistance maximum")
