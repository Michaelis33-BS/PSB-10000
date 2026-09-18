# Installation

This release supports **Python 3.8 and newer**.

## Ubuntu / Linux (recommended)

From the extracted package directory:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -e ".[serial]"
```

For Ethernet-only use, omit the serial extra:

```bash
python3 -m pip install -e .
```

Verify the driver:

```bash
python3 -c "from ea_psb10000 import PSB10000; print('EA-PSB driver loaded successfully')"
```

## Install the wheel directly

```bash
python3 -m pip install ea_psb10000-0.2.1-py3-none-any.whl
```

USB/serial support requires `pyserial>=3.5`.

## Why version 0.2.1?

Version 0.2.1 is based on the Python-3.8-compatible 0.1.1 driver you were already using. It keeps that public API and removes Python-3.10-only dataclass behavior, while adding the verified SCPI spelling fixes, per-counter alarm queries, complete documented error-code catalog, and the Rev-2 hardware verifier.

For the least-friction Python 3.8 install, install the wheel directly. Ethernet operation has no third-party runtime dependency.
