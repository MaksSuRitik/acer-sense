import subprocess
import os
from core.config import load_config, save_config

def _helper_path() -> str:
    dev_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts/ec-helper.sh"))
    return dev_path if os.path.exists(dev_path) else '/usr/lib/acer-sense/scripts/ec-helper.sh'


def set_charge_limit(limit: int, persist: bool = True) -> bool:
    """Apply a supported limit through polkit and persist only a successful change."""
    if limit not in (80, 100):
        return False

    try:
        subprocess.run(['pkexec', _helper_path(), str(limit)], check=True, timeout=30)
        if persist:
            save_config({"charge_limit": limit})
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def apply_saved_charge_limit() -> bool:
    """Re-apply the last confirmed setting after application startup."""
    limit = load_config().get("charge_limit", 100)
    return set_charge_limit(limit, persist=False)
