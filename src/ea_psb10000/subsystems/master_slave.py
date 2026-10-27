# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: Master/slave role, enable, termination, bias, initialization, and status access.

"""Master-slave configuration."""

from __future__ import annotations

from typing import Union

from .base import Subsystem
from ..enums import MasterSlaveRole
from ..util import bool_token


class MasterSlaveSubsystem(Subsystem):
    """Master/slave bus configuration and initialization helpers."""

    @property
    def enabled(self) -> bool:
        """Read and return the current enabled state from the instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:MS:ENABle?``."""

        return self._query_bool("SYSTem:MS:ENABle?")

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Validate and write the enabled state to the instrument.
        
        Underlying SCPI used here: ``SYSTem:MS:ENABle {value}``, ``SYSTem:MS:ENABle``."""

        self._write(f"SYSTem:MS:ENABle {bool_token(value)}")

    @property
    def role(self) -> MasterSlaveRole:
        """Read and return the current master/slave role from the instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:MS:LINK?``."""

        return MasterSlaveRole(self._query("SYSTem:MS:LINK?").strip().upper())

    @role.setter
    def role(self, value: Union[MasterSlaveRole, str]) -> None:
        """Validate and write the master/slave role to the instrument.
        
        Underlying SCPI used here: ``SYSTem:MS:LINK {value}``, ``SYSTem:MS:LINK``."""

        token = value.value if isinstance(value, MasterSlaveRole) else str(value).upper()
        if token not in {"MASTER", "SLAVE"}:
            raise ValueError("role must be MASTER or SLAVE")
        self._write(f"SYSTem:MS:LINK {token}")

    @property
    def termination(self) -> bool:
        """Read and return the current master/slave bus termination from the instrument or
        driver state.
        
        Underlying SCPI used here: ``SYSTem:MS:TERMination?``."""

        return self._query_bool("SYSTem:MS:TERMination?")

    @termination.setter
    def termination(self, value: bool) -> None:
        """Validate and write the master/slave bus termination to the instrument.
        
        Underlying SCPI used here: ``SYSTem:MS:TERMination {value}``,
        ``SYSTem:MS:TERMination``."""

        self._write(f"SYSTem:MS:TERMination {bool_token(value)}")

    @property
    def bias(self) -> bool:
        """Read and return the current master/slave bus bias from the instrument or driver
        state.
        
        Underlying SCPI used here: ``SYSTem:MS:BIAS?``."""

        return self._query_bool("SYSTem:MS:BIAS?")

    @bias.setter
    def bias(self, value: bool) -> None:
        """Validate and write the master/slave bus bias to the instrument.
        
        Underlying SCPI used here: ``SYSTem:MS:BIAS {value}``, ``SYSTem:MS:BIAS``."""

        self._write(f"SYSTem:MS:BIAS {bool_token(value)}")

    def initialize(self) -> str:
        """Command the instrument to initialize the configured master/slave system and return
        the instrument response.
        
        Underlying SCPI used here: ``SYSTem:MS:INITialisation``."""

        self._write("SYSTem:MS:INITialisation")
        return self.condition

    @property
    def condition(self) -> str:
        """Read and return the current master/slave condition from the instrument or driver
        state.
        
        Underlying SCPI used here: ``SYSTem:MS:CONDition?``."""

        return self._query("SYSTem:MS:CONDition?").strip().upper()

    @property
    def units(self) -> int:
        """Read and return the current number of initialized master/slave units from the
        instrument or driver state.
        
        Underlying SCPI used here: ``SYSTem:MS:UNITs?``."""

        return self._query_int("SYSTem:MS:UNITs?")
