import os
from pathlib import Path
import subprocess
from core.config import load_config, save_config


def _helper_path() -> str:
    installed = "/usr/lib/acer-sense/scripts/ec-helper.sh"
    if os.path.exists(installed):
        return installed
    dev_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts/ec-helper.sh"))
    return dev_path


def apply_battery_hysteresis(target: int, current_capacity: int) -> bool:
    """Evaluate hysteresis and send the appropriate EC charge byte.

    EC register 221 (0xDD):
      0x80: Inhibit AC charging (stop charging now)
      0x00: Allow AC charging (normal charge)

    Logic for target=80:
      - capacity >= 80: send '80' (stop charging)
      - capacity <= 78: send '100' (resume charging until 80%)
      - capacity == 79: preserve current state (deadband)
    Logic for target=100:
      - send '100' (allow charging)
    """
    cur_ec = get_charge_limit_from_ec()  # returns 80 (inhibited) or 100 (enabled)

    if target == 80:
        if current_capacity >= 80:
            if cur_ec != 80:
                return _send_raw_ec_command("80")
            return True
        elif current_capacity <= 78:
            if cur_ec != 100:
                return _send_raw_ec_command("100")
            return True
        else:
            # 79% hysteresis band: do not alter state
            return True
    else:  # target == 100
        if cur_ec != 100:
            return _send_raw_ec_command("100")
        return True


def _send_raw_ec_command(arg: str) -> bool:
    try:
        r = subprocess.run(["pkexec", _helper_path(), arg], capture_output=True, timeout=15, check=False)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def set_charge_limit(limit: int, persist: bool = True) -> bool:
    """Apply a supported limit (80 or 100) using hysteresis and persist setting."""
    if limit not in (80, 100):
        return False

    if persist:
        save_config({"charge_limit": limit})
        # Also try to update /etc/acer-sense/charge_limit for the background systemd service
        try:
            p = Path("/etc/acer-sense/charge_limit")
            if p.parent.exists() and os.access(str(p.parent), os.W_OK):
                p.write_text(str(limit), encoding="utf-8")
        except OSError:
            pass

    # Read current capacity from sysfs to apply hysteresis immediately
    cap = None
    for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        cap_file = bat / "capacity"
        try:
            cap = int(cap_file.read_text(encoding="utf-8").strip())
            break
        except (OSError, ValueError):
            continue

    if cap is not None:
        return apply_battery_hysteresis(target=limit, current_capacity=cap)
    else:
        # Fallback if capacity cannot be read
        return _send_raw_ec_command(str(limit))


def get_charge_limit_from_ec() -> int | None:
    """Read actual limit from EC register 221 (0xDD).

    Returns 80 (charge stopped) or 100 (charge enabled).
    """
    try:
        r = subprocess.run(["pkexec", _helper_path(), "get"], capture_output=True, text=True, timeout=5, check=False)
        if r.returncode == 0:
            out = r.stdout.strip()
            if out in ("80", "100"):
                return int(out)
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def apply_saved_charge_limit() -> bool:
    """Re-apply the last confirmed setting after application startup."""
    limit = load_config().get("charge_limit", 100)
    return set_charge_limit(limit, persist=False)


def set_usb_charging(enabled: bool, persist: bool = True) -> bool:
    """Enable/disable USB charging when laptop is powered off."""
    byte_val = "01" if enabled else "00"
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
    for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        threshold_file = bat / "charge_control_end_threshold"
        try:
            val = int(threshold_file.read_text(encoding="utf-8").strip())
            return val
        except (OSError, ValueError):
            continue
    return None
