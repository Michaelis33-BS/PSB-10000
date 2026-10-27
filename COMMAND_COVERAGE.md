# EA-PSB 10000 Driver Command Coverage

**Writer:** Jeff Michaelis  
**Version:** 0.2.2

The driver intentionally separates commands into three categories:

1. **Typed and verified** — command spelling has been verified against the applicable EA programming documentation and is wrapped by the high-level Python API.
2. **Raw SCPI** — applications can use `query_scpi()` and `write_scpi()` for verified/site-specific commands that do not yet have a typed wrapper.
3. **Registered firmware extensions** — newer features known to exist but lacking a verified SCPI spelling are never guessed; the exact local command must first be registered with `psb.extensions`.

## Typed/verified areas

| Area | Coverage |
|---|---|
| Transport | Ethernet TCP/SCPI and serial/USB-COM |
| Identification | `*IDN?`, nominal U/I/P/R ranges |
| Remote control | acquire, release, owner verification |
| DC terminal | ON/OFF/readback |
| Measurements | voltage/current/power array and fallback individual queries |
| Source | voltage, current, power, resistance |
| Sink | current, power, resistance |
| Protection | OVP, source/sink OCP, source/sink OPP |
| Adjustment limits | source U/I/P/R and sink I/P/R limits |
| User events | UVD/UCD/OVD/OCD/OPD plus supported sink events/actions |
| System | user text, resistance mode, after-state behavior, controller speed, SEMI F47, `*CLS`, `*RST` |
| Status | STB, event registers, QUESTIONABLE/secondary/OPERATION condition/event/enable registers |
| Alarms | alarm decoding and individual alarm counters |
| Error queue | `SYSTem:ERRor?`, `NEXT?`, `ALL?`, documented error-code catalog |
| Analog interface | range, monitor routing, pins 6/14/15, REM-SB level/action |
| Communications | serial timeout, ModBus enable, optional-interface settings, tags, CAN, LAN |
| Watchdog | instrument interface monitoring and optional host heartbeat |
| Diagnostics | device/runtime counters, source/sink Ah and kWh |
| Master/slave | enable, role, termination, bias, initialize, condition, unit count |
| Function generator | arbitrary sequences and XY table loading/control |
| Testing | deterministic `ScriptedTransport` and real-hardware verifier |

## Deliberately not guessed

The newer user manual documents these settings, but the programming-guide revision used for this driver does not provide verified SCPI spellings for them:

- Fast discharge enable / voltage / current / duration
- Actual-value filter mode / buffer size
- STBY zero stabilization

Use `psb.extensions.register(...)` only after the exact command is verified for the installed firmware.

## Safety behavior

The driver never automatically replays a state-changing write after a transport failure. Reconnect and read actual instrument state before deciding whether a write must be repeated.

Automatic post-write SCPI error checking captures relevant alarm condition registers before reading the error queue because error-queue access can acknowledge alarm information after the original physical cause has cleared.

See `README.md` for the complete Python API and SCPI command mapping.
