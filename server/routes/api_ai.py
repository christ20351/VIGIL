"""
VIGIL 2.1 - API Routes for AI Monitoring & Copilot
"""

from typing import Any, Dict, Optional
from ai.engine import AIEngine
import config
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

ai_engine = AIEngine(config_provider=config)


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
            result = ai_engine.diagnose_agent(req.hostname, shared_data)
        else:
            result = ai_engine.diagnose_cluster(shared_data)
        return result

    @app.post("/api/ai/chat")
    async def chat_copilot(req: ChatRequest, request: Request):
        if not req.prompt or not req.prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt vide.")
        shared_data = getattr(app.state, "computers_data", {})
        res = ai_engine.chat_with_copilot(
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
                up_dict[field] = val

        if up_dict:
            config.save_config(up_dict)

        return {"status": "ok", "message": "Configuration IA sauvegardée."}

    @app.get("/api/ai/status")
    async def get_ai_status():
        return ai_engine.test_connection()

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
        created = watchdog.run_scan_cycle() if watchdog else 0
        return {"status": "ok", "reports_created": created}
