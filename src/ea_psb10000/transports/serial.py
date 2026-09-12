"""Serial/USB-serial SCPI transport."""

from __future__ import annotations

from threading import RLock
from typing import Any

from .base import SCPITransport
from ..exceptions import PSBConnectionError, PSBTimeoutError


class SerialTransport(SCPITransport):
    def __init__(
        self,
        port: str,
        *,
        baudrate: int = 115200,
        timeout: float = 2.0,
        write_timeout: float = 2.0,
        terminator: bytes = b"\n",
    ) -> None:
        super().__init__()
        self.port = port
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self.write_timeout = float(write_timeout)
        self.terminator = terminator
        self._serial: Any | None = None
        self._lock = RLock()

    @property
    def is_open(self) -> bool:
        return bool(self._serial is not None and self._serial.is_open)

    def open(self) -> None:
        with self._lock:
            if self.is_open:
                return
            try:
                import serial  # type: ignore
            except ImportError as exc:
                raise PSBConnectionError(
                    "pyserial is required for SerialTransport; install ea-psb10000[serial]"
                ) from exc
            try:
                self._serial = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=self.timeout,
                    write_timeout=self.write_timeout,
                )
            except Exception as exc:
                raise PSBConnectionError(f"Could not open serial port {self.port!r}: {exc}") from exc

    def close(self) -> None:
        with self._lock:
            ser, self._serial = self._serial, None
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass

    def _ser(self):
        if not self.is_open:
            raise PSBConnectionError("Serial transport is not open")
        return self._serial

    def write(self, command: str) -> None:
        with self._lock:
            data = command.rstrip("\r\n").encode("ascii") + self.terminator
            try:
                self._ser().write(data)
                self._ser().flush()
            except Exception as exc:
                name = exc.__class__.__name__.lower()
                if "timeout" in name:
                    raise PSBTimeoutError(f"Timed out writing {command!r}") from exc
                raise PSBConnectionError(f"Serial write failed: {exc}") from exc

    def query(self, command: str) -> str:
        with self._lock:
            self.write(command)
            try:
                data = self._ser().read_until(self.terminator)
            except Exception as exc:
                raise PSBConnectionError(f"Serial read failed: {exc}") from exc
            if not data or not data.endswith(self.terminator):
                raise PSBTimeoutError(f"Timed out waiting for response to {command!r}")
            return data.rstrip(b"\r\n").decode("ascii", errors="replace").strip()
