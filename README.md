# EA-PSB 10000 Python Driver

Reusable SCPI driver for EA Elektro-Automatik / Tektronix EA-PSB 10000-series
programmable bidirectional DC power supplies.

The package is designed to be imported by test scripts, production utilities,
GUIs, ATE software, notebooks, and higher-level automation rather than being a
single bench script.

## Design priorities

- Ethernet and serial/USB transports behind one API.
- Connecting never enables the DC terminal.
- Remote control is explicit (`acquire_remote()`).
- State-changing commands are never silently replayed after a connection loss.
- Thread-safe command/query transactions.
- Model ratings are queried from the instrument instead of hard-coded.
- Setpoints are checked against the instrument's adjustment limits.
- SCPI error queue is checked after writes by default.
- Alarm condition registers are captured **before** reading `SYST:ERR?`, because
  EA documents that reading the error queue can acknowledge cleared alarms.
- Source and sink current/power/resistance are separate APIs.
- Raw SCPI access is available for future firmware additions.
- Function generator support includes arbitrary sequences and PSB XY tables.
- Instrument-side interface monitoring plus an optional Python heartbeat/watchdog.
- Optional-interface configuration helpers for Ethernet, RS232/CAN/CANopen/Profibus/Profinet settings documented by EA.

## Install

From this folder:

```bash
python -m pip install -e .
```

For serial/USB-serial support:

```bash
python -m pip install -e ".[serial]"
```

## Basic Ethernet use

```python
from ea_psb10000 import PSB10000

with PSB10000.ethernet("192.168.1.50") as psb:
    print(psb.info)
    print(psb.ratings)

    # Merely connecting does NOT acquire remote control or enable DC.
    psb.acquire_remote()

    psb.source.configure(voltage=32.0, current=18.0, power=600.0)
    psb.sink.configure(current=8.0, power=600.0)

    psb.protection.ovp = 54.0
    psb.protection.source_ocp = 20.0
    psb.protection.source_opp = 650.0

    psb.output.on()
    print(psb.measure())
    print(psb.status.snapshot(include_measurement_for_flow=True))
    psb.output.off()
    psb.release_remote()
```

If you want automatic cleanup after a successful or failed test:

```python
with PSB10000.ethernet(
    "192.168.1.50",
    output_off_on_exit=True,
    release_remote_on_exit=True,
) as psb:
    psb.acquire_remote()
    # test work...
```

## Source/sink rules

The PSB automatically transitions between source and sink based on voltage
setpoint versus terminal voltage. Convenience helpers implement the rules EA
publishes:

```python
psb.source_only()  # sink current setpoint -> 0 A
psb.sink_only()    # voltage setpoint -> 0 V
```

## Errors and alarms

SCPI command errors are Python exceptions:

```python
from ea_psb10000 import PSBSCPIError, PSBAlarmError, PSBConnectionError

try:
    psb.source.voltage = 32
except PSBSCPIError as exc:
    for error in exc.errors:
        print(error.code, error.message)
except PSBAlarmError as exc:
    print(exc.alarms)
except PSBConnectionError:
    # Treat connection-loss-after-write as an indeterminate write outcome.
    # Reconnect and read instrument state; do not blindly replay a command.
    raise
```

Read status explicitly at any time:

```python
status = psb.status.snapshot()
if status.alarm_active:
    print(status.active_alarms)
if status.active_events:
    print(status.active_events)
```

The error queue API is deliberately explicit because `SYST:ERR?` has alarm-
acknowledgement side effects on EA instruments:

```python
status_before_ack = psb.status.snapshot()
errors = psb.errors.drain()
```

## Adjustment limits

```python
limits = psb.limits.snapshot(refresh=True)
print(limits)

psb.limits.set_voltage(minimum=0, maximum=40)
psb.limits.set_source_current(maximum=18)
psb.limits.set_sink_current(maximum=10)
```

Higher-level setpoint setters consult the cached adjustment-limit snapshot and
reject out-of-range values before transmitting them.

## User supervision events

```python
from ea_psb10000 import EventAction

psb.events.configure("OVD", threshold=40, action=EventAction.ALARM)
psb.events.configure("OCD", threshold=9, action=EventAction.WARNING, sink=True)
```

## Analog-interface configuration

```python
psb.analog.range_volts = 10
psb.analog.monitor_mode = "DEFAULT"
psb.analog.set_pin6("ALL")
psb.analog.set_pin14("ALL")
psb.analog.set_pin15("POW")
psb.analog.rem_sb_level = "NORMAL"
psb.analog.rem_sb_action = "AUTO"
```

## Master/slave

```python
psb.master_slave.role = "MASTER"
psb.master_slave.termination = True
psb.master_slave.bias = True
psb.master_slave.enabled = True
print(psb.master_slave.initialize())
print(psb.master_slave.units)
```

## Ethernet configuration

On PSB 10000 hardware the built-in RJ45 is LAN index 2 in the documented SCPI
scheme:

```python
psb.communications.select_lan(2)
print(psb.communications.ip_address)
print(psb.communications.mac_address)
```

Changing IP, DHCP, TCP port, or socket timeout can intentionally break the
connection you are currently using. Prefer making network-setting changes over
USB/serial or plan to reconnect using the new settings.


## Interface monitoring / watchdog

The PSB can supervise the controlling digital interface. The Python layer can
also send an opt-in heartbeat so long tests do not time out while otherwise idle:

```python
psb.system.state_after_remote = "OFF"
psb.watchdog.configure(
    enabled=True,
    timeout_s=5,
    heartbeat=True,
    heartbeat_interval_s=1.0,
)
```

The heartbeat only sends `*STB?`; it never changes a setpoint or output state.
`PSB10000.close()` stops the heartbeat thread before closing the transport.

## Controller speed and SEMI F47

These commands are verified in EA's 10000/20000-series SCPI programming guide:

```python
psb.system.voltage_controller_speed = "FAST"
psb.system.semi_f47 = True
```

## Function generator

```python
from ea_psb10000 import ArbitrarySequence

seq = ArbitrarySequence(
    start_amplitude=0,
    end_amplitude=0,
    start_frequency_hz=0,
    end_frequency_hz=0,
    start_angle_deg=0,
    start_level=0,
    end_level=32,
    sequence_time_s=1.0,
)

psb.function_generator.configure_arbitrary([seq], target="VOLTAGE")
psb.function_generator.run()
```

EA documents that arbitrary/XY data must be submitted and recommends waiting at
least two seconds after submission. The driver does this by default.

## 2025-only settings: deliberate no-guess policy

The supplied 2025 user manual documents three settings whose exact SCPI spellings
are not present in the programming-guide revision available for verification:

- actual-value filter mode and buffer size;
- STBY zero stabilization;
- fast discharge enable, voltage, current, and duration.

The user manual explicitly delegates digital command syntax to the separate
"Programming Guide ModBus & SCPI". This package therefore **does not invent
SCPI spellings** for those three features. Controller speed and SEMI F47 are
implemented normally because their SCPI commands are documented.

`psb.extensions` provides a controlled registration mechanism once the exact
commands for the installed firmware are confirmed:

```python
psb.extensions.register(
    "fast_discharge",
    set_command="<verified command here>",
    query_command="<verified query here>",
)
```

Then high-level validation can still be used. For example, the driver enforces
0..102% nominal voltage/current and 0..5000 ms for fast discharge, matching the
2025 user manual.

## Raw SCPI escape hatch

```python
print(psb.query_scpi("*IDN?"))
psb.write_scpi("<verified future command>")
```

For intentional low-level work where *you* will handle the error queue:

```python
psb.write_scpi("<command>", check_errors=False)
```

## Test without hardware

`ScriptedTransport` is included so software that consumes this driver can be
unit-tested without energizing a supply:

```python
from ea_psb10000 import PSB10000
from ea_psb10000.testing import ScriptedTransport
```

Run this package's tests with:

```bash
python -m pytest
```

## Command coverage

See [`COMMAND_COVERAGE.md`](COMMAND_COVERAGE.md) for the typed API surface,
known firmware-dependent gaps, and the no-guess policy.

## Documentation basis

The implementation is based on the EA-PSB 10000 user manual supplied with this
project and EA's "Programming Guide ModBus & SCPI" command definitions. Where
the 2025 user manual describes a feature but does not provide its digital SCPI
syntax, the driver raises `PSBUnsupportedFeatureError` rather than guessing.
