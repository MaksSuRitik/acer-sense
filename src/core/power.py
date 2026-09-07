import subprocess


VALID_PROFILES = {"power-saver", "balanced", "performance"}

def get_power_profile() -> str:
    try:
        result = subprocess.run(['powerprofilesctl', 'get'], capture_output=True, text=True,
                                timeout=2, check=False)
        profile = result.stdout.strip()
        return profile if profile in VALID_PROFILES else "balanced"
    except (OSError, subprocess.SubprocessError):
        return "balanced"

def set_power_profile(profile: str) -> bool:
    """profile: 'power-saver', 'balanced', 'performance'"""
    try:
        if profile not in VALID_PROFILES:
            return False
        subprocess.run(['powerprofilesctl', 'set', profile], check=True, timeout=5)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
