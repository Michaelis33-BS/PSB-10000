"""Analog-interface configuration exposed by SCPI."""

from __future__ import annotations

from .base import Subsystem


class AnalogInterfaceSubsystem(Subsystem):
    _MONITOR_VALUES = {"DEFAULT", "EL", "PS", "ELPS", "PSEL", "COMBINATION"}
    _PIN6 = {"OT", "PF", "ALL"}
    _PIN14 = {"OVP", "OCP", "OPP", "OVP/OCP", "OVP/OPP", "OCP/OPP", "ALL"}
    _PIN15 = {"CONT", "POW"}

    @property
    def range_volts(self) -> int:
        return int(float(self._query("SYSTem:CONFig:ANALog:REFerence?")))

    @range_volts.setter
    def range_volts(self, value: int) -> None:
        if int(value) not in {5, 10}:
            raise ValueError("analog range must be 5 or 10 V")
        self._write(f"SYSTem:CONFig:ANALog:REFerence {int(value)}")

    @property
    def monitor_mode(self) -> str:
        return self._query("SYSTem:CONFig:ANALog:MONitor?").strip().upper()

    @monitor_mode.setter
    def monitor_mode(self, value: str) -> None:
        token = value.upper()
        if token not in self._MONITOR_VALUES:
            raise ValueError(f"monitor_mode must be one of {sorted(self._MONITOR_VALUES)}")
        self._write(f"SYSTem:CONFig:ANALog:MONitor {token}")

    def set_pin6(self, value: str) -> None:
        token = value.upper()
        if token not in self._PIN6:
            raise ValueError(f"pin6 must be one of {sorted(self._PIN6)}")
        self._write(f"SYSTem:CONFig:ANALog:PIN6 {token}")

    def set_pin14(self, value: str) -> None:
        token = value.upper()
        if token not in self._PIN14:
            raise ValueError(f"pin14 must be one of {sorted(self._PIN14)}")
        self._write(f"SYSTem:CONFig:ANALog:PIN14 {token}")

    def set_pin15(self, value: str) -> None:
        token = value.upper()
        if token not in self._PIN15:
            raise ValueError(f"pin15 must be one of {sorted(self._PIN15)}")
        self._write(f"SYSTem:CONFig:ANALog:PIN15 {token}")

    @property
    def rem_sb_level(self) -> str:
        return self._query("SYSTem:CONFig:ANALog:REMSb:LEVel?").strip().upper()

    @rem_sb_level.setter
    def rem_sb_level(self, value: str) -> None:
        token = value.upper()
        if token not in {"NORMAL", "INVERTED"}:
            raise ValueError("REM-SB level must be NORMAL or INVERTED")
        self._write(f"SYSTem:CONFig:ANALog:REMSb:LEVel {token}")

    @property
    def rem_sb_action(self) -> str:
        return self._query("SYSTem:CONFig:ANALog:REMSb:ACTion?").strip().upper()

    @rem_sb_action.setter
    def rem_sb_action(self, value: str) -> None:
        token = value.upper()
        aliases = {"DC OFF": "OFF", "DC_ON_OFF": "AUTO", "DC ON/OFF": "AUTO"}
        token = aliases.get(token, token)
        if token not in {"OFF", "AUTO"}:
            raise ValueError("REM-SB action must be OFF or AUTO")
        self._write(f"SYSTem:CONFig:ANALog:REMSb:ACTion {token}")
