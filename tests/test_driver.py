from __future__ import annotations

import pytest

from ea_psb10000 import PSB10000, PSBSCPIError, PSBValidationError
from ea_psb10000.testing import ScriptedTransport


def base_responses():
    return {
        "*IDN?": "EA ELEKTRO-AUTOMATIK,PSB 10060-60 2U,123456,KE 3.10",
        "SYST:NOM:VOLT?": "60 V",
        "SYST:NOM:CURR?": "60 A",
        "SYST:NOM:POW?": "1500 W",
        "SYST:NOM:RES:MIN?": "0.05 Ohm",
        "SYST:NOM:RES:MAX?": "100 Ohm",
        "VOLT:LIM:LOW?": "0 V",
        "VOLT:LIM:HIGH?": "60 V",
        "CURR:LIM:LOW?": "0 A",
        "CURR:LIM:HIGH?": "60 A",
        "POW:LIM:HIGH?": "1500 W",
        "RES:LIM:HIGH?": "100 Ohm",
        "SINK:CURR:LIM:LOW?": "0 A",
        "SINK:CURR:LIM:HIGH?": "60 A",
        "SINK:POW:LIM:HIGH?": "1500 W",
        "SINK:RES:LIM:HIGH?": "100 Ohm",
        "MEAS:ARR?": "32.00 V,-8.00 A,-256 W",
    }


def connected_driver(**kwargs):
    t = ScriptedTransport(base_responses())
    d = PSB10000(t, write_settle_s=0, **kwargs)
    d.connect()
    return d, t


def test_identification_and_ratings():
    d, _ = connected_driver()
    assert d.info.model == "PSB 10060-60 2U"
    assert d.ratings.voltage == 60
    assert d.ratings.current == 60
    assert d.ratings.power == 1500


def test_measurement_sign_identifies_sink():
    d, _ = connected_driver()
    m = d.measure()
    assert m.voltage == 32
    assert m.current == -8
    assert m.power == -256
    assert m.flow.value == "SINK"


def test_source_setpoint_validated_and_sent():
    d, t = connected_driver(raise_on_alarm_after_write=False)
    d.source.voltage = 32
    assert "VOLT 32" in t.commands


def test_setpoint_outside_adjustment_limit_rejected_before_write():
    d, t = connected_driver(raise_on_alarm_after_write=False)
    before = list(t.commands)
    with pytest.raises(PSBValidationError):
        d.source.voltage = 61
    assert "VOLT 61" not in t.commands[len(before):]


def test_scpi_error_becomes_exception():
    responses = base_responses()
    responses["SYST:ERR?"] = ['-222,"Data out of range"', '0,"No error"']
    t = ScriptedTransport(responses)
    d = PSB10000(t, write_settle_s=0, raise_on_alarm_after_write=False)
    d.connect()
    with pytest.raises(PSBSCPIError) as exc:
        d.output.on()
    assert exc.value.errors[0].code == -222


def test_source_only_sets_sink_current_zero():
    d, t = connected_driver(raise_on_alarm_after_write=False)
    d.source_only()
    assert "SINK:CURR 0" in t.commands


def test_sink_only_sets_voltage_zero():
    d, t = connected_driver(raise_on_alarm_after_write=False)
    d.sink_only()
    assert "VOLT 0" in t.commands


def test_verified_controller_speed_and_semi_f47_commands():
    d, t = connected_driver(raise_on_alarm_after_write=False)
    d.system.voltage_controller_speed = "FAST"
    d.system.semi_f47 = True
    assert "SYST:CONF:CONT:SPE FAST" in t.commands
    assert "SYST:CONF:SEMIF47 ENABLE" in t.commands


def test_interface_watchdog_configuration():
    d, t = connected_driver(raise_on_alarm_after_write=False)
    d.watchdog.configure(enabled=True, timeout_s=7, heartbeat=False)
    assert "SYST:COMM:MON:TIME 7" in t.commands
    assert "SYST:COMM:MON:ACT ON" in t.commands
