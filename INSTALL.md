# EA-PSB 10000 Driver Installation

**Writer:** Jeff Michaelis  
**Version:** 0.2.2  
**Python:** 3.8+

## Install the wheel

Windows with Python 3.8 explicitly selected:

```bat
py -3.8 -m pip install ea_psb10000-0.2.2-py3-none-any.whl
```

Linux:

```bash
python3.8 -m pip install ./ea_psb10000-0.2.2-py3-none-any.whl
```

Ethernet operation has no external runtime dependency.

## Serial / USB-COM support

Install `pyserial` into the same interpreter:

```bash
python -m pip install pyserial>=3.5
```

When installing from source, the serial extra can do this automatically:

```bash
python -m pip install -e ".[serial]"
```

## Editable source install

From the driver directory:

```bash
python -m pip install -e .
```

## Verify the installed version

```bash
python -c "import ea_psb10000; print(ea_psb10000.__version__)"
```

Expected:

```text
0.2.2
```

## Run the hardware-free tests

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## Run the hardware verifier over Ethernet

```bash
python examples/verify_psb_commands.py --host 192.168.13.17 --verbose --release-remote
```

## Run the hardware verifier over USB/serial

Windows:

```bat
py -3.8 examples\verify_psb_commands.py --serial COM5 --verbose --release-remote
```

Linux:

```bash
python3.8 examples/verify_psb_commands.py --serial /dev/ttyUSB0 --verbose --release-remote
```

For a complete command reference, verifier safety flags, SCPI mappings, and usage examples, see `README.md`.
