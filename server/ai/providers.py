"""
VIGIL AI — External LLM Provider HTTP Connectors (Ollama & OpenAI)
"""

import json
import urllib.request
from typing import Dict, Any


def call_ollama_api(prompt: str, system_prompt: str, endpoint: str, model: str) -> str:
    """Effectue un appel API synchrone vers un serveur Ollama local."""
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


def call_openai_api(prompt: str, system_prompt: str, endpoint: str, model: str, api_key: str) -> str:
    """Effectue un appel API synchrone vers OpenAI ou toute API compatible OpenAI."""
    base_url = endpoint.rstrip("/") if endpoint else "https://api.openai.com"
    url = f"{base_url}/v1/chat/completions" if not base_url.endswith("/v1") else f"{base_url}/chat/completions"

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
        "temperature": 0.2,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        choices = res.get("choices", [])
        return choices[0]["message"]["content"] if choices else ""
