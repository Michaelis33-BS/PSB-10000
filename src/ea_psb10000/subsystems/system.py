"""Device-wide configuration and control."""

from __future__ import annotations

from .base import Subsystem
from ..enums import AfterState, ControllerSpeed, ResistanceMode, RestoreState
from ..util import bool_token


class SystemSubsystem(Subsystem):
    @property
    def user_text(self) -> str:
        return self._query("SYST:CONF:USER:TEXT?").strip().strip('"')

    @user_text.setter
    def user_text(self, text: str) -> None:
        if len(text) > 40:
            raise ValueError("EA user text is limited to 40 characters")
        escaped = text.replace('"', "'")
        self._write(f'SYST:CONF:USER:TEXT "{escaped}"')

    @property
    def resistance_mode(self) -> ResistanceMode:
        token = self._query("SYST:CONF:MODE?").strip().upper()
        return ResistanceMode(token)

    @resistance_mode.setter
    def resistance_mode(self, value: ResistanceMode | str) -> None:
        token = value.value if isinstance(value, ResistanceMode) else str(value).upper()
        if token not in {"UIP", "UIR"}:
            raise ValueError("resistance mode must be UIP or UIR")
        self._write(f"SYST:CONF:MODE {token}")

    @property
    def state_after_remote(self) -> AfterState:
        return AfterState(self._query("POW:STAG:AFT:REM?").strip().upper())

    @state_after_remote.setter
    def state_after_remote(self, state: AfterState | str) -> None:
        token = state.value if isinstance(state, AfterState) else str(state).upper()
        self._write(f"POW:STAG:AFT:REM {token}")

    @property
    def state_after_power_on(self) -> RestoreState:
        return RestoreState(self._query("SYST:CONF:OUTP:REST?").strip().upper())

    @state_after_power_on.setter
    def state_after_power_on(self, state: RestoreState | str) -> None:
        token = state.value if isinstance(state, RestoreState) else str(state).upper()
        self._write(f"SYST:CONF:OUTP:REST {token}")

    @property
    def state_after_pf(self) -> AfterState:
        return AfterState(self._query("SYST:ALARM:ACT:PFAIL?").strip().upper())

    @state_after_pf.setter
    def state_after_pf(self, state: AfterState | str) -> None:
        token = state.value if isinstance(state, AfterState) else str(state).upper()
        self._write(f"SYST:ALARM:ACT:PFAIL {token}")

    @property
    def state_after_ot(self) -> AfterState:
        return AfterState(self._query("SYST:ALARM:ACT:OTEM?").strip().upper())

    @state_after_ot.setter
    def state_after_ot(self, state: AfterState | str) -> None:
        token = state.value if isinstance(state, AfterState) else str(state).upper()
        self._write(f"SYST:ALARM:ACT:OTEM {token}")

    def reset(self) -> None:
        """Issue *RST. EA documents that this enters remote and switches DC off."""
        self._write("*RST", check_errors=False)
        self._device._limit_cache = None
        self._device._ratings_cache = None

    def clear_status(self) -> None:
        self._write("*CLS", check_errors=False)

    def restart(self) -> None:
        """Warm restart if supported by the installed firmware.

        The 2025 user manual lists Restart as a front-panel function but does not
        publish its SCPI command. Use the raw interface if a later programming
        guide documents one for your firmware.
        """
        self._device._unsupported("warm restart SCPI command is not verified in the supplied documentation")

    @property
    def semi_f47(self) -> bool:
        token = self._query("SYST:CONF:SEMIF47?").strip().upper()
        return token in {"1", "ON", "ENABLE", "ENABLED"}

    @semi_f47.setter
    def semi_f47(self, enabled: bool) -> None:
        self._write(f"SYST:CONF:SEMIF47 {'ENABLE' if enabled else 'DISABLE'}")

    def set_semi_f47(self, enabled: bool) -> None:
        self.semi_f47 = enabled

    @property
    def voltage_controller_speed(self) -> ControllerSpeed:
        token = self._query("SYST:CONF:CONT:SPE?").strip().upper()
        if token.startswith("NORM"):
            token = "NORM"
        return ControllerSpeed(token)

    @voltage_controller_speed.setter
    def voltage_controller_speed(self, speed: ControllerSpeed | str) -> None:
        token = str(getattr(speed, "value", speed)).upper()
        token = {"NORMAL": "NORM", "NORMALIZED": "NORM"}.get(token, token)
        if token not in {"SLOW", "NORM", "FAST"}:
            raise ValueError("speed must be SLOW, NORM/NORMAL, or FAST")
        self._write(f"SYST:CONF:CONT:SPE {token}")

    def set_voltage_controller_speed(self, speed: ControllerSpeed | str) -> None:
        self.voltage_controller_speed = speed
