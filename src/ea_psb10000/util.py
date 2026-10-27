# Writer: Jeff Michaelis
# Project: EA-PSB 10000 Python Driver
# Python compatibility: Python 3.8+
# Purpose: Shared validation and SCPI-response parsing helpers.

"""Internal parsing and validation helpers.

These functions deliberately fail loudly on malformed instrument responses.
Silently converting a bad response to zero or ``False`` can be dangerous in
power-supply automation because the caller may make a control decision from an
invented value.
"""

from __future__ import annotations

import math
import re
from typing import List

from .exceptions import PSBProtocolError, PSBValidationError, SCPIErrorRecord

# Accept ordinary decimal numbers and scientific notation while allowing units
# or surrounding text in a response.  The first numeric token is used.
_NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?")


def ensure_finite(value: float, name: str) -> float:
    """Convert ``value`` to ``float`` and reject NaN, infinity, and non-numbers."""

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise PSBValidationError(f"{name} must be numeric, got {value!r}") from exc
    if not math.isfinite(result):
        raise PSBValidationError(f"{name} must be finite, got {value!r}")
    return result


def ensure_range(value: float, low: float, high: float, name: str) -> float:
    """Validate an inclusive numeric range and return the normalized float value."""

    value = ensure_finite(value, name)
    if value < low or value > high:
        raise PSBValidationError(f"{name}={value:g} outside allowed range {low:g}..{high:g}")
    return value


def parse_float(response: str, *, name: str = "value") -> float:
    """Parse the first numeric token from a SCPI response as ``float``."""

    match = _NUMBER_RE.search(response.strip())
    if not match:
        raise PSBProtocolError(f"Could not parse {name} as a number from {response!r}")
    try:
        return float(match.group(0))
    except ValueError as exc:
        raise PSBProtocolError(f"Could not parse {name} from {response!r}") from exc


def parse_int(response: str, *, name: str = "value") -> int:
    """Parse a numeric SCPI response and round it to the nearest integer."""

    return int(round(parse_float(response, name=name)))


def parse_bool(response: str) -> bool:
    """Parse standard EA/SCPI boolean spellings (1/0, ON/OFF, TRUE/FALSE)."""

    token = response.strip().upper()
    if token in {"1", "ON", "TRUE"}:
        return True
    if token in {"0", "OFF", "FALSE"}:
        return False
    raise PSBProtocolError(f"Could not parse boolean response {response!r}")


def bool_token(value: bool) -> str:
    """Convert a Python truth value to the SCPI token ``ON`` or ``OFF``."""

    return "ON" if bool(value) else "OFF"


def parse_csv_numbers(response: str) -> List[float]:
    """Parse a comma-separated SCPI numeric response into a list of floats."""

    values: List[float] = []
    for item in response.strip().split(","):
        values.append(parse_float(item))
    return values


def parse_scpi_error(response: str) -> SCPIErrorRecord:
    """Parse an EA SCPI error-queue response such as ``-100,"Command error"``."""

    raw = response.strip()
    if not raw:
        raise PSBProtocolError("Empty SCPI error response")
    if "," in raw:
        code_s, message = raw.split(",", 1)
    else:
        code_s, message = raw, ""
    try:
        code = int(code_s.strip())
    except ValueError as exc:
        raise PSBProtocolError(f"Malformed SCPI error response: {raw!r}") from exc
    message = message.strip().strip('"')
    return SCPIErrorRecord(code=code, message=message, raw=raw)
