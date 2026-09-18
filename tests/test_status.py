from ea_psb10000 import PSB10000
from ea_psb10000.testing import ScriptedTransport


def test_alarm_decode_and_status_bits():
    responses = {
        "*IDN?": "EA ELEKTRO-AUTOMATIK,PSB 10060-60 2U,1,KE 3.10",
        "SYST:NOM:VOLT?": "60",
        "SYST:NOM:CURR?": "60",
        "SYST:NOM:POW?": "1500",
        "SYST:NOM:RES:MIN?": "0.05",
        "SYST:NOM:RES:MAX?": "100",
        "STATus:QUEStionable:CONDition?": str((1 << 3) | (1 << 10) | (1 << 11)),
        "STATus:SECond:QUEStionable:CONDition?": "0",
        "STATus:OPERation:CONDition?": str(1 << 8),
        "*STB?": "0",
        "SYST:LOCK:OWNER?": "REMOTE",
    }
    t = ScriptedTransport(responses)
    d = PSB10000(t, write_settle_s=0)
    d.connect()
    s = d.status.snapshot()
    assert s.output_on is True
    assert s.regulation_mode.value == "CV"
    assert "OT" in s.active_alarms
    assert s.remote_owner.value == "REMOTE"


def test_secondary_cause_bit_is_not_false_alarm_but_sharebus_is():
    assert PSB10000  # keep import used
    from ea_psb10000.subsystems.status import StatusSubsystem
    assert StatusSubsystem.decode_alarms(0, 1 << 0) == ()
    assert StatusSubsystem.decode_alarms(0, 1 << 2) == ("SF",)
