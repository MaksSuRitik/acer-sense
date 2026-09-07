import subprocess
import os
from core.config import load_config, save_config


def _helper_path() -> str:
    dev_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts/ec-helper.sh"))
    return dev_path if os.path.exists(dev_path) else "/usr/lib/acer-sense/scripts/ec-helper.sh"


def set_charge_limit(limit: int, persist: bool = True) -> bool:
    """Apply a supported limit through polkit and persist only a successful change."""
    if limit not in (80, 100):
        return False
    try:
        subprocess.run(["pkexec", _helper_path(), str(limit)], check=True, timeout=30)
        if persist:
            save_config({"charge_limit": limit})
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def apply_saved_charge_limit() -> bool:
    """Re-apply the last confirmed setting after application startup."""
    limit = load_config().get("charge_limit", 100)
    return set_charge_limit(limit, persist=False)


def set_usb_charging(enabled: bool, persist: bool = True) -> bool:
    """Enable/disable USB charging when the laptop is powered off.

    Записывает в EC-регистр 0xEF (смещение 239):
      0x01 — включено, 0x00 — отключено.
    Это смещение типично для платформ Acer AN5x5/Swift; на других моделях
    может отличаться — функция возвращает False, не прерывая работу.
    """
    byte_val = "01" if enabled else "00"
    ec_path = "/sys/kernel/debug/ec/ec0/io"
    if not os.path.exists(ec_path):
        return False
    try:
        subprocess.run(
            ["pkexec", _helper_path(), f"usb:{byte_val}"],
            check=True,
            timeout=30,
        )
        if persist:
            save_config({"usb_charging": enabled})
        return True
    except (OSError, subprocess.SubprocessError):
        # Неподдерживаемая команда — не аварийно
        return False


def get_charge_limit_from_sysfs() -> int | None:
    """Read the current charge threshold from sysfs (kernel ≥ 5.4 with ACPI driver)."""
    import pathlib
    for bat in sorted(pathlib.Path("/sys/class/power_supply").glob("BAT*")):
        threshold_file = bat / "charge_control_end_threshold"
        try:
            val = int(threshold_file.read_text(encoding="utf-8").strip())
            return val
        except (OSError, ValueError):
            continue
    return None
