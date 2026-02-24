"""
Gestion du nettoyage des données et ping des agents
"""

import threading
import time

import requests


def clean_old_data(computers_data):
    """Vérifie la connexion des agents toutes les 60 secondes via ping"""

    def ping_loop():
        while True:
            time.sleep(60)  # Ping toutes les 60 secondes

            to_remove = []

            for hostname, data in list(computers_data.items()):
                agent_ip = data.get("agent_ip")
                if not agent_ip:
                    to_remove.append(hostname)
                    continue

                # Ping l'agent
                try:
                    response = requests.get(f"http://{agent_ip}:8080/ping", timeout=5)
                    if response.status_code != 200:
                        to_remove.append(hostname)
                except Exception:
                    to_remove.append(hostname)

            for hostname in to_remove:
                if hostname in computers_data:
                    data = computers_data[hostname]
                    if not data.get("offline"):
                        print(f"⚠️  {hostname} déconnecté (ping échoué)")
                        data["offline"] = True
                        data["offline_since"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                        # envoyer alerte aux clients web
                        try:
                            import asyncio

                            from websocket_handler import client_manager, main_loop

                            if main_loop:
                                asyncio.run_coroutine_threadsafe(
                                    client_manager.broadcast(
                                        {
                                            "type": "alert",
                                            "hostname": hostname,
                                            "message": "Agent hors ligne (ping échoué)",
                                            "timestamp": time.strftime(
                                                "%Y-%m-%dT%H:%M:%S"
                                            ),
                                        }
                                    ),
                                    main_loop,
                                )
                                # mise à jour de l'agent
                                asyncio.run_coroutine_threadsafe(
                                    client_manager.broadcast(
                                        {
                                            "type": "agent_update",
                                            "hostname": hostname,
                                            "data": data,
                                        }
                                    ),
                                    main_loop,
                                )
                        except Exception:
                            pass

    # Démarre le thread de nettoyage en arrière-plan
    thread = threading.Thread(target=ping_loop, daemon=True)
    thread.start()
    return thread
