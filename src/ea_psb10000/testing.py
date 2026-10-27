# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: Deterministic scripted transport for unit tests that do not require connected hardware.

"""Small scripted transport useful for unit-testing software built on this driver."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable
from typing import Deque, Dict, List, Optional, Union

from .transports.base import SCPITransport
from .exceptions import PSBConnectionError


class ScriptedTransport(SCPITransport):
    """A deterministic in-memory SCPI transport.

    ``responses`` maps a query command to either one string or an iterable of
    strings consumed in order. Unmapped status/error queries receive safe
    defaults; all other unmapped queries raise KeyError.
    """

    def __init__(self, responses: Optional[Dict[str, Union[str, Iterable[str]]]] = None) -> None:
        super().__init__()
        self._open = False
        self.commands: List[str] = []
        self._responses: Dict[str, Deque[str]] = {}
        for key, value in (responses or {}).items():
            if isinstance(value, str):
                self._responses[key] = deque([value])
            else:
                self._responses[key] = deque(value)
        self.defaults = {
            'SYST:ERR?': '0,"No error"',
            'STAT:QUES:COND?': '0',
            'STAT:SEC:QUES:COND?': '0',
            'STAT:OPER:COND?': '0',
            '*STB?': '0',
            'OUTP?': 'OFF',
            'SYST:LOCK:OWNER?': 'NONE',
        }

    @property
    def is_open(self) -> bool:
        """Read and return the current is open from the instrument or driver state."""

        return self._open

    def open(self) -> None:
        """Perform the open operation."""

        self._open = True

    def close(self) -> None:
        """Perform the close operation."""

        self._open = False

    def write(self, command: str) -> None:
        """Perform the write operation."""

        if not self._open:
            raise PSBConnectionError("scripted transport is closed")
        self.commands.append(command)

    def query(self, command: str) -> str:
        """Perform the query operation."""

        if not self._open:
            raise PSBConnectionError("scripted transport is closed")
        self.commands.append(command)
        queue = self._responses.get(command)
        if queue:
            value = queue[0]
            if len(queue) > 1:
                queue.popleft()
            return value
        if command in self.defaults:
            return self.defaults[command]
        raise KeyError(f"No scripted response for {command!r}")
