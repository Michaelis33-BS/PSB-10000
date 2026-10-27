# EA-PSB 10000 Python Driver

**Writer:** Jeff Michaelis  
**Package:** `ea-psb10000`  
**Version:** 0.2.2  
**Python:** 3.8 and newer  
**Purpose:** Reusable Python control, monitoring, error handling, verification, and automation for EA Elektro-Automatik / Tektronix EA-PSB 10000-series programmable bidirectional DC power supplies.

---

## 1. Overview

This package provides a reusable Python driver for EA-PSB 10000-series bidirectional power supplies. It is intended to be imported into test scripts, production ATE, engineering utilities, GUIs, notebooks, automated battery charge/discharge software, and other higher-level Python applications.

The package supports both source and regenerative sink operation and separates the instrument into logical subsystems such as source setpoints, sink setpoints, protection, adjustment limits, status, communications, function generation, and diagnostics.

The driver is designed around several safety and robustness rules:

- Merely creating or connecting a `PSB10000` object does **not** switch the DC terminal on.
- Digital remote control is explicit through `acquire_remote()`.
- The output is only energized by an explicit `psb.output.on()` or equivalent raw SCPI command.
- State-changing writes are not automatically replayed after a connection failure because the final instrument state could be indeterminate.
- Setpoints are checked against the instrument's reported adjustment limits before they are sent.
- Nominal voltage, current, power, and available resistance range are read from the connected instrument instead of hard-coded for one PSB model.
- Writes normally check the instrument SCPI error queue after the command.
- Alarm-condition registers are sampled before automatic error-queue acknowledgement so alarm information is not unnecessarily lost.
- Source and sink current, power, and resistance have separate APIs.
- Ethernet and serial/USB-COM use the same high-level driver interface.
- Long-form SCPI spellings are used in areas where firmware compatibility is improved by avoiding ambiguous abbreviations.
- The package contains a hardware verifier that can write a safe alternate value, query it back, record status changes, restore the original value, and test error handling.

---

## 2. Python 3.8 compatibility

Version 0.2.2 is maintained for Python 3.8 compatibility. The package metadata declares:

```text
python_requires >= 3.8
```

The source intentionally avoids requiring Python features introduced after Python 3.8 for normal operation. The serial transport has one optional dependency, `pyserial`.

Check the interpreter you are using:

```bash
python --version
```

On Windows, if multiple Python versions are installed:

```bat
py -3.8 --version
```

Install with the same interpreter that will run your application:

```bat
py -3.8 -m pip install ea_psb10000-0.2.2-py3-none-any.whl
```

or on Linux:

```bash
python3.8 -m pip install ./ea_psb10000-0.2.2-py3-none-any.whl
```

---

## 3. Installation

### 3.1 Install the wheel

Ethernet-only use does not require any third-party runtime dependency:

```bash
python -m pip install ./ea_psb10000-0.2.2-py3-none-any.whl
```

### 3.2 Install from source

From the project directory:

```bash
python -m pip install -e .
```

### 3.3 Install serial/USB-COM support

From source:

```bash
python -m pip install -e ".[serial]"
```

or install `pyserial` separately:

```bash
python -m pip install pyserial>=3.5
```

### 3.4 Development/test dependencies

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

---

## 4. Package import

The primary class is `PSB10000`:

```python
from ea_psb10000 import PSB10000
```

Common public objects can also be imported from the package root:

```python
from ea_psb10000 import (
    PSB10000,
    ArbitrarySequence,
    EventAction,
    ControllerSpeed,
    AfterState,
    MasterSlaveRole,
    PowerFlow,
    RegulationMode,
    RemoteOwner,
    ResistanceMode,
    PSBError,
    PSBConnectionError,
    PSBTimeoutError,
    PSBProtocolError,
    PSBValidationError,
    PSBRemoteControlError,
    PSBUnsupportedFeatureError,
    PSBSCPIError,
    PSBAlarmError,
)
```

---

## 5. Ethernet connection

The built-in EA Ethernet SCPI port defaults to TCP port 5025.

```python
from ea_psb10000 import PSB10000

with PSB10000.ethernet("192.168.13.17") as psb:
    print(psb.info)
    print(psb.ratings)
```

Equivalent explicit connection management:

```python
psb = PSB10000.ethernet(
    "192.168.13.17",
    port=5025,
    timeout=2.0,
    connect_timeout=5.0,
)

psb.connect()
try:
    print(psb.info)
finally:
    psb.close()
```

### Ethernet constructor arguments

| Argument | Default | Meaning |
|---|---:|---|
| `host` | required | IP address or hostname of the PSB |
| `port` | `5025` | TCP SCPI port |
| `timeout` | `2.0` s | Read/response timeout |
| `connect_timeout` | `5.0` s | Socket connection timeout |
| `check_errors_after_write` | `True` | Query the SCPI error queue after writes |
| `raise_on_alarm_after_write` | `True` | Raise `PSBAlarmError` when an alarm is active after a write |
| `write_settle_s` | `0.02` s | Delay before post-write status/error checks |
| `strict_model` | `True` | Reject a connected device that does not identify as a PSB 10000-family unit |
| `output_off_on_exit` | `False` | If enabled, try to switch output off during successful/error context cleanup |
| `release_remote_on_exit` | `False` | If enabled, release digital remote control during context cleanup |
| `logger` | standard logger | Optional custom `logging.Logger` |

A useful safety-oriented context manager is:

```python
with PSB10000.ethernet(
    "192.168.13.17",
    output_off_on_exit=True,
    release_remote_on_exit=True,
) as psb:
    psb.acquire_remote()
    # test operations
```

---

## 6. Serial / USB-COM connection

Install `pyserial` first, then use the serial constructor.

Windows:

```python
from ea_psb10000 import PSB10000

with PSB10000.serial("COM5", baudrate=115200, timeout=2.0) as psb:
    print(psb.info)
```

Linux:

```python
with PSB10000.serial("/dev/ttyUSB0", baudrate=115200) as psb:
    print(psb.info)
```

Serial/USB is especially useful when intentionally testing or changing Ethernet settings because changing the active IP address, DHCP state, port, or LAN timeout can terminate an Ethernet connection.

---

## 7. Connection lifecycle and remote control

### Check whether the transport is open

```python
print(psb.connected)
```

### Open and close

```python
psb.connect()
psb.close()
```

### Acquire digital remote control

```python
psb.acquire_remote()
```

Underlying SCPI:

```text
SYST:LOCK ON
SYST:LOCK:OWNER?
```

`acquire_remote()` verifies that the instrument actually reports `REMOTE` ownership.

### Verify remote control before a critical operation

```python
psb.require_remote()
```

### Read raw ownership state

```python
owner = psb.remote_owner_raw()
print(owner)
```

Underlying SCPI:

```text
SYST:LOCK:OWNER?
```

### Release remote control

```python
psb.release_remote()
```

Underlying SCPI:

```text
SYST:LOCK OFF
```

**Important:** the device setting `state_after_remote` controls what happens to the DC terminal when remote control is released.

---

## 8. Identification and nominal ratings

The driver automatically identifies the instrument and reads its nominal ratings when connecting.

```python
print(psb.info.manufacturer)
print(psb.info.model)
print(psb.info.serial_number)
print(psb.info.firmware)
print(psb.info.raw_idn)

print(psb.ratings.voltage)
print(psb.ratings.current)
print(psb.ratings.power)
print(psb.ratings.resistance_min)
print(psb.ratings.resistance_max)
```

SCPI commands:

| Purpose | SCPI |
|---|---|
| Identification | `*IDN?` |
| Nominal voltage | `SYST:NOM:VOLT?` |
| Nominal current | `SYST:NOM:CURR?` |
| Nominal power | `SYST:NOM:POW?` |
| Minimum nominal resistance | `SYST:NOM:RES:MIN?` |
| Maximum nominal resistance | `SYST:NOM:RES:MAX?` |

Refresh cached identity/ratings:

```python
psb.refresh_device_data()
```

---

## 9. Measurements

Read voltage, current, and power together:

```python
m = psb.measure()
print("Voltage:", m.voltage)
print("Current:", m.current)
print("Power:", m.power)
print("Flow:", m.flow)
```

The driver prefers:

```text
MEAS:ARR?
```

and falls back to:

```text
MEAS:VOLT?
MEAS:CURR?
MEAS:POW?
```

A simple polling loop:

```python
import time

with PSB10000.ethernet("192.168.13.17") as psb:
    while True:
        m = psb.measure()
        print(f"{m.voltage:8.3f} V  {m.current:8.3f} A  {m.power:9.2f} W  {m.flow}")
        time.sleep(0.5)
```

Sink operation may be represented by negative measured current and/or power depending on the instrument response.

---

## 10. DC terminal control

The driver never enables the DC terminal just because it connected.

Read state:

```python
print(psb.output.enabled)
```

Switch on:

```python
psb.output.on()
```

Switch off:

```python
psb.output.off()
```

Set from a Boolean:

```python
psb.output.set(True)
psb.output.set(False)
```

SCPI:

```text
OUTP?
OUTP ON
OUTP OFF
```

---

## 11. Source-mode setpoints

Read/write source voltage:

```python
print(psb.source.voltage)
psb.source.voltage = 32.0
```

SCPI:

```text
VOLT?
VOLT <value>
```

Read/write source current:

```python
print(psb.source.current)
psb.source.current = 18.0
```

SCPI:

```text
CURR?
CURR <value>
```

Read/write source power:

```python
print(psb.source.power)
psb.source.power = 600.0
```

SCPI:

```text
POW?
POW <value>
```

Read/write source resistance:

```python
print(psb.source.resistance)
psb.source.resistance = 5.0
```

SCPI:

```text
RES?
RES <value>
```

Set several values at once:

```python
psb.source.configure(
    voltage=32.0,
    current=18.0,
    power=600.0,
)
```

`configure()` sends separate commands in a deterministic order; it is not an atomic transaction. If a later command fails, earlier writes remain applied.

---

## 12. Sink-mode setpoints

Read/write sink current:

```python
print(psb.sink.current)
psb.sink.current = 10.0
```

SCPI:

```text
SINK:CURR?
SINK:CURR <value>
```

Read/write sink power:

```python
print(psb.sink.power)
psb.sink.power = 600.0
```

SCPI:

```text
SINK:POW?
SINK:POW <value>
```

Read/write sink resistance:

```python
print(psb.sink.resistance)
psb.sink.resistance = 5.0
```

SCPI:

```text
SINK:RES?
SINK:RES <value>
```

Configure several sink values:

```python
psb.sink.configure(
    current=10.0,
    power=600.0,
)
```

---

## 13. Source-only, sink-only, and bidirectional helpers

Force source-only behavior by setting sink current to zero:

```python
psb.source_only()
```

Force sink-only behavior by setting voltage setpoint to zero:

```python
psb.sink_only()
```

Restore explicit bidirectional settings:

```python
psb.bidirectional(voltage=32.0, sink_current=10.0)
```

These helpers only manipulate setpoints; they do not switch the DC terminal on.

---

## 14. Programmable protection

### OVP

```python
print(psb.protection.ovp)
psb.protection.ovp = 58.0
```

SCPI:

```text
VOLT:PROT?
VOLT:PROT <value>
```

### Source OCP

```python
print(psb.protection.source_ocp)
psb.protection.source_ocp = 20.0
```

SCPI:

```text
CURR:PROT?
CURR:PROT <value>
```

### Source OPP

```python
print(psb.protection.source_opp)
psb.protection.source_opp = 650.0
```

SCPI:

```text
POW:PROT?
POW:PROT <value>
```

### Sink OCP

```python
print(psb.protection.sink_ocp)
psb.protection.sink_ocp = 12.0
```

SCPI:

```text
SINK:CURR:PROT?
SINK:CURR:PROT <value>
```

### Sink OPP

```python
print(psb.protection.sink_opp)
psb.protection.sink_opp = 650.0
```

SCPI:

```text
SINK:POW:PROT?
SINK:POW:PROT <value>
```

Read all programmable protection settings:

```python
print(psb.protection.snapshot())
```

**Protection warning:** OVP/OCP/OPP are hard protective functions. Test software should not intentionally trip them unless the test plan explicitly requires it and the connected hardware is safe for the resulting shutdown behavior.

---

## 15. Adjustment limits

Read the current limit snapshot:

```python
limits = psb.limits.snapshot(refresh=True)
print(limits)
```

The snapshot includes:

```text
voltage_min
voltage_max
source_current_min
source_current_max
source_power_max
source_resistance_max
sink_current_min
sink_current_max
sink_power_max
sink_resistance_max
```

Set voltage limits:

```python
psb.limits.set_voltage(minimum=0.0, maximum=40.0)
```

Set source-current limits:

```python
psb.limits.set_source_current(minimum=0.0, maximum=18.0)
```

Set source-power maximum:

```python
psb.limits.set_source_power(600.0)
```

Set sink-current limits:

```python
psb.limits.set_sink_current(minimum=0.0, maximum=10.0)
```

Set sink-power maximum:

```python
psb.limits.set_sink_power(600.0)
```

Set resistance maxima:

```python
psb.limits.set_source_resistance_max(50.0)
psb.limits.set_sink_resistance_max(50.0)
```

SCPI reference:

| Python setting | Read SCPI | Write SCPI |
|---|---|---|
| Voltage minimum | `VOLT:LIM:LOW?` | `VOLT:LIM:LOW <value>` |
| Voltage maximum | `VOLT:LIM:HIGH?` | `VOLT:LIM:HIGH <value>` |
| Source current minimum | `CURR:LIM:LOW?` | `CURR:LIM:LOW <value>` |
| Source current maximum | `CURR:LIM:HIGH?` | `CURR:LIM:HIGH <value>` |
| Source power maximum | `POW:LIM:HIGH?` | `POW:LIM:HIGH <value>` |
| Source resistance maximum | `RES:LIM:HIGH?` | `RES:LIM:HIGH <value>` |
| Sink current minimum | `SINK:CURR:LIM:LOW?` | `SINK:CURR:LIM:LOW <value>` |
| Sink current maximum | `SINK:CURR:LIM:HIGH?` | `SINK:CURR:LIM:HIGH <value>` |
| Sink power maximum | `SINK:POW:LIM:HIGH?` | `SINK:POW:LIM:HIGH <value>` |
| Sink resistance maximum | `SINK:RES:LIM:HIGH?` | `SINK:RES:LIM:HIGH <value>` |

The driver caches the limit snapshot because every source/sink setter validates against it. A limit-setting call automatically invalidates the cache. You can explicitly invalidate it with:

```python
psb.limits.invalidate()
```

---

## 16. User supervision events

Supported source-side event names:

```text
UVD, UCD, OVD, OCD, OPD
```

Supported sink-side event names:

```text
UCD, OCD, OPD
```

Set/read a source threshold:

```python
psb.events.set_threshold("OVD", 34.0)
print(psb.events.get_threshold("OVD"))
```

Set/read an action:

```python
from ea_psb10000 import EventAction

psb.events.set_action("OVD", EventAction.WARNING)
print(psb.events.get_action("OVD"))
```

Configure threshold and action together:

```python
psb.events.configure(
    "OVD",
    threshold=34.0,
    action=EventAction.WARNING,
)
```

Sink example:

```python
psb.events.configure(
    "OCD",
    threshold=11.0,
    action=EventAction.WARNING,
    sink=True,
)
```

Source SCPI pattern:

```text
SYST:CONF:<EVENT>?
SYST:CONF:<EVENT> <threshold>
SYST:CONF:<EVENT>:ACT?
SYST:CONF:<EVENT>:ACT <NONE|SIGNAL|WARNING|ALARM>
```

Sink SCPI pattern:

```text
SYST:SINK:CONF:<EVENT>?
SYST:SINK:CONF:<EVENT> <threshold>
SYST:SINK:CONF:<EVENT>:ACT?
SYST:SINK:CONF:<EVENT>:ACT <NONE|SIGNAL|WARNING|ALARM>
```

An `ALARM` event action may switch the DC terminal off. Use it deliberately.

---

## 17. System configuration

### User text

```python
print(psb.system.user_text)
psb.system.user_text = "PCDU ATE"
```

SCPI:

```text
SYSTem:CONFig:USER:TEXT?
SYSTem:CONFig:USER:TEXT "<text>"
```

Maximum driver-accepted length: 40 characters.

### Resistance mode

```python
print(psb.system.resistance_mode)
psb.system.resistance_mode = "UIR"
psb.system.resistance_mode = "UIP"
```

SCPI:

```text
SYSTem:CONFig:MODe?
SYSTem:CONFig:MODe <UIP|UIR>
```

### State after remote control

```python
print(psb.system.state_after_remote)
psb.system.state_after_remote = "OFF"
# or
psb.system.state_after_remote = "AUTO"
```

SCPI:

```text
POWer:STAGe:AFTer:REMote?
POWer:STAGe:AFTer:REMote <OFF|AUTO>
```

### State after power-on

```python
print(psb.system.state_after_power_on)
psb.system.state_after_power_on = "OFF"
# HMI Restore behavior is represented by SCPI token AUTO.
psb.system.state_after_power_on = "AUTO"
```

SCPI:

```text
SYSTem:CONFig:OUTPut:RESTore?
SYSTem:CONFig:OUTPut:RESTore <OFF|AUTO>
```

### State after PF alarm

```python
print(psb.system.state_after_pf)
psb.system.state_after_pf = "OFF"
```

SCPI:

```text
SYSTem:ALARm:ACTion:PFAil?
SYSTem:ALARm:ACTion:PFAil <OFF|AUTO>
```

### State after OT alarm

```python
print(psb.system.state_after_ot)
psb.system.state_after_ot = "OFF"
```

SCPI:

```text
SYSTem:ALARm:ACTion:OTEMperature?
SYSTem:ALARm:ACTion:OTEMperature <OFF|AUTO>
```

### Voltage-controller speed

```python
from ea_psb10000 import ControllerSpeed

print(psb.system.voltage_controller_speed)
psb.system.voltage_controller_speed = ControllerSpeed.FAST
# or
psb.system.set_voltage_controller_speed("NORMAL")
```

SCPI:

```text
SYSTem:CONFig:CONTroller:SPEed?
SYSTem:CONFig:CONTroller:SPEed <SLOW|NORM|FAST>
```

### SEMI F47

```python
print(psb.system.semi_f47)
psb.system.semi_f47 = True
psb.system.set_semi_f47(False)
```

SCPI:

```text
SYSTem:CONFig:SEMif47?
SYSTem:CONFig:SEMif47 ENABle
SYSTem:CONFig:SEMif47 DISable
```

Availability depends on model/firmware/AC-input conditions.

### Clear status

```python
psb.system.clear_status()
```

SCPI:

```text
*CLS
```

### Reset

```python
psb.system.reset()
```

SCPI:

```text
*RST
```

The driver intentionally does not automatically check the error queue immediately after `*RST`. Reset can alter remote/output state and cached values. Treat reset as a disruptive command.

### Warm restart

`psb.system.restart()` currently raises `PSBUnsupportedFeatureError` because a warm-restart SCPI spelling has not been verified for this driver revision.

---

## 18. Status registers

### Basic condition registers

```python
print(psb.status.status_byte())
print(psb.status.questionable())
print(psb.status.secondary_questionable())
print(psb.status.operation())
```

SCPI:

```text
*STB?
STATus:QUEStionable:CONDition?
STATus:SECond:QUEStionable:CONDition?
STATus:OPERation:CONDition?
```

### Event registers

```python
print(psb.status.questionable_event())
print(psb.status.secondary_questionable_event())
print(psb.status.operation_event())
print(psb.status.event_status())
```

SCPI:

```text
STATus:QUEStionable:EVENt?
STATus:SECond:QUEStionable:EVENt?
STATus:OPERation:EVENt?
*ESR?
```

Reading event registers may clear/consume latched event information according to SCPI behavior. Do not poll them blindly if another process relies on those latches.

### Enable masks

```python
print(psb.status.questionable_enable)
psb.status.questionable_enable = 0xFFFF

print(psb.status.secondary_questionable_enable)
psb.status.secondary_questionable_enable = 0xFFFF

print(psb.status.operation_enable)
psb.status.operation_enable = 0xFFFF

print(psb.status.event_status_enable)
psb.status.event_status_enable = 0xFF

print(psb.status.service_request_enable)
psb.status.service_request_enable = 0xFF
```

SCPI:

```text
STATus:QUEStionable:ENABle?
STATus:QUEStionable:ENABle <0..65535>
STATus:SECond:QUEStionable:ENABle?
STATus:SECond:QUEStionable:ENABle <0..65535>
STATus:OPERation:ENABle?
STATus:OPERation:ENABle <0..65535>
*ESE?
*ESE <0..255>
*SRE?
*SRE <0..255>
```

### Decoded snapshot

```python
status = psb.status.snapshot(include_measurement_for_flow=True)

print(status.status_byte)
print(status.questionable)
print(status.secondary_questionable)
print(status.operation)
print(status.output_on)
print(status.remote_owner)
print(status.regulation_mode)
print(status.power_flow)
print(status.active_alarms)
print(status.active_events)
```

Decoded alarm names include:

```text
OVP, OCP, OPP, OT, PF, MSP, SF
```

Decoded user-event names include:

```text
OVD, UVD, OCD, UCD, OPD
```

Raise if an alarm is active:

```python
psb.status.raise_for_alarms()
```

---

## 19. Alarm counters

Read one counter:

```python
print(psb.status.alarm_counter("OVP"))
```

Read all available counters:

```python
print(psb.status.alarm_counters())
```

Supported names and SCPI commands:

| Name | SCPI |
|---|---|
| `OVP` | `SYSTem:ALARm:COUNt:OVOLtage?` |
| `OT` | `SYSTem:ALARm:COUNt:OTEMperature?` |
| `OPP` | `SYSTem:ALARm:COUNt:OPOWer?` |
| `OCP` | `SYSTem:ALARm:COUNt:OCURrent?` |
| `PF` | `SYSTem:ALARm:COUNt:PFAil?` |
| `SF` | `SYSTem:ALARm:COUNt:SHARebusfail?` |
| `SINK_OPP` | `SYSTem:SINK:ALARm:COUNt:OPOWer?` |
| `SINK_OCP` | `SYSTem:SINK:ALARm:COUNt:OCURrent?` |

`alarm_counters()` queries counters independently so one unsupported counter does not prevent the others from being read.

---

## 20. SCPI error handling

High-level writes call `write_scpi()` and, by default, perform post-write status and SCPI error checking.

Example:

```python
from ea_psb10000 import PSBSCPIError, PSBAlarmError

try:
    psb.source.voltage = 32.0
except PSBSCPIError as exc:
    print("Command:", exc.command)
    for error in exc.errors:
        print(error.code, error.message, error.raw)
except PSBAlarmError as exc:
    print("Active alarms:", exc.alarms)
```

### Read the next error

```python
record = psb.errors.next()
print(record.code, record.message)
```

SCPI:

```text
SYSTem:ERRor?
```

### Explicit NEXT form

```python
record = psb.errors.next_explicit()
```

SCPI:

```text
SYSTem:ERRor:NEXT?
```

### Drain until no error

```python
errors = psb.errors.drain(max_errors=16)
```

### Read ALL

```python
errors = psb.errors.all()
```

SCPI:

```text
SYSTem:ERRor:ALL?
```

### Raise if queue is non-empty

```python
psb.errors.raise_if_any(command="manual operation")
```

### Documented error-code catalog implemented by the driver

| Code | Driver description |
|---:|---|
| `0` | No error |
| `-100` | Command error |
| `-102` | Syntax error |
| `-108` | Parameter not allowed |
| `-200` | Execution error |
| `-201` | Invalid while in local |
| `-220` | Parameter error |
| `-221` | Settings conflict |
| `-222` | Data out of range |
| `-223` | Too much data |
| `-224` | Illegal parameter value |
| `-225` | Out of memory |
| `-999` | Safety OVP |

Get a copy of the catalog:

```python
print(psb.errors.known_errors())
```

**Important:** reading the EA error queue can acknowledge alarm information after the physical alarm cause has cleared. The driver therefore captures alarm condition registers before its automatic post-write error query.

---

## 21. Exception classes

| Exception | Meaning |
|---|---|
| `PSBError` | Base driver exception |
| `PSBConnectionError` | Transport cannot connect, disconnects, or is used while closed |
| `PSBTimeoutError` | SCPI response timed out |
| `PSBProtocolError` | Response could not be parsed or violated expected format |
| `PSBValidationError` | Local value validation failed before transmission |
| `PSBRemoteControlError` | Required remote ownership was not obtained or retained |
| `PSBUnsupportedFeatureError` | Feature/command deliberately not implemented because it is unverified or unavailable |
| `PSBSCPIError` | Instrument returned one or more SCPI error records |
| `PSBAlarmError` | Active PSB alarm detected after a write |

---

## 22. Analog-interface configuration

### Reference range

```python
print(psb.analog.range_volts)
psb.analog.range_volts = 5
psb.analog.range_volts = 10
```

SCPI:

```text
SYSTem:CONFig:ANALog:REFerence?
SYSTem:CONFig:ANALog:REFerence <5|10>
```

### Monitor routing

```python
print(psb.analog.monitor_mode)
psb.analog.monitor_mode = "DEFAULT"
```

Accepted values:

```text
DEFAULT, EL, PS, ELPS, PSEL, COMBINATION
```

SCPI:

```text
SYSTem:CONFig:ANALog:MONitor?
SYSTem:CONFig:ANALog:MONitor <mode>
```

### Pin 6 routing

```python
psb.analog.set_pin6("ALL")
```

Accepted:

```text
OT, PF, ALL
```

SCPI:

```text
SYSTem:CONFig:ANALog:PIN6 <value>
```

### Pin 14 routing

```python
psb.analog.set_pin14("ALL")
```

Accepted:

```text
OVP, OCP, OPP, OVP/OCP, OVP/OPP, OCP/OPP, ALL
```

SCPI:

```text
SYSTem:CONFig:ANALog:PIN14 <value>
```

### Pin 15 routing

```python
psb.analog.set_pin15("POW")
```

Accepted:

```text
CONT, POW
```

SCPI:

```text
SYSTem:CONFig:ANALog:PIN15 <value>
```

### REM-SB logic level

```python
print(psb.analog.rem_sb_level)
psb.analog.rem_sb_level = "NORMAL"
psb.analog.rem_sb_level = "INVERTED"
```

SCPI:

```text
SYSTem:CONFig:ANALog:REMSb:LEVel?
SYSTem:CONFig:ANALog:REMSb:LEVel <NORMAL|INVERTED>
```

### REM-SB action

```python
print(psb.analog.rem_sb_action)
psb.analog.rem_sb_action = "OFF"
psb.analog.rem_sb_action = "AUTO"
```

SCPI:

```text
SYSTem:CONFig:ANALog:REMSb:ACTion?
SYSTem:CONFig:ANALog:REMSb:ACTion <OFF|AUTO>
```

---

## 23. Communications subsystem

The communications API contains both the built-in Ethernet interface and optional communication-module settings. Commands that only apply to an installed option may fail or be unsupported when no option module is present.

### 23.1 Serial/USB inter-byte timeout

```python
print(psb.communications.serial_message_timeout_ms)
psb.communications.serial_message_timeout_ms = 10
```

SCPI:

```text
SYSTem:COMMunicate:TIMeout?
SYSTem:COMMunicate:TIMeout <5..65535 ms>
```

This setting is for USB/RS232 message timing; it is not the Ethernet socket timeout.

### 23.2 ModBus protocol enable

```python
print(psb.communications.modbus_enabled)
psb.communications.modbus_enabled = True
psb.communications.set_modbus_enabled(False)
```

SCPI:

```text
SYSTem:COMMunicate:PROTocol:MODBus?
SYSTem:COMMunicate:PROTocol:MODBus ENABle
SYSTem:COMMunicate:PROTocol:MODBus DISable
```

### 23.3 Optional-interface identification

```python
print(psb.communications.interface_code)
print(psb.communications.interface_type)
print(psb.communications.interface_serial)
print(psb.communications.interface_baud_index)
print(psb.communications.interface_address)
```

SCPI:

```text
SYSTem:COMMunicate:INTerface:CODe?
SYSTem:COMMunicate:INTerface:TYPe?
SYSTem:COMMunicate:INTerface:SERial?
SYSTem:COMMunicate:INTerface:BAUD?
SYSTem:COMMunicate:INTerface:ADDRess?
```

Write optional-interface settings:

```python
psb.communications.interface_baud_index = 3
psb.communications.set_interface_address(5)
```

SCPI:

```text
SYSTem:COMMunicate:INTerface:BAUD <0..9>
SYSTem:COMMunicate:INTerface:ADDRess <1..127>
```

### 23.4 Profibus/Profinet-style tags

```python
psb.communications.set_function_tag("PSB-A")
psb.communications.set_location_tag("LAB-1")
psb.communications.set_installation_date("2026-10-26")
psb.communications.set_interface_description("Power Supply Bench")
psb.communications.set_station_name("psb10060-60")
```

SCPI:

```text
SYSTem:COMMunicate:PROFibus:FTAG "<text>"
SYSTem:COMMunicate:PROFibus:LTAG "<text>"
SYSTem:COMMunicate:PROFibus:DATe "<text>"
SYSTem:COMMunicate:PROFibus:DESCription "<text>"
SYSTem:COMMunicate:PROFibus:NAMe "<text>"
```

Driver text limits:

| Field | Maximum characters |
|---|---:|
| Function tag | 32 |
| Location tag | 22 |
| Installation date | 40 |
| Interface description | 54 |
| Station name | 200 |

### 23.5 CAN configuration

```python
psb.communications.configure_can(
    node_id=0x100,
    broadcast_id=0x200,
    extended_id=False,
    dlc_always_8=True,
    termination=True,
)
```

SCPI:

```text
SYSTem:COMMunicate:CAN:FORMat <BASE|EXT>
SYSTem:COMMunicate:CAN:NODe <id>
SYSTem:COMMunicate:CAN:BROadcast <id>
SYSTem:COMMunicate:CAN:DLC <AUTO|FILL>
SYSTem:COMMunicate:CAN:TERMination <ON|OFF>
```

Cyclic read setup:

```python
psb.communications.set_can_cyclic_read_ms("ACTUAL", 100)
psb.communications.set_can_cyclic_read_ms("STATUS", 100)
psb.communications.set_can_cyclic_read_ms("ACTUAL", 0)  # disable
```

Supported cyclic groups:

```text
ACTUAL
LIMITS_UI
LIMITS_PR
SINK_LIMITS
SETPOINTS
SINK_SETPOINTS
STATUS
```

Interval must be `0` (off) or 20..5000 ms.

CAN read/send base IDs:

```python
psb.communications.set_can_read_base_id(0x100)
psb.communications.set_can_send_base_id(0x200)
```

SCPI:

```text
SYSTem:COMMunicate:CAN:READ:NODe <id>
SYSTem:COMMunicate:CAN:SEND:NODe <id>
```

---

## 24. Ethernet/LAN configuration

Select the interface whose LAN settings are being addressed:

```python
psb.communications.select_lan(2)
print(psb.communications.lan_index)
```

The built-in RJ45 is normally LAN index 2 on PSB 10000 hardware; index 1 is used for an applicable slot interface.

SCPI:

```text
SYSTem:COMMunicate:LAN:INDex <1|2>
SYSTem:COMMunicate:LAN:INDex?
```

### IP address

```python
print(psb.communications.ip_address)
psb.communications.ip_address = "192.168.13.17"
```

```text
SYSTem:COMMunicate:LAN:ADDRess?
SYSTem:COMMunicate:LAN:ADDRess <address>
```

### Subnet mask

```python
print(psb.communications.subnet_mask)
psb.communications.subnet_mask = "255.255.255.0"
```

```text
SYSTem:COMMunicate:LAN:SMASk?
SYSTem:COMMunicate:LAN:SMASk <mask>
```

### Gateway

```python
print(psb.communications.gateway)
psb.communications.gateway = "192.168.13.1"
```

```text
SYSTem:COMMunicate:LAN:GATeway?
SYSTem:COMMunicate:LAN:GATeway <address>
```

### TCP control port

```python
print(psb.communications.tcp_port)
psb.communications.tcp_port = 5025
```

```text
SYSTem:COMMunicate:LAN:CONTrol?
SYSTem:COMMunicate:LAN:CONTrol <0..65535>
```

The driver rejects reserved ports 502 and 537.

### DHCP

```python
print(psb.communications.dhcp)
psb.communications.dhcp = False
```

```text
SYSTem:COMMunicate:LAN:DHCP?
SYSTem:COMMunicate:LAN:DHCP <ON|OFF>
```

### TCP keepalive

```python
print(psb.communications.keepalive)
psb.communications.keepalive = True
```

```text
SYSTem:COMMunicate:LAN:KEEPalive?
SYSTem:COMMunicate:LAN:KEEPalive <ON|OFF>
```

### Ethernet socket timeout

```python
print(psb.communications.ethernet_timeout_s)
psb.communications.ethernet_timeout_s = 30
```

```text
SYSTem:COMMunicate:LAN:TIMeout?
SYSTem:COMMunicate:LAN:TIMeout <0 or 5..65535 s>
```

`0` disables the timeout.

### Hostname

```python
print(psb.communications.hostname)
psb.communications.hostname = "psb10060"
```

```text
SYSTem:COMMunicate:LAN:HOSTname?
SYSTem:COMMunicate:LAN:HOSTname "<name>"
```

Driver limit: 1..54 characters.

### Domain

```python
print(psb.communications.domain)
psb.communications.domain = "lab.local"
```

```text
SYSTem:COMMunicate:LAN:DOMain?
SYSTem:COMMunicate:LAN:DOMain "<domain>"
```

Driver limit: 54 characters.

### MAC address

```python
print(psb.communications.mac_address)
```

```text
SYSTem:COMMunicate:LAN:MAC?
```

### DNS

```python
psb.communications.set_dns("192.168.13.1")
psb.communications.set_dns("192.168.13.1", "8.8.8.8")
```

```text
SYSTem:COMMunicate:LAN:DNS1 <address>
SYSTem:COMMunicate:LAN:DNS2 <address>
```

**Network-setting warning:** changing IP address, DHCP, TCP port, subnet, gateway, or timeout while connected through that same Ethernet interface can intentionally break the current session. Prefer changing/testing mutable LAN settings while controlling the supply through serial/USB.

---

## 25. Interface-monitoring watchdog

EA interface monitoring can exit remote control if communication stops for too long. The Python driver also offers an optional host heartbeat that periodically sends `*STB?`.

Read/write instrument monitor state:

```python
print(psb.watchdog.enabled)
psb.watchdog.enabled = True
```

SCPI:

```text
SYST:COMM:MON:ACT?
SYST:COMM:MON:ACT <ON|OFF>
```

Read/write timeout:

```python
print(psb.watchdog.timeout_s)
psb.watchdog.timeout_s = 5
```

SCPI:

```text
SYST:COMM:MON:TIME?
SYST:COMM:MON:TIME <1..36000 s>
```

Configure monitor and Python heartbeat together:

```python
psb.system.state_after_remote = "OFF"
psb.watchdog.configure(
    enabled=True,
    timeout_s=5,
    heartbeat=True,
    heartbeat_interval_s=1.0,
)
```

Inspect heartbeat state:

```python
print(psb.watchdog.heartbeat_running)
print(psb.watchdog.last_error)
```

Manual heartbeat:

```python
status_byte = psb.watchdog.ping()
```

Start/stop host heartbeat directly:

```python
psb.watchdog.start_heartbeat(1.0)
psb.watchdog.stop_heartbeat()
```

The heartbeat changes no setpoint and does not toggle the output. It sends only `*STB?`.

---

## 26. Diagnostics and accumulated counters

```python
print(psb.diagnostics.device_class)
print(psb.diagnostics.operation_hours)
print(psb.diagnostics.dc_on_hours)
print(psb.diagnostics.dc_off_hours)
print(psb.diagnostics.source_amp_hours)
print(psb.diagnostics.source_kilowatt_hours)
print(psb.diagnostics.sink_amp_hours)
print(psb.diagnostics.sink_kilowatt_hours)
```

SCPI:

| Python property | SCPI |
|---|---|
| `device_class` | `SYST:DEV:CLASS?` |
| `operation_hours` | `DIAG:INF:DEV:OTIM?` |
| `dc_on_hours` | `DIAG:INF:DEV:ONT?` |
| `dc_off_hours` | `DIAG:INF:DEV:OFFT?` |
| `source_amp_hours` | `FETC:AHO?` |
| `source_kilowatt_hours` | `FETC:WHO?` |
| `sink_amp_hours` | `FETC:SINK:AHO?` |
| `sink_kilowatt_hours` | `FETC:SINK:WHO?` |

---

## 27. Master/slave operation

Read/write enable state:

```python
print(psb.master_slave.enabled)
psb.master_slave.enabled = True
```

```text
SYSTem:MS:ENABle?
SYSTem:MS:ENABle <ON|OFF>
```

Role:

```python
print(psb.master_slave.role)
psb.master_slave.role = "MASTER"
```

```text
SYSTem:MS:LINK?
SYSTem:MS:LINK <MASTER|SLAVE>
```

Termination:

```python
print(psb.master_slave.termination)
psb.master_slave.termination = True
```

```text
SYSTem:MS:TERMination?
SYSTem:MS:TERMination <ON|OFF>
```

Bias:

```python
print(psb.master_slave.bias)
psb.master_slave.bias = True
```

```text
SYSTem:MS:BIAS?
SYSTem:MS:BIAS <ON|OFF>
```

Initialize:

```python
condition = psb.master_slave.initialize()
print(condition)
```

```text
SYSTem:MS:INITialisation
SYSTem:MS:CONDition?
```

Read initialized unit count:

```python
print(psb.master_slave.units)
```

```text
SYSTem:MS:UNITs?
```

**Master/slave warning:** changing role, termination, bias, enable state, or initialization changes system topology/behavior. The hardware verifier does not perform these writes unless explicitly enabled.

---

## 28. Function generator: arbitrary waveform

The function generator is intentionally a separately gated feature because configuring it overwrites existing function-generator setup.

Create a sequence:

```python
from ea_psb10000 import ArbitrarySequence

seq = ArbitrarySequence(
    start_amplitude=0.0,
    end_amplitude=0.0,
    start_frequency_hz=0.0,
    end_frequency_hz=0.0,
    start_angle_deg=0.0,
    start_level=0.0,
    end_level=32.0,
    sequence_time_s=1.0,
)
```

Upload:

```python
psb.function_generator.configure_arbitrary(
    [seq],
    target="VOLTAGE",
    cycles=1,
    start_sequence=1,
    submit_delay_s=2.0,
    verify_each_value=False,
    check_each_write=False,
)
```

Start/stop:

```python
psb.function_generator.run()
print(psb.function_generator.state)
psb.function_generator.stop()
psb.function_generator.exit()
```

Principal SCPI commands:

```text
FUNC:GEN:SEL NONE
FUNC:GEN:SEL VOLTAGE
FUNC:GEN:SEL CURRENT
FUNC:GEN:WAVE:STAR <sequence>
FUNC:GEN:WAVE:END <sequence>
FUNC:GEN:WAVE:NUM <cycles>
FUNC:GEN:WAVE:LEV <sequence>
FUNC:GEN:WAVE:IND <index>
FUNC:GEN:WAVE:DATA <value>
FUNC:GEN:WAVE:DATA?
FUNC:GEN:WAVE:SUBM
FUNC:GEN:WAVE:STAT RUN
FUNC:GEN:WAVE:STAT STOP
FUNC:GEN:WAVE:STAT?
```

Driver validation includes:

```text
1..99 sequences
0..999 cycles (0 = infinite)
0..10000 Hz frequency
0..359 degrees start angle
0.0001..36000 seconds sequence time
amplitude/level ranges checked against connected-unit nominal ratings
```

`check_each_write=False` is intentionally the default for bulk function data because checking the SCPI error queue after every table field is slow. Input values are validated locally and the submit operation is checked. Use `check_each_write=True` when debugging a command-by-command bench problem.

---

## 29. Function generator: XY tables

Upload an XY table:

```python
values = [0.0, 1.0, 2.0, 3.0]

psb.function_generator.load_xy(
    "IU",
    values,
    second_table=False,
    submit_delay_s=2.0,
)
```

Supported driver mode tokens:

```text
FC, IUPS, IUEL, IU, PV, PVA, PVB
```

Table length:

```text
1..4096 values
```

Principal SCPI:

```text
FUNC:GEN:SEL <mode>
FUNC:GEN:XY:LEV <index>
FUNC:GEN:XY:DATA <value>
FUNC:GEN:XY:SEC:LEV <index>
FUNC:GEN:XY:SEC:DATA <value>
FUNC:GEN:XY:SUBM FIRST
FUNC:GEN:XY:SUBM SECOND
```

---

## 30. Newer firmware features that are not guessed

The supplied 2025 user manual documents newer HMI features whose exact digital SCPI spellings were not present in the programming-guide revision used to verify this driver:

```text
Fast discharge enable / voltage / current / duration
Actual-value filter mode / buffer size
STBY zero stabilization
```

The driver deliberately does **not** invent SCPI commands for these features. Instead, `psb.extensions` lets a site register exact commands after they are verified against the firmware-specific programming guide.

Example registration:

```python
psb.extensions.register(
    "fast_discharge",
    set_command="<verified command>",
    query_command="<verified query>",
)
```

Register related parameters the same way, then use the validated high-level helper:

```python
psb.extensions.configure_fast_discharge(
    enabled=True,
    voltage=5.0,
    current=10.0,
    duration_ms=1000,
)
```

Other extension helpers:

```python
psb.extensions.configure_actual_value_filter(
    mode="MOVING",
    buffer_size=8,
)

psb.extensions.set_stby_zero_stabilization(True)
```

Direct registered access:

```python
psb.extensions.set_raw_registered("my_setting", 123)
print(psb.extensions.query_registered("my_setting"))
```

This registration mechanism preserves a strict no-guess policy while still allowing new firmware features to be used without modifying the driver core.

---

## 31. Raw SCPI access

Any verified or future SCPI command can be sent directly.

Query:

```python
print(psb.query_scpi("*IDN?"))
```

Write with normal post-write checking:

```python
psb.write_scpi("VOLT 32")
```

Write without automatic error checking:

```python
psb.write_scpi("<command>", check_errors=False)
```

Use `check_errors=False` only when your application intentionally owns the error-queue handling. A normal high-level write should keep error checking enabled.

---

## 32. Logging

The driver uses Python's standard `logging` package.

```python
import logging

logging.basicConfig(level=logging.DEBUG)

with PSB10000.ethernet("192.168.13.17") as psb:
    print(psb.info)
```

Or supply a custom logger:

```python
logger = logging.getLogger("my_psb_test")
psb = PSB10000.ethernet("192.168.13.17", logger=logger)
```

DEBUG logging includes SCPI command/query traffic from the driver transaction layer.

---

## 33. Connection-loss behavior

The driver deliberately does not automatically replay a state-changing command after a transport failure.

Example:

```python
from ea_psb10000 import PSBConnectionError

try:
    psb.source.voltage = 32.0
except PSBConnectionError:
    # The write may or may not have reached the hardware.
    # Reconnect and READ the actual state before deciding what to do next.
    raise
```

This is intentional. Replaying an output transition, setpoint transition, reset, or protection change when the first write may already have succeeded can cause an unintended second transition.

---

## 34. Ping / connection health

A simple non-mutating health check:

```python
if psb.ping():
    print("PSB responding")
```

`ping()` sends `*IDN?` and returns `False` on communication/protocol failure.

For an interface-monitor heartbeat, prefer `psb.watchdog.ping()`, which sends only `*STB?`.

---

## 35. Hardware-free tests with `ScriptedTransport`

The package includes a deterministic in-memory transport for unit tests.

```python
from ea_psb10000 import PSB10000
from ea_psb10000.testing import ScriptedTransport

transport = ScriptedTransport({
    "*IDN?": "EA Elektro-Automatik GmbH & Co. KG,PSB 10060-60,123456,V4.10",
    "SYST:NOM:VOLT?": "60",
    "SYST:NOM:CURR?": "60",
    "SYST:NOM:POW?": "1500",
    "SYST:NOM:RES:MIN?": "0.04",
    "SYST:NOM:RES:MAX?": "80",
})

psb = PSB10000(transport)
psb.connect()
try:
    print(psb.info)
    print(psb.ratings)
finally:
    psb.close()
```

Every write/query is recorded in:

```python
print(transport.commands)
```

This lets application code verify exactly what SCPI traffic it would generate without energizing hardware.

---

## 36. Hardware command verifier

The project includes:

```text
examples/verify_psb_commands.py
```

The verifier is designed for bench checkout of the driver against a real PSB. For most writable settings it performs:

```text
1. Read original value.
2. Capture relevant status.
3. Write a safe alternate value.
4. Query the value back.
5. Compare using a realistic instrument-resolution tolerance.
6. Capture status again and log status-register changes.
7. Restore the original value.
8. Query the restored value.
9. Record PASS / FAIL / SKIP / INFO plus error details.
```

The verifier forces the DC terminal OFF before ordinary setting tests.

### 36.1 Normal Ethernet verification

```bash
python examples/verify_psb_commands.py \
    --host 192.168.13.17 \
    --verbose \
    --release-remote
```

Default reports:

```text
psb_command_check.csv
psb_command_check.json
```

### 36.2 Serial/USB verification

Windows:

```bat
py -3.8 examples\verify_psb_commands.py --serial COM5 --verbose --release-remote
```

Linux:

```bash
python3.8 examples/verify_psb_commands.py \
    --serial /dev/ttyUSB0 \
    --verbose \
    --release-remote
```

### 36.3 Verifier options

| Option | Purpose / safety effect |
|---|---|
| `--host HOST` | Use Ethernet |
| `--serial PORT` | Use serial/USB-COM |
| `--port PORT` | Ethernet SCPI port, default 5025 |
| `--baudrate BAUD` | Serial baud rate, default 115200 |
| `--timeout SEC` | SCPI response timeout |
| `--connect-timeout SEC` | Ethernet connect timeout |
| `--write-settle SEC` | Delay before post-write status/error check |
| `--output-toggle` | Permit an actual OUTP ON/OFF test after configuring benign output values |
| `--network-settings` | Permit mutable LAN-setting tests; disruptive writes are intended for serial/USB control |
| `--optional-interface` | Permit writes to an installed optional communication module |
| `--watchdog` | Permit interface-monitor timeout/enable changes |
| `--master-slave` | Permit master/slave setting changes |
| `--master-slave-init` | Permit master/slave initialization; implies topology-changing behavior |
| `--function-generator` | Permit destructive function-generator configuration testing |
| `--clear-status` | Permit `*CLS` |
| `--reset` | Permit `*RST` at the end of the run |
| `--release-remote` | Release remote control on exit if the verifier acquired it |
| `--no-error-injection` | Disable safe live invalid-command probes |
| `--deep-error-injection` | Also attempt documented response-buffer overflow error coverage; never deliberately induces Safety OVP |
| `--test-ip` | Alternate IP for serial-controlled write/read/restore test |
| `--test-mask` | Alternate subnet mask for serial-controlled write/read/restore test |
| `--test-gateway` | Alternate gateway for serial-controlled write/read/restore test |
| `--test-tcp-port` | Alternate TCP port for serial-controlled write/read/restore test |
| `--test-dns` | Alternate DNS values for serial-controlled test |
| `--csv PATH` | CSV output path; empty string disables |
| `--json PATH` | JSON output path; empty string disables |
| `--verbose` | Print detailed failure/skip diagnostics inline |

### 36.4 Error testing performed by the verifier

The verifier exercises software parsing/exception coverage for every driver-listed error code. It can also perform safe live invalid-command probes against the instrument.

It deliberately does **not** create Safety OVP (`-999`) because that is a physical protective condition and may require a power cycle. Software handling for the code is still tested.

The deeper `-225` response-buffer-overflow exercise is gated behind `--deep-error-injection`.

### 36.5 Why some commands are SKIP

A SKIP is not automatically a failure. Examples include:

```text
optional-interface command when no option module is installed
serial-only timeout during an Ethernet verification run
network writes while the active transport is Ethernet
master/slave initialization unless explicitly enabled
function-generator configuration unless explicitly enabled
newer firmware extension commands that have not been locally registered
```

---

## 37. Complete high-level API / SCPI mapping

This table is a compact reference for the principal public driver calls. Sections above contain detailed examples and safety notes.

### Core device

| Python API | SCPI / behavior |
|---|---|
| `psb.info` | `*IDN?` |
| `psb.ratings` | `SYST:NOM:VOLT?`, `CURR?`, `POW?`, resistance MIN/MAX |
| `psb.acquire_remote()` | `SYST:LOCK ON`, then owner verification |
| `psb.release_remote()` | `SYST:LOCK OFF`, then owner verification |
| `psb.remote_owner_raw()` | `SYST:LOCK:OWNER?` |
| `psb.measure()` | `MEAS:ARR?`, fallback individual measurement queries |
| `psb.query_scpi(cmd)` | Raw query |
| `psb.write_scpi(cmd)` | Raw write with configurable post-write checking |
| `psb.ping()` | `*IDN?` |

### Output and setpoints

| Python API | Read SCPI | Write SCPI |
|---|---|---|
| `psb.output.enabled` | `OUTP?` | — |
| `psb.output.on()` | — | `OUTP ON` |
| `psb.output.off()` | — | `OUTP OFF` |
| `psb.source.voltage` | `VOLT?` | `VOLT <value>` |
| `psb.source.current` | `CURR?` | `CURR <value>` |
| `psb.source.power` | `POW?` | `POW <value>` |
| `psb.source.resistance` | `RES?` | `RES <value>` |
| `psb.sink.current` | `SINK:CURR?` | `SINK:CURR <value>` |
| `psb.sink.power` | `SINK:POW?` | `SINK:POW <value>` |
| `psb.sink.resistance` | `SINK:RES?` | `SINK:RES <value>` |

### Protection

| Python API | Read SCPI | Write SCPI |
|---|---|---|
| `protection.ovp` | `VOLT:PROT?` | `VOLT:PROT <value>` |
| `protection.source_ocp` | `CURR:PROT?` | `CURR:PROT <value>` |
| `protection.source_opp` | `POW:PROT?` | `POW:PROT <value>` |
| `protection.sink_ocp` | `SINK:CURR:PROT?` | `SINK:CURR:PROT <value>` |
| `protection.sink_opp` | `SINK:POW:PROT?` | `SINK:POW:PROT <value>` |

### Limits

| Python API | SCPI |
|---|---|
| `limits.set_voltage()` | `VOLT:LIM:LOW/HIGH` |
| `limits.set_source_current()` | `CURR:LIM:LOW/HIGH` |
| `limits.set_source_power()` | `POW:LIM:HIGH` |
| `limits.set_source_resistance_max()` | `RES:LIM:HIGH` |
| `limits.set_sink_current()` | `SINK:CURR:LIM:LOW/HIGH` |
| `limits.set_sink_power()` | `SINK:POW:LIM:HIGH` |
| `limits.set_sink_resistance_max()` | `SINK:RES:LIM:HIGH` |

### Events

| Python API | SCPI pattern |
|---|---|
| Source event threshold | `SYST:CONF:<EVENT>` / `?` |
| Source event action | `SYST:CONF:<EVENT>:ACT` / `?` |
| Sink event threshold | `SYST:SINK:CONF:<EVENT>` / `?` |
| Sink event action | `SYST:SINK:CONF:<EVENT>:ACT` / `?` |

### System

| Python API | SCPI |
|---|---|
| `system.user_text` | `SYSTem:CONFig:USER:TEXT` / `?` |
| `system.resistance_mode` | `SYSTem:CONFig:MODe` / `?` |
| `system.state_after_remote` | `POWer:STAGe:AFTer:REMote` / `?` |
| `system.state_after_power_on` | `SYSTem:CONFig:OUTPut:RESTore` / `?` |
| `system.state_after_pf` | `SYSTem:ALARm:ACTion:PFAil` / `?` |
| `system.state_after_ot` | `SYSTem:ALARm:ACTion:OTEMperature` / `?` |
| `system.voltage_controller_speed` | `SYSTem:CONFig:CONTroller:SPEed` / `?` |
| `system.semi_f47` | `SYSTem:CONFig:SEMif47` / `?` |
| `system.clear_status()` | `*CLS` |
| `system.reset()` | `*RST` |

### Status

| Python API | SCPI |
|---|---|
| `status.status_byte()` | `*STB?` |
| `status.event_status()` | `*ESR?` |
| `status.event_status_enable` | `*ESE` / `?` |
| `status.service_request_enable` | `*SRE` / `?` |
| `status.questionable()` | `STATus:QUEStionable:CONDition?` |
| `status.questionable_event()` | `STATus:QUEStionable:EVENt?` |
| `status.questionable_enable` | `STATus:QUEStionable:ENABle` / `?` |
| `status.secondary_questionable()` | `STATus:SECond:QUEStionable:CONDition?` |
| `status.secondary_questionable_event()` | `STATus:SECond:QUEStionable:EVENt?` |
| `status.secondary_questionable_enable` | `STATus:SECond:QUEStionable:ENABle` / `?` |
| `status.operation()` | `STATus:OPERation:CONDition?` |
| `status.operation_event()` | `STATus:OPERation:EVENt?` |
| `status.operation_enable` | `STATus:OPERation:ENABle` / `?` |

### Error queue

| Python API | SCPI |
|---|---|
| `errors.next()` | `SYSTem:ERRor?` |
| `errors.next_explicit()` | `SYSTem:ERRor:NEXT?` |
| `errors.all()` | `SYSTem:ERRor:ALL?` |
| `errors.drain()` | repeated `SYSTem:ERRor?` |

### Analog

| Python API | SCPI |
|---|---|
| `analog.range_volts` | `SYSTem:CONFig:ANALog:REFerence` / `?` |
| `analog.monitor_mode` | `SYSTem:CONFig:ANALog:MONitor` / `?` |
| `analog.set_pin6()` | `SYSTem:CONFig:ANALog:PIN6` |
| `analog.set_pin14()` | `SYSTem:CONFig:ANALog:PIN14` |
| `analog.set_pin15()` | `SYSTem:CONFig:ANALog:PIN15` |
| `analog.rem_sb_level` | `SYSTem:CONFig:ANALog:REMSb:LEVel` / `?` |
| `analog.rem_sb_action` | `SYSTem:CONFig:ANALog:REMSb:ACTion` / `?` |

### Communications/LAN

| Python API | SCPI |
|---|---|
| `communications.serial_message_timeout_ms` | `SYSTem:COMMunicate:TIMeout` / `?` |
| `communications.modbus_enabled` | `SYSTem:COMMunicate:PROTocol:MODBus` / `?` |
| `communications.interface_code` | `SYSTem:COMMunicate:INTerface:CODe?` |
| `communications.interface_type` | `SYSTem:COMMunicate:INTerface:TYPe?` |
| `communications.interface_serial` | `SYSTem:COMMunicate:INTerface:SERial?` |
| `communications.interface_baud_index` | `SYSTem:COMMunicate:INTerface:BAUD` / `?` |
| `communications.interface_address` | `SYSTem:COMMunicate:INTerface:ADDRess` / `?` |
| `communications.select_lan()` | `SYSTem:COMMunicate:LAN:INDex` |
| `communications.lan_index` | `SYSTem:COMMunicate:LAN:INDex?` |
| `communications.ip_address` | `SYSTem:COMMunicate:LAN:ADDRess` / `?` |
| `communications.subnet_mask` | `SYSTem:COMMunicate:LAN:SMASk` / `?` |
| `communications.gateway` | `SYSTem:COMMunicate:LAN:GATeway` / `?` |
| `communications.tcp_port` | `SYSTem:COMMunicate:LAN:CONTrol` / `?` |
| `communications.dhcp` | `SYSTem:COMMunicate:LAN:DHCP` / `?` |
| `communications.keepalive` | `SYSTem:COMMunicate:LAN:KEEPalive` / `?` |
| `communications.ethernet_timeout_s` | `SYSTem:COMMunicate:LAN:TIMeout` / `?` |
| `communications.hostname` | `SYSTem:COMMunicate:LAN:HOSTname` / `?` |
| `communications.domain` | `SYSTem:COMMunicate:LAN:DOMain` / `?` |
| `communications.mac_address` | `SYSTem:COMMunicate:LAN:MAC?` |
| `communications.set_dns()` | `SYSTem:COMMunicate:LAN:DNS1/DNS2` |

### Watchdog

| Python API | SCPI |
|---|---|
| `watchdog.enabled` | `SYST:COMM:MON:ACT` / `?` |
| `watchdog.timeout_s` | `SYST:COMM:MON:TIME` / `?` |
| `watchdog.ping()` | `*STB?` |

### Diagnostics

| Python API | SCPI |
|---|---|
| `diagnostics.device_class` | `SYST:DEV:CLASS?` |
| `diagnostics.operation_hours` | `DIAG:INF:DEV:OTIM?` |
| `diagnostics.dc_on_hours` | `DIAG:INF:DEV:ONT?` |
| `diagnostics.dc_off_hours` | `DIAG:INF:DEV:OFFT?` |
| `diagnostics.source_amp_hours` | `FETC:AHO?` |
| `diagnostics.source_kilowatt_hours` | `FETC:WHO?` |
| `diagnostics.sink_amp_hours` | `FETC:SINK:AHO?` |
| `diagnostics.sink_kilowatt_hours` | `FETC:SINK:WHO?` |

### Master/slave

| Python API | SCPI |
|---|---|
| `master_slave.enabled` | `SYSTem:MS:ENABle` / `?` |
| `master_slave.role` | `SYSTem:MS:LINK` / `?` |
| `master_slave.termination` | `SYSTem:MS:TERMination` / `?` |
| `master_slave.bias` | `SYSTem:MS:BIAS` / `?` |
| `master_slave.initialize()` | `SYSTem:MS:INITialisation` |
| `master_slave.condition` | `SYSTem:MS:CONDition?` |
| `master_slave.units` | `SYSTem:MS:UNITs?` |

---

## 38. Example: safe 32 V source configuration

```python
from ea_psb10000 import PSB10000

with PSB10000.ethernet(
    "192.168.13.17",
    output_off_on_exit=True,
    release_remote_on_exit=True,
) as psb:
    psb.acquire_remote()

    # Configure while output is still OFF.
    psb.source.configure(voltage=32.0, current=18.0, power=600.0)
    psb.sink.configure(current=10.0, power=600.0)

    psb.protection.ovp = 58.0
    psb.protection.source_ocp = 20.0
    psb.protection.source_opp = 650.0
    psb.protection.sink_ocp = 12.0
    psb.protection.sink_opp = 650.0

    psb.system.voltage_controller_speed = "FAST"

    # Explicitly energize only after all settings are established.
    psb.output.on()

    print(psb.measure())
    print(psb.status.snapshot(include_measurement_for_flow=True))

    psb.output.off()
```

---

## 39. Example: robust measurement/application loop

```python
import time
from ea_psb10000 import PSB10000, PSBConnectionError, PSBAlarmError

with PSB10000.ethernet(
    "192.168.13.17",
    output_off_on_exit=True,
    release_remote_on_exit=True,
) as psb:
    psb.acquire_remote()
    psb.source.configure(voltage=32.0, current=18.0, power=600.0)

    while True:
        try:
            status = psb.status.snapshot(include_measurement_for_flow=True)
            measurement = psb.measure()

            print(
                measurement.voltage,
                measurement.current,
                measurement.power,
                status.regulation_mode,
                status.power_flow,
            )

            if status.alarm_active:
                raise PSBAlarmError(
                    status.active_alarms,
                    questionable=status.questionable,
                    secondary=status.secondary_questionable,
                )

            time.sleep(0.5)

        except PSBConnectionError:
            # Do not blindly replay writes. Reconnect and first read the actual
            # instrument state because the final state of an interrupted write
            # may be unknown.
            raise
```

---

## 40. Troubleshooting

### `PSBConnectionError: Could not connect`

Check:

```text
PSB IP address
TCP port (normally 5025)
PC and PSB subnet
firewall/VLAN routing
that SCPI is enabled on the instrument
that another controller has not changed the port/IP
```

### Remote control is not granted

Check the HMI setting that allows remote control. If the front panel is in Local/inhibit state, a digital controller cannot acquire ownership.

### `-100 Command error`

Use verbose logging and verify the exact firmware/programming-guide command spelling. This driver uses corrected long-form spellings for several PSB 10000 settings specifically to reduce firmware parser ambiguity.

### A command works but readback is rounded

The PSB has finite internal resolution. Values such as power or resistance may read back slightly differently than the exact Python float transmitted. The supplied verifier uses realistic absolute tolerances rather than requiring bit-for-bit floating-point equality.

### Error appears to belong to the following command

SCPI errors can remain queued. The hardware verifier deliberately drains/isolate errors around tests so a stale error is less likely to be attributed to the next command. Application software that sends raw unchecked writes should manage the error queue explicitly.

### Serial import fails

Install `pyserial` into the same interpreter:

```bash
python -m pip install pyserial>=3.5
```

### `PSBUnsupportedFeatureError`

The feature is deliberately unimplemented or unavailable rather than guessed. This is expected for locally unregistered newer firmware extensions and the unverified warm-restart command.

---

## 41. Project files

```text
src/ea_psb10000/                Driver package
src/ea_psb10000/subsystems/     High-level functional groups
src/ea_psb10000/transports/     Ethernet and serial transports
examples/basic_ethernet.py      Minimal Ethernet example
examples/safe_poll.py           Safe polling example
examples/robust_session.py      More defensive session example
examples/verify_psb_commands.py Hardware command/readback/error verifier
tests/                          Hardware-free unit tests
COMMAND_COVERAGE.md              Coverage/no-guess summary
INSTALL.md                       Installation notes
README.md                        Main programming reference
```

---

## 42. Documentation basis and command policy

The implementation is based on the EA-PSB 10000 user documentation and the applicable EA Programming Guide ModBus & SCPI command definitions used during development and bench verification.

The package uses a strict command policy:

1. Commands with verified syntax are implemented as typed Python APIs.
2. Any command can still be sent through the raw SCPI escape hatch when the application intentionally owns validation/error handling.
3. A newer feature proven to exist by the user manual but lacking a verified SCPI spelling is **not guessed**. It is exposed through the extension-registration mechanism only after the exact command is locally verified.

This policy is intended to make production and ATE behavior predictable and auditable.

---

## 43. License

MIT License. See `LICENSE`.

**Writer:** Jeff Michaelis
