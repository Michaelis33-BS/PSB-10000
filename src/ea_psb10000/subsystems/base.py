"""Shared subsystem helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..device import PSB10000


class Subsystem:
    def __init__(self, device: "PSB10000") -> None:
        self._device = device

    def _query(self, command: str) -> str:
        return self._device.query_scpi(command)

    def _write(self, command: str, *, check_errors: bool | None = None) -> None:
        self._device.write_scpi(command, check_errors=check_errors)

    def _query_float(self, command: str) -> float:
        return self._device._query_float(command)

    def _query_int(self, command: str) -> int:
        return self._device._query_int(command)

    def _query_bool(self, command: str) -> bool:
        return self._device._query_bool(command)

    def _set_enum(self, command: str, value: Any, *, check_errors: bool | None = None) -> None:
        token = getattr(value, "value", value)
        self._write(f"{command} {str(token).upper()}", check_errors=check_errors)
