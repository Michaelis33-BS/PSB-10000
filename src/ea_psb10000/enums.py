# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: Validated symbolic values used throughout the public driver API.

"""Enumerations used by the EA-PSB 10000 driver.

The instrument represents many settings as short SCPI strings.  Exposing those
values as enums gives application code readable names while still preserving the
exact token that must be sent to the supply.  Every enum derives from ``str`` so
it remains convenient to log, serialize, compare, or pass through helper code.
"""

from __future__ import annotations

from enum import Enum


class _StrEnum(str, Enum):
    """Small Python-3.8-compatible replacement for the newer stdlib StrEnum."""

    def __str__(self) -> str:
        """Return the SCPI token instead of the default ``EnumClass.MEMBER`` text."""

        return self.value


class OnOff(_StrEnum):
    """Generic ON/OFF state used by SCPI boolean-style settings."""

    ON = "ON"
    OFF = "OFF"


class EventAction(_StrEnum):
    """Action taken when a user-defined supervision threshold is crossed.

    ``NONE`` disables the reaction, ``SIGNAL`` only signals the condition,
    ``WARNING`` reports a warning, and ``ALARM`` may switch the DC terminal off.
    """

    NONE = "NONE"
    SIGNAL = "SIGN"
    WARNING = "WARN"
    ALARM = "ALARM"


class ControllerSpeed(_StrEnum):
    """Voltage-controller dynamic response selection."""

    SLOW = "SLOW"
    NORMAL = "NORM"
    FAST = "FAST"


class RegulationMode(_StrEnum):
    """Regulation mode decoded from the operation-status register."""

    CV = "CV"
    CC = "CC"
    CP = "CP"
    CR = "CR"
    UNKNOWN = "UNKNOWN"


class PowerFlow(_StrEnum):
    """Direction of DC power flow inferred from status and/or measurements."""

    SOURCE = "SOURCE"
    SINK = "SINK"
    IDLE = "IDLE"


class RemoteOwner(_StrEnum):
    """Current control ownership reported by the instrument."""

    REMOTE = "REMOTE"
    NONE = "NONE"
    LOCAL = "LOCAL"
    UNKNOWN = "UNKNOWN"


class AfterState(_StrEnum):
    """Common post-event behavior for settings that support OFF or AUTO."""

    OFF = "OFF"
    AUTO = "AUTO"


class RestoreState(_StrEnum):
    """Power-on output behavior.

    The HMI describes ``AUTO`` as *Restore*; the SCPI programming interface uses
    the token ``AUTO``.
    """

    OFF = "OFF"
    RESTORE = "AUTO"


class ResistanceMode(_StrEnum):
    """Main setpoint mode: U/I/P or U/I/R."""

    UIP = "UIP"
    UIR = "UIR"


class AnalogRange(_StrEnum):
    """Analog-interface reference/full-scale voltage range."""

    V5 = "5"
    V10 = "10"


class RemSBLevel(_StrEnum):
    """Polarity interpretation for the analog-interface REM-SB input."""

    NORMAL = "NORMAL"
    INVERTED = "INVERTED"


class RemSBAction(_StrEnum):
    """Action allowed from REM-SB outside analog remote control."""

    DC_OFF = "OFF"
    DC_ON_OFF = "AUTO"


class MasterSlaveRole(_StrEnum):
    """Role of the unit in an EA master/slave system."""

    MASTER = "MASTER"
    SLAVE = "SLAVE"


class FunctionTarget(_StrEnum):
    """Setpoint controlled by the internal arbitrary function generator."""

    VOLTAGE = "VOLT"
    CURRENT = "CURR"
    NONE = "NONE"


class FilterMode(_StrEnum):
    """Actual-value filter mode documented by newer firmware.

    These values are provided for application-side validation.  The exact SCPI
    spelling for this newer feature must be registered through
    ``psb.extensions`` before it can be used.
    """

    FIXED = "FIXED"
    MOVING = "MOVING"
    OFF = "OFF"
