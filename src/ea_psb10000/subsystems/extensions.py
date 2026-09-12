"""2025 HMI features whose current SCPI spellings are not in the supplied manual.

The uploaded 2025 user manual confirms these settings exist, but it explicitly
places digital command syntax in a separate Programming Guide ModBus & SCPI.
The public programming guide we could verify predates these firmware additions.
This subsystem therefore never guesses a command name.  It offers a controlled
registration mechanism so a site can add a command from its exact programming
guide/firmware revision without editing the driver core.
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Subsystem
from ..exceptions import PSBUnsupportedFeatureError
from ..util import ensure_range


@dataclass(slots=True, frozen=True)
class SettingCommand:
    set_command: str
    query_command: str | None = None


class FirmwareExtensionsSubsystem(Subsystem):
    def __init__(self, device):
        super().__init__(device)
        self._commands: dict[str, SettingCommand] = {}

    def register(self, name: str, *, set_command: str, query_command: str | None = None) -> None:
        self._commands[name.lower()] = SettingCommand(set_command, query_command)

    def _cmd(self, name: str) -> SettingCommand:
        try:
            return self._commands[name.lower()]
        except KeyError as exc:
            raise PSBUnsupportedFeatureError(
                f"No verified SCPI command is registered for {name!r}. "
                "The 2025 user manual documents the feature but not its digital command syntax."
            ) from exc

    def set_raw_registered(self, name: str, value: str | int | float | bool) -> None:
        cmd = self._cmd(name)
        if isinstance(value, bool):
            token = "ON" if value else "OFF"
        else:
            token = str(value)
        self._write(f"{cmd.set_command} {token}")

    def query_registered(self, name: str) -> str:
        cmd = self._cmd(name)
        if not cmd.query_command:
            raise PSBUnsupportedFeatureError(f"No query command registered for {name!r}")
        return self._query(cmd.query_command)

    def configure_fast_discharge(self, *, enabled: bool, voltage: float | None = None, current: float | None = None, duration_ms: int | None = None) -> None:
        if voltage is not None:
            ensure_range(voltage, 0.0, self._device.ratings.voltage * 1.02, "fast-discharge voltage")
            self.set_raw_registered("fast_discharge_voltage", voltage)
        if current is not None:
            ensure_range(current, 0.0, self._device.ratings.current * 1.02, "fast-discharge current")
            self.set_raw_registered("fast_discharge_current", current)
        if duration_ms is not None:
            ensure_range(duration_ms, 0.0, 5000.0, "fast-discharge duration ms")
            self.set_raw_registered("fast_discharge_duration", int(duration_ms))
        self.set_raw_registered("fast_discharge", enabled)

    def configure_actual_value_filter(self, *, mode: str, buffer_size: int) -> None:
        mode = mode.upper()
        if mode not in {"FIXED", "MOVING", "OFF"}:
            raise ValueError("filter mode must be FIXED, MOVING, or OFF")
        ensure_range(buffer_size, 2, 24, "actual-value filter buffer size")
        self.set_raw_registered("actual_value_filter_mode", mode)
        self.set_raw_registered("actual_value_filter_buffer_size", int(buffer_size))

    def set_stby_zero_stabilization(self, enabled: bool) -> None:
        self.set_raw_registered("stby_zero_stabilization", enabled)
