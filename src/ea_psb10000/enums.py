"""Strongly typed values used by the EA-PSB 10000 driver."""

from __future__ import annotations

from enum import Enum


class _StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class OnOff(_StrEnum):
    ON = "ON"
    OFF = "OFF"


class EventAction(_StrEnum):
    NONE = "NONE"
    SIGNAL = "SIGN"
    WARNING = "WARN"
    ALARM = "ALARM"


class ControllerSpeed(_StrEnum):
    SLOW = "SLOW"
    NORMAL = "NORM"
    FAST = "FAST"


class RegulationMode(_StrEnum):
    CV = "CV"
    CC = "CC"
    CP = "CP"
    CR = "CR"
    UNKNOWN = "UNKNOWN"


class PowerFlow(_StrEnum):
    SOURCE = "SOURCE"
    SINK = "SINK"
    IDLE = "IDLE"


class RemoteOwner(_StrEnum):
    REMOTE = "REMOTE"
    NONE = "NONE"
    LOCAL = "LOCAL"
    UNKNOWN = "UNKNOWN"


class AfterState(_StrEnum):
    OFF = "OFF"
    AUTO = "AUTO"


class RestoreState(_StrEnum):
    OFF = "OFF"
    RESTORE = "AUTO"  # SCPI guide uses AUTO for HMI 'Restore'.


class ResistanceMode(_StrEnum):
    UIP = "UIP"
    UIR = "UIR"


class AnalogRange(_StrEnum):
    V5 = "5"
    V10 = "10"


class RemSBLevel(_StrEnum):
    NORMAL = "NORMAL"
    INVERTED = "INVERTED"


class RemSBAction(_StrEnum):
    DC_OFF = "OFF"
    DC_ON_OFF = "AUTO"


class MasterSlaveRole(_StrEnum):
    MASTER = "MASTER"
    SLAVE = "SLAVE"


class FunctionTarget(_StrEnum):
    VOLTAGE = "VOLT"
    CURRENT = "CURR"
    NONE = "NONE"


class FilterMode(_StrEnum):
    FIXED = "FIXED"
    MOVING = "MOVING"
    OFF = "OFF"
