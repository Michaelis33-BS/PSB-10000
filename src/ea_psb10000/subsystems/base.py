# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: Common plumbing shared by all high-level instrument subsystems.

"""Shared helpers for subsystem classes.

Subsystem objects intentionally delegate all transport access to ``PSB10000``.
That centralizes locking, logging, connection checks, alarm capture, and SCPI
error handling instead of duplicating those safety behaviors in every module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..device import PSB10000


class Subsystem:
    """Base class that routes typed subsystem operations through the parent driver."""

    def __init__(self, device: "PSB10000") -> None:
        """Store the parent driver; no communication occurs during construction."""

        self._device = device

    def _query(self, command: str) -> str:
        """Issue a raw query through the parent driver's locked transaction path."""

        return self._device.query_scpi(command)

    def _write(self, command: str, *, check_errors: Optional[bool] = None) -> None:
        """Issue a write through the parent driver, optionally overriding error checks."""

        self._device.write_scpi(command, check_errors=check_errors)

    def _query_float(self, command: str) -> float:
        """Query and parse a floating-point response using the driver's parser."""

        return self._device._query_float(command)

    def _query_int(self, command: str) -> int:
        """Query and parse an integer response using the driver's parser."""

        return self._device._query_int(command)

    def _query_bool(self, command: str) -> bool:
        """Query and parse an ON/OFF-style response using the driver's parser."""

        return self._device._query_bool(command)

    def _set_enum(self, command: str, value: Any, *, check_errors: Optional[bool] = None) -> None:
        """Write either an enum's ``.value`` or a caller-supplied token in uppercase."""

        token = getattr(value, "value", value)
        self._write(f"{command} {str(token).upper()}", check_errors=check_errors)
