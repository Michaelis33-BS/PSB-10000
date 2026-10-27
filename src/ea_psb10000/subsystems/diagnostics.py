# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: Lifetime/runtime counters and source/sink energy diagnostics.

"""Read-only device counters and accumulated energy information."""

from __future__ import annotations

from .base import Subsystem


class DiagnosticsSubsystem(Subsystem):
    """Read-only device lifetime, DC-terminal runtime, charge, and energy counters."""

    @property
    def device_class(self) -> int:
        """Read and return the current device class from the instrument or driver state.
        
        Underlying SCPI used here: ``SYST:DEV:CLASS?``."""

        return self._query_int("SYST:DEV:CLASS?")

    @property
    def operation_hours(self) -> float:
        """Read and return the current total powered operation hours from the instrument or
        driver state.
        
        Underlying SCPI used here: ``DIAG:INF:DEV:OTIM?``."""

        return self._query_float("DIAG:INF:DEV:OTIM?")

    @property
    def dc_on_hours(self) -> float:
        """Read and return the current DC-terminal ON hours from the instrument or driver
        state.
        
        Underlying SCPI used here: ``DIAG:INF:DEV:ONT?``."""

        return self._query_float("DIAG:INF:DEV:ONT?")

    @property
    def dc_off_hours(self) -> float:
        """Read and return the current DC-terminal OFF hours from the instrument or driver
        state.
        
        Underlying SCPI used here: ``DIAG:INF:DEV:OFFT?``."""

        return self._query_float("DIAG:INF:DEV:OFFT?")

    @property
    def source_amp_hours(self) -> float:
        """Read and return the current source amp-hours from the instrument or driver state.
        
        Underlying SCPI used here: ``FETC:AHO?``."""

        return self._query_float("FETC:AHO?")

    @property
    def source_kilowatt_hours(self) -> float:
        """Read and return the current source kilowatt-hours from the instrument or driver
        state.
        
        Underlying SCPI used here: ``FETC:WHO?``."""

        return self._query_float("FETC:WHO?")

    @property
    def sink_amp_hours(self) -> float:
        """Read and return the current sink amp-hours from the instrument or driver state.
        
        Underlying SCPI used here: ``FETC:SINK:AHO?``."""

        return self._query_float("FETC:SINK:AHO?")

    @property
    def sink_kilowatt_hours(self) -> float:
        """Read and return the current sink kilowatt-hours from the instrument or driver state.
        
        Underlying SCPI used here: ``FETC:SINK:WHO?``."""

        return self._query_float("FETC:SINK:WHO?")
