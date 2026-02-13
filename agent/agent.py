"""
Agent de Monitoring - Version 3.0 (WebSocket Real-time)
Collecte les métriques système et les envoie au serveur central via WebSocket
"""

import asyncio
import json
import socket
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import websockets
from config import SERVER_IP, SERVER_PORT, UPDATE_INTERVAL
from system_info import get_system_info

# ================================
# CONFIGURATION
# ================================
HOSTNAME = socket.gethostname()
AGENT_PORT = 8080  # Port pour le ping du serveur
WS_URL = f"ws://{SERVER_IP}:{SERVER_PORT}/ws/agent"


def get_local_ip():
    """Détecte l'IP locale de la machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


LOCAL_IP = get_local_ip()
# ================================


def print_vigil_banner():
    banner = r"""
 __     __ ___    _       _     _ 
 \ \   / // __|  (_)     (_)   | |
  \ \_/ /| (_|    _  ___  _  __| |
   \   /  \__ \  | |/ _ \| |/ _` |
    |_|   |___/  | | (_) | | (_| |
                _/ |\___/|_|\__,_|
               |__/

           VIGIL - Monitoring
"""
    print(banner)


async def send_data_websocket():
    """Envoie les données au serveur central via WebSocket"""
    print("🚀 Démarrage de la connexion WebSocket...")

    reconnect_delay = 1

    while True:
        try:
            # Désactiver les pings automatiques (ping_interval=None) pour éviter les timeouts
            # Les données envoyées toutes les 5s maintiennent la connexion vivante
            async with websockets.connect(
                WS_URL, ping_interval=None, close_timeout=10  # Pas de ping automatique
            ) as websocket:
                print(f"✓ Connecté au serveur WebSocket: {WS_URL}")
                reconnect_delay = 1  # Reset delay on successful connection

                # Envoyer le hostname en premier
                await websocket.send(
                    json.dumps(
                        {"type": "register", "hostname": HOSTNAME, "local_ip": LOCAL_IP}
                    )
                )

                # Envoyer les données continuellement
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

                        print(
                            f"✓ CPU={data['cpu_percent']:.1f}% | "
                            f"RAM={data['memory']['percent']:.1f}% | "
                            f"↓{data['network']['bytes_recv_per_sec']/1024:.1f}KB/s | "
                            f"↑{data['network']['bytes_sent_per_sec']/1024:.1f}KB/s | "
                            f"TCP={tcp_count} | "
                            f"Proc={proc_count}"
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
            print(f"✗ Erreur WebSocket: {e}. Reconnexion dans {reconnect_delay}s...")
        except Exception as e:
            print(f"✗ Erreur: {e}. Reconnexion dans {reconnect_delay}s...")

        # Attendre avant de reconnecter avec backoff exponentiel
        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, 30)  # Max 30 secondes


class PingHandler(BaseHTTPRequestHandler):
    """Handler pour les requêtes de ping du serveur (fallback)"""

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
    """Démarre le serveur de ping en arrière-plan (pour fallback)"""
    try:
        server = HTTPServer(("0.0.0.0", AGENT_PORT), PingHandler)
        print(f"🌐 Serveur ping démarré sur le port {AGENT_PORT} (fallback)")
        server.serve_forever()
    except Exception as e:
        print(f"❌ Erreur serveur ping: {e}")


if __name__ == "__main__":
    print("=" * 70)
    print(f"🤖 Agent de Monitoring v3.0 - {HOSTNAME}")
    print_vigil_banner()
    print("=" * 70)
    print(f"📡 Serveur cible     : {WS_URL}")
    print(f"⏱️  Intervalle       : {UPDATE_INTERVAL}s")
    print(f"🌐 Port ping         : {AGENT_PORT} (fallback)")
    print(f"💻 OS détecté       : {sys.platform}")
    print(f"🖥️  IP locale        : {LOCAL_IP}")
    print("=" * 70)
    print()

    # Démarre le serveur de ping dans un thread séparé (pour fallback)
    ping_thread = threading.Thread(target=start_ping_server, daemon=True)
    ping_thread.start()

    try:
        # Lancer l'agent WebSocket
        asyncio.run(send_data_websocket())
    except KeyboardInterrupt:
        print("\n✓ Agent arrêté")
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\n🛑 Arrêt de l'agent...")
        sys.exit(0)
