"""Example pattern for a long-running ATE/test application."""

from ea_psb10000 import PSB10000, PSBAlarmError, PSBConnectionError, PSBSCPIError

HOST = "192.168.1.50"


def run() -> None:
    with PSB10000.ethernet(
        HOST,
        output_off_on_exit=True,
        release_remote_on_exit=True,
    ) as psb:
        psb.acquire_remote()

        # Fail safe when remote ownership is lost, then enable instrument-side
        # communication monitoring. The host heartbeat is optional.
        psb.system.state_after_remote = "OFF"
        psb.watchdog.configure(enabled=True, timeout_s=5, heartbeat=True)

        psb.source.configure(voltage=32.0, current=18.0, power=600.0)
        psb.sink.configure(current=8.0, power=600.0)

        psb.protection.ovp = 54.0
        psb.output.on()

        try:
            values = psb.measure()
            status = psb.status.snapshot(include_measurement_for_flow=True)
            print(values)
            print(status)
        finally:
            psb.output.off()


if __name__ == "__main__":
    try:
        run()
    except (PSBSCPIError, PSBAlarmError, PSBConnectionError) as exc:
        print(f"PSB test aborted: {exc}")
        raise
