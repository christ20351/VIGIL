"""
VIGIL AI — Database-Driven Copilot Assistant Module
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional
from ai.agent_diag import diagnose_single_agent
from ai.cluster_diag import diagnose_entire_cluster
from ai.db_analytics import analyze_host_db_history, get_cluster_db_summary
from ai.providers import call_ollama_api, call_openai_api


def run_copilot_chat(
    prompt: str,
    computers_data: Dict[str, Any],
    cfg: Dict[str, Any],
    context_hostname: Optional[str] = None,
) -> Dict[str, Any]:
    """Traite la question de l'administrateur en combinant données BD et modèle LLM ou moteur autonome."""
    provider = cfg.get("AI_PROVIDER", "auto_rule")
    low_prompt = prompt.lower()

    # 1. Extraction des données réelles de la base SQLite
    db_summary = get_cluster_db_summary(hours=24)
    cluster_diag = diagnose_entire_cluster(computers_data)

    host_db_data = {}
    if context_hostname and context_hostname in computers_data:
        host_db_data = analyze_host_db_history(context_hostname, hours=24)

    # 2. Si un provider LLM est configuré, envoyer le contexte enrichi par la base de données
    if provider in ["ollama", "openai"] and cfg.get("AI_ENABLED", True):
        try:
            db_context = f"SANTÉ BD CLUSTER (24H):\n{json.dumps(cluster_summary_short(cluster_diag, db_summary), ensure_ascii=False)}\n"
            if host_db_data:
                db_context += f"\nDONNÉES BD HÔTE '{context_hostname}':\n{json.dumps(host_db_data, ensure_ascii=False)}\n"

            sys_prompt = cfg.get("AI_SYSTEM_PROMPT", "Vous êtes VIGIL AI, un copilote d'administration système.")
            full_prompt = f"DONNÉES EXTRAITES DE LA BASE SQLITE VIGIL :\n{db_context}\n\nQUESTION ADM SYS :\n{prompt}"

            if provider == "ollama":
                reply = call_ollama_api(full_prompt, sys_prompt, cfg.get("AI_ENDPOINT", ""), cfg.get("AI_MODEL", ""))
            else:
                reply = call_openai_api(full_prompt, sys_prompt, cfg.get("AI_ENDPOINT", ""), cfg.get("AI_MODEL", ""), cfg.get("AI_API_KEY", ""))

            if reply:
                return {"reply": reply, "provider": provider, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            pass  # Fallback au moteur guidé par la base de données ci-dessous

    # 3. Moteur autonome VIGIL basé directement sur SQLite
    reply = ""

    if any(w in low_prompt for w in ["historique", "24h", "base", "sqlite", "tendance", "hier", "semaine"]):
        reply = (
            f"### 🗄️ Analyse Historique de la Base de Données SQLite (24h)\n\n"
            f"- **Alertes enregistrées** : **{db_summary['total_notifications']}** ({db_summary['critical_count']} critiques, {db_summary['warning_count']} avertissements)\n"
            f"- **Score moyen santé cluster** : **{cluster_diag['health_score']}/100** (`{cluster_diag['status']}`)\n\n"
            f"**Dernières alertes en base :**\n"
            + ("\n".join(f"- `{a}`" for a in db_summary["recent_alerts"][:5]) if db_summary["recent_alerts"] else "- Aucune alerte majeure enregistrée.")
        )

    elif any(w in low_prompt for w in ["alerte", "notification", "critique", "nuit", "warning"]):
        if db_summary["recent_alerts"]:
            reply = (
                f"### ⚠️ Synthèse des Alertes Récentes en Base SQLite ({db_summary['total_notifications']} au total)\n\n"
                + "\n".join(f"- {a}" for a in db_summary["recent_alerts"])
            )
        else:
            reply = "### ✅ Aucune alerte critique ou avertissement en base de données sur les dernières 24 heures."

    elif any(w in low_prompt for w in ["cpu", "ram", "processus", "charge", "pic", "mémoire"]):
        procs_found = []
        for h, d in computers_data.items():
            h_data = analyze_host_db_history(h, hours=24)
            if h_data["top_historical_procs"]:
                procs_found.append(f"**{h}** (Pic CPU 24h: {h_data['peak_cpu']}%):\n  " + ", ".join(h_data["top_historical_procs"]))

        if procs_found:
            reply = "### ⚡ Analyse des Processus et Pics de Charge (Base SQLite)\n\n" + "\n\n".join(procs_found)
        else:
            reply = f"### 📊 Métriques CPU & RAM (24h)\nMoyenne globale CPU: **{cluster_diag.get('health_score')}%**. Aucun pic anormal répertorié."

    elif any(w in low_prompt for w in ["disque", "smart", "panne", "stockage", "température"]):
        disks_warn = []
        for h, d in computers_data.items():
            h_data = analyze_host_db_history(h, hours=24)
            if h_data["smart_warnings"]:
                disks_warn.append(f"**{h}** : " + ", ".join(h_data["smart_warnings"]))

        if disks_warn:
            reply = "### 🚨 Alertes S.M.A.R.T. Détectées en Base de Données\n\n" + "\n".join(f"- {dw}" for dw in disks_warn)
        else:
            reply = "### 💾 Santé des Disques (Base SQLite)\nTous les rapports S.M.A.R.T. historiques indiquent un état sain (`PASSED`)."

    else:
        reply = (
            f"### 🤖 Copilote VIGIL AI (Moteur BD SQLite)\n\n"
            f"J'analyse **{len(computers_data)} hôtes** et l'historique SQLite (**{db_summary['total_notifications']} alertes** sur 24h).\n\n"
            f"**Exemples de requêtes prises en charge :**\n"
            f"- *'Analyse l'historique de la base de données sur 24h'*\n"
            f"- *'Quelles alertes critiques ont eu lieu cette nuit ?'*\n"
            f"- *'Montre-moi les pics de CPU et les processus en base'*\n"
            f"- *'Vérifie les journaux S.M.A.R.T. pour les risques de panne'*\n"
        )

    return {"reply": reply, "provider": "smart_db_engine", "timestamp": datetime.now().isoformat()}


def cluster_summary_short(cluster_diag: dict, db_summary: dict) -> dict:
    return {
        "health_score": cluster_diag.get("health_score"),
        "status": cluster_diag.get("status"),
        "total_hosts": cluster_diag.get("total_hosts"),
        "online_hosts": cluster_diag.get("online_hosts"),
        "recent_db_alerts": db_summary.get("recent_alerts", [])[:5],
    }
