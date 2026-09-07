"""Background Battery Charge Limiter Daemon with Hysteresis.

Hysteresis logic for 80% optimized charge limit:
  - If battery percent >= 80%: inhibit AC charge (EC 221 = 0x80)
  - If battery percent <= 78%: resume AC charge (EC 221 = 0x00)
  - If 79%: maintain current state (prevents cycling on the boundary)
  - If target is 100%: ensure AC charge is enabled (EC 221 = 0x00)
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Optional

from core.config import load_config
from core.ec_control import (
    apply_battery_hysteresis,
    get_charge_limit_from_ec,
    set_charge_limit,
)

logger = logging.getLogger(__name__)


def get_current_capacity() -> Optional[int]:
    """Read current battery capacity percent from sysfs."""
    for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        cap_file = bat / "capacity"
        try:
            val = int(cap_file.read_text(encoding="utf-8").strip())
            return val
        except (OSError, ValueError):
            continue
    return None


class BatteryMonitorThread(threading.Thread):
    """Monitors battery capacity every interval_seconds and adjusts EC register 221."""

    def __init__(self, interval_seconds: float = 10.0):
        super().__init__(name="BatteryMonitorThread", daemon=True)
        self.interval = interval_seconds
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()

    def stop(self):
        self._stop_event.set()
        self._wake_event.set()

    def trigger(self):
        """Immediately wake up the monitor to evaluate new state."""
        self._wake_event.set()

    def run(self):
        logger.info("BatteryMonitorThread started.")
        while not self._stop_event.is_set():
            try:
                self._check_and_apply()
            except Exception as e:
                logger.error("Error in BatteryMonitorThread: %s", e)

            # Wait for interval or wake trigger
            self._wake_event.wait(self.interval)
            self._wake_event.clear()

    def _check_and_apply(self):
        config = load_config()
        target = config.get("charge_limit", 100)
        capacity = get_current_capacity()
        if capacity is None:
            return

        apply_battery_hysteresis(target=target, current_capacity=capacity)


# Singleton monitor instance for the application
_monitor_thread: Optional[BatteryMonitorThread] = None


def start_battery_monitor():
    global _monitor_thread
    if _monitor_thread is None or not _monitor_thread.is_alive():
        _monitor_thread = BatteryMonitorThread(interval_seconds=10.0)
        _monitor_thread.start()


def stop_battery_monitor():
    global _monitor_thread
    if _monitor_thread and _monitor_thread.is_alive():
        _monitor_thread.stop()
        _monitor_thread = None


def trigger_battery_monitor():
    global _monitor_thread
    if _monitor_thread and _monitor_thread.is_alive():
        _monitor_thread.trigger()
