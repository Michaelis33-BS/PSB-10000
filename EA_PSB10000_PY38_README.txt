EA-PSB 10000 Driver v0.2.1 - Python 3.8+
==========================================

This version is based directly on the Python-3.8-compatible v0.1.1 driver.
It preserves the public API and adds the SCPI command fixes and Rev-2 verifier.

Recommended install on Python 3.8:

  python3 --version
  python3 -m pip uninstall -y ea-psb10000
  python3 -m pip install ./ea_psb10000-0.2.1-py3-none-any.whl

Verify install:

  python3 -c "import ea_psb10000; print(ea_psb10000.__version__)"

Expected:
  0.2.1

Run the normal Ethernet verification:

  python3 verify_psb_commands_py38_rev2.py --host 192.168.13.17 --verbose --release-remote

The normal run:
- forces the DC terminal OFF before mutation tests;
- tests every documented SCPI error code in software;
- performs safe live invalid-command/error-queue probes;
- does NOT intentionally trigger Safety OVP (-999);
- does NOT modify live Ethernet addressing while connected over Ethernet;
- restores ordinary writable settings after each read/write test where practical.

Optional deeper error-queue test:

  python3 verify_psb_commands_py38_rev2.py --host 192.168.13.17 --verbose --deep-error-injection

This additionally attempts the documented -225 response-buffer-overflow condition.

Outputs:
  psb_command_check.csv
  psb_command_check.json
