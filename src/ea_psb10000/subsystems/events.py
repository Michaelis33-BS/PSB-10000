# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: User supervision thresholds/actions such as UVD, OVD, UCD, OCD, and OPD.

"""User-defined supervision event controls."""

from __future__ import annotations

from typing import Optional, Union

from .base import Subsystem
from ..enums import EventAction
from ..util import ensure_finite

_SOURCE_EVENTS = {"UVD", "UCD", "OVD", "OCD", "OPD"}
_SINK_EVENTS = {"UCD", "OCD", "OPD"}


class EventsSubsystem(Subsystem):
    """User supervision event thresholds and actions for source and sink operation."""

    def _prefix(self, name: str, sink: bool) -> str:
        key = name.upper()
        allowed = _SINK_EVENTS if sink else _SOURCE_EVENTS
        if key not in allowed:
            side = "sink" if sink else "source"
            raise ValueError(f"Unsupported {side} user event {name!r}; expected one of {sorted(allowed)}")
        return f"SYST:SINK:CONF:{key}" if sink else f"SYST:CONF:{key}"

    def set_threshold(self, name: str, value: float, *, sink: bool = False) -> None:
        """Validate and write threshold."""

        value = ensure_finite(value, f"{name} threshold")
        if value < 0:
            raise ValueError("event thresholds must be non-negative")
        self._write(f"{self._prefix(name, sink)} {value:.12g}")

    def get_threshold(self, name: str, *, sink: bool = False) -> float:
        """Read and return threshold."""

        return self._query_float(f"{self._prefix(name, sink)}?")

    def set_action(self, name: str, action: Union[EventAction, str], *, sink: bool = False) -> None:
        """Validate and write action."""

        token = action.value if isinstance(action, EventAction) else str(action).upper()
        aliases = {"SIGNAL": "SIGN", "WARNING": "WARN"}
        token = aliases.get(token, token)
        if token not in {"NONE", "SIGN", "WARN", "ALARM", "SIGNAL", "WARNING"}:
            raise ValueError(f"Invalid event action {action!r}")
        # The long forms documented by EA are accepted by the instrument; use them
        # for readability where applicable.
        wire = {"SIGN": "SIGNAL", "WARN": "WARNING"}.get(token, token)
        self._write(f"{self._prefix(name, sink)}:ACT {wire}")

    def get_action(self, name: str, *, sink: bool = False) -> str:
        """Read and return action."""

        return self._query(f"{self._prefix(name, sink)}:ACT?").strip().upper()

    def configure(
        self,
        name: str,
        *,
        threshold: Optional[float] = None,
        action: Optional[Union[EventAction, str]] = None,
        sink: bool = False,
    ) -> None:
        """Validate and configure configure using only the values supplied by the caller."""

        if threshold is not None:
            self.set_threshold(name, threshold, sink=sink)
        if action is not None:
            self.set_action(name, action, sink=sink)
