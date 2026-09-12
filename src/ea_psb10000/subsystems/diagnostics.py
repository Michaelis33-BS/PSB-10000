"""Read-only device counters and accumulated energy information."""

from __future__ import annotations

from .base import Subsystem


class DiagnosticsSubsystem(Subsystem):
    @property
    def device_class(self) -> int:
        return self._query_int("SYST:DEV:CLASS?")

    @property
    def operation_hours(self) -> float:
        return self._query_float("DIAG:INF:DEV:OTIM?")

    @property
    def dc_on_hours(self) -> float:
        return self._query_float("DIAG:INF:DEV:ONT?")

    @property
    def dc_off_hours(self) -> float:
        return self._query_float("DIAG:INF:DEV:OFFT?")

    @property
    def source_amp_hours(self) -> float:
        return self._query_float("FETC:AHO?")

    @property
    def source_kilowatt_hours(self) -> float:
        return self._query_float("FETC:WHO?")

    @property
    def sink_amp_hours(self) -> float:
        return self._query_float("FETC:SINK:AHO?")

    @property
    def sink_kilowatt_hours(self) -> float:
        return self._query_float("FETC:SINK:WHO?")
