"""SCPI error queue handling and documented error-code catalog."""

from __future__ import annotations

import re

from .base import Subsystem
from ..exceptions import PSBSCPIError, SCPIErrorRecord
from ..util import parse_scpi_error

# EA 10000/20000-series Programming Guide error list.  Keep this centralized so
# applications and the hardware verifier can test every documented code without
# deliberately creating dangerous physical faults.
KNOWN_SCPI_ERRORS: dict[int, str] = {
    0: "No error",
    -100: "Command error",
    -102: "Syntax error",
    -108: "Parameter not allowed",
    -200: "Execution error",
    -201: "Invalid while in local",
    -220: "Parameter error",
    -221: "Settings conflict",
    -222: "Data out of range",
    -223: "Too much data",
    -224: "Illegal parameter value",
    -225: "Out of memory",
    -999: "Safety OVP",
}


class ErrorSubsystem(Subsystem):
    def next(self) -> SCPIErrorRecord:
        """Read/acknowledge the next queue entry."""
        return parse_scpi_error(self._query("SYSTem:ERRor?"))

    def next_explicit(self) -> SCPIErrorRecord:
        """Equivalent documented NEXT query, useful for command coverage tests."""
        return parse_scpi_error(self._query("SYSTem:ERRor:NEXT?"))

    def drain(self, *, max_errors: int = 16) -> list[SCPIErrorRecord]:
        result: list[SCPIErrorRecord] = []
        for _ in range(max_errors):
            record = self.next()
            if not record.is_error:
                break
            result.append(record)
        return result

    def all(self) -> list[SCPIErrorRecord]:
        """Use SYSTem:ERRor:ALL? and parse its up-to-five returned records."""
        raw = self._query("SYSTem:ERRor:ALL?").strip()
        if not raw:
            return []
        pattern = re.compile(r'(-?\d+)\s*,\s*"([^"]*)"')
        matches = pattern.findall(raw)
        if not matches:
            record = parse_scpi_error(raw)
            return [] if not record.is_error else [record]
        return [
            SCPIErrorRecord(int(code), msg, f'{code},"{msg}"')
            for code, msg in matches
            if int(code) != 0
        ]

    @staticmethod
    def known_errors() -> dict[int, str]:
        return dict(KNOWN_SCPI_ERRORS)

    def raise_if_any(self, *, command: str | None = None) -> None:
        errors = self.drain()
        if errors:
            raise PSBSCPIError(errors, command=command)
