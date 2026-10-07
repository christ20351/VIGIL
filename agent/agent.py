"""
Agent de Monitoring - Version 3.0 (WebSocket Real-time)
Collecte les métriques système et les envoie au serveur central via WebSocket
"""

import asyncio
import json
import os
import secrets
import socket
import shutil
import string
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import websockets

# ================================================================
#  HELPERS CONFIG
# ================================================================


def _get_config_path() -> str:
    """
    Toujours à côté du .exe (binaire PyInstaller) ou du script (dev).
    _MEIPASS est un dossier TEMP détruit à chaque fermeture → ne jamais
    stocker de données persistantes dedans.
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "agent_config.json")


CONFIG_FILE = _get_config_path()


def _load_json_config():
    """Charge agent_config.json. Retourne None si absent ou invalide."""
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "SERVER_IP" in data and "SERVER_PORT" in data:
            return data
    except Exception:
        pass
    return None


def _save_json_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def _clear():
    os.system("cls" if sys.platform == "win32" else "clear")


def _print_banner():
    print(
        r"""
 __     __ ___    _       _     _
 \ \   / // __|  (_)     (_)   | |
  \ \_/ /| (_|    _  ___  _  __| |
   \   /  \__ \  | |/ _ \| |/ _` |
    |_|   |___/  | | (_) | | (_| |
                _/ |\___/|_|\__,_|
               |__/

           VIGIL - Monitoring System
"""
    )


def _ask(label, default=None, cast=str, validate=None, secret=False):
    """Pose une question dans le terminal avec valeur par défaut."""
    import getpass

    while True:
        hint = f" [{default}]" if default is not None else ""
        prompt = f"  {label}{hint} : "
        try:
            raw = getpass.getpass(prompt) if secret else input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\n\n  [!] Configuration annulée.")
            sys.exit(0)

        value = (
            raw.strip()
            if raw.strip()
            else (str(default) if default is not None else "")
        )

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
    Configuration interactive dans le terminal.
    """
    _clear()
    print("=" * 62)
    _print_banner()
    print("=" * 62)

    if existing:
        print("\n  [INFO] Configuration existante :\n")
        print(
            f"    Serveur    : {existing.get('SERVER_IP')}:{existing.get('SERVER_PORT')}"
        )
        print(f"    Intervalle : {existing.get('UPDATE_INTERVAL', 1)}s")
        print(
            f"    SMART      : {'activé' if existing.get('HDD_SMART_ENABLED', True) else 'désactivé'}"
        )
        print()
        try:
            rep = input("  Reconfigurer ? (o/N) : ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            rep = ""
        if rep != "o":
            return existing
        print()

    print("  ┌────────────────────────────────────────────────────┐")
    print("  │          Configuration de l'agent VIGIL            │")
    print("  └────────────────────────────────────────────────────┘")
    print()
    print("  [ Connexion au serveur ]")

    server_ip = _ask(
        "IP ou hostname du serveur VIGIL",
        default=(
            existing.get("SERVER_IP", "192.168.1.10") if existing else "192.168.1.10"
        ),
    )
    server_port = _ask(
        "Port du serveur",
        default=existing.get("SERVER_PORT", 5000) if existing else 5000,
        cast=int,
        validate=lambda v: 1 <= v <= 65535,
    )
    interval = _ask(
        "Intervalle d'envoi (secondes)",
        default=existing.get("UPDATE_INTERVAL", 1) if existing else 1,
        cast=int,
        validate=lambda v: v >= 1,
    )

    print()
    print("  [ Monitoring S.M.A.R.T. ]")
    smart_enabled = _ask_bool(
        "Activer la surveillance S.M.A.R.T. des disques ?",
        default=existing.get("HDD_SMART_ENABLED", True) if existing else True,
    )
    temp_warning = _ask(
        "Seuil température WARNING (°C)",
        default=existing.get("HDD_TEMP_WARNING", 45) if existing else 45,
        cast=int,
        validate=lambda v: 1 <= v <= 100,
    )
    temp_critical = _ask(
        "Seuil température CRITICAL (°C)",
        default=existing.get("HDD_TEMP_CRITICAL", 55) if existing else 55,
        cast=int,
        validate=lambda v: 1 <= v <= 100,
    )

    print()
    print("  ┌────────────────────────────────────────────────────┐")
    print("  │                   Récapitulatif                    │")
    print("  └────────────────────────────────────────────────────┘")
    print(f"    Serveur cible : ws://{server_ip}:{server_port}/ws/agent")
    print(f"    Intervalle    : {interval}s")
    print(f"    SMART         : {'activé' if smart_enabled else 'désactivé'}")
    if smart_enabled:
        print(f"    Temp WARNING  : {temp_warning}°C")
        print(f"    Temp CRITICAL : {temp_critical}°C")
    print()

    try:
        ok = input("  Confirmer et démarrer ? (O/n) : ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ok = ""
    if ok == "n":
        print("\n  [!] Annulé. Relancez l'agent pour recommencer.\n")
        sys.exit(0)

    cfg = {
        "SERVER_IP": server_ip,
        "SERVER_PORT": server_port,
        "UPDATE_INTERVAL": interval,
        "ENABLE_AUTH": existing.get("ENABLE_AUTH", False) if existing else False,
        "AUTH_TOKEN": existing.get("AUTH_TOKEN", None) if existing else None,
        "HDD_SMART_ENABLED": smart_enabled,
        "HDD_TEMP_WARNING": temp_warning,
        "HDD_TEMP_CRITICAL": temp_critical,
        # intervalles de collecte (secondes) — modifiables directement ici
        "PROCESSES_INTERVAL": (existing or {}).get("PROCESSES_INTERVAL", 10),
        "CONNECTIONS_INTERVAL": (existing or {}).get("CONNECTIONS_INTERVAL", 10),
        "INTERFACES_INTERVAL": (existing or {}).get("INTERFACES_INTERVAL", 30),
        "SMART_INTERVAL": (existing or {}).get("SMART_INTERVAL", 300),
        "LOG_EVERY": (existing or {}).get("LOG_EVERY", 10),
    }
    _save_json_config(cfg)
    print(f"\n  [OK] Configuration sauvegardée → {CONFIG_FILE}")
    time.sleep(1)
    return cfg


# ================================================================
#  POINT D'ENTRÉE
# ================================================================
if __name__ == "__main__":

    force = "--reconfigure" in sys.argv or "--config" in sys.argv
    json_cfg = _load_json_config()

    if force or not json_cfg:
        json_cfg = _interactive_setup(json_cfg)

    # Charger la config finale
    SERVER_IP = json_cfg["SERVER_IP"]
    SERVER_PORT = json_cfg["SERVER_PORT"]
    UPDATE_INTERVAL = json_cfg.get("UPDATE_INTERVAL", 1)
    ENABLE_AUTH = json_cfg.get("ENABLE_AUTH", False)
    AUTH_TOKEN = json_cfg.get("AUTH_TOKEN", None)
    HDD_SMART_ENABLED = json_cfg.get("HDD_SMART_ENABLED", True)
    HDD_TEMP_WARNING = json_cfg.get("HDD_TEMP_WARNING", 45)
    HDD_TEMP_CRITICAL = json_cfg.get("HDD_TEMP_CRITICAL", 55)
    # exécution privilégiée des commandes distantes — désactivée par
    # défaut : activez PRIVILEGED_EXECUTION: true dans agent_config.json
    # uniquement si un sudoers NOPASSWD est configuré pour l'utilisateur de
    # l'agent (sinon préfixer sudo -n fait échouer toutes les commandes).
    # Modèle recommandé : lancer le service agent avec les droits root.
    PRIVILEGED_EXECUTION = json_cfg.get("PRIVILEGED_EXECUTION", False)

    # ── Intervalles de collecte (secondes) — ajustables dans agent_config.json ──
    # Les métriques cœur (CPU/RAM/disque/réseau) partent à UPDATE_INTERVAL ;
    # les sections coûteuses sont collectées moins souvent et mises en cache
    # par le serveur, qui reconstruit le payload complet.
    PROCESSES_INTERVAL = json_cfg.get("PROCESSES_INTERVAL", 10)
    CONNECTIONS_INTERVAL = json_cfg.get("CONNECTIONS_INTERVAL", 10)
    INTERFACES_INTERVAL = json_cfg.get("INTERFACES_INTERVAL", 30)
    SMART_INTERVAL = json_cfg.get("SMART_INTERVAL", 300)
    LOG_EVERY = max(1, json_cfg.get("LOG_EVERY", 10))

    # Fallback token depuis server/config.yaml si pas dans agent_config.json
    if not AUTH_TOKEN:
        try:
            import yaml

            cfg_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "server", "config.yaml")
            )
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                if "AUTH_TOKEN" in data:
                    AUTH_TOKEN = data.get("AUTH_TOKEN")
                if "ENABLE_AUTH" in data:
                    ENABLE_AUTH = bool(data.get("ENABLE_AUTH"))
        except Exception:
            pass

    from smart_monitor import check_smart_alerts, get_all_disks_smart
    from system_info import get_system_info
    from inventory import collect_inventory

    INVENTORY_INTERVAL = max(300, json_cfg.get("INVENTORY_INTERVAL", 21600))

    HOSTNAME = socket.gethostname()
    AGENT_PORT = 8080
    WS_URL = f"ws://{SERVER_IP}:{SERVER_PORT}/ws/agent"

    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    LOCAL_IP = get_local_ip()

    _clear()
    print("=" * 70)
    print(f"🤖 Agent de Monitoring v3.0 - {HOSTNAME}")
    _print_banner()
    print("=" * 70)
    print(f"📡 Serveur cible     : {WS_URL}")
    print(f"⏱️  Intervalle       : {UPDATE_INTERVAL}s (métriques cœur)")
    print(f"⚙️  Collectes        : processus {PROCESSES_INTERVAL}s | connexions {CONNECTIONS_INTERVAL}s | interfaces {INTERFACES_INTERVAL}s | SMART {SMART_INTERVAL}s")
    print(f"🌐 Port ping         : {AGENT_PORT} (fallback)")
    print(f"💻 OS détecté       : {sys.platform}")
    print(f"🖥️  IP locale        : {LOCAL_IP}")
    print(f"📁 Config chargée   : {CONFIG_FILE}")
    print(f"💾 SMART monitoring  : {'activé' if HDD_SMART_ENABLED else 'désactivé'}")
    print(f"🔑 Commandes privilégiées : {'activé' if PRIVILEGED_EXECUTION else 'désactivé'}")
    print("=" * 70)
    print()

    def _as_privileged(command: str) -> str:
        """Préfixe la commande pour l'exécuter avec les droits maximum.

        - root déjà : exécution directe.
        - POSIX non root : `sudo -n` (nécessite un sudoers NOPASSWD pour
          l'utilisateur de l'agent, ou un agent lancé via sudo).
        - Windows : pas de préfixe — lancer l'agent en session Administrateur.
        """
        if not PRIVILEGED_EXECUTION:
            return command
        if os.name == "nt":
            return command  # élévation gérée au lancement de l'agent
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            return command  # déjà root
        if not shutil.which("sudo"):
            return command  # sudo absent : exécution telle quelle
        return f"sudo -n {command}"

    def _run_shell_command(command: str, timeout: int) -> dict:
        """Exécute une commande système locale (demandée par le serveur)."""
        command = _as_privileged(command)
        try:
            r = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            # tronquer les sorties énormes pour ne pas saturer le canal WS
            return {
                "stdout": (r.stdout or "")[-20000:],
                "stderr": (r.stderr or "")[-20000:],
                "exit_code": r.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": f"Timeout après {timeout}s", "exit_code": -1}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "exit_code": -1}

    async def handle_server_messages(websocket):
        """Récepteur: traite les messages du serveur (commandes à exécuter)."""
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if msg.get("type") == "exec":
                command = (msg.get("command") or "").strip()
                cmd_id = msg.get("id")
                timeout = int(msg.get("timeout") or 60)
                if not command:
                    await websocket.send(json.dumps({
                        "type": "exec_result", "id": cmd_id,
                        "stdout": "", "stderr": "Commande vide", "exit_code": -1,
                    }))
                    continue
                print(f"⚙️  Commande distante reçue: {command}")
                result = await asyncio.to_thread(_run_shell_command, command, timeout)
                await websocket.send(json.dumps({"type": "exec_result", "id": cmd_id, **result}))

    async def send_data_websocket():
        print("🚀 Démarrage de la connexion WebSocket...")
        reconnect_delay = 1

        # ── Cache S.M.A.R.T. : smartctl est un sous-processus coûteux, on
        # l'exécute dans un thread dédié à son propre rythme (SMART_INTERVAL)
        # au lieu de chaque seconde.
        smart_cache = {
            "payload": {"available": False, "disks": [], "alerts": []},
            "fresh": False,
        }

        def smart_worker():
            while True:
                if HDD_SMART_ENABLED:
                    try:
                        disks = get_all_disks_smart()
                        alerts = check_smart_alerts(
                            disks,
                            temp_warning=HDD_TEMP_WARNING,
                            temp_critical=HDD_TEMP_CRITICAL,
                        )
                        smart_cache["payload"] = {
                            "available": bool(disks),
                            "disks": disks,
                            "alerts": alerts,
                            "disks_count": len(disks),
                        }
                        smart_cache["fresh"] = True
                    except Exception as e:
                        print(f"⚠️  Erreur collecte SMART: {e}")
                time.sleep(SMART_INTERVAL)

        threading.Thread(target=smart_worker, daemon=True, name="SmartWorker").start()
        # première collecte immédiate au démarrage
        smart_cache["fresh"] = True

        while True:
            try:
                async with websockets.connect(
                    WS_URL, ping_interval=None, close_timeout=10
                ) as websocket:
                    print(f"✓ Connecté au serveur WebSocket: {WS_URL}")
                    reconnect_delay = 1

                    register_payload = {
                        "type": "register",
                        "hostname": HOSTNAME,
                        "local_ip": LOCAL_IP,
                    }
                    if ENABLE_AUTH and AUTH_TOKEN:
                        register_payload["auth_token"] = AUTH_TOKEN

                    await websocket.send(json.dumps(register_payload))

                    # récepteur des commandes distantes envoyées par le serveur
                    receiver_task = asyncio.create_task(
                        handle_server_messages(websocket)
                    )

                    last_procs = last_conns = last_ifaces = float("-inf")
                    tick = 0
                    last_inventory = float("-inf")

                    try:
                        while True:
                            try:
                                now = time.monotonic()

                                # ── Inventaire (au boot puis toutes les 6 h) ──
                                if now - last_inventory >= INVENTORY_INTERVAL:
                                    try:
                                        inv = await asyncio.to_thread(collect_inventory)
                                        await websocket.send(json.dumps({
                                            "type": "inventory",
                                            "hostname": HOSTNAME,
                                            "data": inv,
                                        }))
                                        print("📦 Inventaire envoyé")
                                    except Exception as e:
                                        print(f"⚠️  Erreur inventaire: {e}")
                                    last_inventory = now

                                # ── Métriques système (sections lourdes cadencées) ──
                                want_procs = now - last_procs >= PROCESSES_INTERVAL
                                want_conns = now - last_conns >= CONNECTIONS_INTERVAL
                                want_ifaces = now - last_ifaces >= INTERFACES_INTERVAL

                                data = get_system_info(
                                    include_processes=want_procs,
                                    include_connections=want_conns,
                                    include_interfaces=want_ifaces,
                                )
                                if want_procs:
                                    last_procs = now
                                if want_conns:
                                    last_conns = now
                                if want_ifaces:
                                    last_ifaces = now

                                # ── Données S.M.A.R.T. (issues du cache) ────────
                                smart_payload = None
                                if smart_cache["fresh"]:
                                    smart_payload = smart_cache["payload"]
                                    smart_cache["fresh"] = False

                                # ── Envoi au serveur ───────────────────────────
                                msg = {
                                    "type": "metrics",
                                    "hostname": HOSTNAME,
                                    "timestamp": datetime.now().isoformat(),
                                    "data": data,
                                }
                                if smart_payload is not None:
                                    msg["smart"] = smart_payload
                                await websocket.send(json.dumps(msg))

                                # ── Log console (1 ligne sur LOG_EVERY) ─────────
                                tick += 1
                                if tick % LOG_EVERY == 1:
                                    net = data["network"]
                                    tcp = (
                                        data.get("protocols", {})
                                        .get("tcp", {})
                                        .get("established", "?")
                                    )
                                    smart_log = ""
                                    sp = smart_cache["payload"]
                                    if HDD_SMART_ENABLED and sp.get("available"):
                                        disks_summary = " ".join(
                                            f"{d.get('disk','?')}:{d.get('health','?')}({d.get('temperature')}°C)"
                                            for d in sp.get("disks", [])
                                            if d.get("available")
                                        )
                                        smart_log = (
                                            f" | 💾 {disks_summary}" if disks_summary else ""
                                        )
                                    print(
                                        f"✓ CPU={data['cpu_percent']:.1f}% | "
                                        f"RAM={data['memory']['percent']:.1f}% | "
                                        f"↓{net['bytes_recv_per_sec']/1024:.1f}KB/s | "
                                        f"↑{net['bytes_sent_per_sec']/1024:.1f}KB/s | "
                                        f"TCP={tcp}{smart_log}"
                                    )

                            except json.JSONDecodeError as e:
                                print(f"⚠️  Erreur JSON: {e}")
                            except Exception as e:
                                print(f"⚠️  Erreur lors de l'envoi: {e}")
                                break

                            await asyncio.sleep(UPDATE_INTERVAL)
                    finally:
                        receiver_task.cancel()
                        try:
                            await receiver_task
                        except Exception:
                            pass

            except ConnectionRefusedError:
                print(f"✗ Serveur indisponible. Reconnexion dans {reconnect_delay}s...")
            except websockets.exceptions.WebSocketException as e:
                print(
                    f"⚠️  Erreur WebSocket: {e}. Reconnexion dans {reconnect_delay}s..."
                )
            except Exception as e:
                print(f"✗ Erreur: {e}. Reconnexion dans {reconnect_delay}s...")

            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 30)

    class PingHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/ping":
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"status": "ok", "hostname": HOSTNAME}).encode()
                )
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    def start_ping_server():
        try:
            server = HTTPServer(("0.0.0.0", AGENT_PORT), PingHandler)
            print(f"🌐 Serveur ping démarré sur le port {AGENT_PORT} (fallback)")
            server.serve_forever()
        except Exception as e:
            print(f"❌ Erreur serveur ping: {e}")

    ping_thread = threading.Thread(target=start_ping_server, daemon=True)
    ping_thread.start()

    try:
        asyncio.run(send_data_websocket())
    except KeyboardInterrupt:
        print("\n\n🛑 Agent arrêté proprement.")
        sys.exit(0)
