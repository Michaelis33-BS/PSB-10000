from ea_psb10000 import PSB10000

HOST = "192.168.1.50"

with PSB10000.ethernet(
    HOST,
    output_off_on_exit=True,
    release_remote_on_exit=True,
) as psb:
    print("Device:", psb.info)
    print("Ratings:", psb.ratings)
    print("Limits:", psb.limits.snapshot())

    psb.acquire_remote()

    psb.source.configure(voltage=32.0, current=18.0, power=600.0)
    psb.sink.configure(current=8.0, power=600.0)

    psb.output.on()
    print("Measurements:", psb.measure())
    print("Status:", psb.status.snapshot(include_measurement_for_flow=True))
    psb.output.off()
