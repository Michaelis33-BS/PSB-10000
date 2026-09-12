from __future__ import annotations

import pytest

from ea_psb10000 import ArbitrarySequence, PSB10000
from ea_psb10000.testing import ScriptedTransport


def make_driver():
    responses = {
        "*IDN?": "EA ELEKTRO-AUTOMATIK,PSB 10060-60 2U,1,KE 3.10",
        "SYST:NOM:VOLT?": "60",
        "SYST:NOM:CURR?": "60",
        "SYST:NOM:POW?": "1500",
        "SYST:NOM:RES:MIN?": "0.05",
        "SYST:NOM:RES:MAX?": "100",
    }
    t = ScriptedTransport(responses)
    d = PSB10000(t, write_settle_s=0, raise_on_alarm_after_write=False)
    d.connect()
    return d, t


def test_xy_second_table_uses_common_submit_command():
    d, t = make_driver()
    d.function_generator.load_xy("IU", [1.0, 2.0], second_table=True, submit_delay_s=0)
    assert "FUNC:GEN:XY:SEC:LEV 0" in t.commands
    assert "FUNC:GEN:XY:SUBM SECOND" in t.commands
    assert "FUNC:GEN:XY:SEC:SUBM" not in t.commands


def test_pv_xy_mode_is_accepted():
    d, t = make_driver()
    d.function_generator.load_xy("PV", [1.0], submit_delay_s=0)
    assert "FUNC:GEN:SEL PV" in t.commands


def test_negative_voltage_offset_is_rejected():
    d, _ = make_driver()
    seq = ArbitrarySequence(0, 0, 0, 0, 0, -1, 0, 1)
    with pytest.raises(Exception):
        d.function_generator.configure_arbitrary([seq], target="VOLTAGE", submit_delay_s=0)
