from __future__ import annotations

from ea_psb10000 import PSB10000
from ea_psb10000.testing import ScriptedTransport


def base_responses():
    return {
        "*IDN?": "EA ELEKTRO-AUTOMATIK,PSB 10060-60 2U,1,KE 3.10",
        "SYST:NOM:VOLT?": "60",
        "SYST:NOM:CURR?": "60",
        "SYST:NOM:POW?": "1500",
        "SYST:NOM:RES:MIN?": "0.05",
        "SYST:NOM:RES:MAX?": "100",
        "SYSTem:COMMunicate:TIMeout?": "5",
        "SYSTem:COMMunicate:LAN:TIMeout?": "10",
        "SYSTem:CONFig:ANALog:REFerence?": "10",
        "SYSTem:CONFig:USER:TEXT?": '"HELLO"',
    }


def test_correct_timeout_spellings_are_used():
    t = ScriptedTransport(base_responses())
    d = PSB10000(t, write_settle_s=0, check_errors_after_write=False)
    d.connect()
    assert d.communications.serial_message_timeout_ms == 5
    assert d.communications.ethernet_timeout_s == 10
    d.communications.serial_message_timeout_ms = 25
    d.communications.ethernet_timeout_s = 30
    assert "SYSTem:COMMunicate:TIMeout 25" in t.commands
    assert "SYSTem:COMMunicate:LAN:TIMeout 30" in t.commands
    assert not any(cmd.startswith("SYST:COMM:TIME") for cmd in t.commands)


def test_full_form_analog_reference_and_user_text_commands():
    t = ScriptedTransport(base_responses())
    d = PSB10000(t, write_settle_s=0, check_errors_after_write=False)
    d.connect()
    assert d.analog.range_volts == 10
    assert d.system.user_text == "HELLO"
    d.analog.range_volts = 5
    d.system.user_text = "TEST"
    assert "SYSTem:CONFig:ANALog:REFerence 5" in t.commands
    assert 'SYSTem:CONFig:USER:TEXT "TEST"' in t.commands
