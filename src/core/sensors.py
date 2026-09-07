"""Hardware sensor readings: CPU, GPU, RAM, fans, battery."""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

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
    """Return CPU package temperature in °C (highest core), or 0 if unavailable."""
    try:
        temps = psutil.sensors_temperatures()
        # Try coretemp first (Intel), then k10temp (AMD), then acpitz as last resort
        for chip in ("coretemp", "k10temp", "cpu_thermal"):
            if chip in temps:
                entries = [e for e in temps[chip] if e.current is not None]
                if entries:
                    return int(max(e.current for e in entries))
        # Fallback: any thermal sensor
        for entries in temps.values():
            valid = [e for e in entries if e.current is not None and e.current < 150]
            if valid:
                return int(max(e.current for e in valid))
    except Exception:
        pass
    return 0


# ---------------------------------------------------------------------------
# Temperature sensors (all)
# ---------------------------------------------------------------------------

def get_temperature_readings() -> dict[str, float]:
    """Return every available thermal reading as {label: celsius}."""
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


# ---------------------------------------------------------------------------
# GPU temperature  (NVIDIA RTX / AMD / Intel)
# ---------------------------------------------------------------------------

# Chips that indicate a GPU in psutil temperatures (not storage drives)
_GPU_CHIP_KEYS = {"amdgpu", "radeon", "nouveau", "nvidia", "intel_gpu"}

# Simple in-process cache so repeated UI calls don't fork nvidia-smi each time
_gpu_temp_cache: tuple[float, Optional[int]] = (0.0, None)  # (timestamp, value)
_GPU_CACHE_TTL = 2.0  # seconds


def get_gpu_temp() -> Optional[int]:
    """Return discrete GPU temperature in °C, or None if unavailable.

    Priority:
    1. nvidia-smi (reliable for NVIDIA RTX/GTX, no driver issues)
    2. psutil sensors_temperatures() — amdgpu / radeon
    3. hwmon sysfs scan for known GPU driver names
    """
    global _gpu_temp_cache
    now = time.monotonic()
    if now - _gpu_temp_cache[0] < _GPU_CACHE_TTL and _gpu_temp_cache[1] is not None:
        return _gpu_temp_cache[1]

    temp: Optional[int] = None

    # ── 1. nvidia-smi (fastest, most accurate for NVIDIA) ──────────────────
    if shutil.which("nvidia-smi"):
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2, check=False,
            )
            if result.returncode == 0:
                raw = result.stdout.strip().splitlines()[0].strip()
                if raw.isdigit():
                    temp = int(raw)
        except (OSError, subprocess.SubprocessError, ValueError):
            pass

    # ── 2. psutil sensors — AMD / fallback ─────────────────────────────────
    if temp is None:
        try:
            temps = psutil.sensors_temperatures()
            for chip_key in _GPU_CHIP_KEYS:
                if chip_key in temps:
                    entries = [e for e in temps[chip_key] if e.current is not None]
                    if entries:
                        temp = int(max(e.current for e in entries))
                        break
        except Exception:
            pass

    # ── 3. hwmon sysfs direct scan ─────────────────────────────────────────
    if temp is None:
        temp = _hwmon_gpu_temp()

    _gpu_temp_cache = (now, temp)
    return temp


def _hwmon_gpu_temp() -> Optional[int]:
    """Fallback: scan /sys/class/hwmon for GPU-related driver names."""
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

def _read_int(path: Path) -> Optional[int]:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def get_battery_temp() -> Optional[int]:
    """Return battery temperature in °C from sysfs, or None."""
    for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        raw = _read_int(bat / "temp")
        if raw is not None:
            return raw // 10  # tenths of degree → degrees
    return None


# Simple in-process cache for EC-based cycle count (expensive pkexec call)
_cycles_cache: tuple[float, Optional[int]] = (0.0, None)
_CYCLES_CACHE_TTL = 60.0  # seconds — EC cycles don't change during a session


def _get_cycles_from_ec() -> Optional[int]:
    """Read battery cycle count from EC registers via ec-helper.sh (pkexec).

    EC dump analysis (offsets 0x90-0xDF):
      - Cycle count NOT in this range (confirmed from 3-state dump analysis)
      - Previously located at 0xF4-0xF5 in a wider RW-Everything dump
      - 0xBD (189) = 0x6A = 106 is stable but doesn't match user's 160+ figure
      - We try 0xF4-0xF5 first, fall back to sysfs
    """
    global _cycles_cache
    now = time.monotonic()
    if now - _cycles_cache[0] < _CYCLES_CACHE_TTL and _cycles_cache[1] is not None:
        return _cycles_cache[1]

    installed = "/usr/lib/acer-sense/scripts/ec-helper.sh"
    if not Path(installed).exists():
        return None

    try:
        result = subprocess.run(
            ["pkexec", installed, "cycles"],
            capture_output=True, text=True, timeout=8, check=False,
        )
        if result.returncode == 0:
            raw = result.stdout.strip()
            if raw.isdigit():
                val = int(raw)
                if 0 < val < 10000:
                    _cycles_cache = (now, val)
                    return val
    except (OSError, subprocess.SubprocessError, ValueError):
        pass

    return None


def get_battery_info() -> dict:
    """Return battery state dict."""
    battery_paths = sorted(Path("/sys/class/power_supply").glob("BAT*"))
    battery_path = battery_paths[0] if battery_paths else None

    try:
        bat = psutil.sensors_battery()
    except Exception:
        bat = None

    percent = round(bat.percent) if bat else _read_int(battery_path / "capacity") if battery_path else None
    plugged = bool(bat.power_plugged) if bat else False
    status = "Unknown"
    cycles: Optional[int] = None
    health_percent: Optional[int] = None
    temperature = get_battery_temp()

    if battery_path:
        try:
            status = (battery_path / "status").read_text(encoding="utf-8").strip()
        except OSError:
            pass

        # Try sysfs cycle_count first (fast, no auth)
        sysfs_cycles = _read_int(battery_path / "cycle_count")
        if sysfs_cycles and sysfs_cycles > 0:
            cycles = sysfs_cycles
        else:
            # sysfs reports 0 — try EC registers (requires pkexec, cached)
            cycles = _get_cycles_from_ec()

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
