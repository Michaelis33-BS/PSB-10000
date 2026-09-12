"""OVP/OCP/OPP controls."""

from __future__ import annotations

from .base import Subsystem
from ..models import ProtectionSnapshot
from ..util import ensure_range


class ProtectionSubsystem(Subsystem):
    @property
    def ovp(self) -> float:
        return self._query_float("VOLT:PROT?")

    @ovp.setter
    def ovp(self, value: float) -> None:
        value = ensure_range(value, 0.0, self._device.ratings.voltage * 1.10, "OVP")
        self._write(f"VOLT:PROT {value:.12g}")

    @property
    def source_ocp(self) -> float:
        return self._query_float("CURR:PROT?")

    @source_ocp.setter
    def source_ocp(self, value: float) -> None:
        value = ensure_range(value, 0.0, self._device.ratings.current * 1.10, "source OCP")
        self._write(f"CURR:PROT {value:.12g}")

    @property
    def source_opp(self) -> float:
        return self._query_float("POW:PROT?")

    @source_opp.setter
    def source_opp(self, value: float) -> None:
        value = ensure_range(value, 0.0, self._device.ratings.power * 1.10, "source OPP")
        self._write(f"POW:PROT {value:.12g}")

    @property
    def sink_ocp(self) -> float:
        return self._query_float("SINK:CURR:PROT?")

    @sink_ocp.setter
    def sink_ocp(self, value: float) -> None:
        value = ensure_range(value, 0.0, self._device.ratings.current * 1.10, "sink OCP")
        self._write(f"SINK:CURR:PROT {value:.12g}")

    @property
    def sink_opp(self) -> float:
        return self._query_float("SINK:POW:PROT?")

    @sink_opp.setter
    def sink_opp(self, value: float) -> None:
        value = ensure_range(value, 0.0, self._device.ratings.power * 1.10, "sink OPP")
        self._write(f"SINK:POW:PROT {value:.12g}")

    def snapshot(self) -> ProtectionSnapshot:
        return ProtectionSnapshot(
            ovp=self.ovp,
            source_ocp=self.source_ocp,
            source_opp=self.source_opp,
            sink_ocp=self.sink_ocp,
            sink_opp=self.sink_opp,
        )
