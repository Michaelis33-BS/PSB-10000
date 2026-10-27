# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: Programmable OVP/OCP/OPP protection thresholds and snapshots.

"""OVP/OCP/OPP controls."""

from __future__ import annotations

from .base import Subsystem
from ..models import ProtectionSnapshot
from ..util import ensure_range


class ProtectionSubsystem(Subsystem):
    """Programmable source/sink OVP/OCP/OPP thresholds with model-aware range validation."""

    @property
    def ovp(self) -> float:
        """Read and return the current OVP threshold from the instrument or driver state.
        
        Underlying SCPI used here: ``VOLT:PROT?``."""

        return self._query_float("VOLT:PROT?")

    @ovp.setter
    def ovp(self, value: float) -> None:
        """Validate and write the OVP threshold to the instrument.
        
        Underlying SCPI used here: ``VOLT:PROT {value}``, ``VOLT:PROT``."""

        value = ensure_range(value, 0.0, self._device.ratings.voltage * 1.10, "OVP")
        self._write(f"VOLT:PROT {value:.12g}")

    @property
    def source_ocp(self) -> float:
        """Read and return the current source OCP threshold from the instrument or driver
        state.
        
        Underlying SCPI used here: ``CURR:PROT?``."""

        return self._query_float("CURR:PROT?")

    @source_ocp.setter
    def source_ocp(self, value: float) -> None:
        """Validate and write the source OCP threshold to the instrument.
        
        Underlying SCPI used here: ``CURR:PROT {value}``, ``CURR:PROT``."""

        value = ensure_range(value, 0.0, self._device.ratings.current * 1.10, "source OCP")
        self._write(f"CURR:PROT {value:.12g}")

    @property
    def source_opp(self) -> float:
        """Read and return the current source OPP threshold from the instrument or driver
        state.
        
        Underlying SCPI used here: ``POW:PROT?``."""

        return self._query_float("POW:PROT?")

    @source_opp.setter
    def source_opp(self, value: float) -> None:
        """Validate and write the source OPP threshold to the instrument.
        
        Underlying SCPI used here: ``POW:PROT {value}``, ``POW:PROT``."""

        value = ensure_range(value, 0.0, self._device.ratings.power * 1.10, "source OPP")
        self._write(f"POW:PROT {value:.12g}")

    @property
    def sink_ocp(self) -> float:
        """Read and return the current sink OCP threshold from the instrument or driver state.
        
        Underlying SCPI used here: ``SINK:CURR:PROT?``."""

        return self._query_float("SINK:CURR:PROT?")

    @sink_ocp.setter
    def sink_ocp(self, value: float) -> None:
        """Validate and write the sink OCP threshold to the instrument.
        
        Underlying SCPI used here: ``SINK:CURR:PROT {value}``, ``SINK:CURR:PROT``."""

        value = ensure_range(value, 0.0, self._device.ratings.current * 1.10, "sink OCP")
        self._write(f"SINK:CURR:PROT {value:.12g}")

    @property
    def sink_opp(self) -> float:
        """Read and return the current sink OPP threshold from the instrument or driver state.
        
        Underlying SCPI used here: ``SINK:POW:PROT?``."""

        return self._query_float("SINK:POW:PROT?")

    @sink_opp.setter
    def sink_opp(self, value: float) -> None:
        """Validate and write the sink OPP threshold to the instrument.
        
        Underlying SCPI used here: ``SINK:POW:PROT {value}``, ``SINK:POW:PROT``."""

        value = ensure_range(value, 0.0, self._device.ratings.power * 1.10, "sink OPP")
        self._write(f"SINK:POW:PROT {value:.12g}")

    def snapshot(self) -> ProtectionSnapshot:
        """Read the related settings and return an immutable snapshot object."""

        return ProtectionSnapshot(
            ovp=self.ovp,
            source_ocp=self.source_ocp,
            source_opp=self.source_opp,
            sink_ocp=self.sink_ocp,
            sink_opp=self.sink_opp,
        )
