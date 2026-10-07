"""
VIGIL 2.1 - API Routes for AI Monitoring & Copilot
"""

import asyncio
import time
from typing import Any, Dict, Optional
from ai.engine import AIEngine
import config
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

ai_engine = AIEngine(config_provider=config)

# Rate limiting simple en mémoire pour le chat IA : {ip: [timestamps]}
_chat_rate: dict = {}


def _check_chat_rate_limit(request: Request) -> bool:
    """Retourne True si l'IP dépasse le quota de requêtes IA par minute."""
    limit = getattr(config, "AI_RATE_LIMIT_PER_MIN", 20) or 0
    if limit <= 0:
        return False
    ip = request.client.host if request.client else "?"
    now = time.time()
    recent = [t for t in _chat_rate.get(ip, []) if now - t < 60]
    if len(recent) >= limit:
        _chat_rate[ip] = recent
        return True
    recent.append(now)
    _chat_rate[ip] = recent
    return False


class DiagnoseRequest(BaseModel):
    hostname: Optional[str] = None


class ChatRequest(BaseModel):
    prompt: str
    hostname: Optional[str] = None
    chat_history: Optional[list] = None


class ConfigUpdateRequest(BaseModel):
    AI_ENABLED: Optional[bool] = None
    AI_PROVIDER: Optional[str] = None
    AI_API_KEY: Optional[str] = None
    AI_MODEL: Optional[str] = None
    AI_ENDPOINT: Optional[str] = None
    AI_SYSTEM_PROMPT: Optional[str] = None


def register(app: FastAPI):

    @app.post("/api/ai/diagnose")
    async def diagnose_machine_or_cluster(req: DiagnoseRequest, request: Request):
        shared_data = getattr(app.state, "computers_data", {})
        if req.hostname and req.hostname != "all":
            if req.hostname not in shared_data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Agent '{req.hostname}' non trouvé.",
                )
            result = await asyncio.to_thread(
                ai_engine.diagnose_agent, req.hostname, shared_data
            )
        else:
            result = await asyncio.to_thread(ai_engine.diagnose_cluster, shared_data)
        return result

    @app.post("/api/ai/chat")
    async def chat_copilot(req: ChatRequest, request: Request):
        if not req.prompt or not req.prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt vide.")
        if _check_chat_rate_limit(request):
            return JSONResponse(
                {"error": "Trop de requêtes IA — réessayez dans une minute."},
                status_code=429,
            )
        shared_data = getattr(app.state, "computers_data", {})
        # L'appel LLM est bloquant (urllib) → exécuté dans un thread pour ne
        # pas figer la boucle d'événements (agents WebSocket compris).
        res = await asyncio.to_thread(
            ai_engine.chat_with_copilot,
            user_prompt=req.prompt,
            context_hostname=req.hostname,
            computers_data=shared_data,
            chat_history=req.chat_history,
        )
        return res

    @app.get("/api/ai/config")
    async def get_ai_config():
        key = getattr(config, "AI_API_KEY", "")
        masked_key = ""
        if key:
            masked_key = key[:4] + "..." + key[-4:] if len(key) > 8 else "********"

        return {
            "AI_ENABLED": getattr(config, "AI_ENABLED", True),
            "AI_PROVIDER": getattr(config, "AI_PROVIDER", "auto_rule"),
            "AI_API_KEY": masked_key,
            "AI_MODEL": getattr(config, "AI_MODEL", "llama3"),
            "AI_ENDPOINT": getattr(config, "AI_ENDPOINT", "http://localhost:11434"),
            "AI_SYSTEM_PROMPT": getattr(
                config,
                "AI_SYSTEM_PROMPT",
                "Vous êtes VIGIL AI, un copilote d'administration système.",
            ),
        }

    @app.post("/api/ai/config")
    async def update_ai_config(updates: ConfigUpdateRequest):
        up_dict = {}
        for field, val in updates.model_dump(exclude_unset=True).items():
            if val is not None:
                # do not overwrite with masked key string if submitted unchanged
                if field == "AI_API_KEY" and "..." in str(val):
                    continue
                # clé vide → conserver l'actuelle
                if field == "AI_API_KEY" and str(val).strip() == "":
                    continue
                up_dict[field] = val

        if up_dict:
            config.save_config(up_dict)

        return {"status": "ok", "message": "Configuration IA sauvegardée."}

    @app.get("/api/ai/status")
    async def get_ai_status():
        return await asyncio.to_thread(ai_engine.test_connection)

    @app.get("/api/ai/autonomous/reports")
    async def get_autonomous_reports(unresolved: bool = False):
        from ai.autonomous_db import query_autonomous_ai_reports
        return query_autonomous_ai_reports(limit=50, unresolved_only=unresolved)

    @app.post("/api/ai/autonomous/resolve/{report_id}")
    async def resolve_autonomous_report(report_id: int):
        from ai.autonomous_db import mark_ai_report_resolved
        ok = mark_ai_report_resolved(report_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Rapport d'incident non trouvé.")
        return {"status": "ok", "message": f"Incident {report_id} marqué comme résolu."}

    @app.post("/api/ai/autonomous/trigger")
    async def trigger_autonomous_scan():
        watchdog = getattr(app.state, "ai_watchdog", None)
        created = await asyncio.to_thread(watchdog.run_scan_cycle) if watchdog else 0
        return {"status": "ok", "reports_created": created}

    # ── Intelligence Vili : analyse avancée ────────────────────────
    @app.get("/api/ai/analytics")
    async def get_ai_analytics():
        """Anomalies, prévisions de saturation, dégradations, tempêtes."""
        from ai.analytics import get_intelligence_report

        shared_data = getattr(app.state, "computers_data", {})
        # calcul CPU potentiellement lourd (BD) → thread
        return await asyncio.to_thread(get_intelligence_report, shared_data)

    @app.get("/api/ai/watch")
    async def list_watch_rules(active_only: bool = False):
        from db import storage

        return storage.list_watch_rules(active_only=active_only)

    @app.delete("/api/ai/watch/{rule_id}")
    async def remove_watch_rule(rule_id: int):
        from db import storage

        ok = storage.delete_watch_rule(rule_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Règle non trouvée.")
        return {"status": "ok"}

    @app.post("/api/ai/watch")
    async def create_watch_rule(request: Request):
        """Création manuelle d'une règle {description, metric, operator, threshold, hostname, duration_sec}."""
        from ai.watch import create_rule_from_parsed

        try:
            data = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="JSON invalide.")
        metric = (data.get("metric") or "").strip()
        if metric not in ("cpu", "ram", "disk", "net_total", "temp"):
            raise HTTPException(status_code=400, detail="Métrique inconnue.")
        try:
            threshold = float(data.get("threshold", 0))
        except Exception:
            raise HTTPException(status_code=400, detail="Seuil invalide.")
        if threshold <= 0:
            raise HTTPException(status_code=400, detail="Le seuil doit être positif.")
        rule_id = create_rule_from_parsed(
            {
                "description": (data.get("description") or f"{metric} {data.get('operator', '>')} {threshold}")[:200],
                "metric": metric,
                "operator": "<" if data.get("operator") == "<" else ">",
                "threshold": threshold,
                "hostname": data.get("hostname") or None,
                "duration_sec": int(data.get("duration_sec") or 0),
            },
            created_by="admin",
        )
        return {"status": "ok", "rule_id": rule_id}

    @app.post("/api/ai/daily-report")
    async def trigger_daily_report():
        """Génère immédiatement le rapport quotidien Vili."""
        from ai.actions import generate_daily_report

        shared_data = getattr(app.state, "computers_data", {})
        return await asyncio.to_thread(generate_daily_report, shared_data)

    # ── Demandes d'autorisation de commandes (Vili → admin) ────────
    class ApprovalDecision(BaseModel):
        approved: bool

    @app.get("/api/ai/approvals")
    async def list_approvals(status: str = "pending", limit: int = 50):
        from db import storage

        return storage.list_approvals(
            status=status if status != "all" else None, limit=limit
        )

    @app.post("/api/ai/approvals/{approval_id}/decide")
    async def decide_approval(approval_id: int, decision: ApprovalDecision, request: Request):
        """
        Décision de l'admin sur une demande de Vili : Oui → exécute la
        commande sur l'agent et archive le résultat ; Non → refuse.
        """
        from db import storage
        from websocket_handler import (
            broadcast_approval_done,
            send_command_to_agent,
        )

        approval = storage.get_approval(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Demande non trouvée.")
        if approval["status"] != "pending":
            return {"status": "already_decided", "approval": approval}

        if not storage.decide_approval(approval_id, decision.approved, decided_by="admin"):
            raise HTTPException(status_code=409, detail="Demande déjà tranchée.")

        if not decision.approved:
            from websocket_handler import notify_dashboard_sync

            notify_dashboard_sync(
                approval["hostname"],
                f"🚫 Commande refusée par l'admin : `{approval['command']}`",
                "info",
            )
            done = storage.get_approval(approval_id)
            broadcast_approval_done(done)
            return {"status": "refused", "approval": done}

        # Oui → exécution réelle sur l'agent
        if approval["hostname"] not in getattr(app.state, "computers_data", {}):
            storage.save_approval_result(
                approval_id, {"ok": False, "error": "Agent hors ligne au moment de l'exécution."}
            )
            done = storage.get_approval(approval_id)
            broadcast_approval_done(done)
            return JSONResponse(
                {"status": "approved_but_offline", "approval": done}, status_code=502
            )

        timeout = int(getattr(config, "AGENT_COMMAND_TIMEOUT", 60) or 60)
        result = await send_command_to_agent(
            approval["hostname"], approval["command"], timeout=timeout
        )
        storage.save_approval_result(approval_id, result)

        from websocket_handler import notify_dashboard_sync

        ok = result.get("ok")
        out = (result.get("stdout") or result.get("stderr") or result.get("error") or "")[:300]
        notify_dashboard_sync(
            approval["hostname"],
            f"✅ Commande approuvée et exécutée : `{approval['command']}` → "
            + (out if ok else f"échec : {out}"),
            "info" if ok else "error",
        )
        done = storage.get_approval(approval_id)
        broadcast_approval_done(done)
        return {"status": "executed", "approval": done}

    @app.post("/api/ai/approvals/decide-batch")
    async def decide_approvals_batch(request: Request):
        """
        Décision sur un PLAN d'action complet (plusieurs demandes issues
        du chat) : Oui → exécute séquentiellement dans l'ordre ; Non →
        refuse tout. Payload : {ids: [int...], approved: bool}
        """
        from db import storage
        from websocket_handler import (
            broadcast_approval_done,
            notify_dashboard_sync,
            send_command_to_agent,
        )

        try:
            data = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="JSON invalide.")
        ids = data.get("ids") or []
        approved = bool(data.get("approved"))
        if not isinstance(ids, list) or not ids:
            raise HTTPException(status_code=400, detail="Liste d'ids attendue.")

        timeout = int(getattr(config, "AGENT_COMMAND_TIMEOUT", 60) or 60)
        results = []
        for aid in ids[:6]:
            approval = storage.get_approval(int(aid))
            if not approval or approval["status"] != "pending":
                results.append({"id": aid, "status": "skipped"})
                continue
            if not approved:
                storage.decide_approval(int(aid), False, decided_by="admin")
                done = storage.get_approval(int(aid))
                broadcast_approval_done(done)
                results.append({"id": aid, "status": "refused"})
                continue

            storage.decide_approval(int(aid), True, decided_by="admin")
            if approval["hostname"] not in getattr(app.state, "computers_data", {}):
                storage.save_approval_result(
                    int(aid), {"ok": False, "error": "Agent hors ligne."}
                )
                results.append({"id": aid, "status": "approved_but_offline"})
                continue

            result = await send_command_to_agent(
                approval["hostname"], approval["command"], timeout=timeout
            )
            storage.save_approval_result(int(aid), result)
            ok = result.get("ok")
            out = (result.get("stdout") or result.get("stderr") or result.get("error") or "")[:300]
            notify_dashboard_sync(
                approval["hostname"],
                f"✅ Plan approuvé — étape exécutée : `{approval['command']}` → "
                + (out if ok else f"échec : {out}"),
                "info" if ok else "error",
            )
            done = storage.get_approval(int(aid))
            broadcast_approval_done(done)
            results.append({
                "id": aid, "status": "executed", "result": result,
            })

        return {"status": "ok", "approved": approved, "results": results}
