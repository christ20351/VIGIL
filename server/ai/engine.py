"""
Vili — Main Engine Facade (< 75 lines)
"""

import logging
from typing import Any, Dict, List, Optional
from ai.agent_diag import diagnose_single_agent
from ai.cluster_diag import diagnose_entire_cluster
from ai.natural_copilot import respond_naturally
from ai.providers import call_ollama_api, call_openai_api

logger = logging.getLogger("vigil.ai")


class AIEngine:
    def __init__(self, config_provider=None):
        self.config_provider = config_provider

    def _get_cfg(self) -> Dict[str, Any]:
        if callable(self.config_provider):
            return self.config_provider()
        elif hasattr(self.config_provider, "AI_PROVIDER"):
            return {
                "AI_ENABLED": getattr(self.config_provider, "AI_ENABLED", True),
                "AI_PROVIDER": getattr(self.config_provider, "AI_PROVIDER", "auto_rule"),
                "AI_API_KEY": getattr(self.config_provider, "AI_API_KEY", ""),
                "AI_MODEL": getattr(self.config_provider, "AI_MODEL", "llama3"),
                "AI_ENDPOINT": getattr(self.config_provider, "AI_ENDPOINT", "http://localhost:11434"),
                "AI_SYSTEM_PROMPT": getattr(self.config_provider, "AI_SYSTEM_PROMPT", "Vous êtes Vili."),
            }
        return {"AI_ENABLED": True, "AI_PROVIDER": "auto_rule"}

    def test_connection(self) -> Dict[str, Any]:
        cfg = self._get_cfg()
        provider = (cfg.get("AI_PROVIDER") or "auto_rule").lower()
        if provider == "auto_rule":
            if cfg.get("AI_API_KEY"):
                pass  # une clé est configurée : on teste le provider auto ci-dessous
            else:
                return {"status": "ok", "provider": "auto_rule", "message": "Moteur BD VIGIL autonome actif."}
        try:
            if provider == "ollama":
                call_ollama_api("Test", "Test", cfg.get("AI_ENDPOINT", ""), cfg.get("AI_MODEL", ""), timeout=10)
            else:
                from ai.providers import call_llm_provider

                call_llm_provider(
                    "Réponds uniquement par : OK",
                    "Tu es un test de connectivité.",
                    {**cfg, "AI_TIMEOUT": 15},
                )
            return {"status": "ok", "provider": provider, "message": f"Connexion {provider} réussie."}
        except Exception as e:
            return {"status": "error", "provider": provider, "message": f"Échec de connexion : {e}"}

    def diagnose_agent(self, hostname: str, computers_data: Dict[str, Any]) -> Dict[str, Any]:
        return diagnose_single_agent(hostname, computers_data.get(hostname, {}))

    def diagnose_cluster(self, computers_data: Dict[str, Any], notifications: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        return diagnose_entire_cluster(computers_data)

    def chat_with_copilot(
        self,
        user_prompt: str,
        context_hostname: Optional[str] = None,
        computers_data: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        cfg = self._get_cfg()
        return respond_naturally(
            user_prompt,
            computers_data or {},
            cfg,
            context_hostname,
            chat_history=chat_history,
        )
