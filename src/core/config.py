import os
import json

CONFIG_FILE = os.path.expanduser("~/.config/acer-sense/settings.json")

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"charge_limit": 100, "bluelight_temp": 4500, "bluelight_enabled": False}

def save_config(data: dict):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    config = load_config()
    config.update(data)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
