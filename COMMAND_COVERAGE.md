# EA-PSB 10000 Driver Command Coverage

This package separates three categories deliberately:

1. **Typed + verified**: command syntax is documented in EA's ModBus/SCPI programming guide and wrapped in a Python API.
2. **Read/write raw SCPI**: every verified or future SCPI command remains available through `query_scpi()` / `write_scpi()` even when no typed convenience wrapper exists yet.
3. **2025 firmware extensions requiring registration**: the 2025 user manual proves the setting exists, but the available programming-guide revision does not publish the exact SCPI spelling. The driver refuses to guess and uses `psb.extensions.register(...)` instead.

## Typed + verified surface

| Area | Coverage |
|---|---|
| Connection | TCP/SCPI Ethernet (default 5025), serial/USB-COM, thread-safe I/O |
| Identification | `*IDN?`, nominal U/I/P/R ranges, model-aware validation |
| Remote control | acquire/release/owner verification |
| DC terminal | explicit on/off/query; connecting never energizes output |
| Measurements | voltage/current/power array with signed sink current/power |
| Source setpoints | U, I, P, R |
| Sink setpoints | I, P, R |
| Protection | OVP, source/sink OCP, source/sink OPP |
| Adjustment limits | source U/I/P/R, sink I/P/R |
| User events | UVD/UCD/OVD/OCD/OPD plus sink UCD/OCD/OPD and actions |
| System configuration | state after remote/power/PF/OT, user text, R mode, controller speed, SEMI F47 |
| Status | STB, Questionable, Secondary Questionable, Operation, alarms/events, regulation mode, source/sink state |
| Alarm management | error queue, alarm-safe status capture before acknowledgement, alarm counters |
| Analog interface | range, monitor routing, pins 6/14/15, REM-SB level/action |
| Master-slave | enable, role, init, condition, units, termination, bias |
| Ethernet settings | primary/secondary selection, IP, mask, gateway, DHCP, DNS, TCP port, host/domain, keepalive, timeout, MAC |
| Optional interfaces | module identity/address/baud; Profibus/Profinet tags; CAN IDs/DLC/termination/cyclic reads |
| Interface monitoring | instrument timeout/action plus opt-in Python heartbeat |
| Diagnostics | operation/DC-on/DC-off time, source/sink Ah and kWh, device class |
| Function generator | arbitrary generator sequence loading/control and bidirectional XY table 1/table 2 loading |
| Testing | deterministic `ScriptedTransport` for hardware-free unit tests |

## Deliberately not guessed

The supplied 2025 PSB user manual adds these HMI settings, but the available programming-guide revision used for command verification does not expose their exact SCPI names:

- Fast discharge enable / voltage / current / duration
- Actual-value filter mode / buffer size
- STBY zero stabilization

The validated helpers are present under `psb.extensions`, but a site must register the exact command strings from the programming guide matching the installed firmware before use.

## Specialized function-generator applications

Arbitrary and raw XY curve handling are typed. The PSB also has specialized high-level simulations/tests (extended PV/EN 50530, MPP tracking, battery test, etc.). Those remain available through raw SCPI today but do not yet have dedicated typed Python configuration objects in this release. This is intentional: those modes contain large, mode-specific parameter matrices and should not be represented by guessed or weakly typed APIs.

## Safety behavior

The driver never automatically retries a state-changing write after a transport failure. If a socket or serial link fails during a write, the final instrument state is indeterminate; replaying the command could duplicate a transition. Reconnect, read back state, then decide what to do.

Likewise, `SYST:ERR?` is not treated as a harmless query: EA documents that it can acknowledge alarm status after the physical cause has cleared. High-level writes capture the alarm condition registers first.
