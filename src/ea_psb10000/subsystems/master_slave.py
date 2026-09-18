"""Master-slave configuration."""

from __future__ import annotations

from .base import Subsystem
from ..enums import MasterSlaveRole
from ..util import bool_token


class MasterSlaveSubsystem(Subsystem):
    @property
    def enabled(self) -> bool:
        return self._query_bool("SYSTem:MS:ENABle?")

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._write(f"SYSTem:MS:ENABle {bool_token(value)}")

    @property
    def role(self) -> MasterSlaveRole:
        return MasterSlaveRole(self._query("SYSTem:MS:LINK?").strip().upper())

    @role.setter
    def role(self, value: MasterSlaveRole | str) -> None:
        token = value.value if isinstance(value, MasterSlaveRole) else str(value).upper()
        if token not in {"MASTER", "SLAVE"}:
            raise ValueError("role must be MASTER or SLAVE")
        self._write(f"SYSTem:MS:LINK {token}")

    @property
    def termination(self) -> bool:
        return self._query_bool("SYSTem:MS:TERMination?")

    @termination.setter
    def termination(self, value: bool) -> None:
        self._write(f"SYSTem:MS:TERMination {bool_token(value)}")

    @property
    def bias(self) -> bool:
        return self._query_bool("SYSTem:MS:BIAS?")

    @bias.setter
    def bias(self, value: bool) -> None:
        self._write(f"SYSTem:MS:BIAS {bool_token(value)}")

    def initialize(self) -> str:
        self._write("SYSTem:MS:INITialisation")
        return self.condition

    @property
    def condition(self) -> str:
        return self._query("SYSTem:MS:CONDition?").strip().upper()

    @property
    def units(self) -> int:
        return self._query_int("SYSTem:MS:UNITs?")
