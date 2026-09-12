"""Exception hierarchy for the EA-PSB 10000 driver."""

from __future__ import annotations

from dataclasses import dataclass


class PSBError(Exception):
    """Base exception for all driver errors."""


class PSBConnectionError(PSBError):
    """The transport could not connect or the connection was lost."""


class PSBTimeoutError(PSBConnectionError):
    """A transport operation timed out."""


class PSBProtocolError(PSBError):
    """A malformed or unexpected protocol response was received."""


class PSBValidationError(PSBError, ValueError):
    """A requested value is invalid before it is sent to the instrument."""


class PSBRemoteControlError(PSBError):
    """Remote ownership could not be acquired or is required for an operation."""


class PSBUnsupportedFeatureError(PSBError, NotImplementedError):
    """The requested feature is not supported by this model/firmware/driver mapping."""


@dataclass(slots=True, frozen=True)
class SCPIErrorRecord:
    """One entry returned by the instrument SCPI error queue."""

    code: int
    message: str
    raw: str

    @property
    def is_error(self) -> bool:
        return self.code != 0


class PSBSCPIError(PSBProtocolError):
    """The instrument reported one or more SCPI/device errors."""

    def __init__(self, errors: list[SCPIErrorRecord], *, command: str | None = None):
        self.errors = errors
        self.command = command
        detail = "; ".join(f"{e.code}: {e.message}" for e in errors) or "unknown SCPI error"
        prefix = f"after {command!r}: " if command else ""
        super().__init__(f"Instrument error {prefix}{detail}")


class PSBAlarmError(PSBError):
    """One or more active device alarms were detected."""

    def __init__(self, alarms: tuple[str, ...], *, questionable: int, secondary: int = 0):
        self.alarms = alarms
        self.questionable = questionable
        self.secondary = secondary
        names = ", ".join(alarms) if alarms else "unknown alarm"
        super().__init__(
            f"Active PSB alarm(s): {names} "
            f"(QUESTIONABLE=0x{questionable:04X}, SECONDARY=0x{secondary:04X})"
        )
