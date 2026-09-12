"""DC terminal output/input switching."""

from __future__ import annotations

from .base import Subsystem


class OutputSubsystem(Subsystem):
    def on(self) -> None:
        self._write("OUTP ON")

    def off(self) -> None:
        self._write("OUTP OFF")

    @property
    def enabled(self) -> bool:
        return self._query_bool("OUTP?")

    def set(self, enabled: bool) -> None:
        self.on() if enabled else self.off()
