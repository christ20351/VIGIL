"""
Agent de Monitoring - Version 3.0 (WebSocket Real-time)
Collecte les métriques système et les envoie au serveur central via WebSocket
"""

import asyncio
import json
import os
import socket
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import websockets

# ================================================================
#  HELPERS CONFIG
# ================================================================

CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "agent_config.json"
)


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


def _interactive_setup(existing: dict = None) -> dict:
    """
    Configuration interactive dans le terminal.
    Demande uniquement : IP serveur, port, intervalle.
    Le token d'auth est géré côté serveur — l'agent le lit depuis
    agent_config.json s'il y est déjà (mis en place par l'admin).
    """
    _clear()
    print("=" * 62)
    _print_banner()
    print("=" * 62)

    # ── Config existante : proposer de garder ou modifier ────────
    if existing:
        print("\n  [INFO] Configuration existante :\n")
        print(
            f"    Serveur    : {existing.get('SERVER_IP')}:{existing.get('SERVER_PORT')}"
        )
        print(f"    Intervalle : {existing.get('UPDATE_INTERVAL', 1)}s")
        print()
        try:
            rep = input("  Reconfigurer ? (o/N) : ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            rep = ""
        if rep != "o":
            return existing
        print()

    # ── Saisie ──────────────────────────────────────────────────
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

    # ── Récapitulatif ───────────────────────────────────────────
    print()
    print("  ┌────────────────────────────────────────────────────┐")
    print("  │                   Récapitulatif                    │")
    print("  └────────────────────────────────────────────────────┘")
    print(f"    Serveur cible : ws://{server_ip}:{server_port}/ws/agent")
    print(f"    Intervalle    : {interval}s")
    print()

    try:
        ok = input("  Confirmer et démarrer ? (O/n) : ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ok = ""
    if ok == "n":
        print("\n  [!] Annulé. Relancez l'agent pour recommencer.\n")
        sys.exit(0)

    # Conserver le token existant s'il y en a un (mis par l'admin)
    cfg = {
        "SERVER_IP": server_ip,
        "SERVER_PORT": server_port,
        "UPDATE_INTERVAL": interval,
        "ENABLE_AUTH": existing.get("ENABLE_AUTH", False) if existing else False,
        "AUTH_TOKEN": existing.get("AUTH_TOKEN", None) if existing else None,
    }
    _save_json_config(cfg)
    print("\n  [OK] Configuration sauvegardée → agent_config.json")
    time.sleep(1)
    return cfg


# ================================================================
#  POINT D'ENTRÉE  (tout le reste s'exécute ici, une seule fois)
# ================================================================
if __name__ == "__main__":

    # ── 1. Décider si on lance le setup ─────────────────────────
    # Déclenchement si :
    #   • aucun agent_config.json valide  → premier lancement
    #   • --reconfigure / --config passé  → reconfiguration forcée
    force = "--reconfigure" in sys.argv or "--config" in sys.argv
    json_cfg = _load_json_config()

    if force or not json_cfg:
        json_cfg = _interactive_setup(json_cfg)

    # ── 2. Charger la config finale ──────────────────────────────
    SERVER_IP = json_cfg["SERVER_IP"]
    SERVER_PORT = json_cfg["SERVER_PORT"]
    UPDATE_INTERVAL = json_cfg.get("UPDATE_INTERVAL", 1)
    ENABLE_AUTH = json_cfg.get("ENABLE_AUTH", False)
    AUTH_TOKEN = json_cfg.get("AUTH_TOKEN", None)

    # ── Fallback config.py si json_cfg venait d'un config.py ─────
    # (cas installation classique via dépôt cloné sans agent_config.json)
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
                print(
                    f"(agent) fallback token depuis {cfg_path}: "
                    f"ENABLE_AUTH={ENABLE_AUTH}, AUTH_TOKEN={'***' if AUTH_TOKEN else None}"
                )
        except Exception:
            pass

    # ── 3. Importer les métriques ────────────────────────────────
    from system_info import get_system_info

    # ── 4. Variables runtime ─────────────────────────────────────
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

    # ── 5. Bannière de démarrage ─────────────────────────────────
    _clear()
    print("=" * 70)
    print(f"🤖 Agent de Monitoring v3.0 - {HOSTNAME}")
    _print_banner()
    print("=" * 70)
    print(f"📡 Serveur cible     : {WS_URL}")
    print(f"⏱️  Intervalle       : {UPDATE_INTERVAL}s")
    print(f"🌐 Port ping         : {AGENT_PORT} (fallback)")
    print(f"💻 OS détecté       : {sys.platform}")
    print(f"🖥️  IP locale        : {LOCAL_IP}")
    print("=" * 70)
    print()

    # ── 6. Fonctions WebSocket & ping ────────────────────────────
    async def send_data_websocket():
        print("🚀 Démarrage de la connexion WebSocket...")
        reconnect_delay = 1

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

                    dbg = {**register_payload}
                    if "auth_token" in dbg:
                        dbg["auth_token"] = "***"
                    print(f"-> register payload: {dbg}")
                    await websocket.send(json.dumps(register_payload))

                    while True:
                        try:
                            data = get_system_info()
                            await websocket.send(
                                json.dumps(
                                    {
                                        "type": "metrics",
                                        "hostname": HOSTNAME,
                                        "timestamp": datetime.now().isoformat(),
                                        "data": data,
                                    }
                                )
                            )

                            tcp_count = data["protocols"]["tcp"]["established"]
                            proc_count = len(data["processes"])
                            net = data["network"]
                            print(
                                f"✓ CPU={data['cpu_percent']:.1f}% | "
                                f"RAM={data['memory']['percent']:.1f}% | "
                                f"↓{net['bytes_recv_per_sec']/1024:.1f}KB/s | "
                                f"↑{net['bytes_sent_per_sec']/1024:.1f}KB/s | "
                                f"TCP={tcp_count} | Proc={proc_count}"
                            )
                        except json.JSONDecodeError as e:
                            print(f"⚠️  Erreur JSON: {e}")
                        except Exception as e:
                            print(f"⚠️  Erreur lors de l'envoi: {e}")
                            break

                        await asyncio.sleep(UPDATE_INTERVAL)

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

    # ── 7. Démarrage ─────────────────────────────────────────────
    ping_thread = threading.Thread(target=start_ping_server, daemon=True)
    ping_thread.start()

    try:
        asyncio.run(send_data_websocket())
    except KeyboardInterrupt:
        print("\n\n🛑 Agent arrêté proprement.")
        sys.exit(0)
