"""
WebSocket support pour les mises à jour en temps réel
Gère deux types de WebSocket:
1. /ws         - Pour les clients web (navigateur)
2. /ws/agent   - Pour les agents qui envoient les données
"""

import asyncio
import json
from datetime import datetime

from config import ALLOWED_AGENT_IPS, ALLOWED_CLIENT_IPS

# stockage historique
try:
    from db.storage import insert_metric, insert_notification
except ImportError:
    insert_metric = lambda *args, **kwargs: None
    insert_notification = lambda *args, **kwargs: None

from fastapi import WebSocket, WebSocketDisconnect

# événement loop principal (capturé à l'initialisation FastAPI)
main_loop = None


def set_main_loop(loop):
    global main_loop
    main_loop = loop


class ClientConnectionManager:
    """Gère les connexions WebSocket des clients web"""

    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"✓ Client web connecté (total: {len(self.active_connections)})")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"✗ Client web déconnecté (total: {len(self.active_connections)})")

    async def broadcast(self, message: dict):
        """Envoie un message à tous les clients connectés"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


class AgentConnectionManager:
    """Gère les connexions WebSocket des agents"""

    def __init__(self):
        self.agent_connections = {}  # hostname -> websocket

    async def connect(self, websocket: WebSocket, hostname: str):
        self.agent_connections[hostname] = websocket
        print(
            f"✓ Agent connecté: {hostname} (total agents: {len(self.agent_connections)})"
        )

    def disconnect(self, hostname: str):
        if hostname in self.agent_connections:
            del self.agent_connections[hostname]
            print(
                f"✗ Agent déconnecté: {hostname} (total agents: {len(self.agent_connections)})"
            )

    async def get_agent_socket(self, hostname: str):
        return self.agent_connections.get(hostname)

    def get_all_agents(self):
        return list(self.agent_connections.keys())


# Managers globaux
client_manager = ClientConnectionManager()
agent_manager = AgentConnectionManager()

# état pour la surveillance des seuils par agent
_threshold_state = {}


# ================================================================
#  VÉRIFICATION DES SEUILS (CPU / RAM / DISK / SMART)
# ================================================================


def _check_thresholds(hostname: str, agent_data: dict, smart_payload: dict) -> list:
    """
    Contrôle les valeurs contre les seuils configurés.
    Retourne une liste de tuples (message, severity).
    """
    import time

    now = time.time()
    state = _threshold_state.setdefault(hostname, {})
    alerts = []

    from config import (
        CPU_ALERT_DURATION,
        CPU_ALERT_THRESHOLD,
        DISK_ALERT_THRESHOLD,
        RAM_ALERT_THRESHOLD,
    )

    # ── CPU ───────────────────────────────────────────────────────
    cpu = agent_data.get("cpu_percent", 0)
    if cpu >= CPU_ALERT_THRESHOLD:
        if "cpu" not in state:
            state["cpu"] = now
        elif now - state["cpu"] >= CPU_ALERT_DURATION:
            alerts.append((f"CPU élevé ({cpu:.1f}%)", "warning"))
            state["cpu"] = now
    else:
        state.pop("cpu", None)

    # ── RAM ───────────────────────────────────────────────────────
    ram = agent_data.get("memory", {}).get("percent", 0)
    if ram > RAM_ALERT_THRESHOLD:
        alerts.append((f"RAM critique ({ram:.1f}%)", "error"))

    # ── DISQUE ────────────────────────────────────────────────────
    disk = agent_data.get("disk", {}).get("percent", 0)
    if disk >= DISK_ALERT_THRESHOLD:
        alerts.append((f"Disque plein ({disk:.1f}%)", "error"))

    # ── S.M.A.R.T. ────────────────────────────────────────────────
    if smart_payload and smart_payload.get("available"):
        for alert in smart_payload.get("alerts", []):
            disk_name = alert.get("disk", "?")
            alert_type = alert.get("type", "unknown")
            level = alert.get("level", "WARNING")
            message = alert.get("message", "")

            # Clé unique pour éviter le spam (re-alerte toutes les 5 min)
            alert_key = f"smart_{disk_name}_{alert_type}"
            if alert_key not in state or now - state[alert_key] >= 300:
                severity = "error" if level == "CRITICAL" else "warning"
                alerts.append((message, severity))
                state[alert_key] = now

    return alerts


# ================================================================
#  ENDPOINT CLIENTS WEB
# ================================================================


async def web_client_endpoint(websocket: WebSocket, computers_data):
    """Endpoint WebSocket pour les clients web"""
    client_ip = websocket.client.host
    if ALLOWED_CLIENT_IPS and client_ip not in ALLOWED_CLIENT_IPS:
        await websocket.close(code=1008, reason="IP not allowed")
        return

    await client_manager.connect(websocket)
    try:
        # Envoi initial de l'état complet
        await websocket.send_json(
            {
                "type": "update",
                "data": computers_data,
                "timestamp": datetime.now().isoformat(),
            }
        )

        while True:
            await websocket.send_json(
                {
                    "type": "update",
                    "data": computers_data,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        client_manager.disconnect(websocket)
    except Exception:
        client_manager.disconnect(websocket)


# ================================================================
#  ENDPOINT AGENTS
# ================================================================


async def agent_endpoint(websocket: WebSocket, computers_data):
    """Endpoint WebSocket pour les agents qui envoient les données"""
    client_ip = websocket.client.host
    if ALLOWED_AGENT_IPS and client_ip not in ALLOWED_AGENT_IPS:
        await websocket.close(code=1008, reason="IP not allowed")
        return

    hostname = None
    agent_ip = client_ip

    try:
        await websocket.accept()
        print(f"-> agent connection accepted from {client_ip}")

        # ── Message d'enregistrement initial ──────────────────────
        try:
            initial_msg = await websocket.receive_json()
        except WebSocketDisconnect:
            print(
                f"! WebSocketDisconnect while waiting initial register from {client_ip}"
            )
            return
        except Exception as e:
            print(f"! Exception while receiving initial register from {client_ip}: {e}")
            try:
                await websocket.close(code=1011, reason="receive error")
            except Exception:
                pass
            return

        # ── Authentification ──────────────────────────────────────
        try:
            from config import AUTH_TOKEN, ENABLE_AUTH
        except ImportError:
            ENABLE_AUTH = False
            AUTH_TOKEN = None

        if ENABLE_AUTH and AUTH_TOKEN:
            token = initial_msg.get("auth_token")
            if token is None:
                print(
                    f"! Warning: no auth token provided by {client_ip} (accepting for backward compatibility)"
                )
            elif token != AUTH_TOKEN:
                print(
                    f"✗ Invalid auth token from {client_ip}: received={token!r} expected=***"
                )
                await websocket.close(code=1008, reason="Invalid token")
                return

        # ── Extraction hostname ────────────────────────────────────
        if isinstance(initial_msg, dict):
            if initial_msg.get("type") == "register":
                hostname = initial_msg.get("hostname")
                agent_ip = initial_msg.get("local_ip") or client_ip
            else:
                hostname = initial_msg.get("hostname") or initial_msg.get("host")
                agent_ip = initial_msg.get("local_ip") or client_ip

        if not hostname:
            print(
                f"✗ No hostname provided by agent from {client_ip}; closing connection"
            )
            try:
                await websocket.close(code=1000, reason="No hostname provided")
            except Exception:
                pass
            return

        await agent_manager.connect(websocket, hostname)

        # ── Boucle de réception des métriques ─────────────────────
        while True:
            try:
                message = await websocket.receive_json()
            except WebSocketDisconnect:
                print(
                    f"! WebSocketDisconnect while receiving from {hostname} ({client_ip})"
                )
                break
            except Exception as e:
                print(
                    f"! Exception while receiving JSON from {hostname} ({client_ip}): {e}"
                )
                break

            if message.get("type") == "metrics":
                agent_data = message.get("data", {})
                agent_data["agent_ip"] = agent_ip
                agent_data["last_seen"] = datetime.now().isoformat()
                agent_data["offline"] = False
                agent_data.pop("offline_since", None)

                # ── Récupération payload SMART ─────────────────────
                smart_payload = message.get("smart", {})

                # Validation basique du payload SMART
                if not isinstance(smart_payload, dict):
                    smart_payload = {}

                # Attacher les données SMART à l'agent dans computers_data
                agent_data["smart"] = smart_payload

                # ── Persistance en base ────────────────────────────
                try:
                    insert_metric(hostname, agent_data)
                except Exception:
                    pass

                computers_data[hostname] = agent_data

                # ── Log console ────────────────────────────────────
                smart_log = ""
                if smart_payload.get("available"):
                    disks = smart_payload.get("disks", [])
                    smart_log = " | 💾 " + " ".join(
                        f"{d['disk']}:{d.get('health','?')} {d.get('temperature','?')}°C"
                        for d in disks
                        if d.get("available")
                    )

                print(
                    f"📊 {hostname}: "
                    f"CPU={agent_data.get('cpu_percent', 0):.1f}% | "
                    f"RAM={agent_data.get('memory', {}).get('percent', 0):.1f}% | "
                    f"TCP={agent_data.get('protocols', {}).get('tcp', {}).get('established', 0)}"
                    f"{smart_log}"
                )

                # ── Vérification des seuils + alertes ─────────────
                threshold_alerts = _check_thresholds(
                    hostname, agent_data, smart_payload
                )

                for msg, sev in threshold_alerts:
                    try:
                        insert_notification(hostname, msg, sev)
                    except Exception:
                        pass
                    try:
                        await client_manager.broadcast(
                            {
                                "type": "alert",
                                "hostname": hostname,
                                "message": msg,
                                "severity": sev,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    except Exception as e:
                        print(f"⚠️  Échec broadcast alertes: {e}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"❌ Erreur agent {hostname}: {e}")
    finally:
        # ── Marquage hors ligne ────────────────────────────────────
        if hostname:
            data = computers_data.get(hostname, {})
            if data and not data.get("offline"):
                data["offline"] = True
                data["offline_since"] = datetime.now().isoformat()
                try:
                    insert_notification(hostname, "Agent hors ligne", "error")
                except Exception:
                    pass
                try:
                    await client_manager.broadcast(
                        {
                            "type": "alert",
                            "hostname": hostname,
                            "message": "Agent hors ligne",
                            "severity": "error",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    await client_manager.broadcast(
                        {
                            "type": "agent_update",
                            "hostname": hostname,
                            "data": data,
                        }
                    )
                except Exception:
                    pass
            agent_manager.disconnect(hostname)


# ================================================================
#  SETUP
# ================================================================


def setup_websocket(app, computers_data):
    """Configure les endpoints WebSocket sur l'app FastAPI"""

    @app.on_event("startup")
    async def _capture_loop():
        set_main_loop(asyncio.get_running_loop())

    @app.websocket("/ws")
    async def websocket_web_clients(websocket: WebSocket):
        await web_client_endpoint(websocket, computers_data)

    @app.websocket("/ws/agent")
    async def websocket_agents(websocket: WebSocket):
        await agent_endpoint(websocket, computers_data)
