# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: Device-wide configuration, reset/status-clear behavior, controller speed, and SEMI F47.

"""Device-wide configuration and control."""

from __future__ import annotations

from typing import Union

from .base import Subsystem
from ..enums import AfterState, ControllerSpeed, ResistanceMode, RestoreState


class SystemSubsystem(Subsystem):
    """Device-wide configuration including state restoration, resistance mode, controller speed, SEMI F47, reset, and clear-status."""

    @property
    def user_text(self) -> str:
        """Read and return the current user text from the instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:CONFig:USER:TEXT?``."""

        return self._query("SYSTem:CONFig:USER:TEXT?").strip().strip('"')

    @user_text.setter
    def user_text(self, text: str) -> None:
        """Validate and write the user text to the instrument.
        
        Underlying SCPI used here: ``SYSTem:CONFig:USER:TEXT "{value}"``,
        ``SYSTem:CONFig:USER:TEXT "``."""

        if len(text) > 40:
            raise ValueError("EA user text is limited to 40 characters")
        escaped = text.replace('"', "'")
        self._write(f'SYSTem:CONFig:USER:TEXT "{escaped}"')

    @property
    def resistance_mode(self) -> ResistanceMode:
        """Read and return the current UIP/UIR resistance-mode selection from the instrument or
        driver state.
        
        Underlying SCPI used here: ``SYSTem:CONFig:MODe?``."""

        token = self._query("SYSTem:CONFig:MODe?").strip().upper()
        return ResistanceMode(token)

    @resistance_mode.setter
    def resistance_mode(self, value: Union[ResistanceMode, str]) -> None:
        """Validate and write the UIP/UIR resistance-mode selection to the instrument.
        
        Underlying SCPI used here: ``SYSTem:CONFig:MODe {value}``, ``SYSTem:CONFig:MODe``."""

        token = value.value if isinstance(value, ResistanceMode) else str(value).upper()
        if token not in {"UIP", "UIR"}:
            raise ValueError("resistance mode must be UIP or UIR")
        self._write(f"SYSTem:CONFig:MODe {token}")

    @property
    def state_after_remote(self) -> AfterState:
        """Read and return the current DC terminal state after leaving remote control from the
        instrument or driver state.
        
        Underlying SCPI used here: ``POWer:STAGe:AFTer:REMote?``."""

        return AfterState(self._query("POWer:STAGe:AFTer:REMote?").strip().upper())

    @state_after_remote.setter
    def state_after_remote(self, state: Union[AfterState, str]) -> None:
        """Validate and write the DC terminal state after leaving remote control to the
        instrument.
        
        Underlying SCPI used here: ``POWer:STAGe:AFTer:REMote {value}``,
        ``POWer:STAGe:AFTer:REMote``."""

        token = state.value if isinstance(state, AfterState) else str(state).upper()
        self._write(f"POWer:STAGe:AFTer:REMote {token}")

    @property
    def state_after_power_on(self) -> RestoreState:
        """Read and return the current output restore behavior after power-on from the
        instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:CONFig:OUTPut:RESTore?``."""

        return RestoreState(self._query("SYSTem:CONFig:OUTPut:RESTore?").strip().upper())

    @state_after_power_on.setter
    def state_after_power_on(self, state: Union[RestoreState, str]) -> None:
        """Validate and write the output restore behavior after power-on to the instrument.
        
        Underlying SCPI used here: ``SYSTem:CONFig:OUTPut:RESTore {value}``,
        ``SYSTem:CONFig:OUTPut:RESTore``."""

        token = state.value if isinstance(state, RestoreState) else str(state).upper()
        self._write(f"SYSTem:CONFig:OUTPut:RESTore {token}")

    @property
    def state_after_pf(self) -> AfterState:
        """Read and return the current state after power-fail alarm recovery from the
        instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:ALARm:ACTion:PFAil?``."""

        return AfterState(self._query("SYSTem:ALARm:ACTion:PFAil?").strip().upper())

    @state_after_pf.setter
    def state_after_pf(self, state: Union[AfterState, str]) -> None:
        """Validate and write the state after power-fail alarm recovery to the instrument.
        
        Underlying SCPI used here: ``SYSTem:ALARm:ACTion:PFAil {value}``,
        ``SYSTem:ALARm:ACTion:PFAil``."""

        token = state.value if isinstance(state, AfterState) else str(state).upper()
        self._write(f"SYSTem:ALARm:ACTion:PFAil {token}")

    @property
    def state_after_ot(self) -> AfterState:
        """Read and return the current state after overtemperature alarm recovery from the
        instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:ALARm:ACTion:OTEMperature?``."""

        return AfterState(self._query("SYSTem:ALARm:ACTion:OTEMperature?").strip().upper())

    @state_after_ot.setter
    def state_after_ot(self, state: Union[AfterState, str]) -> None:
        """Validate and write the state after overtemperature alarm recovery to the instrument.
        
        Underlying SCPI used here: ``SYSTem:ALARm:ACTion:OTEMperature {value}``,
        ``SYSTem:ALARm:ACTion:OTEMperature``."""

        token = state.value if isinstance(state, AfterState) else str(state).upper()
        self._write(f"SYSTem:ALARm:ACTion:OTEMperature {token}")

    def reset(self) -> None:
        """Issue *RST. EA documents that this enters remote and switches DC off."""
        self._write("*RST", check_errors=False)
        self._device._limit_cache = None
        self._device._ratings_cache = None

    def clear_status(self) -> None:
        """Perform the clear status operation.
        
        Underlying SCPI used here: ``*CLS``."""

        self._write("*CLS", check_errors=False)

    def restart(self) -> None:
        """Warm restart if supported by the installed firmware."""
        self._device._unsupported("warm restart SCPI command is not verified in the supplied documentation")

    @property
    def semi_f47(self) -> bool:
        """Read and return the current SEMI F47 enable state from the instrument or driver
        state.
        
        Underlying SCPI used here: ``SYSTem:CONFig:SEMif47?``."""

        token = self._query("SYSTem:CONFig:SEMif47?").strip().upper()
        return token in {"1", "ON", "ENABLE", "ENABLED"}

    @semi_f47.setter
    def semi_f47(self, enabled: bool) -> None:
        """Validate and write the SEMI F47 enable state to the instrument.
        
        Underlying SCPI used here: ``SYSTem:CONFig:SEMif47 {value}``,
        ``SYSTem:CONFig:SEMif47``."""

        self._write(f"SYSTem:CONFig:SEMif47 {'ENABle' if enabled else 'DISable'}")

    def set_semi_f47(self, enabled: bool) -> None:
        """Validate and write semi f47."""

        self.semi_f47 = enabled

    @property
    def voltage_controller_speed(self) -> ControllerSpeed:
        """Read and return the current voltage-controller speed from the instrument or driver
        state.
        
        Underlying SCPI used here: ``SYSTem:CONFig:CONTroller:SPEed?``."""

        token = self._query("SYSTem:CONFig:CONTroller:SPEed?").strip().upper()
        if token.startswith("NORM"):
            token = "NORM"
        return ControllerSpeed(token)

    @voltage_controller_speed.setter
    def voltage_controller_speed(self, speed: Union[ControllerSpeed, str]) -> None:
        """Validate and write the voltage-controller speed to the instrument.
        
        Underlying SCPI used here: ``SYSTem:CONFig:CONTroller:SPEed {value}``,
        ``SYSTem:CONFig:CONTroller:SPEed``."""

        token = str(getattr(speed, "value", speed)).upper()
        token = {"NORMAL": "NORM", "NORMALIZED": "NORM"}.get(token, token)
        if token not in {"SLOW", "NORM", "FAST"}:
            raise ValueError("speed must be SLOW, NORM/NORMAL, or FAST")
        self._write(f"SYSTem:CONFig:CONTroller:SPEed {token}")

    def set_voltage_controller_speed(self, speed: Union[ControllerSpeed, str]) -> None:
        """Validate and write voltage controller speed."""

        self.voltage_controller_speed = speed
