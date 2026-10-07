"""
Vili — Moteur d'actions de l'agent IA autonome.

Cycle complet : analyse de TOUTES les données (métriques live + historique
base de données + notifications + incidents) → décision par LLM (GLM) →
actions:
  - notify(severity, message)  : notification interne sur le dashboard admin
  - run_command(hostname, cmd) : commande système exécutée sur l'agent

Niveaux d'autonomie (AI_AUTONOMOUS_ACTIONS):
  off     → Vili notifie uniquement
  propose → Vili suggère des commandes (l'admin les exécute en 1 clic)
  auto    → Vili exécute lui-même (avec garde-fous anti-destructeurs)
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Any, Dict, List

import config
from ai.agent_diag import diagnose_single_agent
from ai.autonomous_db import save_autonomous_ai_report
from ai.db_analytics import get_cluster_db_summary
from ai.providers import call_llm_provider

# Commandes trop dangereuses pour une exécution automatique — Vili les
# transforme en simple proposition soumises à l'admin.
_FORBIDDEN_AUTO_PATTERNS = [
    "rm -rf /", "rm -fr /", "mkfs", "shutdown", "reboot", "halt", "poweroff",
    "dd if=", ":(){", "format c:", "del /f /s /q c:", "rd /s /q c:",
    "shutdown /r", "shutdown /s", "> /dev/sda", "wipefs",
]


VILI_SYSTEM_PROMPT = """Tu es Vili, l'agent IA autonome de supervision de la plateforme VIGIL.

### TA MISSION
Tu surveilles une infrastructure informatique. À chaque cycle, tu reçois un état complet de TOUTES les machines (métriques temps réel, historiques de la base de données, alertes récentes, incidents en cours). Tu dois :
1. Analyser la situation globale et détecter les problèmes réels (saturation CPU/RAM/disque, disques S.M.A.R.T. défaillants, agents hors ligne, surcharges réseau, processus anormaux).
2. Prendre des DÉCISIONS concrètes d'administration système.
3. Déclencher des actions pour corriger ou alerter.

### PROTOCOLE D'ACTIONS (STRICT)
Réponds en DEUX parties :
1. Une analyse concise en Markdown (max 15 lignes) pour l'administrateur.
2. PUIS un unique bloc de décision JSON, exactement au format :
```json
{"actions": [{"type": "notify", "severity": "info|warning|error", "message": "..."}, {"type": "run_command", "hostname": "...", "command": "...", "reason": "..."}, {"type": "watch_rule", "description": "...", "metric": "cpu|ram|disk|net_total|temp", "operator": ">|<", "threshold": 80, "hostname": "...", "reason": "..."}]}
```

### RÈGLES
- `notify` : toujours pertinent (synthèse, alerte précoce, confirmation).
- `run_command` : propose une commande corrective (relancer un service, purger des logs, tuer un processus fautif, nettoyer un cache). Elle ne sera JAMAIS exécutée directement : l'administrateur reçoit une demande de confirmation (Oui/Non) sur son dashboard et décide. Jamais de commande destructive (pas de rm -rf /, mkfs, shutdown, reboot) — celles-ci sont signalées risquées.
- `watch_rule` : installe une surveillance continue (ex: « préviens si la RAM de X dépasse 90% ») quand l'admin a exprimé ce besoin ou quand un métrique mérite un suivi rapproché après un incident.
- N'invente jamais de hostname : utilise uniquement ceux listés dans les données.
- Si tout est sain, réponds une analyse courte et {"actions": []}.
- Maximum 5 actions par cycle.
"""


def _is_forbidden_auto(command: str) -> bool:
    c = command.lower()
    return any(p in c for p in _FORBIDDEN_AUTO_PATTERNS)


def build_vili_context(computers_data: Dict[str, Any]) -> str:
    """Construit le contexte complet (live + BD) soumis à Vili."""
    from ai.db_analytics import analyze_host_db_history

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"=== ÉTAT DE L'INFRASTRUCTURE VIGIL ({now_str}) ===", ""]

    if not computers_data:
        lines.append("Aucun agent connecté.")
    for host, data in computers_data.items():
        diag = diagnose_single_agent(host, data)
        offline = data.get("offline", False)
        lines.append(f"### {host} [{'HORS LIGNE' if offline else 'EN LIGNE'}] (score {diag['health_score']}/100)")
        lines.append(
            f"- CPU {data.get('cpu_percent', 0):.1f}% | RAM {data.get('memory', {}).get('percent', 0):.1f}%"
            f" | Disque {data.get('disk', {}).get('percent', 0):.1f}%"
        )
        hist = diag.get("db_history") or {}
        if hist:
            lines.append(
                f"- Historique 24h: CPU moy {hist.get('avg_cpu')}% (pic {hist.get('peak_cpu')}%),"
                f" RAM moy {hist.get('avg_ram')}%"
            )
            if hist.get("smart_warnings"):
                lines.append(f"- ⚠️ S.M.A.R.T.: {', '.join(hist['smart_warnings'])}")
            if hist.get("top_historical_procs"):
                lines.append(f"- Processus lourds récurrents: {', '.join(hist['top_historical_procs'][:4])}")
        procs = data.get("processes") or []
        if procs:
            top = sorted(procs, key=lambda p: p.get("cpu_percent", 0), reverse=True)[:4]
            lines.append("- Top processus: " + ", ".join(
                f"{p.get('name')} ({p.get('cpu_percent', 0)}% CPU)" for p in top))
        if diag.get("issues"):
            lines.append("- Problèmes: " + " ; ".join(diag["issues"]))
        lines.append("")

    # alertes récentes
    summary = get_cluster_db_summary(hours=6)
    lines.append(f"### Notifications base (6h): {summary['total_notifications']} "
                 f"(critiques: {summary['critical_count']}, erreurs: {summary['error_count']})")
    for a in summary["recent_alerts"][:10]:
        lines.append(f"- [{a['timestamp']}] {a['hostname']}: {a['message']}")
    return "\n".join(lines)


def _extract_decision_json(reply: str) -> Dict[str, Any]:
    """Extrait le bloc de décision JSON de la réponse du modèle."""
    if not reply:
        return {"actions": []}
    # bloc ```json ... ``` prioritaire
    m = re.search(r"```json\s*(\{.*?\})\s*```", reply, re.DOTALL)
    if not m:
        m = re.search(r"(\{\s*\"actions\"\s*:.*\})", reply, re.DOTALL)
    if not m:
        return {"actions": []}
    try:
        data = json.loads(m.group(1))
        if isinstance(data, dict) and isinstance(data.get("actions"), list):
            return data
    except Exception:
        pass
    return {"actions": []}


def _markdown_without_json(reply: str) -> str:
    reply = re.sub(r"```json\s*\{.*?\}\s*```", "", reply, flags=re.DOTALL).strip()
    return reply or "(analyse vide)"


def _execute_command_sync(hostname: str, command: str, timeout: int) -> Dict[str, Any]:
    """Exécute une commande via le canal WS depuis un thread (boucle Vili)."""
    from websocket_handler import main_loop, send_command_to_agent

    if main_loop is None:
        return {"ok": False, "error": "Boucle d'événements serveur indisponible."}
    fut = asyncio.run_coroutine_threadsafe(
        send_command_to_agent(hostname, command, timeout=timeout), main_loop
    )
    try:
        return fut.result(timeout=timeout + 20)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def run_vili_decision_cycle(computers_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cycle complet Vili : contexte → LLM → actions.
    Retourne un résumé {analysis, actions_taken}.
    """
    mode = (getattr(config, "AI_AUTONOMOUS_ACTIONS", "propose") or "propose").lower()
    cfg = {
        "AI_PROVIDER": getattr(config, "AI_PROVIDER", "auto_rule"),
        "AI_API_KEY": getattr(config, "AI_API_KEY", ""),
        "AI_MODEL": getattr(config, "AI_MODEL", ""),
        "AI_ENDPOINT": getattr(config, "AI_ENDPOINT", ""),
        "AI_TIMEOUT": getattr(config, "AI_TIMEOUT", 60),
    }

    context = build_vili_context(computers_data)

    # Couche d'intelligence : anomalies, prévisions de saturation,
    # dégradations, corrélations d'incidents + règles actives
    try:
        from ai.analytics import format_intelligence_for_prompt
        context += "\n\n" + format_intelligence_for_prompt(computers_data)
    except Exception as e:
        print(f"[VILI] analytics indisponible: {e}")
    try:
        from ai.watch import format_watch_rules_for_prompt
        wr = format_watch_rules_for_prompt()
        if wr:
            context += "\n\n" + wr
    except Exception:
        pass

    reply = call_llm_provider(
        prompt=context,
        system_prompt=VILI_SYSTEM_PROMPT,
        cfg=cfg,
    )
    analysis = _markdown_without_json(reply)
    decision = _extract_decision_json(reply)

    from websocket_handler import notify_dashboard_sync

    taken: List[Dict[str, Any]] = []
    proposed_commands: List[Dict[str, Any]] = []

    for action in decision["actions"][:5]:
        if not isinstance(action, dict):
            continue
        a_type = action.get("type")
        try:
            if a_type == "notify":
                severity = action.get("severity", "info")
                if severity not in ("info", "warning", "error"):
                    severity = "info"
                message = f"🤖 Vili : {action.get('message', '')}"
                notify_dashboard_sync(action.get("hostname") or "cluster", message, severity)
                taken.append({"type": "notify", "severity": severity})

            elif a_type == "watch_rule":
                metric = (action.get("metric") or "").strip()
                if metric not in ("cpu", "ram", "disk", "net_total", "temp"):
                    continue
                hostname = action.get("hostname") or None
                if hostname and hostname not in computers_data:
                    hostname = None  # hôte inconnu → toutes les machines
                try:
                    threshold = float(action.get("threshold", 0) or 0)
                except Exception:
                    continue
                if threshold <= 0:
                    continue
                operator = "<" if action.get("operator") == "<" else ">"
                description = action.get("description") or (
                    f"{metric} {operator} {threshold} sur {hostname or 'toutes les machines'}"
                )
                try:
                    from ai.watch import create_rule_from_parsed

                    rule_id = create_rule_from_parsed(
                        {
                            "description": description,
                            "metric": metric,
                            "operator": operator,
                            "threshold": threshold,
                            "hostname": hostname,
                            "duration_sec": 0,
                        },
                        created_by="vili",
                    )
                    notify_dashboard_sync(
                        hostname or "cluster",
                        f"👁️ Vili a installé une surveillance : {description} (règle #{rule_id})",
                        "info",
                    )
                    taken.append({"type": "watch_rule", "rule_id": rule_id})
                except Exception as e:
                    print(f"[VILI] création watch_rule échouée: {e}")

            elif a_type == "run_command":
                hostname = action.get("hostname", "")
                command = (action.get("command") or "").strip()
                reason = action.get("reason", "")
                if hostname not in computers_data or not command:
                    continue

                # ── Toute commande de Vili passe par l'admin (Oui / Non) ──
                # En mode "auto", seules les commandes non destructrices
                # sont soumises ; les interdites restent visibles aussi
                # (l'admin décide), marquées comme risquées.
                risky = _is_forbidden_auto(command)
                try:
                    from db.storage import create_approval
                    from websocket_handler import broadcast_approval_request

                    approval_id = create_approval(
                        hostname, command, reason,
                        created_by="vili",
                    )
                    approval = {
                        "id": approval_id,
                        "hostname": hostname,
                        "command": command,
                        "reason": reason,
                        "ts": datetime.now().isoformat(),
                    }
                    broadcast_approval_request(approval)
                    notify_dashboard_sync(
                        hostname,
                        f"🤖 Vili demande l'autorisation d'exécuter `{command}` "
                        f"sur {hostname} — {reason}. Confirmez (Oui/Non) "
                        "depuis la notification sur le dashboard.",
                        "warning",
                    )
                    taken.append({
                        "type": "approval_request", "approval_id": approval_id,
                        "hostname": hostname, "command": command,
                        "risky": risky,
                    })
                except Exception as e:
                    print(f"[VILI] création demande d'autorisation échouée: {e}")
        except Exception as e:
            print(f"[VILI] Erreur exécution action {action}: {e}")

    # persister un rapport Vili (analyse + actions) pour le dashboard
    if taken or proposed_commands:
        save_autonomous_ai_report(
            "cluster",
            f"🤖 Vili — Cycle autonome ({len(taken)} action(s))",
            "warning" if any(t.get("type") == "run_command" for t in taken) else "info",
            analysis[:1500],
            {
                "mode": mode,
                "actions": taken,
                "proposed_commands": proposed_commands,
                "model": cfg.get("AI_MODEL") or cfg.get("AI_PROVIDER"),
            },
        )

    return {"analysis": analysis, "actions_taken": taken, "mode": mode}


# ================================================================
#  RAPPORT QUOTIDIEN AUTOMATIQUE
# ================================================================

DAILY_REPORT_PROMPT = """Tu es Vili. Rédige le RAPPORT QUOTIDIEN de l'infrastructure VIGIL pour l'administrateur.

Structure obligatoire :
### 🌅 Rapport quotidien Vili — {date}
1. **Synthèse exécutive** (3 lignes max : état général, faits marquants)
2. **Incidents des dernières 24h** (avec cause probable quand le contexte le suggère)
3. **Anomalies & tendances** (écarts au comportement normal, dégradations progressives)
4. **Prévisions** (saturations à venir avec échéances)
5. **Recommandations** (2-4 actions concrètes priorisées)

Sois factuel : cite les valeurs réelles du contexte. Pas de JSON dans ce rapport."""


def generate_daily_report(computers_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Génère et diffuse le rapport quotidien : synthèse 24h + anomalies +
    prévisions + recommandations. Sauvegardé comme rapport IA et notifié
    sur le dashboard.
    """
    from ai.analytics import format_intelligence_for_prompt
    from ai.autonomous_db import save_autonomous_ai_report
    from websocket_handler import notify_dashboard_sync

    cfg = {
        "AI_PROVIDER": getattr(config, "AI_PROVIDER", "auto_rule"),
        "AI_API_KEY": getattr(config, "AI_API_KEY", ""),
        "AI_MODEL": getattr(config, "AI_MODEL", ""),
        "AI_ENDPOINT": getattr(config, "AI_ENDPOINT", ""),
        "AI_TIMEOUT": getattr(config, "AI_TIMEOUT", 60),
    }

    today = datetime.now().strftime("%d/%m/%Y")
    context = build_vili_context(computers_data)
    context += "\n\n" + format_intelligence_for_prompt(computers_data)

    reply = call_llm_provider(
        prompt=context,
        system_prompt=DAILY_REPORT_PROMPT.format(date=today),
        cfg=cfg,
    )
    report = (reply or "").strip() or "Rapport indisponible (LLM sans réponse)."

    save_autonomous_ai_report(
        "cluster",
        f"🌅 Rapport quotidien Vili — {today}",
        "info",
        report[:4000],
        {"type": "daily_report", "date": today},
    )
    notify_dashboard_sync(
        "cluster",
        f"🌅 Rapport quotidien de Vili disponible ({today}) — onglet rapports IA.",
        "info",
    )
    return {"status": "ok", "report": report[:2000], "date": today}
