"""Master-slave configuration."""

from __future__ import annotations

from .base import Subsystem
from ..enums import MasterSlaveRole
from ..util import bool_token, ensure_range


class MasterSlaveSubsystem(Subsystem):
    @property
    def enabled(self) -> bool:
        return self._query_bool("SYST:MS:ENAB?")

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._write(f"SYST:MS:ENAB {bool_token(value)}")

    @property
    def role(self) -> MasterSlaveRole:
        return MasterSlaveRole(self._query("SYST:MS:LINK?").strip().upper())

    @role.setter
    def role(self, value: MasterSlaveRole | str) -> None:
        token = value.value if isinstance(value, MasterSlaveRole) else str(value).upper()
        if token not in {"MASTER", "SLAVE"}:
            raise ValueError("role must be MASTER or SLAVE")
        self._write(f"SYST:MS:LINK {token}")

    @property
    def termination(self) -> bool:
        return self._query_bool("SYST:MS:TERM?")

    @termination.setter
    def termination(self, value: bool) -> None:
        self._write(f"SYST:MS:TERM {bool_token(value)}")

    @property
    def bias(self) -> bool:
        return self._query_bool("SYST:MS:BIAS?")

    @bias.setter
    def bias(self, value: bool) -> None:
        self._write(f"SYST:MS:BIAS {bool_token(value)}")

    def initialize(self) -> str:
        self._write("SYST:MS:INIT")
        return self.condition

    @property
    def condition(self) -> str:
        return self._query("SYST:MS:COND?").strip().upper()

    @property
    def units(self) -> int:
        return self._query_int("SYST:MS:UNITS?")
