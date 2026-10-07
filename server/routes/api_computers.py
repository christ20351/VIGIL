from typing import Optional

import config
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class CommandRequest(BaseModel):
    command: str
    timeout: Optional[int] = None


def register(app: FastAPI):
    @app.get("/api/computers")
    def get_computers():
        """API pour récupérer les données de tous les PC"""
        return app.state.computers_data

    @app.get("/api/computers/{hostname}")
    def get_computer(hostname: str):
        """API pour récupérer les données complètes d'un PC (détail à la demande)."""
        if hostname in app.state.computers_data:
            return app.state.computers_data[hostname]
        return JSONResponse({"error": "Computer not found"}, status_code=404)

    # route additionnelle utilisée par le JS (fallback dans onglet SMART)
    @app.get("/api/computers/{hostname}/smart")
    def get_computer_smart(hostname: str):
        """Ne renvoie que le payload SMART d'un agent (vide si non disponible)."""
        if hostname in app.state.computers_data:
            data = app.state.computers_data[hostname]
            return {"smart": data.get("smart", {})}
        return JSONResponse({"error": "Computer not found"}, status_code=404)

    # ── Groupes & maintenance ─────────────────────────────────────
    @app.get("/api/groups")
    def list_groups_route():
        """Groupes distincts + métadonnées par machine (groupe, maintenance)."""
        from db.storage import get_agent_meta, list_groups

        hosts = {}
        for hostname in app.state.computers_data:
            meta = get_agent_meta(hostname)
            hosts[hostname] = {
                "group": meta.get("group_name") or "",
                "maintenance_until": meta.get("maintenance_until"),
            }
        return {"groups": list_groups(), "hosts": hosts}

    class GroupAssign(BaseModel):
        group: str

    @app.post("/api/computers/{hostname}/group")
    def assign_group(hostname: str, req: GroupAssign):
        from db.storage import set_agent_group

        set_agent_group(hostname, (req.group or "").strip()[:60])
        return {"status": "ok", "hostname": hostname, "group": req.group}

    class MaintenanceRequest(BaseModel):
        minutes: int

    @app.post("/api/computers/{hostname}/maintenance")
    def start_maintenance(hostname: str, req: MaintenanceRequest):
        """Silence les alertes de cette machine pendant N minutes."""
        from datetime import datetime, timedelta

        from db.storage import set_maintenance

        minutes = max(1, min(int(req.minutes or 30), 10080))
        until = (datetime.now() + timedelta(minutes=minutes)).isoformat()
        set_maintenance(hostname, until)
        return {"status": "ok", "hostname": hostname, "maintenance_until": until}

    @app.delete("/api/computers/{hostname}/maintenance")
    def stop_maintenance(hostname: str):
        from db.storage import set_maintenance

        set_maintenance(hostname, None)
        return {"status": "ok", "hostname": hostname, "maintenance_until": None}

    @app.post("/api/computers/{hostname}/command")
    async def run_remote_command(hostname: str, req: CommandRequest, request: Request):
        """
        Exécute une commande système sur l'agent `hostname` et retourne
        sa sortie. Nécessite AGENT_COMMANDS_ENABLED (Paramètres) — et
        l'authentification activée sur tout réseau non totalement sûr.
        """
        if not config.ENABLE_AUTH:
            print(
                "[SECURITE] Commande distante demandée alors que ENABLE_AUTH=false "
                "— toute personne sur le réseau peut exécuter des commandes."
            )
        if not getattr(config, "AGENT_COMMANDS_ENABLED", False):
            return JSONResponse(
                {
                    "error": "Exécution de commandes désactivée. "
                    "Activez AGENT_COMMANDS_ENABLED dans les Paramètres."
                },
                status_code=423,
            )
        command = (req.command or "").strip()
        if not command:
            return JSONResponse({"error": "Commande vide."}, status_code=400)
        if hostname not in app.state.computers_data:
            return JSONResponse({"error": "Machine inconnue."}, status_code=404)

        from websocket_handler import send_command_to_agent

        try:
            import security_events

            client_ip = request.client.host if request.client else "-"
            security_events.log_security_event(
                "remote_command",
                f"Commande exécutée sur {hostname} : {command[:120]}",
                severity="warning",
                source=client_ip,
            )
        except Exception:
            pass

        timeout = req.timeout or int(getattr(config, "AGENT_COMMAND_TIMEOUT", 60) or 60)
        result = await send_command_to_agent(hostname, command, timeout=timeout)
        status = 200 if result.get("ok") else 502
        return JSONResponse(result, status_code=status)
