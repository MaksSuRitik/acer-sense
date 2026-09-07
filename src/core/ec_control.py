import subprocess
import os
from core.config import load_config, save_config


def _helper_path() -> str:
    dev_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts/ec-helper.sh"))
    return dev_path if os.path.exists(dev_path) else "/usr/lib/acer-sense/scripts/ec-helper.sh"


def set_charge_limit(limit: int, persist: bool = True) -> bool:
    """Apply a supported limit through polkit and persist setting."""
    if limit not in (80, 100):
        return False
    
    config = load_config()
    custom_offset = config.get("ec_charge_offset")
    custom_byte_80 = config.get("ec_charge_byte_80", "80")
    custom_byte_100 = config.get("ec_charge_byte_100", "00")

    arg = str(limit)
    if custom_offset is not None:
        b = custom_byte_80 if limit == 80 else custom_byte_100
        arg = f"raw:{custom_offset}:{b}"

    success = False
    try:
        r = subprocess.run(["pkexec", _helper_path(), arg], capture_output=True, timeout=15, check=False)
        success = (r.returncode == 0)
    except (OSError, subprocess.SubprocessError):
        success = False

    if persist:
        save_config({"charge_limit": limit})
    return success


def apply_saved_charge_limit() -> bool:
    """Re-apply the last confirmed setting after application startup."""
    limit = load_config().get("charge_limit", 100)
    return set_charge_limit(limit, persist=False)


def set_usb_charging(enabled: bool, persist: bool = True) -> bool:
    """Enable/disable USB charging when laptop is powered off."""
    byte_val = "01" if enabled else "00"
    ec_path = "/sys/kernel/debug/ec/ec0/io"
    if not os.path.exists(ec_path):
        return False
    try:
        r = subprocess.run(
            ["pkexec", _helper_path(), f"usb:{byte_val}"],
            capture_output=True,
            timeout=15,
            check=False,
        )
        if persist:
            save_config({"usb_charging": enabled})
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def get_charge_limit_from_sysfs() -> int | None:
    """Read current charge threshold from sysfs if driver supports it."""
    import pathlib
    for bat in sorted(pathlib.Path("/sys/class/power_supply").glob("BAT*")):
        threshold_file = bat / "charge_control_end_threshold"
        try:
            val = int(threshold_file.read_text(encoding="utf-8").strip())
            return val
        except (OSError, ValueError):
            continue
    return None
