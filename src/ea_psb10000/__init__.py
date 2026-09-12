"""Reusable Python driver for EA-PSB 10000 series bidirectional DC supplies."""

from .device import PSB10000
from .enums import (
    AfterState,
    ControllerSpeed,
    EventAction,
    MasterSlaveRole,
    PowerFlow,
    RegulationMode,
    RemoteOwner,
    ResistanceMode,
)
from .exceptions import (
    PSBAlarmError,
    PSBConnectionError,
    PSBError,
    PSBProtocolError,
    PSBRemoteControlError,
    PSBSCPIError,
    PSBTimeoutError,
    PSBUnsupportedFeatureError,
    PSBValidationError,
    SCPIErrorRecord,
)
from .models import (
    ArbitrarySequence,
    DeviceInfo,
    DeviceRatings,
    LimitSnapshot,
    Measurements,
    ProtectionSnapshot,
    StatusSnapshot,
)
from .transports import EthernetTransport, SCPITransport, SerialTransport

__version__ = "0.1.0"

__all__ = [
    "PSB10000",
    "EthernetTransport",
    "SerialTransport",
    "SCPITransport",
    "DeviceInfo",
    "DeviceRatings",
    "Measurements",
    "LimitSnapshot",
    "ProtectionSnapshot",
    "StatusSnapshot",
    "ArbitrarySequence",
    "EventAction",
    "ControllerSpeed",
    "AfterState",
    "MasterSlaveRole",
    "PowerFlow",
    "RegulationMode",
    "RemoteOwner",
    "ResistanceMode",
    "PSBError",
    "PSBConnectionError",
    "PSBTimeoutError",
    "PSBProtocolError",
    "PSBValidationError",
    "PSBRemoteControlError",
    "PSBUnsupportedFeatureError",
    "PSBSCPIError",
    "PSBAlarmError",
    "SCPIErrorRecord",
]
