import subprocess
from typing import Optional

VALID_PROFILES = {"power-saver", "balanced", "performance"}

def _get_profile_via_qtdbus() -> Optional[str]:
    try:
        from PyQt6 import QtDBus
        bus = QtDBus.QDBusConnection.systemBus()
        if not bus.isConnected():
            return None
        iface = QtDBus.QDBusInterface(
            'net.hadess.PowerProfiles',
            '/net/hadess/PowerProfiles',
            'org.freedesktop.DBus.Properties',
            bus
        )
        reply = iface.call('Get', 'net.hadess.PowerProfiles', 'ActiveProfile')
        args = reply.arguments()
        if args and isinstance(args[0], str):
            profile = args[0].strip()
            if profile in VALID_PROFILES:
                return profile
    except Exception:
        pass
    return None

def _set_profile_via_qtdbus(profile: str) -> bool:
    try:
        from PyQt6 import QtDBus
        bus = QtDBus.QDBusConnection.systemBus()
        if not bus.isConnected():
            return False
        iface = QtDBus.QDBusInterface(
            'net.hadess.PowerProfiles',
            '/net/hadess/PowerProfiles',
            'org.freedesktop.DBus.Properties',
            bus
        )
        reply = iface.call('Set', 'net.hadess.PowerProfiles', 'ActiveProfile', QtDBus.QDBusVariant(profile))
        return not reply.isError()
    except Exception:
        return False

def get_power_profile() -> str:
    dbus_val = _get_profile_via_qtdbus()
    if dbus_val:
        return dbus_val
    try:
        result = subprocess.run(['powerprofilesctl', 'get'], capture_output=True, text=True,
                                timeout=2, check=False)
        profile = result.stdout.strip()
        return profile if profile in VALID_PROFILES else "balanced"
    except (OSError, subprocess.SubprocessError):
        return "balanced"

def set_power_profile(profile: str) -> bool:
    """profile: 'power-saver', 'balanced', 'performance'"""
    if profile not in VALID_PROFILES:
        return False
    if _set_profile_via_qtdbus(profile):
        return True
    try:
        subprocess.run(['powerprofilesctl', 'set', profile], check=True, timeout=5)
        return True
    except (OSError, subprocess.SubprocessError):
        return False

