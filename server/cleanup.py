"""
Gestion du marquage hors-ligne des agents.

Anciennement basé sur un ping HTTP séquentiel vers chaque agent (à 500
agents, un cycle pouvait prendre 40+ minutes). Désormais : le serveur
surveille l'âge du dernier message WebSocket reçu (last_seen), ce qui est
instantané et parallèle par nature. Le seuil est le paramètre TIMEOUT de
config.yaml ("Secondes avant de marquer un agent hors ligne").
"""

import asyncio
import threading
import time


def clean_old_data(computers_data):
    """Marque hors ligne les agents silencieux depuis plus de TIMEOUT secondes."""

    def watchdog_loop():
        import websocket_handler as _ws

        while True:
            time.sleep(15)

            try:
                import config as _config

                threshold = max(10, int(getattr(_config, "TIMEOUT", 60) or 60))
            except Exception:
                threshold = 60

            for hostname, data in list(computers_data.items()):
                if not isinstance(data, dict) or data.get("offline"):
                    continue
                age = _ws.agent_manager.seconds_since_last_message(hostname)
                # pas encore vu de message (agent connecté en HTTP legacy) :
                # on se base sur last_seen ISO du payload
                if age is None:
                    last_seen = data.get("last_seen")
                    if not last_seen:
                        continue
                    try:
                        from datetime import datetime

                        age = (datetime.now() - datetime.fromisoformat(last_seen)).total_seconds()
                    except Exception:
                        continue
                if age is None or age < threshold:
                    continue

                data["offline"] = True
                data["offline_since"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                print(f"⚠️  {hostname} silencieux depuis {int(age)}s → marqué hors ligne")

                try:
                    # main_loop est lu à l'exécution (renseigné au startup FastAPI)
                    if _ws.main_loop:
                        asyncio.run_coroutine_threadsafe(
                            _ws.client_manager.broadcast(
                                {
                                    "type": "alert",
                                    "hostname": hostname,
                                    "message": "Agent hors ligne (plus de données reçues)",
                                    "severity": "error",
                                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                }
                            ),
                            _ws.main_loop,
                        )
                        asyncio.run_coroutine_threadsafe(
                            _ws.client_manager.broadcast(
                                {
                                    "type": "agent_update",
                                    "hostname": hostname,
                                    "data": data,
                                }
                            ),
                            _ws.main_loop,
                        )
                except Exception:
                    pass

    # Démarre la surveillance en arrière-plan
    thread = threading.Thread(target=watchdog_loop, daemon=True)
    thread.start()
    return thread
