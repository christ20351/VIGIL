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

            is_new = hostname not in computers_data
            computers_data[hostname] = data

            cpu = data.get("cpu_percent", 0)
            ram = data.get("memory", {}).get("percent", 0)

            if is_new:
                print(f"🆕 {hostname} connecté depuis {client_ip}")
            print(f"📊 {hostname:20} | CPU={cpu:5.1f}% | RAM={ram:5.1f}%")

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

    @app.get("/health")
    def health():
        """Endpoint de santé pour vérifier que le serveur fonctionne"""
        return {
            "status": "ok",
            "computers_count": len(computers_data),
            "timestamp": datetime.now().isoformat(),
        }
