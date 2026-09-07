"""Portable system facts for the information dialog; all probes are read-only."""
from __future__ import annotations

from pathlib import Path
import platform
import subprocess

from core.sensors import get_battery_info, get_ram_info, get_temperature_readings
from core.storage import get_physical_drives


def _read_first(*paths: str) -> str | None:
    for path in paths:
        try:
            value = Path(path).read_text(encoding="utf-8").strip()
            if value:
                return value
        except OSError:
            continue
    return None


def _os_name() -> str:
    try:
        release = platform.freedesktop_os_release()
        return release.get("PRETTY_NAME") or release.get("NAME") or "Linux"
    except (AttributeError, OSError):
        return platform.system()


def _cpu_name() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if ":" in line and line.split(":", 1)[0].strip().lower() in {"model name", "hardware"}:
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "Недоступно"


def _graphics() -> str:
    try:
        result = subprocess.run(["lspci", "-mm"], capture_output=True, text=True, timeout=2, check=False)
        rows = [line for line in result.stdout.splitlines() if "VGA compatible controller" in line or "3D controller" in line]
        if rows:
            return "; ".join(rows)
    except OSError:
        pass
    return "Недоступно"


def get_system_info() -> list[tuple[str, str]]:
    """Build values only from local, distribution-independent interfaces."""
    battery = get_battery_info()
    memory = get_ram_info()
    drives = get_physical_drives()
    temperatures = get_temperature_readings()
    model = _read_first("/sys/class/dmi/id/product_name")
    vendor = _read_first("/sys/class/dmi/id/sys_vendor")
    bios_version = _read_first("/sys/class/dmi/id/bios_version")
    bios_date = _read_first("/sys/class/dmi/id/bios_date")
    device_name = " ".join(item for item in (vendor, model) if item) or "Недоступно"
    bios = " ".join(item for item in (bios_version, bios_date) if item) or "Недоступно"
    drive_names = ", ".join(drive["model"] for drive in drives) or "Не обнаружены"
    thermal = ", ".join(f"{name}: {value:g}°C" for name, value in temperatures.items()) or "Недоступно"
    battery_cycles = str(battery["cycles"]) if battery["cycles"] is not None else "Недоступно"
    battery_health = f"{battery['health_percent']}%" if battery["health_percent"] is not None else "Недоступно"
    return [
        ("ОС", _os_name()),
        ("Ядро", platform.release()),
        ("Архитектура", platform.machine() or "Недоступно"),
        ("Устройство", device_name),
        ("Процессор", _cpu_name()),
        ("ОЗУ", f"{memory['total_gb']} ГБ"),
        ("Графика", _graphics()),
        ("Накопители", drive_names),
        ("BIOS", bios),
        ("Циклы аккумулятора", battery_cycles),
        ("Остаточная ёмкость", battery_health),
        ("Температуры", thermal),
    ]
