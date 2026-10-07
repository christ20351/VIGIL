# For terminal dashboard
import argparse
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
import uvicorn

# ================================================================
#  RÉSOLUTION DES CHEMINS (PyInstaller + dev)
# ================================================================


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        # Avec --onedir, les données sont dans _internal/
        return Path(sys._MEIPASS)
    return Path(__file__).parent


BASE_DIR = get_base_dir()
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


# ================================================================
#  IMPORT DES MODULES INTERNES
# config.py gère lui-même la création/chargement de config.yaml
# et le setup interactif au premier lancement
# ================================================================
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

import auth
import config
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse


def print_banner():
    print("+-----------+")
    print("|  V I G I L  |")
    print("+-----------+")
    print("       VIGIL — Monitoring lightweight")


# ================================================================
#  APPLICATION FASTAPI
# ================================================================
app = FastAPI(name="PC Monitor Server")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if config.ENABLE_AUTH:
        path = request.url.path
        if (
            path.startswith("/static")
            or path in ("/login", "/logout", "/health", "/update")
            or path.startswith("/ws")
        ):
            return await call_next(request)
        cookie = request.cookies.get("session")
        user = auth.verify_session(cookie) if cookie else None
        if not user:
            if path.startswith("/api"):
                return JSONResponse({"error": "not authenticated"}, status_code=401)
            else:
                return RedirectResponse("/login")
    response = await call_next(request)
    # Les assets statiques doivent toujours être revalidés : sans cet en-tête,
    # le cache heuristique du navigateur peut servir des fichiers obsolètes
    # (écrans qui semblent ne jamais changer après une mise à jour).
    if request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache"
    return response


# Mount static files — chemin absolu résolu selon contexte
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates — chemin absolu résolu selon contexte
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _compute_asset_version() -> str:
    """Version des assets statiques (mtime le plus récent des .js/.css).

    Injectée en query string (?v=...) dans index.html : toute modification
    d'un fichier statique change l'URL vue par le navigateur et contourne
    son cache sans intervention manuelle.
    """
    latest = 0.0
    if STATIC_DIR.exists():
        for path in STATIC_DIR.rglob("*"):
            if path.is_file() and path.suffix in (".js", ".css"):
                try:
                    latest = max(latest, path.stat().st_mtime)
                except OSError:
                    continue
    return str(int(latest))


templates.env.globals["ASSET_V"] = _compute_asset_version()

# Data partagée
computers_data = {}

# Initialisation stockage historique
try:
    init_db()

    import db.storage as _storage

    _storage.configure(
        storage_interval=config.METRICS_STORAGE_INTERVAL,
        detail_interval=config.METRICS_DETAIL_INTERVAL,
    )

    def _pruner():
        import time

        # première purge rapide au démarrage (utile si le serveur redémarre
        # souvent), puis cadence régulière configurable
        interval = max(60, int(getattr(config, "PRUNE_INTERVAL_MINUTES", 60)) * 60)
        first = True
        while True:
            time.sleep(60 if first else interval)
            first = False
            try:
                _storage.configure(
                    storage_interval=config.METRICS_STORAGE_INTERVAL,
                    detail_interval=config.METRICS_DETAIL_INTERVAL,
                )
                prune_older_than(
                    days=int(getattr(config, "RETENTION_DAYS", 30)),
                    notification_days=int(
                        getattr(config, "NOTIFICATION_RETENTION_DAYS", 90)
                    ),
                )
            except Exception as e:
                print(f"[WARNING] Prune error: {e}")

    threading.Thread(target=_pruner, daemon=True).start()
except Exception:
    pass

# Démarrer la surveillance automatique de la configuration
try:
    config.start_config_watcher(check_interval=2)
except Exception as e:
    print(f"[WARNING] Could not start config watcher: {e}")

# Setup routes & WebSocket
setup_routes(app, templates, computers_data)
setup_websocket(app, computers_data)

# Nettoyage en arrière-plan
clean_old_data(computers_data)

# Démarrage de l'Agent IA Autonome de surveillance en arrière-plan
try:
    import notify_out

    notify_out.setup(config)
except Exception as e:
    print(f"[WARNING] Could not start outbound notifier: {e}")

try:
    from ai.autonomous_agent import AutonomousAgentWatchdog
    watchdog = AutonomousAgentWatchdog(computers_data, check_interval=30)
    watchdog.start()
    app.state.ai_watchdog = watchdog
except Exception as e:
    print(f"[WARNING] Could not start Autonomous AI Watchdog: {e}")


# ================================================================
#  POINT D'ENTRÉE
# ================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serveur de monitoring VIGIL")
    parser.add_argument(
        "--mode",
        choices=["web", "terminal"],
        default="web",
        help="Mode d'affichage: web (défaut) ou terminal",
    )
    args, _unknown = parser.parse_known_args()

    os.system("cls" if sys.platform == "win32" else "clear")
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
        print(f"🌐 Accès réseau     : http://<votre-IP>:{SERVER_PORT}")
        print(f"📡 API endpoint     : http://localhost:{SERVER_PORT}/api/computers")
        print(f"❤️  Health check    : http://localhost:{SERVER_PORT}/health")
        print(f"📁 Config chargée  : {BASE_DIR / 'config.yaml'}")
        print("=" * 60)
        print()
        print("💡 Appuyez sur Ctrl+C pour arrêter le serveur")
        print()

        try:
            uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, reload=False)
        except KeyboardInterrupt:
            print("\n\n🛑 Arrêt du serveur...")
            sys.exit(0)
