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
    def is_open(self) -> bool: ...

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def write(self, command: str) -> None: ...

    @abstractmethod
    def query(self, command: str) -> str: ...

    def __enter__(self) -> "SCPITransport":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
