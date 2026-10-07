"""
VIGIL AI — Unified External LLM Provider HTTP Connectors
"""

import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

# Endpoints par défaut des providers supportés
_DEFAULT_ENDPOINTS = {
    "groq": "https://api.groq.com/openai",
    "openrouter": "https://openrouter.ai/api",
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com",
    "glm": "https://api.z.ai/api/paas/v4",
}


def _chat_url(endpoint: str) -> str:
    """Construit l'URL de chat complet en gérant les bases versionnées (/v1, /v4...)."""
    base = endpoint.rstrip("/") if endpoint else "https://api.openai.com"
    if re.search(r"/v\d+$", base):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _timeout_from_cfg(cfg: Dict[str, Any], default: int = 60) -> int:
    try:
        return max(5, int(cfg.get("AI_TIMEOUT", default) or default))
    except Exception:
        return default


def call_ollama_api(
    prompt: str,
    system_prompt: str,
    endpoint: str,
    model: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    timeout: int = 30,
) -> str:
    """Appel vers Ollama local via l'endpoint /api/chat ou /api/generate."""
    base_url = endpoint.rstrip("/") if endpoint else "http://localhost:11434"
    url = f"{base_url}/api/chat"

    messages = [{"role": "system", "content": system_prompt}]
    if chat_history:
        for msg in chat_history[-8:]:
            r = msg.get("role")
            c = msg.get("content")
            if r in ["user", "assistant"] and c:
                messages.append({"role": r, "content": c})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model or "llama3",
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.3},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            msg = res.get("message", {})
            return msg.get("content", "").strip()
    except Exception:
        # Fallback sur /api/generate si /api/chat échoue
        gen_url = f"{base_url}/api/generate"
        gen_payload = {
            "model": model or "llama3",
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
        }
        gen_data = json.dumps(gen_payload).encode("utf-8")
        gen_req = urllib.request.Request(gen_url, data=gen_data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(gen_req, timeout=timeout) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return res.get("response", "").strip()


def call_openai_compatible_api(
    prompt: str,
    system_prompt: str,
    endpoint: str,
    model: str,
    api_key: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    timeout: int = 60,
) -> str:
    """Appel vers toute API compatible OpenAI (GLM/Z.ai, Groq, OpenRouter, DeepSeek, OpenAI, LM Studio)."""
    url = _chat_url(endpoint)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    messages = [{"role": "system", "content": system_prompt}]
    if chat_history:
        for msg in chat_history[-8:]:
            r = msg.get("role")
            c = msg.get("content")
            if r in ["user", "assistant"] and c:
                messages.append({"role": r, "content": c})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model or "gpt-4o-mini",
        "messages": messages,
        "temperature": 0.25,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            choices = res.get("choices", [])
            if choices and "message" in choices[0]:
                return choices[0]["message"].get("content", "").strip()
            return ""
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Erreur API HTTP {e.code} : {err_body}")
    except Exception as e:
        raise RuntimeError(f"Erreur de connexion API LLM : {e}")


call_openai_api = call_openai_compatible_api


def call_llm_provider(
    prompt: str,
    system_prompt: str,
    cfg: Dict[str, Any],
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Point d'entrée unique pour router l'appel vers le vrai modèle LLM configuré."""
    provider = (cfg.get("AI_PROVIDER") or "auto_rule").lower()
    endpoint = (cfg.get("AI_ENDPOINT") or "").strip()
    model = (cfg.get("AI_MODEL") or "").strip()
    api_key = (cfg.get("AI_API_KEY") or "").strip()
    timeout = _timeout_from_cfg(cfg)

    # endpoint local Ollama mal rempli → on retombe sur l'endpoint du provider
    is_ollama_endpoint = not endpoint or "11434" in endpoint

    if provider == "glm":
        target_endpoint = endpoint if not is_ollama_endpoint else _DEFAULT_ENDPOINTS["glm"]
        target_model = model if model and model not in ["llama3", "gpt-4o-mini"] else "glm-5.3"
        return call_openai_compatible_api(prompt, system_prompt, target_endpoint, target_model, api_key, chat_history, timeout)

    if provider == "groq":
        target_endpoint = endpoint if not is_ollama_endpoint else _DEFAULT_ENDPOINTS["groq"]
        groq_models = [model] if model and model not in ["llama3", "gpt-4o-mini", "llama-3.1-8b-instant", "llama-3.3-70b-versatile"] else []
        groq_models.extend(["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.6-27b", "qwen/qwen3.8-27b"])

        last_err = None
        for m in groq_models:
            if not m:
                continue
            try:
                return call_openai_compatible_api(prompt, system_prompt, target_endpoint, m, api_key, chat_history, timeout)
            except RuntimeError as e:
                last_err = e
                if any(x in str(e).lower() for x in ["model_not_found", "model_decommissioned", "404", "400"]):
                    continue
                # En cas d'erreur de résolution DNS temporaire, faire une courte pause et retenter
                if "temporary failure" in str(e).lower() or "name resolution" in str(e).lower():
                    import time
                    time.sleep(0.5)
                    try:
                        return call_openai_compatible_api(prompt, system_prompt, target_endpoint, m, api_key, chat_history, timeout)
                    except Exception:
                        pass
                raise e
        if last_err:
            raise last_err

    elif provider == "openrouter":
        target_endpoint = endpoint if not is_ollama_endpoint else _DEFAULT_ENDPOINTS["openrouter"]
        target_model = model if model and model not in ["llama3", "gpt-4o-mini"] else "meta-llama/llama-3.2-3b-instruct:free"
        return call_openai_compatible_api(prompt, system_prompt, target_endpoint, target_model, api_key, chat_history, timeout)

    elif provider == "deepseek":
        target_endpoint = endpoint if not is_ollama_endpoint else _DEFAULT_ENDPOINTS["deepseek"]
        target_model = model if model and model not in ["llama3", "gpt-4o-mini"] else "deepseek-chat"
        return call_openai_compatible_api(prompt, system_prompt, target_endpoint, target_model, api_key, chat_history, timeout)

    elif provider == "openai":
        target_endpoint = endpoint if not is_ollama_endpoint else _DEFAULT_ENDPOINTS["openai"]
        target_model = model or "gpt-4o-mini"
        return call_openai_compatible_api(prompt, system_prompt, target_endpoint, target_model, api_key, chat_history, timeout)

    elif provider == "ollama":
        target_endpoint = endpoint or "http://localhost:11434"
        target_model = model or "llama3"
        return call_ollama_api(prompt, system_prompt, target_endpoint, target_model, chat_history, timeout)

    # Mode auto: teste si clé groq / openai ou ollama
    if api_key:
        if api_key.startswith("gsk_"):
            for m in ["groq/compound", "groq/compound-mini", "qwen/qwen3.8-27b", "openai/gpt-oss-120b"]:
                try:
                    return call_openai_compatible_api(prompt, system_prompt, "https://api.groq.com/openai", m, api_key, chat_history, timeout)
                except Exception:
                    continue
        elif api_key.startswith("sk-"):
            return call_openai_compatible_api(prompt, system_prompt, "https://api.openai.com", "gpt-4o-mini", api_key, chat_history, timeout)
        else:
            # Autres formats de clé (ex: GLM Z.ai) → endpoint configuré ou GLM
            base = endpoint if not is_ollama_endpoint else _DEFAULT_ENDPOINTS["glm"]
            return call_openai_compatible_api(prompt, system_prompt, base, model or "glm-5.3", api_key, chat_history, timeout)

    try:
        return call_ollama_api(prompt, system_prompt, "http://localhost:11434", model or "llama3", chat_history, timeout)
    except Exception:
        raise RuntimeError("Aucun provider LLM configuré (clé API ou serveur Ollama requis).")
