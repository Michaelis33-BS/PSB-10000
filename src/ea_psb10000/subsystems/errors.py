"""SCPI error queue handling."""

from __future__ import annotations

import re

from .base import Subsystem
from ..exceptions import PSBSCPIError, SCPIErrorRecord
from ..util import parse_scpi_error


class ErrorSubsystem(Subsystem):
    def next(self) -> SCPIErrorRecord:
        """Read/acknowledge the next queue entry.

        EA documents that SYST:ERR? also acknowledges device-alarm status bits
        whose physical cause is no longer present. Capture status first when the
        alarm history matters.
        """
        return parse_scpi_error(self._query("SYST:ERR?"))

    def drain(self, *, max_errors: int = 16) -> list[SCPIErrorRecord]:
        result: list[SCPIErrorRecord] = []
        for _ in range(max_errors):
            record = self.next()
            if not record.is_error:
                break
            result.append(record)
        return result

    def all(self) -> list[SCPIErrorRecord]:
        """Use SYST:ERR:ALL? and parse its up-to-five returned records."""
        raw = self._query("SYST:ERR:ALL?").strip()
        if not raw:
            return []
        # Responses look like: -100,"Command error", -222,"Data out of range"
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

    def raise_if_any(self, *, command: str | None = None) -> None:
        errors = self.drain()
        if errors:
            raise PSBSCPIError(errors, command=command)
