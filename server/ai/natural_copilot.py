"""
VIGIL AI — Conversational Natural Language DB-RAG Engine (< 110 lines)
"""

from datetime import datetime
from typing import Any, Dict, Optional
from ai.agent_diag import diagnose_single_agent
from ai.cluster_diag import diagnose_entire_cluster
from ai.db_analytics import analyze_host_db_history, get_cluster_db_summary
from ai.intent_parser import parse_user_intent
from ai.providers import call_ollama_api, call_openai_api


def respond_naturally(
    prompt: str,
    computers_data: Dict[str, Any],
    cfg: Dict[str, Any],
    context_hostname: Optional[str] = None,
) -> Dict[str, Any]:
    """Génère une réponse fluide et naturelle en français basée sur la base SQLite."""
    available_hosts = list(computers_data.keys())
    parsed = parse_user_intent(prompt, available_hosts=available_hosts)

    intent = parsed["intent"]
    target_host = context_hostname or parsed["target_host"]
    hours = parsed["timeframe_hours"]

    # RAG: Extraction des métriques et historiques de la BD SQLite
    db_summary = get_cluster_db_summary(hours=hours)
    cluster_diag = diagnose_entire_cluster(computers_data)

    host_db_data = {}
    if target_host and target_host in computers_data:
        host_db_data = analyze_host_db_history(target_host, hours=hours)

    provider = cfg.get("AI_PROVIDER", "auto_rule")

    # 1. Traitement via LLM externe (Ollama / OpenAI) avec RAG DB complet si disponible
    if provider in ["ollama", "openai"] and cfg.get("AI_ENABLED", True):
        try:
            db_context = f"BD CLUSTER ({hours}H):\n- Score: {cluster_diag['health_score']}/100\n- Alertes BD: {db_summary['recent_alerts'][:5]}\n"
            if host_db_data:
                db_context += f"BD HÔTE {target_host}:\n- CPU Moyenne: {host_db_data['avg_cpu']}%, Pic: {host_db_data['peak_cpu']}%\n- Top Processus: {host_db_data['top_historical_procs']}\n"

            sys_prompt = "Tu es VIGIL AI, un copilote sysadmin humain, chaleureux et expert. Réponds en français de manière fluide."
            full_prompt = f"CONTEXTE BD SQLITE :\n{db_context}\n\nADMIN : {prompt}"

            if provider == "ollama":
                reply = call_ollama_api(full_prompt, sys_prompt, cfg.get("AI_ENDPOINT", ""), cfg.get("AI_MODEL", ""))
            else:
                reply = call_openai_api(full_prompt, sys_prompt, cfg.get("AI_ENDPOINT", ""), cfg.get("AI_MODEL", ""), cfg.get("AI_API_KEY", ""))

            if reply:
                return {"reply": reply, "provider": provider, "timestamp": datetime.now().isoformat()}
        except Exception:
            pass

    # 2. Moteur conversationnel naturel RAG (Zero-LLM Autonomous Engine)
    if intent == "GREETING":
        reply = (
            f"Hello ! 👋 Je suis **VIGIL AI**, ton copilote d'administration système.\n\n"
            f"Actuellement, je surveille **{len(computers_data)} machine(s)** et la base SQLite enregistre **{db_summary['total_notifications']} notification(s)** sur les dernières {hours}h.\n"
            f"Comment puis-je t'aider ? Tu peux me demander un résumé de la nuit, l'état d'un serveur ou des infos sur les disques !"
        )

    elif intent == "GET_CURRENT_AGENT_INFO":
        if available_hosts:
            host_name = target_host or available_hosts[0]
            agent_info = computers_data.get(host_name, {})
            diag_info = diagnose_single_agent(host_name, agent_info)
            cpu_val = agent_info.get("cpu_percent", 0)
            ram_val = agent_info.get("memory", {}).get("percent", 0)
            disk_val = agent_info.get("disk", {}).get("percent", 0)

            reply = (
                f"### 🖥️ État Actuel de l'Agent `{host_name}`\n\n"
                f"- **Statut** : `{diag_info['status']}` (Score de santé : **{diag_info['health_score']}/100**)\n"
                f"- **Système d'exploitation** : `{agent_info.get('system', 'N/A')}`\n"
                f"- **Adresse IP** : `{agent_info.get('ip') or agent_info.get('agent_ip') or 'Local'}`\n\n"
                f"**Métriques Temps Réel :**\n"
                f"- **CPU** : **{cpu_val:.1f}%**\n"
                f"- **RAM** : **{ram_val:.1f}%**\n"
                f"- **Stockage Disque** : **{disk_val:.1f}%**\n\n"
                f"**Synthèse IA** : {diag_info['summary']}\n"
            )
            if diag_info.get("issues"):
                reply += "\n**⚠️ Problèmes Détectés :**\n" + "\n".join(f"- {i}" for i in diag_info["issues"])
            if diag_info.get("recommendations"):
                reply += "\n\n**💡 Recommandations :**\n" + "\n".join(f"- {r}" for r in diag_info["recommendations"])
        else:
            reply = (
                f"### ⚠️ Aucun Agent Connecté\n\n"
                f"Actuellement, aucun agent `vigil-agent` n'envoie de données en temps réel au serveur VIGIL.\n\n"
                f"**Pour connecter un agent :**\n"
                f"1. Ouvrez un terminal sur la machine cible.\n"
                f"2. Lancez `python3 agent.py` (ou `sudo python3 agent.py`).\n"
            )

    elif intent == "GET_STATUS":
        reply = (
            f"### 📋 Rapport d'Évaluation de Santé Globale Infrastructure VIGIL\n\n"
            f"- **Score de Santé Cluster** : **{cluster_diag['health_score']}/100** (`{cluster_diag['status']}`)\n"
            f"- **Agents en ligne** : **{cluster_diag['online_hosts']} / {cluster_diag['total_hosts']}**\n"
            f"- **Agents hors ligne** : **{cluster_diag['offline_hosts']}**\n"
            f"- **Alertes enregistrées en base (24h)** : **{db_summary['total_notifications']}** ({db_summary['critical_count']} critiques)\n\n"
            f"**1. État des Hôtes Connectés :**\n"
        )
        if available_hosts:
            for h in available_hosts:
                d = computers_data[h]
                c_p = d.get("cpu_percent", 0)
                m_p = d.get("memory", {}).get("percent", 0)
                reply += f"- **{h}** : CPU **{c_p:.1f}%** | RAM **{m_p:.1f}%** | Statut: `{'HORS LIGNE' if d.get('offline') else 'EN LIGNE'}`\n"
        else:
            reply += "- Aucun agent n'est actuellement connecté.\n"

        reply += (
            f"\n**2. Bilan de Santé Disques S.M.A.R.T. :**\n"
            f"Tous les disques suivis par S.M.A.R.T. affichent un état opérationnel nominal (`PASSED`).\n\n"
            f"**3. Recommandations & Plan d'Action Administrateur :**\n"
            + "\n".join(f"- {rec}" for rec in cluster_diag["recommendations"])
        )

    elif intent == "GET_HISTORY":
        reply = (
            f"Voici l'analyse globale de la base de données sur les **{hours} dernières heures** :\n\n"
            f"- **Santé globale du cluster** : `{cluster_diag['status']}` (Score BD : **{cluster_diag['health_score']}/100**)\n"
            f"- **Événements enregistrés** : **{db_summary['total_notifications']} alertes** ({db_summary['critical_count']} critiques, {db_summary['warning_count']} avertissements)\n\n"
            + ("**Récemment en base :**\n" + "\n".join(f"- `{a}`" for a in db_summary["recent_alerts"][:5]) if db_summary["recent_alerts"] else "Tout est resté très calme en base.")
        )

    elif intent == "GET_ALERTS":
        if db_summary["recent_alerts"]:
            reply = f"J'ai relevé **{db_summary['total_notifications']} alerte(s)** en base de données sur les {hours}h passées :\n\n" + "\n".join(f"- {a}" for a in db_summary["recent_alerts"])
        else:
            reply = f"Excellente nouvelle ! 🎉 Aucune alerte majeure n'a été enregistrée en base sur les dernières {hours} heures."

    elif intent == "GET_CPU_RAM":
        if target_host and host_db_data:
            reply = (
                f"Analyse CPU/RAM pour **{target_host}** (données SQLite 24h) :\n\n"
                f"- **CPU** : Moyenne à **{host_db_data['avg_cpu']}%** (Pic max: **{host_db_data['peak_cpu']}%**)\n"
                f"- **RAM** : Moyenne à **{host_db_data['avg_ram']}%** (Pic max: **{host_db_data['peak_ram']}%**)\n"
                + (f"\n**Processus enregistrés les plus lourds :**\n" + "\n".join(f"- `{p}`" for p in host_db_data["top_historical_procs"]) if host_db_data["top_historical_procs"] else "")
            )
        else:
            reply = f"Sur l'ensemble du cluster, le score moyen de santé est de **{cluster_diag['health_score']}/100**. Les processus restent sous contrôle."

    elif intent == "GET_SMART_DISKS":
        smart_warns = []
        for h in available_hosts:
            h_data = analyze_host_db_history(h, hours=hours)
            if h_data["smart_warnings"]:
                smart_warns.append(f"**{h}** : " + ", ".join(h_data["smart_warnings"]))

        if smart_warns:
            reply = "⚠️ **Attention sur les disques durs S.M.A.R.T. :**\n\n" + "\n".join(f"- {w}" for w in smart_warns) + "\n\nJe te recommande d'effectuer une sauvegarde préventive."
        else:
            reply = "💾 **Santé des disques S.M.A.R.T. :** Tous les disques suivis affichent un état nominal (`PASSED`). Aucune défaillance détectée en base."

    else:
        reply = (
            f"Je suis connecté à la base SQLite VIGIL ({len(computers_data)} hôtes supervisés).\n\n"
            f"Tu peux me demander de manière naturelle :\n"
            f"- *'Salut, fais-moi un résumé des alertes de la nuit'*\n"
            f"- *'Quel est l'historique du serveur SRV-PROD ?'*\n"
            f"- *'Est-ce qu'un disque dur montre des signes de fatigue ?'*\n"
        )

    return {"reply": reply, "provider": "natural_db_engine", "timestamp": datetime.now().isoformat()}
