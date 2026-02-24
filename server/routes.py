"""
Routes API pour le serveur de monitoring
"""

from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

# Variables partagées (importées du main)
computers_data = {}
templates = None


def setup_routes(app: FastAPI, tmpl: Jinja2Templates, shared_data: dict):
    """Configure les routes FastAPI"""
    global computers_data, templates
    computers_data = shared_data
    templates = tmpl

    @app.get("/")
    def index(request: Request):
        """Page principale du dashboard"""
        return templates.TemplateResponse("index.html", {"request": request})

    @app.post("/update")
    async def update(request: Request):
        """Reçoit les données d'un agent"""
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
            from datetime import datetime

            data["last_seen"] = datetime.now().isoformat()
            data["offline"] = False
            data.pop("offline_since", None)

            is_new = hostname not in computers_data
            # stocker historique
            try:
                from db.storage import insert_metric

                insert_metric(hostname, data)
            except Exception:
                pass

            computers_data[hostname] = data
            # persistence
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

    @app.get("/api/computers")
    def get_computers():
        """API pour récupérer les données de tous les PC"""
        return computers_data

    @app.get("/api/computers/{hostname}")
    def get_computer(hostname: str):
        """API pour récupérer les données d'un PC spécifique"""
        if hostname in computers_data:
            return computers_data[hostname]
        return JSONResponse({"error": "Computer not found"}, status_code=404)

    @app.get("/api/settings")
    def get_settings():
        """Retourne quelques paramètres de configuration modifiables"""
        try:
            import config

            keys = [
                "SERVER_HOST",
                "SERVER_PORT",
                "TIMEOUT",
                "CPU_ALERT_THRESHOLD",
            ]
            return {k: getattr(config, k, None) for k in keys}
        except Exception:
            return JSONResponse({"error": "Cannot read settings"}, status_code=500)

    @app.post("/api/settings")
    def post_settings(request: Request):
        """Mets à jour certains paramètres et écrit dans config.py"""
        try:
            data = request.json()
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        try:
            import inspect
            import os
            import re

            import config

            # lock file path
            path = os.path.join(os.path.dirname(__file__), "config.py")
            # apply to module
            for k, v in data.items():
                if hasattr(config, k):
                    setattr(config, k, v)
            # rewrite file lines
            lines = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    m = re.match(r"^(\w+)\s*=", line)
                    if m and m.group(1) in data:
                        val = getattr(config, m.group(1))
                        lines.append(f"{m.group(1)} = {repr(val)}\n")
                    else:
                        lines.append(line)
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return {"status": "ok"}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.get("/api/history/{hostname}")
    def get_history(hostname: str, hours: int = 24):
        """Retourne l'historique des métriques sur les dernières `hours` heures.

        Exemple: /api/history/WORKSTATION-01?hours=72
        """
        try:
            from db.storage import query_history
        except ImportError:
            return JSONResponse({"error": "Storage non disponible"}, status_code=500)

        cutoff = None
        try:
            from datetime import datetime, timedelta

            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        except Exception:
            cutoff = None

        if cutoff:
            rows = query_history(hostname, cutoff)
            return {"hostname": hostname, "history": rows}
        else:
            return JSONResponse({"error": "Invalid parameters"}, status_code=400)


    @app.get("/api/notifications")
    def get_notifications(hours: int = 12, hostname: str = None):
        """Retourne les notifications persistées sur les dernières `hours` heures.

        Optionnel: filtrer par `hostname`.
        """
        try:
            from db.storage import query_notifications
        except ImportError:
            return JSONResponse({"error": "Storage non disponible"}, status_code=500)

        cutoff = None
        try:
            from datetime import datetime, timedelta

            if hours and hours > 0:
                cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        except Exception:
            cutoff = None

        rows = query_notifications(hostname, cutoff)
        return {"notifications": rows}

    @app.get("/script.js")
    def legacy_script():
        """Ancien chemin pour compatibilité, redirige vers le statique"""
        from fastapi.responses import FileResponse

        return FileResponse("static/script.js")

    @app.get("/style.css")
    def legacy_style():
        """Ancien chemin pour compatibilité, redirige vers le statique"""
        from fastapi.responses import FileResponse

        return FileResponse("static/style.css")

    @app.get("/health")
    def health():
        """Endpoint de santé pour vérifier que le serveur fonctionne"""
        return {
            "status": "ok",
            "computers_count": len(computers_data),
            "timestamp": datetime.now().isoformat(),
        }
