import os

import yaml

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
_default = {
    "SERVER_IP": "localhost",
    "SERVER_PORT": 8000,
    "UPDATE_INTERVAL": 1,
    "TIMEOUT": 10,
    "PROCESS_LIMIT": 100,
    "NETWORK_CONN_LIMIT": 100,
    "HDD_SMART_ENABLED": True,
    "HDD_TEMP_WARNING": 45,
    "HDD_TEMP_CRITICAL": 55,
}

def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}
    cfg = _default.copy()
    cfg.update(data)
    return cfg


if not os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(_default, f)


_config_data = _load_config()

for key, val in _config_data.items():
    globals()[key] = val


def save_config(updates: dict) -> None:
    global _config_data
    for k, v in updates.items():
        if k in _default:
            _config_data[k] = v
            globals()[k] = v
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(_config_data, f)


def reload() -> None:
    global _config_data
    _config_data = _load_config()
    for key, val in _config_data.items():
        globals()[key] = val
