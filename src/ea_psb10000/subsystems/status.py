"""Status-register and alarm decoding."""

from __future__ import annotations

from .base import Subsystem
from ..enums import PowerFlow, RegulationMode, RemoteOwner
from ..exceptions import PSBAlarmError
from ..models import StatusSnapshot

# EA Questionable-status register.  These assignments are documented by the
# programming guide register model; bits 10/11/13 and OVP/OT are also shown in
# the guide's examples.  Bit 9 is presently unused in the older guide.
_QUESTIONABLE_ALARMS: dict[int, str] = {
    0: "OVP", 1: "OCP", 2: "OPP", 3: "OT", 13: "PF", 14: "MSP",
}
_QUESTIONABLE_EVENTS: dict[int, str] = {
    4: "OVD", 5: "UVD", 6: "OCD", 7: "UCD", 8: "OPD",
}
# In the second questionable register, bit 0 distinguishes whether an OCP/OPP
# originated in sink/source operation; it is metadata, not a separate alarm.
# Bit 2 is the Share-Bus failure alarm (SF).
_SECONDARY_ALARMS: dict[int, str] = {2: "SF"}


class StatusSubsystem(Subsystem):
    def questionable(self) -> int:
        return self._query_int("STAT:QUES:COND?")

    def secondary_questionable(self) -> int:
        try:
            return self._query_int("STAT:SEC:QUES:COND?")
        except Exception:
            return 0

    def operation(self) -> int:
        return self._query_int("STAT:OPER:COND?")

    def status_byte(self) -> int:
        return self._query_int("*STB?")

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
        # Operation register: CV/CC/CP/CR are bits 8..11.
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
        # On PSB, operation bit 12 indicates source/sink state, but the older
        # register diagram labels only the combined field.  Signed measurement
        # data is a more portable discriminator when available.
        if measurements_current is not None:
            if measurements_current < 0:
                return PowerFlow.SINK
            if measurements_current > 0:
                return PowerFlow.SOURCE
        return PowerFlow.SINK if operation & (1 << 12) else PowerFlow.SOURCE

    def snapshot(self, *, include_measurement_for_flow: bool = False) -> StatusSnapshot:
        # Important ordering: capture alarm/status registers before any call to
        # SYST:ERR?, because reading the error queue acknowledges alarms whose
        # cause has gone away.
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

    def alarm_counters(self) -> dict[str, int]:
        """Read power-cycle alarm occurrence counters documented for PSB."""
        commands = {
            "OVP": "SYST:ALARM:COUNT:OVOL?",
            "OT": "SYST:ALARM:COUNT:OTEM?",
            "OPP": "SYST:ALARM:COUNT:OPOW?",
            "OCP": "SYST:ALARM:COUNT:OCURR?",
            "PF": "SYST:ALARM:COUNT:PFAIL?",
            "SF": "SYST:ALARM:COUNT:SHAREBUSFAIL?",
            "SINK_OPP": "SYST:SINK:ALARM:COUNT:OPOW?",
            "SINK_OCP": "SYST:SINK:ALARM:COUNT:OCURR?",
        }
        return {name: self._query_int(command) for name, command in commands.items()}

    def raise_for_alarms(self) -> None:
        snap = self.snapshot()
        # Do not classify remote/output/function bits as alarms; decode_alarms
        # deliberately only returns protection/supervision/alarm bits.
        if snap.active_alarms:
            raise PSBAlarmError(
                snap.active_alarms,
                questionable=snap.questionable,
                secondary=snap.secondary_questionable,
            )
