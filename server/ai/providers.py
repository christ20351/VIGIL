"""
VIGIL AI — Unified External LLM Provider HTTP Connectors (< 90 lines)
"""

import json
import urllib.error
import urllib.request
from typing import Any, Dict


def call_ollama_api(prompt: str, system_prompt: str, endpoint: str, model: str) -> str:
    """Appel synchrone vers Ollama local."""
    url = f"{endpoint.rstrip('/')}/api/generate"
    payload = {
        "model": model or "llama3",
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res.get("response", "")


def call_openai_compatible_api(prompt: str, system_prompt: str, endpoint: str, model: str, api_key: str) -> str:
    """Appel synchrone vers toute API compatible OpenAI (Groq, OpenRouter, DeepSeek, OpenAI, LM Studio)."""
    base_url = endpoint.rstrip("/") if endpoint else "https://api.openai.com"
    if not base_url.endswith("/v1"):
        url = f"{base_url}/v1/chat/completions"
    else:
        url = f"{base_url}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        choices = res.get("choices", [])
        return choices[0]["message"]["content"] if choices else ""


call_openai_api = call_openai_compatible_api


def call_llm_provider(prompt: str, system_prompt: str, cfg: Dict[str, Any]) -> str:
    """Point d'entrée unique pour router l'appel vers le vrai modèle LLM configuré."""
    provider = cfg.get("AI_PROVIDER", "auto_rule")
    endpoint = cfg.get("AI_ENDPOINT", "")
    model = cfg.get("AI_MODEL", "")
    api_key = cfg.get("AI_API_KEY", "")

    if provider == "ollama" or "11434" in endpoint:
        return call_ollama_api(prompt, system_prompt, endpoint or "http://localhost:11434", model or "llama3")

    elif provider in ["openai", "groq", "openrouter", "deepseek"]:
        default_endpoints = {
            "groq": "https://api.groq.com/openai",
            "openrouter": "https://openrouter.ai/api",
            "deepseek": "https://api.deepseek.com",
            "openai": "https://api.openai.com",
        }
        target_endpoint = endpoint or default_endpoints.get(provider, "https://api.openai.com")
        return call_openai_compatible_api(prompt, system_prompt, target_endpoint, model, api_key)

    # Mode auto: tente d'abord Ollama local
    try:
        return call_ollama_api(prompt, system_prompt, "http://localhost:11434", model or "llama3")
    except Exception:
        if api_key:
            return call_openai_compatible_api(prompt, system_prompt, endpoint or "https://api.openai.com", model or "gpt-4o-mini", api_key)
        raise RuntimeError("Aucun serveur LLM actif (Ollama ou Clé API non disponible).")
