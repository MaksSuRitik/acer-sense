"""Hyprland integration helpers for Acer Sense.

Supports Hyprland 0.55+ Lua configs (dms/binds-user.lua, hyprland.lua)
and standard hyprland.conf configs.
Binds:
  - XF86Launch6 -> Microphone toggle + LED sync
  - XF86Reload  -> Cycle power profile (Fn+F)
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess


def detect_hyprland() -> bool:
    """Return True if Hyprland session is active."""
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return True
    if shutil.which("hyprctl"):
        try:
            r = subprocess.run(["hyprctl", "version"],
                               capture_output=True, text=True, timeout=2, check=False)
            return r.returncode == 0
        except (OSError, subprocess.SubprocessError):
            pass
    return False


def _get_target_config() -> Path:
    home = Path.home()
    candidates = [
        home / ".config" / "hypr" / "dms" / "binds-user.lua",
        home / ".config" / "hypr" / "hyprland.lua",
        home / ".config" / "caelestia" / "hypr-user.lua",
        home / ".config" / "hypr" / "hyprland.conf",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[-1]


def has_keybinds() -> bool:
    """Check if XF86Reload is configured in any Hyprland config file."""
    home = Path.home()
    candidates = [
        home / ".config" / "hypr" / "dms" / "binds-user.lua",
        home / ".config" / "hypr" / "hyprland.lua",
        home / ".config" / "caelestia" / "hypr-user.lua",
        home / ".config" / "hypr" / "hyprland.conf",
    ]
    for cfg in candidates:
        if cfg.exists():
            try:
                content = cfg.read_text(encoding="utf-8")
                if "XF86Reload" in content:
                    return True
            except OSError:
                pass
    return False


def has_mic_keybind() -> bool:
    return has_keybinds()


def install_keybinds() -> bool:
    """Run hyprland-setup.sh to idempotently install the keybinds."""
    dev_setup = Path(__file__).resolve().parents[2] / "scripts" / "hyprland-setup.sh"
    installed_setup = Path("/usr/lib/acer-sense/scripts/hyprland-setup.sh")
    script = dev_setup if dev_setup.exists() else installed_setup
    if not script.exists():
        return False
    try:
        subprocess.run(["bash", str(script)], check=True, timeout=10)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def install_mic_keybind() -> bool:
    return install_keybinds()


def remove_keybinds() -> bool:
    """Remove Acer Sense section from Hyprland configs."""
    home = Path.home()
    candidates = [
        home / ".config" / "hypr" / "dms" / "binds-user.lua",
        home / ".config" / "hypr" / "hyprland.lua",
        home / ".config" / "caelestia" / "hypr-user.lua",
        home / ".config" / "hypr" / "hyprland.conf",
    ]
    changed = False
    for cfg in candidates:
        if not cfg.exists():
            continue
        try:
            content = cfg.read_text(encoding="utf-8")
            pattern = r"(?:--|#) === Acer Sense keybinds ===.*?(?:--|#) === /Acer Sense keybinds ===\n?"
            new_content = re.sub(pattern, "", content, flags=re.DOTALL)
            if new_content != content:
                cfg.write_text(new_content.strip() + "\n", encoding="utf-8")
                changed = True
        except OSError:
            pass
    if changed and shutil.which("hyprctl"):
        subprocess.run(["hyprctl", "reload"], capture_output=True, timeout=5, check=False)
    return changed


def remove_mic_keybind() -> bool:
    return remove_keybinds()


def reload_hyprland() -> bool:
    if not shutil.which("hyprctl"):
        return False
    try:
        r = subprocess.run(["hyprctl", "reload"],
                           capture_output=True, text=True, timeout=5, check=False)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
