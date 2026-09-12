"""User-defined supervision event controls."""

from __future__ import annotations

from .base import Subsystem
from ..enums import EventAction
from ..util import ensure_finite

_SOURCE_EVENTS = {"UVD", "UCD", "OVD", "OCD", "OPD"}
_SINK_EVENTS = {"UCD", "OCD", "OPD"}


class EventsSubsystem(Subsystem):
    def _prefix(self, name: str, sink: bool) -> str:
        key = name.upper()
        allowed = _SINK_EVENTS if sink else _SOURCE_EVENTS
        if key not in allowed:
            side = "sink" if sink else "source"
            raise ValueError(f"Unsupported {side} user event {name!r}; expected one of {sorted(allowed)}")
        return f"SYST:SINK:CONF:{key}" if sink else f"SYST:CONF:{key}"

    def set_threshold(self, name: str, value: float, *, sink: bool = False) -> None:
        value = ensure_finite(value, f"{name} threshold")
        if value < 0:
            raise ValueError("event thresholds must be non-negative")
        self._write(f"{self._prefix(name, sink)} {value:.12g}")

    def get_threshold(self, name: str, *, sink: bool = False) -> float:
        return self._query_float(f"{self._prefix(name, sink)}?")

    def set_action(self, name: str, action: EventAction | str, *, sink: bool = False) -> None:
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
        return self._query(f"{self._prefix(name, sink)}:ACT?").strip().upper()

    def configure(
        self,
        name: str,
        *,
        threshold: float | None = None,
        action: EventAction | str | None = None,
        sink: bool = False,
    ) -> None:
        if threshold is not None:
            self.set_threshold(name, threshold, sink=sink)
        if action is not None:
            self.set_action(name, action, sink=sink)
