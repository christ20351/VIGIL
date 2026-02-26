import os

import yaml

# configuration basée sur YAML. Le fichier réel est server/config.yaml
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

# valeurs par défaut
_default = {
    "SERVER_HOST": "localhost",
    "SERVER_PORT": 8000,
    "ALLOWED_AGENT_IPS": [],
    "ALLOWED_CLIENT_IPS": [],
    "ENABLE_AUTH": False,
    "AUTH_TOKEN": "votre-token-secret-ici",
    "TIMEOUT": 60,
    "PROCESS_LIMIT": 100,
    "NETWORK_CONN_LIMIT": 100,
    "CPU_ALERT_THRESHOLD": 70,
    "CPU_ALERT_DURATION": 25,
    "RAM_ALERT_THRESHOLD": 95,
    "DISK_ALERT_THRESHOLD": 90,
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


# garantit l'existence du fichier YAML au premier import
if not os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(_default, f)


_config_data = _load_config()

# expose les valeurs comme variables de module
for key, val in _config_data.items():
    globals()[key] = val


def save_config(updates: dict) -> None:
    global _config_data
    print("save_config called with", updates, type(updates))
    # apply updates only for known keys, with basic coercion
    if not hasattr(updates, "items"):
        raise TypeError(f"save_config expects a dict, got {type(updates)}")
    for k, v in updates.items():
        if k not in _default:
            # ignore unknown fields
            continue
        default_val = _default[k]
        try:
            if isinstance(default_val, bool):
                # bool('False') is True so convert carefully
                if isinstance(v, str):
                    v2 = v.lower() in ("1", "true", "yes", "on")
                else:
                    v2 = bool(v)
                _config_data[k] = v2
            elif isinstance(default_val, int):
                _config_data[k] = int(v)
            elif isinstance(default_val, list):
                if isinstance(v, (list, tuple)):
                    _config_data[k] = list(v)
                elif isinstance(v, str):
                    # comma-separated
                    _config_data[k] = [x.strip() for x in v.split(",") if x.strip()]
                else:
                    _config_data[k] = []
            else:
                # fallback for str or others
                _config_data[k] = v
            globals()[k] = _config_data[k]
        except Exception as e:
            # log but continue
            print(f"warning: failed to coerce config key {k} -> {e}")
            _config_data[k] = v
            globals()[k] = v
    # before overwriting we keep a backup of the current data
    try:
        if os.path.exists(CONFIG_PATH):
            bak = CONFIG_PATH + ".bak"
            with open(bak, "w", encoding="utf-8") as fb:
                yaml.safe_dump(_config_data, fb)
    except Exception as e:
        print("warning: could not write backup config file:", e)
    # write to YAML
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(_config_data, f)
    except Exception as e:
        print("Error writing config file:", e)
        raise


def reload() -> None:
    global _config_data
    _config_data = _load_config()
    for key, val in _config_data.items():
        globals()[key] = val
