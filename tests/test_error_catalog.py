from __future__ import annotations

import pytest

from ea_psb10000 import PSB10000, PSBSCPIError
from ea_psb10000.subsystems.errors import KNOWN_SCPI_ERRORS
from ea_psb10000.testing import ScriptedTransport
from ea_psb10000.util import parse_scpi_error


@pytest.mark.parametrize("code,message", sorted(KNOWN_SCPI_ERRORS.items()))
def test_every_documented_scpi_error_parses(code: int, message: str):
    record = parse_scpi_error(f'{code},"{message}"')
    assert record.code == code
    assert record.message == message
    assert record.is_error is (code != 0)
    if code != 0:
        exc = PSBSCPIError([record], command="TEST")
        assert exc.errors[0].code == code
        assert str(code) in str(exc)


def _base_responses():
    return {
        "*IDN?": "EA ELEKTRO-AUTOMATIK,PSB 10060-60 2U,1,KE 3.10",
        "SYST:NOM:VOLT?": "60",
        "SYST:NOM:CURR?": "60",
        "SYST:NOM:POW?": "1500",
        "SYST:NOM:RES:MIN?": "0.05",
        "SYST:NOM:RES:MAX?": "100",
    }


def test_error_subsystem_next_next_explicit_and_all():
    responses = _base_responses()
    responses.update({
        "SYSTem:ERRor?": ['-100,"Command error"', '0,"No error"'],
        "SYSTem:ERRor:NEXT?": '-222,"Data out of range"',
        "SYSTem:ERRor:ALL?": '-220,"Parameter error", -224,"Illegal parameter value"',
    })
    t = ScriptedTransport(responses)
    d = PSB10000(t, write_settle_s=0, check_errors_after_write=False)
    d.connect()
    assert d.errors.next().code == -100
    assert d.errors.next_explicit().code == -222
    assert [e.code for e in d.errors.all()] == [-220, -224]


def test_known_error_catalog_contains_safety_ovp_without_hardware_trigger():
    assert KNOWN_SCPI_ERRORS[-999] == "Safety OVP"
