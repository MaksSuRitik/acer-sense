"""Portable system facts for the information dialog; all probes are read-only."""
from __future__ import annotations

from pathlib import Path
import platform
import re
import subprocess

import psutil

from core.sensors import get_battery_info, get_gpu_temp, get_ram_info
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
    """Parse installed graphics adapters into clean, professional lines."""
    try:
        res = subprocess.run(["lspci"], capture_output=True, text=True, timeout=3, check=False)
        lines = res.stdout.splitlines()
    except OSError:
        return "Недоступно"

    gpus: list[str] = []
    for line in lines:
        if not any(k in line.lower() for k in ("vga compatible", "3d controller", "display controller")):
            continue
        parts = line.split(":", 2)
        desc = parts[-1].strip() if len(parts) >= 3 else parts[-1].strip()
        desc = re.sub(r"\s*\(rev\s+[^)]+\)", "", desc)
        is_intel = "intel" in desc.lower()
        is_nvidia = "nvidia" in desc.lower()
        tag = "Встроенная" if is_intel else ("Дискретная" if is_nvidia else "Видеокарта")
        gpus.append(f"{desc}  ({tag})")

    return "\n".join(gpus) if gpus else "Недоступно"


def _format_temperatures() -> str:
    """Group and format thermal readings cleanly by hardware component."""
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return "Недоступно"

    if not temps:
        return "Недоступно"

    sections: list[str] = []

    # 1. CPU
    for cpu_key in ("coretemp", "k10temp", "zenpower"):
        if cpu_key in temps:
            chip = temps[cpu_key]
            pkg_temp = None
            core_temps: list[float] = []
            for entry in chip:
                if "package" in (entry.label or "").lower():
                    pkg_temp = entry.current
                elif entry.current is not None and entry.current > 0:
                    core_temps.append(entry.current)
            if pkg_temp is not None:
                if core_temps:
                    sections.append(f"ЦП (Package): {pkg_temp:g}°C  [ядра: {min(core_temps):g}–{max(core_temps):g}°C]")
                else:
                    sections.append(f"ЦП (Package): {pkg_temp:g}°C")
            elif core_temps:
                sections.append(f"ЦП: {min(core_temps):g}–{max(core_temps):g}°C")
            break

    # 2. Discrete GPU
    gpu_t = get_gpu_temp()
    if gpu_t is not None:
        sections.append(f"GPU (Дискретная): {gpu_t}°C")

    # 3. NVMe / SSDs
    if "nvme" in temps:
        drives: list[str] = []
        for e in temps["nvme"]:
            if (e.label or "").lower() == "composite" and e.current is not None:
                drives.append(f"{round(e.current):g}°C")
        if drives:
            sections.append(f"Накопители (NVMe): {', '.join(drives)}")
        else:
            nvme_vals = [e.current for e in temps["nvme"] if e.current and e.current < 150]
            if nvme_vals:
                sections.append(f"Накопители (NVMe): {min(nvme_vals):g}–{max(nvme_vals):g}°C")

    # 4. Wireless
    for chip_name, entries in temps.items():
        if any(w in chip_name.lower() for w in ("mt79", "iwlwifi", "ath", "wlan", "wifi")):
            vals = [e.current for e in entries if e.current is not None]
            if vals:
                sections.append(f"Wi-Fi адаптер: {vals[0]:g}°C")
                break

    # 5. Motherboard / ACPI
    if "acpitz" in temps:
        vals = [e.current for e in temps["acpitz"] if e.current is not None]
        if vals:
            sections.append(f"Материнская плата: {vals[0]:g}°C")

    # Fallback if none matched
    if not sections:
        for chip_name, entries in temps.items():
            vals = [e.current for e in entries if e.current is not None and e.current > 0]
            if vals:
                sections.append(f"{chip_name}: {vals[0]:g}°C")

    return "\n".join(sections) if sections else "Недоступно"


def get_system_info() -> list[tuple[str, str]]:
    """Build values only from local, distribution-independent interfaces."""
    battery = get_battery_info()
    memory = get_ram_info()
    drives = get_physical_drives()

    model = _read_first("/sys/class/dmi/id/product_name")
    vendor = _read_first("/sys/class/dmi/id/sys_vendor")
    bios_version = _read_first("/sys/class/dmi/id/bios_version")
    bios_date = _read_first("/sys/class/dmi/id/bios_date")

    device_name = " ".join(x for x in (vendor, model) if x) or "Недоступно"
    bios = " ".join(x for x in (bios_version, bios_date) if x) or "Недоступно"
    drive_names = "\n".join(d["model"] for d in drives) or "Не обнаружены"
    bat_cycles = str(battery["cycles"]) if battery["cycles"] is not None else "Недоступно"
    bat_health = (f"{battery['health_percent']}% от заводской"
                  if battery["health_percent"] is not None else "Недоступно")
    bat_temp = (f"{battery['temperature']}°C"
                if battery.get("temperature") is not None else "Недоступно")

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
        ("Циклы аккумулятора", bat_cycles),
        ("Остаточная ёмкость", bat_health),
        ("Температура акк.", bat_temp),
        ("Температуры", _format_temperatures()),
    ]
