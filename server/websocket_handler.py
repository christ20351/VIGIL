"""
WebSocket support pour les mises à jour en temps réel
Gère deux types de WebSocket:
1. /ws - Pour les clients web (navigateur)
2. /ws/agent - Pour les agents qui envoient les données
"""

import asyncio
import json
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

from config import ALLOWED_AGENT_IPS, ALLOWED_CLIENT_IPS


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
                computers_data[hostname] = agent_data

                # Afficher un log
                agent_data = data.get("data", {})
                print(
                    f"📊 {hostname}: "
                    f"CPU={agent_data.get('cpu_percent', 0):.1f}% | "
                    f"RAM={agent_data.get('memory', {}).get('percent', 0):.1f}% | "
                    f"TCP={agent_data.get('protocols', {}).get('tcp', {}).get('established', 0)}"
                )

                # Broadcaster les données mises à jour à tous les clients web
                await client_manager.broadcast(
                    {"type": "agent_update", "hostname": hostname, "data": agent_data}
                )

    except WebSocketDisconnect:
        if hostname:
            agent_manager.disconnect(hostname)
    except Exception as e:
        print(f"❌ Erreur agent {hostname}: {e}")
        if hostname:
            agent_manager.disconnect(hostname)


def setup_websocket(app, computers_data):
    """Configure les endpoints WebSocket sur l'app FastAPI"""

    @app.websocket("/ws")
    async def websocket_web_clients(websocket: WebSocket):
        """WebSocket pour les clients web (navigateur)"""
        await web_client_endpoint(websocket, computers_data)

    @app.websocket("/ws/agent")
    async def websocket_agents(websocket: WebSocket):
        """WebSocket pour les agents (envoient les données)"""
        await agent_endpoint(websocket, computers_data)
