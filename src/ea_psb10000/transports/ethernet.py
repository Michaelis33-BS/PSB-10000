"""Raw TCP/IP SCPI transport for the built-in EA Ethernet interface."""

from __future__ import annotations

import socket
from threading import RLock

from .base import SCPITransport
from ..exceptions import PSBConnectionError, PSBTimeoutError


class EthernetTransport(SCPITransport):
    """Line-oriented SCPI over TCP.

    The PSB 10000 user manual lists TCP port 5025 as the default.  Write
    commands are deliberately never auto-retried because replaying a state-
    changing command after a broken connection is not provably safe.
    """

    def __init__(
        self,
        host: str,
        port: int = 5025,
        *,
        timeout: float = 2.0,
        connect_timeout: float = 5.0,
        terminator: bytes = b"\n",
        max_response_bytes: int = 1_048_576,
        tcp_keepalive: bool = True,
    ) -> None:
        super().__init__()
        self.host = host
        self.port = int(port)
        self.timeout = float(timeout)
        self.connect_timeout = float(connect_timeout)
        self.terminator = terminator
        self.max_response_bytes = int(max_response_bytes)
        self.tcp_keepalive = bool(tcp_keepalive)
        self._sock: socket.socket | None = None
        self._rx = bytearray()
        self._lock = RLock()

    @property
    def is_open(self) -> bool:
        return self._sock is not None

    def open(self) -> None:
        with self._lock:
            if self._sock is not None:
                return
            try:
                sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
                sock.settimeout(self.timeout)
                if self.tcp_keepalive:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                self._sock = sock
                self._rx.clear()
            except socket.timeout as exc:
                raise PSBTimeoutError(f"Timed out connecting to {self.host}:{self.port}") from exc
            except OSError as exc:
                raise PSBConnectionError(f"Could not connect to {self.host}:{self.port}: {exc}") from exc

    def close(self) -> None:
        with self._lock:
            sock, self._sock = self._sock, None
            self._rx.clear()
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    sock.close()
                except OSError:
                    pass

    def _socket(self) -> socket.socket:
        if self._sock is None:
            raise PSBConnectionError("Transport is not connected")
        return self._sock

    def _send(self, command: str) -> None:
        data = command.rstrip("\r\n").encode("ascii") + self.terminator
        try:
            self._socket().sendall(data)
        except socket.timeout as exc:
            self.close()
            raise PSBTimeoutError(f"Timed out sending SCPI command {command!r}") from exc
        except OSError as exc:
            self.close()
            raise PSBConnectionError(f"Connection lost sending {command!r}: {exc}") from exc

    def _readline(self) -> str:
        sock = self._socket()
        while True:
            pos = self._rx.find(self.terminator)
            if pos >= 0:
                line = bytes(self._rx[:pos])
                del self._rx[: pos + len(self.terminator)]
                return line.rstrip(b"\r").decode("ascii", errors="replace").strip()
            if len(self._rx) > self.max_response_bytes:
                self.close()
                raise PSBConnectionError("SCPI response exceeded configured maximum size")
            try:
                chunk = sock.recv(4096)
            except socket.timeout as exc:
                raise PSBTimeoutError("Timed out waiting for SCPI response") from exc
            except OSError as exc:
                self.close()
                raise PSBConnectionError(f"Connection lost while receiving: {exc}") from exc
            if not chunk:
                self.close()
                raise PSBConnectionError("Instrument closed the TCP connection")
            self._rx.extend(chunk)

    def write(self, command: str) -> None:
        with self._lock:
            self._send(command)

    def query(self, command: str) -> str:
        with self._lock:
            self._send(command)
            return self._readline()
