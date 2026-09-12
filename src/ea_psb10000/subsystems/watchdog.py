"""Interface-monitoring watchdog and optional host heartbeat."""

from __future__ import annotations

import logging
from threading import Event, RLock, Thread

from .base import Subsystem
from ..util import ensure_range


class WatchdogSubsystem(Subsystem):
    """Manage the PSB's digital-interface monitoring feature.

    EA's interface monitoring is implemented inside the instrument.  If no
    digital message arrives before the configured timeout, the unit exits
    remote control; the resulting DC-terminal state then follows the device's
    ``State after remote`` setting.

    The optional Python heartbeat is deliberately opt-in.  It periodically
    sends ``*STB?`` so an otherwise idle controlling process can keep the
    instrument-side monitor alive.  It never changes a setpoint or output state.
    """

    def __init__(self, device) -> None:
        super().__init__(device)
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._state_lock = RLock()
        self._interval_s = 1.0
        self._last_error: Exception | None = None
        self._logger = logging.getLogger("ea_psb10000.watchdog")

    @property
    def enabled(self) -> bool:
        return self._query_bool("SYST:COMM:MON:ACT?")

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._write(f"SYST:COMM:MON:ACT {'ON' if value else 'OFF'}")

    @property
    def timeout_s(self) -> int:
        return self._query_int("SYST:COMM:MON:TIME?")

    @timeout_s.setter
    def timeout_s(self, value: int) -> None:
        value = int(ensure_range(value, 1, 36000, "interface monitoring timeout s"))
        self._write(f"SYST:COMM:MON:TIME {value}")

    def configure(
        self,
        *,
        enabled: bool,
        timeout_s: int = 5,
        heartbeat: bool = False,
        heartbeat_interval_s: float | None = None,
    ) -> None:
        """Configure instrument monitoring and optionally start a host heartbeat.

        ``heartbeat_interval_s`` defaults to at most one third of the monitor
        timeout, capped at one second.  The interval must remain below the
        instrument timeout.
        """
        timeout_s = int(ensure_range(timeout_s, 1, 36000, "interface monitoring timeout s"))
        self.timeout_s = timeout_s
        self.enabled = enabled

        if not enabled:
            self.stop_heartbeat()
            return

        if heartbeat:
            interval = heartbeat_interval_s
            if interval is None:
                interval = min(1.0, max(0.1, timeout_s / 3.0))
            if not 0 < float(interval) < timeout_s:
                raise ValueError("heartbeat_interval_s must be > 0 and less than timeout_s")
            self.start_heartbeat(float(interval))
        else:
            self.stop_heartbeat()

    @property
    def heartbeat_running(self) -> bool:
        thread = self._thread
        return bool(thread and thread.is_alive())

    @property
    def last_error(self) -> Exception | None:
        return self._last_error

    def ping(self) -> int:
        """Send one non-mutating heartbeat message and return the status byte."""
        return self._query_int("*STB?")

    def start_heartbeat(self, interval_s: float = 1.0) -> None:
        interval_s = float(interval_s)
        if interval_s <= 0:
            raise ValueError("interval_s must be > 0")
        with self._state_lock:
            self.stop_heartbeat()
            self._interval_s = interval_s
            self._last_error = None
            self._stop_event.clear()
            self._thread = Thread(
                target=self._heartbeat_loop,
                name="ea-psb10000-heartbeat",
                daemon=True,
            )
            self._thread.start()

    def stop_heartbeat(self, join_timeout_s: float = 2.0) -> None:
        with self._state_lock:
            thread = self._thread
            if thread is None:
                return
            self._stop_event.set()
        # Import here to avoid joining the heartbeat thread from itself.
        from threading import current_thread
        if thread is not current_thread() and thread.is_alive():
            thread.join(timeout=max(0.0, float(join_timeout_s)))
        with self._state_lock:
            if self._thread is thread:
                self._thread = None
            self._stop_event.clear()

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(self._interval_s):
            try:
                self.ping()
            except Exception as exc:  # preserve failure for supervising software
                self._last_error = exc
                self._logger.warning("PSB heartbeat failed: %s", exc)
                break
