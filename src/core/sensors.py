from __future__ import annotations

from pathlib import Path

import psutil

def get_cpu_usage() -> float:
    return psutil.cpu_percent(interval=0.1)

def get_ram_info() -> dict:
    mem = psutil.virtual_memory()
    return {
        "percent": mem.percent,
        "total_gb": round(mem.total / (1024**3), 1),
        "used_gb": round(mem.used / (1024**3), 1)
    }

def get_cpu_temp() -> int:
    readings = get_temperature_readings()
    return int(max(readings.values())) if readings else 0


def get_temperature_readings() -> dict[str, float]:
    """Return every available thermal reading, using stable human-readable keys."""
    try:
        temps = psutil.sensors_temperatures()
        readings = {}
        for chip, entries in temps.items():
            for index, entry in enumerate(entries, start=1):
                if entry.current is not None:
                    name = entry.label or f"{chip} {index}"
                    readings[name] = round(float(entry.current), 1)
        return readings
    except Exception:
        return {}


def _read_int(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def get_battery_info() -> dict:
    """Return the portable, read-only battery data Linux exposes through sysfs."""
    battery_paths = sorted(Path("/sys/class/power_supply").glob("BAT*"))
    battery_path = battery_paths[0] if battery_paths else None

    try:
        bat = psutil.sensors_battery()
    except Exception:
        bat = None

    percent = round(bat.percent) if bat else _read_int(battery_path / "capacity") if battery_path else None
    plugged = bool(bat.power_plugged) if bat else False
    status = "Unknown"
    cycles = None
    health_percent = None

    if battery_path:
        try:
            status = (battery_path / "status").read_text(encoding="utf-8").strip()
        except OSError:
            pass
        cycles = _read_int(battery_path / "cycle_count")

        # Kernels expose one of the energy_* or charge_* pairs depending on the driver.
        for current_name, design_name in (("energy_full", "energy_full_design"),
                                          ("charge_full", "charge_full_design")):
            current = _read_int(battery_path / current_name)
            design = _read_int(battery_path / design_name)
            if current and design and design > 0:
                health_percent = round(current * 100 / design)
                break

    return {
        "present": battery_path is not None or bat is not None,
        "percent": percent,
        "plugged": plugged,
        "status": status,
        "cycles": cycles,
        "health_percent": health_percent,
    }
