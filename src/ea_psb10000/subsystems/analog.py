# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: Analog-interface reference, monitoring, signal routing, and REM-SB configuration.

"""Analog-interface configuration exposed by SCPI."""

from __future__ import annotations

from .base import Subsystem


class AnalogInterfaceSubsystem(Subsystem):
    """Configuration for the rear analog interface reference range, monitor routing, alarm pins, and REM-SB behavior."""

    _MONITOR_VALUES = {"DEFAULT", "EL", "PS", "ELPS", "PSEL", "COMBINATION"}
    _PIN6 = {"OT", "PF", "ALL"}
    _PIN14 = {"OVP", "OCP", "OPP", "OVP/OCP", "OVP/OPP", "OCP/OPP", "ALL"}
    _PIN15 = {"CONT", "POW"}

    @property
    def range_volts(self) -> int:
        """Read and return the current analog-interface reference range from the instrument or
        driver state.
        
        Underlying SCPI used here: ``SYSTem:CONFig:ANALog:REFerence?``."""

        return int(float(self._query("SYSTem:CONFig:ANALog:REFerence?")))

    @range_volts.setter
    def range_volts(self, value: int) -> None:
        """Validate and write the analog-interface reference range to the instrument.
        
        Underlying SCPI used here: ``SYSTem:CONFig:ANALog:REFerence {value}``,
        ``SYSTem:CONFig:ANALog:REFerence``."""

        if int(value) not in {5, 10}:
            raise ValueError("analog range must be 5 or 10 V")
        self._write(f"SYSTem:CONFig:ANALog:REFerence {int(value)}")

    @property
    def monitor_mode(self) -> str:
        """Read and return the current analog monitor routing mode from the instrument or
        driver state.
        
        Underlying SCPI used here: ``SYSTem:CONFig:ANALog:MONitor?``."""

        return self._query("SYSTem:CONFig:ANALog:MONitor?").strip().upper()

    @monitor_mode.setter
    def monitor_mode(self, value: str) -> None:
        """Validate and write the analog monitor routing mode to the instrument.
        
        Underlying SCPI used here: ``SYSTem:CONFig:ANALog:MONitor {value}``,
        ``SYSTem:CONFig:ANALog:MONitor``."""

        token = value.upper()
        if token not in self._MONITOR_VALUES:
            raise ValueError(f"monitor_mode must be one of {sorted(self._MONITOR_VALUES)}")
        self._write(f"SYSTem:CONFig:ANALog:MONitor {token}")

    def set_pin6(self, value: str) -> None:
        """Validate and write pin6.
        
        Underlying SCPI used here: ``SYSTem:CONFig:ANALog:PIN6 {value}``,
        ``SYSTem:CONFig:ANALog:PIN6``."""

        token = value.upper()
        if token not in self._PIN6:
            raise ValueError(f"pin6 must be one of {sorted(self._PIN6)}")
        self._write(f"SYSTem:CONFig:ANALog:PIN6 {token}")

    def set_pin14(self, value: str) -> None:
        """Validate and write pin14.
        
        Underlying SCPI used here: ``SYSTem:CONFig:ANALog:PIN14 {value}``,
        ``SYSTem:CONFig:ANALog:PIN14``."""

        token = value.upper()
        if token not in self._PIN14:
            raise ValueError(f"pin14 must be one of {sorted(self._PIN14)}")
        self._write(f"SYSTem:CONFig:ANALog:PIN14 {token}")

    def set_pin15(self, value: str) -> None:
        """Validate and write pin15.
        
        Underlying SCPI used here: ``SYSTem:CONFig:ANALog:PIN15 {value}``,
        ``SYSTem:CONFig:ANALog:PIN15``."""

        token = value.upper()
        if token not in self._PIN15:
            raise ValueError(f"pin15 must be one of {sorted(self._PIN15)}")
        self._write(f"SYSTem:CONFig:ANALog:PIN15 {token}")

    @property
    def rem_sb_level(self) -> str:
        """Read and return the current REM-SB logic level from the instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:CONFig:ANALog:REMSb:LEVel?``."""

        return self._query("SYSTem:CONFig:ANALog:REMSb:LEVel?").strip().upper()

    @rem_sb_level.setter
    def rem_sb_level(self, value: str) -> None:
        """Validate and write the REM-SB logic level to the instrument.
        
        Underlying SCPI used here: ``SYSTem:CONFig:ANALog:REMSb:LEVel {value}``,
        ``SYSTem:CONFig:ANALog:REMSb:LEVel``."""

        token = value.upper()
        if token not in {"NORMAL", "INVERTED"}:
            raise ValueError("REM-SB level must be NORMAL or INVERTED")
        self._write(f"SYSTem:CONFig:ANALog:REMSb:LEVel {token}")

    @property
    def rem_sb_action(self) -> str:
        """Read and return the current REM-SB action from the instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:CONFig:ANALog:REMSb:ACTion?``."""

        return self._query("SYSTem:CONFig:ANALog:REMSb:ACTion?").strip().upper()

    @rem_sb_action.setter
    def rem_sb_action(self, value: str) -> None:
        """Validate and write the REM-SB action to the instrument.
        
        Underlying SCPI used here: ``SYSTem:CONFig:ANALog:REMSb:ACTion {value}``,
        ``SYSTem:CONFig:ANALog:REMSb:ACTion``."""

        token = value.upper()
        aliases = {"DC OFF": "OFF", "DC_ON_OFF": "AUTO", "DC ON/OFF": "AUTO"}
        token = aliases.get(token, token)
        if token not in {"OFF", "AUTO"}:
            raise ValueError("REM-SB action must be OFF or AUTO")
        self._write(f"SYSTem:CONFig:ANALog:REMSb:ACTion {token}")
