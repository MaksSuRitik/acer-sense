from __future__ import annotations

from pathlib import Path

import psutil


# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------

def get_cpu_usage() -> float:
    return psutil.cpu_percent(interval=0.1)


def get_ram_info() -> dict:
    mem = psutil.virtual_memory()
    return {
        "percent": mem.percent,
        "total_gb": round(mem.total / (1024**3), 1),
        "used_gb": round(mem.used / (1024**3), 1),
    }


def get_cpu_temp() -> int:
    readings = get_temperature_readings()
    return int(max(readings.values())) if readings else 0


# ---------------------------------------------------------------------------
# Temperature sensors
# ---------------------------------------------------------------------------

# Ключи psutil → читаемые GPU-имена (проверяем первый совпавший)
_GPU_CHIP_KEYS = {"amdgpu", "radeon", "nouveau", "nvidia", "nvme", "intel_gpu"}

def get_temperature_readings() -> dict[str, float]:
    """Return every available thermal reading, using stable human-readable keys."""
    try:
        temps = psutil.sensors_temperatures()
        readings: dict[str, float] = {}
        for chip, entries in temps.items():
            for index, entry in enumerate(entries, start=1):
                if entry.current is not None:
                    name = entry.label or f"{chip} {index}"
                    readings[name] = round(float(entry.current), 1)
        return readings
    except Exception:
        return {}


def get_gpu_temp() -> int | None:
    """Return GPU temperature in °C, or None if unavailable."""
    try:
        temps = psutil.sensors_temperatures()
        for chip_key in _GPU_CHIP_KEYS:
            if chip_key in temps:
                entries = [e for e in temps[chip_key] if e.current is not None]
                if entries:
                    # Берём максимум, если несколько GPU-зон
                    return int(max(e.current for e in entries))
    except Exception:
        pass
    # Пробуем через hwmon напрямую (для некоторых карт)
    return _hwmon_gpu_temp()


def _hwmon_gpu_temp() -> int | None:
    """Fallback: scan hwmon entries for GPU labels."""
    hwmon_root = Path("/sys/class/hwmon")
    if not hwmon_root.exists():
        return None
    gpu_names = {"amdgpu", "radeon", "nouveau", "nvidia"}
    for hwmon in sorted(hwmon_root.iterdir()):
        name_file = hwmon / "name"
        try:
            hw_name = name_file.read_text(encoding="utf-8").strip().lower()
        except OSError:
            continue
        if any(g in hw_name for g in gpu_names):
            # ищем temp1_input
            for temp_file in sorted(hwmon.glob("temp*_input")):
                try:
                    val = int(temp_file.read_text(encoding="utf-8").strip())
                    return val // 1000  # millidegrees → degrees
                except (OSError, ValueError):
                    continue
    return None


# ---------------------------------------------------------------------------
# Fan speeds
# ---------------------------------------------------------------------------

def get_fan_speeds() -> list[dict]:
    """Return list of {label, rpm} for all fans detected via hwmon."""
    try:
        fans_raw = psutil.sensors_fans()
        fans: list[dict] = []
        for chip, entries in fans_raw.items():
            for index, entry in enumerate(entries, start=1):
                label = entry.label or f"{chip} #{index}"
                fans.append({"label": label, "rpm": entry.current})
        return fans
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Battery
# ---------------------------------------------------------------------------

def _read_int(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def get_battery_temp() -> float | None:
    """Read battery temperature from sysfs (in tenths of a degree → °C)."""
    for bat_path in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        # Linux < 5.x: temp в 0.1 °C; некоторые драйверы — прямо °C
        raw = _read_int(bat_path / "temp")
        if raw is not None:
            # Если значение > 1000 — это millidegrees Celsius
            if raw > 1000:
                return round(raw / 10.0, 1)
            elif raw > 200:
                # tenths of °C
                return round(raw / 10.0, 1)
            else:
                return float(raw)
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
    temperature = get_battery_temp()

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
        "temperature": temperature,
    }
