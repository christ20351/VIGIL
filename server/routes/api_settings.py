import os
import traceback

import config
from fastapi import Request
from fastapi.responses import JSONResponse


def _mask_secret(value) -> str:
    """Masque un secret pour l'affichage (jamais renvoyé en clair par l'API)."""
    if not value:
        return ""
    value = str(value)
    return value[:4] + "..." + value[-4:] if len(value) > 8 else "********"


# Réglages dont la modification apparaît dans le journal de sécurité
_SECURITY_AUDIT_KEYS = (
    "ENABLE_AUTH",
    "AGENT_COMMANDS_ENABLED",
    "ALLOWED_AGENT_IPS",
    "ALLOWED_CLIENT_IPS",
    "SESSION_TTL_HOURS",
    "COOKIE_SECURE",
    "LOGIN_MAX_ATTEMPTS",
)


def _audit_security_changes(data: dict, client_ip: str):
    """Piste d'audit : trace dans le journal de sécurité les changements
    de réglages sensibles effectués via l'API."""
    try:
        import security_events

        defaults = getattr(config, "_default", {}) or {}
        changed = []
        for k in _SECURITY_AUDIT_KEYS:
            if k not in data:
                continue
            current = getattr(config, k, None)
            new = data[k]
            # normalisation identique à config.save_config pour éviter les
            # faux positifs de représentation ("true" vs True, "a,b" vs liste)
            dflt = defaults.get(k)
            try:
                if isinstance(dflt, bool):
                    new = (
                        new.lower() in ("1", "true", "yes", "on")
                        if isinstance(new, str)
                        else bool(new)
                    )
                elif isinstance(dflt, int):
                    new = int(new)
                elif isinstance(dflt, list):
                    new = (
                        [x.strip() for x in new.split(",") if x.strip()]
                        if isinstance(new, str)
                        else list(new)
                    )
            except Exception:
                pass
            if new != current:
                changed.append(f"{k} → {new!r}")
        if not changed:
            return
        auth_disabled = any(c.startswith("ENABLE_AUTH → False") for c in changed)
        security_events.log_security_event(
            "config_changed",
            "Réglages de sécurité modifiés : " + "; ".join(changed),
            severity="critical" if auth_disabled else "info",
            source=client_ip,
        )
    except Exception:
        pass


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
                "HDD_SMART_ENABLED",
                "HDD_TEMP_WARNING",
                "HDD_TEMP_CRITICAL",
                "SESSION_TTL_HOURS",
                "COOKIE_SECURE",
                "LOGIN_MAX_ATTEMPTS",
                "METRICS_STORAGE_INTERVAL",
                "METRICS_DETAIL_INTERVAL",
                "PRUNE_INTERVAL_MINUTES",
                "RETENTION_DAYS",
                "NOTIFICATION_RETENTION_DAYS",
                "BROADCAST_FULL_DETAIL",
                "AI_ENABLED",
                "AI_PROVIDER",
                "AI_MODEL",
                "AI_ENDPOINT",
                "AI_TIMEOUT",
                "AI_RATE_LIMIT_PER_MIN",
                "AI_SCAN_INTERVAL",
                "AI_AUTONOMOUS_ACTIONS",
                "ANOMALY_Z_THRESHOLD",
                "FORECAST_WINDOW_HOURS",
                "STORM_MIN_HOSTS",
                "WATCH_RULE_COOLDOWN",
                "DAILY_REPORT_ENABLED",
                "DAILY_REPORT_HOUR",
                "AI_SYSTEM_PROMPT",
                "AGENT_COMMANDS_ENABLED",
                "AGENT_COMMAND_TIMEOUT",
                "DB_BACKEND",
                "DB_HOST",
                "DB_PORT",
                "DB_NAME",
                "DB_USER",
                "ALERT_WEBHOOK_ENABLED",
                "ALERT_WEBHOOK_URL",
                "ALERT_EMAIL_ENABLED",
                "ALERT_SMTP_HOST",
                "ALERT_SMTP_PORT",
                "ALERT_SMTP_TLS",
                "ALERT_SMTP_USER",
                "ALERT_EMAIL_FROM",
                "ALERT_EMAIL_TO",
                "ALERT_MIN_SEVERITY",
                "FEDERATION_SITE_NAME",
                "FEDERATION_PEERS",
            ]
            out = {k: getattr(config, k, None) for k in keys}
            # secrets jamais exposés en clair
            out["AI_API_KEY"] = _mask_secret(getattr(config, "AI_API_KEY", ""))
            out["DB_PASSWORD"] = _mask_secret(getattr(config, "DB_PASSWORD", ""))
            out["ALERT_SMTP_PASSWORD"] = _mask_secret(getattr(config, "ALERT_SMTP_PASSWORD", ""))
            out["FEDERATION_TOKEN"] = _mask_secret(getattr(config, "FEDERATION_TOKEN", ""))
            return out
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
            if not hasattr(data, "items"):
                msg = f"invalid payload type {type(data)}, expected dict"
                print(msg)
                return JSONResponse({"error": msg}, status_code=400)

            # Ne jamais écraser un secret par sa version masquée ou vide
            for secret_key in ("AI_API_KEY", "AUTH_TOKEN", "DB_PASSWORD",
                               "ALERT_SMTP_PASSWORD", "FEDERATION_TOKEN"):
                val = data.get(secret_key)
                if val is None or str(val).strip() == "" or "..." in str(val):
                    data.pop(secret_key, None)

            # piste d'audit avant application (comparaison anciennes valeurs)
            client_ip = request.client.host if request.client else "-"
            _audit_security_changes(data, client_ip)

            # update the in-memory config and persist
            config.save_config(data)
            # after writing new file nothing else to do
            return {"status": "ok"}
        except Exception as e:
            import traceback

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

    @app.post("/api/settings/reload")
    def reload_settings():
        """
        Recharge les paramètres depuis le config.yaml sans redémarrer le serveur.
        Retourne les changements détectés, le cas échéant.
        """
        try:
            changes = config.check_config_updates()
            if changes:
                return {"status": "ok", "changes": changes}
            else:
                return {"status": "ok", "message": "No changes detected"}
        except Exception as e:
            import traceback

            traceback.print_exc()
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.post("/api/settings/vacuum")
    async def vacuum_database():
        """
        Maintenance base de données : compaction VACUUM pour récupérer
        l'espace disque après les purges (opération bloquante quelques
        secondes à minutes selon la taille de la base).
        """
        import asyncio

        from db import storage as _storage

        ok = await asyncio.to_thread(_storage.vacuum_db)
        if not ok:
            return JSONResponse(
                {"error": "VACUUM échoué (voir logs serveur)"}, status_code=500
            )
        return {"status": "ok", "message": "Base compactée (VACUUM) avec succès."}

    @app.post("/api/settings/test-webhook")
    async def test_webhook():
        import asyncio

        import notify_out

        try:
            msg = await asyncio.to_thread(notify_out.send_test_webhook)
            return {"status": "ok", "message": msg}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=502)

    @app.post("/api/settings/test-email")
    async def test_email():
        import asyncio

        import notify_out

        try:
            msg = await asyncio.to_thread(notify_out.send_test_email)
            return {"status": "ok", "message": msg}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=502)
