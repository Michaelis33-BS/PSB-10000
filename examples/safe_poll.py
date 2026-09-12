import time
from ea_psb10000 import PSB10000, PSBAlarmError, PSBConnectionError

HOST = "192.168.1.50"

with PSB10000.ethernet(HOST, output_off_on_exit=True) as psb:
    psb.acquire_remote()
    psb.output.on()

    try:
        while True:
            status = psb.status.snapshot(include_measurement_for_flow=True)
            values = psb.measure()
            print(values, status.regulation_mode, status.power_flow)
            if status.alarm_active:
                raise PSBAlarmError(
                    status.active_alarms,
                    questionable=status.questionable,
                    secondary=status.secondary_questionable,
                )
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    except PSBConnectionError:
        # Never assume the last write succeeded/failed after transport loss.
        raise
