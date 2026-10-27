# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: Shared base class/abstraction used by subsystems or transports.

"""Transport abstraction for SCPI communication."""

from __future__ import annotations

from abc import ABC, abstractmethod
from threading import RLock


class SCPITransport(ABC):
    """Abstract line-oriented SCPI transport.

    Implementations are responsible for framing commands and responses.  The
    lock guarantees one complete command/query transaction at a time.
    """

    def __init__(self) -> None:
        self._lock = RLock()

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """Return True when the concrete transport currently owns an open I/O handle."""
        raise NotImplementedError

    @abstractmethod
    def open(self) -> None:
        """Open the concrete connection. Implementations should be idempotent when already open."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Close the concrete connection and release underlying OS resources."""
        raise NotImplementedError

    @abstractmethod
    def write(self, command: str) -> None:
        """Transmit one SCPI command without waiting for a response."""
        raise NotImplementedError

    @abstractmethod
    def query(self, command: str) -> str:
        """Transmit one SCPI query and return exactly one line-oriented instrument response."""
        raise NotImplementedError

    def __enter__(self) -> "SCPITransport":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
