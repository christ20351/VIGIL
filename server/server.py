# For terminal dashboard
import argparse
import sys
import threading
from datetime import datetime

import uvicorn

# Importer les modules séparés
from cleanup import clean_old_data
from config import SERVER_HOST, SERVER_PORT
from dashboard import create_terminal_dashboard
from db.storage import init_db, prune_older_than
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from rich.console import Console
from routes import setup_routes
from websocket_handler import setup_websocket


def print_banner():
    print("+-----------+")
    print("|  V I G I L  |")
    print("+-----------+")
    print("       VIGIL — Monitoring lightweight")


app = FastAPI(name="PC Monitor Server")

import auth
import config

# middleware pour rediriger/forcer l'authentification lorsque c'est activé
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if config.ENABLE_AUTH:
        path = request.url.path
        # autoriser les ressources statiques et routes publiques
        if (
            path.startswith("/static")
            or path in ("/login", "/logout", "/health", "/update")
            or path.startswith("/ws")
        ):
            return await call_next(request)
        # vérifier session
        cookie = request.cookies.get("session")
        user = auth.verify_session(cookie) if cookie else None
        if not user:
            if path.startswith("/api"):
                return JSONResponse({"error": "not authenticated"}, status_code=401)
            else:
                return RedirectResponse("/login")
    return await call_next(request)


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Data partagée
computers_data = {}

# initialisation stockage historique
try:
    # le module a été déplacé dans le package `db`
    init_db()

    # lancer un prune quotidien
    def _pruner():
        import time

        while True:
            time.sleep(24 * 3600)
            prune_older_than(30)

    threading.Thread(target=_pruner, daemon=True).start()
except Exception:
    pass

# Setup routes
setup_routes(app, templates, computers_data)

# Setup WebSocket
setup_websocket(app, computers_data)

# Démarre le nettoyage en arrière-plan
clean_old_data(computers_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serveur de monitoring")
    parser.add_argument(
        "--mode",
        choices=["web", "terminal"],
        default="web",
        help="Mode d'affichage: web (défaut) ou terminal",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("🖥️  SERVEUR DE MONITORING v2.0")
    print_banner()
    print("=" * 60)

    if args.mode == "terminal":
        print("📊 Mode terminal activé")
        print("💡 Appuyez sur Ctrl+C pour arrêter")
        print("=" * 60)
        print()
        create_terminal_dashboard(computers_data)
    else:
        print(f"📊 Interface web    : http://localhost:{SERVER_PORT}")
        print(f"🌐 Accès réseau     : http://localhost:{SERVER_PORT}")
        print(f"📡 API endpoint     : http://localhost:{SERVER_PORT}/api/computers")
        print(f"❤️  Health check    : http://localhost:{SERVER_PORT}/health")
        print("=" * 60)
        print()
        print("💡 Appuyez sur Ctrl+C pour arrêter le serveur")
        print()

        try:
            # use app directly (no import string needed for simple runs)
            # reload=True causes uvicorn to require an import string
            # which is tricky when running via `python server.py`.  Instead
            # start with `uvicorn server.server:app --reload` if you need
            # automatic reloading during development.
            uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, reload=False)
        except KeyboardInterrupt:
            print("\n\n🛑 Arrêt du serveur...")
            sys.exit(0)
