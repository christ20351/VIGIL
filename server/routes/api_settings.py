import os
import traceback

import config
from fastapi import Request
from fastapi.responses import JSONResponse


def register(app):
    @app.get("/api/settings")
    def get_settings():
        """Retourne quelques paramètres de configuration modifiables"""
        try:
            keys = [
                "SERVER_HOST",
                "SERVER_PORT",
                "TIMEOUT",
                "CPU_ALERT_THRESHOLD",
                "ENABLE_AUTH",
                # we deliberately do not return AUTH_TOKEN for security
                "ALLOWED_AGENT_IPS",
                "ALLOWED_CLIENT_IPS",
                "PROCESS_LIMIT",
                "NETWORK_CONN_LIMIT",
                "CPU_ALERT_DURATION",
                "RAM_ALERT_THRESHOLD",
                "DISK_ALERT_THRESHOLD",
            ]
            return {k: getattr(config, k, None) for k in keys}
        except Exception:
            return JSONResponse({"error": "Cannot read settings"}, status_code=500)

    @app.post("/api/settings")
    async def post_settings(request: Request):
        """Mets à jour certains paramètres et écrit dans config.yaml via le module config."""
        try:
            data = await request.json()
        except Exception as e:
            print("post_settings: JSON parse error", e)
            return JSONResponse({"error": str(e)}, status_code=400)
        try:
            # debug log
            print("post_settings data:", data, "(type", type(data), ")")
            # guard against awaiting mistake
            if not hasattr(data, "items"):
                msg = f"invalid payload type {type(data)}, expected dict"
                print(msg)
                return JSONResponse({"error": msg}, status_code=400)
            # update the in-memory config and persist
            config.save_config(data)
            # after writing new file nothing else to do
            return {"status": "ok"}
        except Exception as e:
            # log the error for debugging

            traceback.print_exc()
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.post("/api/settings/reset")
    def reset_settings():
        """Remets le fichier de configuration à sa version précédente (backup)."""
        try:
            bak = config.CONFIG_PATH + ".bak"
            if not os.path.exists(bak):
                return JSONResponse({"error": "No backup available"}, status_code=404)
            # copy backup over current
            import shutil

            shutil.copyfile(bak, config.CONFIG_PATH)
            config.reload()
            return {"status": "ok"}
        except Exception as e:
            import traceback

            traceback.print_exc()
            return JSONResponse({"error": str(e)}, status_code=500)
