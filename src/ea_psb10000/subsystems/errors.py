# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: SCPI error queue access and the documented error-code catalog.

"""SCPI error queue handling and documented error-code catalog."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .base import Subsystem
from ..exceptions import PSBSCPIError, SCPIErrorRecord
from ..util import parse_scpi_error

# EA 10000/20000-series Programming Guide error list.  Keep this centralized so
# applications and the hardware verifier can test every documented code without
# deliberately creating dangerous physical faults.
KNOWN_SCPI_ERRORS: Dict[int, str] = {
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
    """Explicit access to the SCPI error queue. Reading this queue can acknowledge cleared alarms on EA instruments."""

    def next(self) -> SCPIErrorRecord:
        """Read/acknowledge the next queue entry."""
        return parse_scpi_error(self._query("SYSTem:ERRor?"))

    def next_explicit(self) -> SCPIErrorRecord:
        """Equivalent documented NEXT query, useful for command coverage tests."""
        return parse_scpi_error(self._query("SYSTem:ERRor:NEXT?"))

    def drain(self, *, max_errors: int = 16) -> List[SCPIErrorRecord]:
        """Read successive SCPI error records until code 0 is returned or max_errors is
        reached. This acknowledges/consumes queue entries."""

        result: List[SCPIErrorRecord] = []
        for _ in range(max_errors):
            record = self.next()
            if not record.is_error:
                break
            result.append(record)
        return result

    def all(self) -> List[SCPIErrorRecord]:
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
    def known_errors() -> Dict[int, str]:
        """Return a copy of the driver catalog of documented EA SCPI error codes."""

        return dict(KNOWN_SCPI_ERRORS)

    def raise_if_any(self, *, command: Optional[str] = None) -> None:
        """Drain the SCPI error queue and raise PSBSCPIError if any queued errors are present."""

        errors = self.drain()
        if errors:
            raise PSBSCPIError(errors, command=command)
