# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: DC terminal ON/OFF control and readback.

"""DC terminal output/input switching."""

from __future__ import annotations

from .base import Subsystem


class OutputSubsystem(Subsystem):
    """DC terminal switching commands. Merely constructing or connecting the driver never calls these methods."""

    def on(self) -> None:
        """Switch the DC terminal ON using an explicit SCPI write."""

        self._write("OUTP ON")

    def off(self) -> None:
        """Switch the DC terminal OFF using an explicit SCPI write."""

        self._write("OUTP OFF")

    @property
    def enabled(self) -> bool:
        """Read and return the current enabled state from the instrument or driver state.
        
        Underlying SCPI used here: ``OUTP?``."""

        return self._query_bool("OUTP?")

    def set(self, enabled: bool) -> None:
        """Perform the set operation."""

        self.on() if enabled else self.off()
