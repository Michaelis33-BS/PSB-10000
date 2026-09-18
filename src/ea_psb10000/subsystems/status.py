"""Status-register, event-register, and alarm-counter access."""

from __future__ import annotations

from .base import Subsystem
from ..enums import PowerFlow, RegulationMode, RemoteOwner
from ..exceptions import PSBAlarmError
from ..models import StatusSnapshot
from ..util import ensure_range

_QUESTIONABLE_ALARMS: dict[int, str] = {
    0: "OVP", 1: "OCP", 2: "OPP", 3: "OT", 13: "PF", 14: "MSP",
}
_QUESTIONABLE_EVENTS: dict[int, str] = {
    4: "OVD", 5: "UVD", 6: "OCD", 7: "UCD", 8: "OPD",
}
_SECONDARY_ALARMS: dict[int, str] = {2: "SF"}

ALARM_COUNTER_COMMANDS: dict[str, str] = {
    "OVP": "SYSTem:ALARm:COUNt:OVOLtage?",
    "OT": "SYSTem:ALARm:COUNt:OTEMperature?",
    "OPP": "SYSTem:ALARm:COUNt:OPOWer?",
    "OCP": "SYSTem:ALARm:COUNt:OCURrent?",
    "PF": "SYSTem:ALARm:COUNt:PFAil?",
    "SF": "SYSTem:ALARm:COUNt:SHARebusfail?",
    "SINK_OPP": "SYSTem:SINK:ALARm:COUNt:OPOWer?",
    "SINK_OCP": "SYSTem:SINK:ALARm:COUNt:OCURrent?",
}


class StatusSubsystem(Subsystem):
    def questionable(self) -> int:
        return self._query_int("STATus:QUEStionable:CONDition?")

    def questionable_event(self) -> int:
        return self._query_int("STATus:QUEStionable:EVENt?")

    @property
    def questionable_enable(self) -> int:
        return self._query_int("STATus:QUEStionable:ENABle?")

    @questionable_enable.setter
    def questionable_enable(self, value: int) -> None:
        value = int(ensure_range(value, 0, 65535, "questionable enable mask"))
        self._write(f"STATus:QUEStionable:ENABle {value}")

    def secondary_questionable(self) -> int:
        try:
            return self._query_int("STATus:SECond:QUEStionable:CONDition?")
        except Exception:
            # Older/non-10000 firmware can omit this extra register.
            return 0

    def secondary_questionable_event(self) -> int:
        return self._query_int("STATus:SECond:QUEStionable:EVENt?")

    @property
    def secondary_questionable_enable(self) -> int:
        return self._query_int("STATus:SECond:QUEStionable:ENABle?")

    @secondary_questionable_enable.setter
    def secondary_questionable_enable(self, value: int) -> None:
        value = int(ensure_range(value, 0, 65535, "secondary questionable enable mask"))
        self._write(f"STATus:SECond:QUEStionable:ENABle {value}")

    def operation(self) -> int:
        return self._query_int("STATus:OPERation:CONDition?")

    def operation_event(self) -> int:
        return self._query_int("STATus:OPERation:EVENt?")

    @property
    def operation_enable(self) -> int:
        return self._query_int("STATus:OPERation:ENABle?")

    @operation_enable.setter
    def operation_enable(self, value: int) -> None:
        value = int(ensure_range(value, 0, 65535, "operation enable mask"))
        self._write(f"STATus:OPERation:ENABle {value}")

    def status_byte(self) -> int:
        return self._query_int("*STB?")

    def event_status(self) -> int:
        """Read *ESR?. Reading ESR clears the event-status register."""
        return self._query_int("*ESR?")

    @property
    def event_status_enable(self) -> int:
        return self._query_int("*ESE?")

    @event_status_enable.setter
    def event_status_enable(self, value: int) -> None:
        value = int(ensure_range(value, 0, 255, "event status enable mask"))
        self._write(f"*ESE {value}")

    @property
    def service_request_enable(self) -> int:
        return self._query_int("*SRE?")

    @service_request_enable.setter
    def service_request_enable(self, value: int) -> None:
        value = int(ensure_range(value, 0, 255, "service request enable mask"))
        self._write(f"*SRE {value}")

    @staticmethod
    def decode_alarms(questionable: int, secondary: int = 0) -> tuple[str, ...]:
        names = [name for bit, name in _QUESTIONABLE_ALARMS.items() if questionable & (1 << bit)]
        names.extend(name for bit, name in _SECONDARY_ALARMS.items() if secondary & (1 << bit))
        return tuple(names)

    @staticmethod
    def decode_events(questionable: int) -> tuple[str, ...]:
        return tuple(name for bit, name in _QUESTIONABLE_EVENTS.items() if questionable & (1 << bit))

    @staticmethod
    def _regulation(operation: int) -> RegulationMode:
        if operation & (1 << 8):
            return RegulationMode.CV
        if operation & (1 << 9):
            return RegulationMode.CC
        if operation & (1 << 10):
            return RegulationMode.CP
        if operation & (1 << 11):
            return RegulationMode.CR
        return RegulationMode.UNKNOWN

    @staticmethod
    def _flow(operation: int, measurements_current: float | None = None) -> PowerFlow:
        if measurements_current is not None:
            if measurements_current < 0:
                return PowerFlow.SINK
            if measurements_current > 0:
                return PowerFlow.SOURCE
        return PowerFlow.SINK if operation & (1 << 12) else PowerFlow.SOURCE

    def snapshot(self, *, include_measurement_for_flow: bool = False) -> StatusSnapshot:
        # Capture alarm/status registers before any SYSTem:ERRor? access. EA
        # documents error-queue reads as alarm acknowledgement for cleared causes.
        q = self.questionable()
        sq = self.secondary_questionable()
        op = self.operation()
        stb = self.status_byte()
        owner_raw = self._device.remote_owner_raw()
        owner = RemoteOwner.__members__.get(owner_raw, RemoteOwner.UNKNOWN)
        output = bool(q & (1 << 11))
        current = None
        if include_measurement_for_flow:
            try:
                current = self._device.measure().current
            except Exception:
                current = None
        return StatusSnapshot(
            status_byte=stb,
            questionable=q,
            secondary_questionable=sq,
            operation=op,
            output_on=output,
            remote_owner=owner,
            regulation_mode=self._regulation(op),
            power_flow=self._flow(op, current),
            active_alarms=self.decode_alarms(q, sq),
            active_events=self.decode_events(q),
            raw={
                "owner": owner_raw,
                "questionable": str(q),
                "secondary_questionable": str(sq),
                "operation": str(op),
                "status_byte": str(stb),
            },
        )

    def alarm_counter(self, name: str) -> int:
        key = name.strip().upper()
        if key not in ALARM_COUNTER_COMMANDS:
            raise ValueError(f"unknown alarm counter {name!r}; choose {', '.join(ALARM_COUNTER_COMMANDS)}")
        return self._query_int(ALARM_COUNTER_COMMANDS[key])

    def alarm_counters(self) -> dict[str, int]:
        """Read all documented PSB power-cycle alarm counters.

        A caller that wants per-command fault isolation should use
        :meth:`alarm_counter`; this aggregate method intentionally propagates a
        failed/unsupported query.
        """
        return {name: self.alarm_counter(name) for name in ALARM_COUNTER_COMMANDS}

    def raise_for_alarms(self) -> None:
        snap = self.snapshot()
        if snap.active_alarms:
            raise PSBAlarmError(
                snap.active_alarms,
                questionable=snap.questionable,
                secondary=snap.secondary_questionable,
            )
