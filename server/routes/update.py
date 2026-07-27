from datetime import datetime

import config
from fastapi import Request
from fastapi.responses import JSONResponse


def register(app):
    @app.post("/update")
    async def update(request: Request):
        """Reçoit les données d'un agent."""
        # optional token check for agents
        if config.ENABLE_AUTH:
            token = request.headers.get("X-AUTH-TOKEN") or (await request.json()).get(
                "auth_token"
            )
            if token != config.AUTH_TOKEN:
                return JSONResponse(
                    {"status": "error", "message": "Invalid token"}, status_code=401
                )
        try:
            data = await request.json()

            if not data or "hostname" not in data:
                return JSONResponse(
                    {"status": "error", "message": "Invalid data"}, status_code=400
                )

            hostname = data["hostname"]
            client_ip = request.client.host
            data["agent_ip"] = client_ip  # Stocke l'IP pour le ping
            # marquage temporel et statut
            data["last_seen"] = datetime.now().isoformat()
            data["offline"] = False
            data.pop("offline_since", None)

            is_new = hostname not in app.state.computers_data
            # stocker historique
            try:
                from db.storage import insert_metric

                insert_metric(hostname, data)
            except Exception:
                pass

            app.state.computers_data[hostname] = data
            # persistence (deux fois pour compatibilité historique)
            try:
                from db.storage import insert_metric

                insert_metric(hostname, data)
            except Exception:
                pass

            cpu = data.get("cpu_percent", 0)
            ram = data.get("memory", {}).get("percent", 0)

            if is_new:
                print(f"🆕 {hostname} connecté depuis {client_ip}")
            print(f"📊 {hostname:20} | CPU={cpu:5.1f}% | RAM={ram:5.1f}%")

            # diffuser la mise à jour aux clients WebSocket
            try:
                from websocket_handler import _check_thresholds, client_manager

                # vérifier les seuils et envoyer des alertes éventuelles
                alerts = _check_thresholds(hostname, data)
                for msg in alerts:
                    # persist the alert in DB when possible
                    try:
                        from db.storage import insert_notification

                        sev = "info"
                        t = (msg or "").lower()
                        if "hors ligne" in t or "disque" in t or "critique" in t:
                            sev = "error"
                        elif "élevé" in t or "alerte" in t or "échec" in t:
                            sev = "warning"
                        insert_notification(hostname, msg, sev)
                    except Exception:
                        pass

                    await client_manager.broadcast(
                        {
                            "type": "alert",
                            "hostname": hostname,
                            "message": msg,
                            "severity": sev,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                await client_manager.broadcast(
                    {"type": "agent_update", "hostname": hostname, "data": data}
                )
            except Exception:
                pass

            return {"status": "ok"}

        except Exception as e:
            print(f"❌ Erreur lors de la réception: {e}")
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
