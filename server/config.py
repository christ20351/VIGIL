import os
import sys
import time
import yaml


# ================================================================
#  RÉSOLUTION DU CHEMIN CONFIG (PyInstaller + dev)
# ================================================================

def _get_config_path() -> str:
    """
    Retourne le chemin absolu de config.yaml :
    - Binaire PyInstaller → dossier du .exe  (sys.executable)
    - Script Python normal → dossier de config.py
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "config.yaml")


CONFIG_PATH = _get_config_path()

# valeurs par défaut
_default = {
    "SERVER_HOST": "0.0.0.0",
    "SERVER_PORT": 5000,
    "ALLOWED_AGENT_IPS": [],
    "ALLOWED_CLIENT_IPS": [],
    "ENABLE_AUTH": False,
    "AUTH_TOKEN": "votre-token-secret-ici",
    "TIMEOUT": 60,
    "PROCESS_LIMIT": 100,
    "NETWORK_CONN_LIMIT": 100,
    "CPU_ALERT_THRESHOLD": 90,
    "CPU_ALERT_DURATION": 25,
    "RAM_ALERT_THRESHOLD": 95,
    "DISK_ALERT_THRESHOLD": 90,
}


# ================================================================
#  SETUP INTERACTIF (premier lancement)
# ================================================================

def _clear():
    os.system("cls" if sys.platform == "win32" else "clear")


def _print_banner():
    print(r"""
 __     __ ___    _       _     _
 \ \   / // __|  (_)     (_)   | |
  \ \_/ /| (_|    _  ___  _  __| |
   \   /  \__ \  | |/ _ \| |/ _` |
    |_|   |___/  | | (_) | | (_| |
                _/ |\___/|_|\__,_|
               |__/

           VIGIL - Monitoring Server
""")


def _ask(label, default=None, cast=str, validate=None):
    while True:
        hint = f" [{default}]" if default is not None else ""
        prompt = f"  {label}{hint} : "
        try:
            raw = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\n\n  [!] Configuration annulée.")
            sys.exit(0)

        value = raw.strip() if raw.strip() else (str(default) if default is not None else "")

        if not value:
            print("  [!] Ce champ est obligatoire.")
            continue
        try:
            value = cast(value)
        except (ValueError, TypeError):
            print("  [!] Valeur invalide, réessayez.")
            continue
        if validate and not validate(value):
            print("  [!] Valeur hors limites, réessayez.")
            continue
        return value


def _ask_bool(label, default=False) -> bool:
    hint = "O/n" if default else "o/N"
    try:
        raw = input(f"  {label} ({hint}) : ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return default
    if raw in ("o", "oui", "y", "yes", "1"):
        return True
    if raw in ("n", "non", "no", "0"):
        return False
    return default


def _interactive_setup(existing: dict = None) -> dict:
    """
    Menu de configuration interactif affiché au premier lancement
    ou si --reconfigure est passé en argument.
    """
    _clear()
    print("=" * 62)
    _print_banner()
    print("=" * 62)

    # Si config existante, proposer de garder ou modifier
    if existing:
        print("\n  [INFO] Configuration existante :\n")
        print(f"    Host       : {existing.get('SERVER_HOST')}:{existing.get('SERVER_PORT')}")
        print(f"    Auth       : {'activée' if existing.get('ENABLE_AUTH') else 'désactivée'}")
        print()
        try:
            rep = input("  Reconfigurer ? (o/N) : ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            rep = ""
        if rep != "o":
            return existing
        print()

    print("  ┌────────────────────────────────────────────────────┐")
    print("  │        Configuration du serveur VIGIL              │")
    print("  └────────────────────────────────────────────────────┘")
    print()

    # Réseau
    print("  [ Réseau ]")
    host = _ask(
        "Interface d'écoute (0.0.0.0 = toutes)",
        default=existing.get("SERVER_HOST", "0.0.0.0") if existing else "0.0.0.0",
    )
    port = _ask(
        "Port du serveur",
        default=existing.get("SERVER_PORT", 5000) if existing else 5000,
        cast=int,
        validate=lambda v: 1 <= v <= 65535,
    )

    print()
    print("  [ Authentification ]")
    enable_auth = _ask_bool(
        "Activer l'authentification par token ?",
        default=existing.get("ENABLE_AUTH", False) if existing else False,
    )
    token = existing.get("AUTH_TOKEN", "votre-token-secret-ici") if existing else "votre-token-secret-ici"
    if enable_auth:
        import secrets, string
        generated = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
        token = _ask(
            "Token secret",
            default=existing.get("AUTH_TOKEN", generated) if existing else generated,
        )

    print()
    print("  [ Seuils d'alerte ]")
    cpu_threshold = _ask(
        "Seuil CPU (%)",
        default=existing.get("CPU_ALERT_THRESHOLD", 90) if existing else 90,
        cast=int,
        validate=lambda v: 1 <= v <= 100,
    )
    ram_threshold = _ask(
        "Seuil RAM (%)",
        default=existing.get("RAM_ALERT_THRESHOLD", 95) if existing else 95,
        cast=int,
        validate=lambda v: 1 <= v <= 100,
    )
    disk_threshold = _ask(
        "Seuil Disque (%)",
        default=existing.get("DISK_ALERT_THRESHOLD", 90) if existing else 90,
        cast=int,
        validate=lambda v: 1 <= v <= 100,
    )

    # Récapitulatif
    print()
    print("  ┌────────────────────────────────────────────────────┐")
    print("  │                   Récapitulatif                    │")
    print("  └────────────────────────────────────────────────────┘")
    print(f"    Serveur    : http://{host}:{port}")
    print(f"    Auth       : {'activée — token: ' + token if enable_auth else 'désactivée'}")
    print(f"    Alertes    : CPU>{cpu_threshold}% | RAM>{ram_threshold}% | Disque>{disk_threshold}%")
    print()

    try:
        ok = input("  Confirmer et démarrer ? (O/n) : ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ok = ""
    if ok == "n":
        print("\n  [!] Annulé. Relancez le serveur pour recommencer.\n")
        sys.exit(0)

    cfg = _default.copy()
    if existing:
        cfg.update(existing)
    cfg.update({
        "SERVER_HOST": host,
        "SERVER_PORT": port,
        "ENABLE_AUTH": enable_auth,
        "AUTH_TOKEN": token,
        "CPU_ALERT_THRESHOLD": cpu_threshold,
        "RAM_ALERT_THRESHOLD": ram_threshold,
        "DISK_ALERT_THRESHOLD": disk_threshold,
    })

    # Sauvegarder
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f)

    print(f"\n  [OK] Configuration sauvegardée → {CONFIG_PATH}")
    time.sleep(1)
    return cfg


# ================================================================
#  CHARGEMENT CONFIG
# ================================================================

def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}
    cfg = _default.copy()
    cfg.update(data)
    return cfg


def _init():
    """
    Point d'entrée appelé à l'import :
    - Premier lancement (pas de config.yaml) → setup interactif
    - --reconfigure en argument → setup interactif
    - Config existante → chargement silencieux
    """
    force = "--reconfigure" in sys.argv or "--config" in sys.argv
    exists = os.path.exists(CONFIG_PATH)

    if force or not exists:
        existing = _load_config() if exists else None
        cfg = _interactive_setup(existing)
    else:
        cfg = _load_config()

    return cfg


_config_data = _init()

# Expose les valeurs comme variables de module
for _key, _val in _config_data.items():
    globals()[_key] = _val


# ================================================================
#  SAVE / RELOAD
# ================================================================

def save_config(updates: dict) -> None:
    global _config_data
    if not hasattr(updates, "items"):
        raise TypeError(f"save_config expects a dict, got {type(updates)}")

    for k, v in updates.items():
        if k not in _default:
            continue
        default_val = _default[k]
        try:
            if isinstance(default_val, bool):
                v2 = v.lower() in ("1", "true", "yes", "on") if isinstance(v, str) else bool(v)
                _config_data[k] = v2
            elif isinstance(default_val, int):
                _config_data[k] = int(v)
            elif isinstance(default_val, list):
                if isinstance(v, (list, tuple)):
                    _config_data[k] = list(v)
                elif isinstance(v, str):
                    _config_data[k] = [x.strip() for x in v.split(",") if x.strip()]
                else:
                    _config_data[k] = []
            else:
                _config_data[k] = v
            globals()[k] = _config_data[k]
        except Exception as e:
            print(f"warning: failed to coerce config key {k} -> {e}")
            _config_data[k] = v
            globals()[k] = v

    # Backup avant écrasement
    try:
        if os.path.exists(CONFIG_PATH):
            bak = CONFIG_PATH + ".bak"
            with open(bak, "w", encoding="utf-8") as fb:
                yaml.safe_dump(_config_data, fb)
    except Exception as e:
        print("warning: could not write backup config file:", e)

    # Écriture
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(_config_data, f)
        print(f"[OK] config.yaml sauvegardé → {CONFIG_PATH}")
    except Exception as e:
        print("Error writing config file:", e)
        raise


def reload() -> None:
    global _config_data
    _config_data = _load_config()
    for key, val in _config_data.items():
        globals()[key] = val