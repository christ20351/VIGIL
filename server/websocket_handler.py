"""
WebSocket support pour les mises à jour en temps réel
Gère deux types de WebSocket:
1. /ws - Pour les clients web (navigateur)
2. /ws/agent - Pour les agents qui envoient les données
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
            except Exception as e:
                disconnected.append(connection)

        # Nettoyer les connexions mortes
        for conn in disconnected:
            self.disconnect(conn)


class AgentConnectionManager:
    """Gère les connexions WebSocket des agents"""

    def __init__(self):
        self.agent_connections = {}  # hostname -> websocket

    async def connect(self, websocket: WebSocket, hostname: str):
        # NOTE: websocket.accept() est appelé dans agent_endpoint avant cet appel
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
        """Récupère la socket WebSocket d'un agent"""
        return self.agent_connections.get(hostname)

    def get_all_agents(self):
        """Retourne la liste de tous les agents connectés"""
        return list(self.agent_connections.keys())


# Managers globaux
client_manager = ClientConnectionManager()
agent_manager = AgentConnectionManager()

# état pour la surveillance des seuils par agent
_threshold_state = {}


# ----- helpers ----------------------------------------------------------
def _check_thresholds(hostname: str, data: dict):
    """Contrôle les valeurs contre des seuils et retourne les messages d'alerte.

    Le code appelant s'occupera du broadcast pour rester dans le contexte
    asynchrone.

    Les règles par défaut peuvent être configurées dans `server/config.py`.
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

    cpu = data.get("cpu_percent", 0)
    if cpu >= CPU_ALERT_THRESHOLD:
        if "cpu" not in state:
            state["cpu"] = now
        elif now - state["cpu"] >= CPU_ALERT_DURATION:
            alerts.append(f"CPU élevé ({cpu:.1f}%)")
            state["cpu"] = now
    else:
        state.pop("cpu", None)

    ram = data.get("memory", {}).get("percent", 0)
    if ram > RAM_ALERT_THRESHOLD:
        alerts.append(f"RAM critique ({ram:.1f}%)")

    disk = data.get("disk", {}).get("percent", 0)
    if disk >= DISK_ALERT_THRESHOLD:
        alerts.append(f"Disque plein ({disk:.1f}%)")

    return alerts


async def web_client_endpoint(websocket: WebSocket, computers_data):
    """Endpoint WebSocket pour les clients web"""
    client_ip = websocket.client.host
    if ALLOWED_CLIENT_IPS and client_ip not in ALLOWED_CLIENT_IPS:
        await websocket.close(code=1008, reason="IP not allowed")
        return

    await client_manager.connect(websocket)
    try:
        # Envoyer les données actuelles immédiatement à la connexion
        await websocket.send_json(
            {
                "type": "update",
                "data": computers_data,
                "timestamp": datetime.now().isoformat(),
            }
        )

        while True:
            # Envoyer les données mises à jour toutes les secondes
            await websocket.send_json(
                {
                    "type": "update",
                    "data": computers_data,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            # Attendre 1 seconde pour des mises à jour plus fréquentes
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        client_manager.disconnect(websocket)
    except Exception as e:
        client_manager.disconnect(websocket)


async def agent_endpoint(websocket: WebSocket, computers_data):
    """Endpoint WebSocket pour les agents qui envoient les données"""
    client_ip = websocket.client.host
    if ALLOWED_AGENT_IPS and client_ip not in ALLOWED_AGENT_IPS:
        await websocket.close(code=1008, reason="IP not allowed")
        return

    hostname = None
    try:
        # IMPORTANT: Accepter d'abord, puis lire les messages
        await websocket.accept()

        # Attendre le premier message contenant le hostname (register)
        initial_msg = await websocket.receive_json()

        # Accepter "register" ou hostname directement
        if initial_msg.get("type") == "register":
            hostname = initial_msg.get("hostname")
            agent_ip = initial_msg.get("local_ip")
        else:
            hostname = initial_msg.get("hostname")
            agent_ip = initial_msg.get("local_ip")

        if not hostname:
            await websocket.close(code=1000, reason="No hostname provided")
            return

        await agent_manager.connect(websocket, hostname)

        # Recevoir les données de l'agent continuellement
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "metrics":
                # Mettre à jour les données du computer
                agent_data = data.get("data", {})
                agent_data["agent_ip"] = agent_ip  # Ajouter l'IP de l'agent
                # champs de suivi
                agent_data["last_seen"] = datetime.now().isoformat()
                agent_data["offline"] = False
                # supprimer l'éventuelle date de mise hors ligne
                agent_data.pop("offline_since", None)

                # enregistrer dans la base historique
                try:
                    from db.storage import insert_metric

                    insert_metric(hostname, agent_data)
                except Exception:
                    pass

                computers_data[hostname] = agent_data
                # stocker en base
                try:
                    insert_metric(hostname, agent_data)
                except Exception:
                    pass

                # journaliser
                print(
                    f"📊 {hostname}: "
                    f"CPU={agent_data.get('cpu_percent', 0):.1f}% | "
                    f"RAM={agent_data.get('memory', {}).get('percent', 0):.1f}% | "
                    f"TCP={agent_data.get('protocols', {}).get('tcp', {}).get('established', 0)}"
                )

                # vérifier les seuils et envoyer des alertes éventuelles
                alerts = _check_thresholds(hostname, agent_data)
                if alerts:
                    # broadcast each alert (nous sommes déjà dans un contexte async)
                    for msg in alerts:
                        # persist the alert
                        try:
                            sev = "info"
                            t = (msg or "").lower()
                            if "hors ligne" in t or "disque" in t or "critique" in t:
                                sev = "error"
                            elif "élevé" in t or "alerte" in t or "échec" in t:
                                sev = "warning"
                            insert_notification(hostname, msg, sev)
                        except Exception:
                            pass
                        try:
                            await client_manager.broadcast(
                                {
                                    "type": "alert",
                                    "hostname": hostname,
                                    "message": msg,
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )
                        except Exception as e:
                            print(f"⚠️  Échec broadcast alertes: {e}")

    except WebSocketDisconnect:
        if hostname:
            # marquer hors ligne immédiatement
            data = computers_data.get(hostname, {})
            if data and not data.get("offline"):
                data["offline"] = True
                data["offline_since"] = datetime.now().isoformat()
                # alerte hors ligne
                try:
                    # persist and broadcast
                    try:
                        insert_notification(hostname, "Agent hors ligne", "error")
                    except Exception:
                        pass
                    await client_manager.broadcast(
                        {
                            "type": "alert",
                            "hostname": hostname,
                            "message": "Agent hors ligne",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    # also push an update so the offline flag propagates
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
    except Exception as e:
        print(f"❌ Erreur agent {hostname}: {e}")
        if hostname:
            # même logique de marquage hors ligne
            data = computers_data.get(hostname, {})
            if data and not data.get("offline"):
                data["offline"] = True
                data["offline_since"] = datetime.now().isoformat()
                try:
                    try:
                        insert_notification(hostname, "Agent hors ligne (erreur)", "error")
                    except Exception:
                        pass
                    await client_manager.broadcast(
                        {
                            "type": "alert",
                            "hostname": hostname,
                            "message": "Agent hors ligne (erreur)",
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


def setup_websocket(app, computers_data):
    """Configure les endpoints WebSocket sur l'app FastAPI"""

    # capturer la boucle d'exécution utilisée par FastAPI/uvicorn
    @app.on_event("startup")
    async def _capture_loop():
        set_main_loop(asyncio.get_running_loop())

    @app.websocket("/ws")
    async def websocket_web_clients(websocket: WebSocket):
        """WebSocket pour les clients web (navigateur)"""
        await web_client_endpoint(websocket, computers_data)

    @app.websocket("/ws/agent")
    async def websocket_agents(websocket: WebSocket):
        """WebSocket pour les agents (envoient les données)"""
        await agent_endpoint(websocket, computers_data)
