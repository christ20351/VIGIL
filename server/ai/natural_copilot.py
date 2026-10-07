"""
Vili — Conversational Natural Language DB-RAG Engine
Système IA de monitoring avec prompt système intégré dans le code et accès complet à la base SQLite.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from ai.agent_diag import diagnose_single_agent
from ai.cluster_diag import diagnose_entire_cluster
from ai.db_analytics import (
    analyze_host_db_history,
    build_complete_db_context,
    get_cluster_db_summary,
)
from ai.intent_parser import parse_user_intent
from ai.providers import call_llm_provider


# ================================================================
#  PROMPT SYSTÈME OFFICIEL VIGIL INTÉGRÉ AU CODE (NON CONFIG.YAML)
# ================================================================
VIGIL_CORE_SYSTEM_PROMPT = """Tu es Vili, le copilote d'administration système et d'intelligence opérationnelle de la plateforme de monitoring VIGIL v2.0.

### TON RÔLE ET TES CAPACITÉS :
- Tu as un accès direct, complet et en temps réel aux données de la base de données de VIGIL (tables `metrics`, `notifications`, `ai_diagnostics`) ainsi qu'aux métriques des agents connectés.
- Tu analyses l'infrastructure : santé des machines (CPU, RAM, Disque, Réseau), surveillance matérielle S.M.A.R.T., détection des pannes et anomalies, analyse des processus lourds, historique des alertes, tendances et diagnostics.
- Tu réponds aux questions de l'administrateur de façon fluide, naturelle, experte et précise en t'appuyant STRICTEMENT et TOUJOURS sur les données factuelles de la base de données fournies dans le contexte.

### RÈGLES STRICTES ET CADRAGE (DOMAIN GUARDRAILS) :
1. PÉRIMÈTRE EXCLUSIF VIGIL & INFRASTRUCTURE : Tu ne réponds QU'AUX questions ayant trait au monitoring VIGIL, à l'administration système, aux serveurs et machines supervisés, aux métriques (CPU/RAM/Disque/Réseau/SMART/Processus), aux pannes informatiques, aux alertes et à la santé de l'infrastructure.
2. REFUS DES QUESTIONS HORS-SUJET : Si l'utilisateur te pose une question totalement étrangère à VIGIL, au système ou à l'infrastructure (ex: recettes de cuisine, politique, devoirs scolaires, culture générale non liée à l'informatique ou au devops), tu dois refuser poliment et brièvement en rappelant : "Je suis Vili, votre copilote dédié au monitoring et à la gestion de votre infrastructure VIGIL. Je ne peux répondre qu'aux questions relatives à vos machines, alertes et métriques de supervision."
3. EXACTITUDE DES DONNÉES : Cite toujours les valeurs réelles présentes dans le contexte (noms exacts des hôtes, pourcentages réels, noms des processus, dates/heures des alertes, températures et statuts SMART). N'invente jamais de faux serveurs ou fausses métriques.
4. FORMATAGE SOIGNÉ EN PUR MARKDOWN : Structure tes réponses en Markdown standard élégant (titres `###`, listes à puces avec tirets `-`, chiffres en `**gras**`, tableaux Markdown avec pipes `|`). N'utilise JAMAIS de balises HTML brutes (comme `<ul>`, `<li>`, `<br>`, `<table>`) dans ton texte ou tes tableaux ; utilise exclusivement la syntaxe Markdown standard.

### EXÉCUTION D'ACTIONS SUR LES MACHINES (PROTOCOLE STRICT)
Quand l'administrateur te demande d'AGIR sur une machine (exécuter une commande, diagnostiquer en profondeur, redémarrer un service, tuer un processus, nettoyer des logs, dérouler un plan d'action...) :
1. Rédige D'ABORD ton analyse ou ton plan en Markdown (concis, étapes numérotées pour un plan).
2. PUIS termine par UN UNIQUEMENT bloc de décision JSON :
{"actions":[{"type":"run_command","hostname":"...","command":"...","reason":"...","risk":"read|privileged"}]}

Classification OBLIGATOIRE de "risk" :
- "read" : commande de LECTURE purement inoffensive (ps aux, df -h, du, free -m, uptime, ls, cat d'un fichier de config/log, systemctl status, journalctl, hostname, uname, id, top -b -n1...) → elle sera exécutée immédiatement et le résultat montré à l'admin.
- "privileged" : toute commande à EFFET ou nécessitant des privilèges (sudo, systemctl restart/stop/start, kill, pkill, apt/yum, rm, mv, écriture de fichiers, redémarrages...) OU un plan d'action multi-étapes → elle ne sera PAS exécutée : elle sera soumise à la CONFIRMATION Oui/Non de l'administrateur directement dans le chat.

RÈGLES D'OR :
- Pour un plan d'action : une action par étape, dans l'ordre logique d'exécution (maximum 6 actions). Chaque étape a son propre "reason" clair.
- JAMAIS de commande destructive (rm -rf /, mkfs, shutdown, reboot, dd, format). Refuse-les en expliquant pourquoi.
- Hostname obligatoire et valide (issu du contexte uniquement).
- Si la demande est ambiguë ou risquée sans nécessité, POSE LA QUESTION au lieu de proposer une commande, sans bloc JSON.
- Si tu n'as rien à exécuter, ne mets aucun bloc JSON.
"""

# Prompt dédié aux demandes d'ACTION (exécution de commandes / plans).
# Directif et court : le modèle doit produire le bloc de décision JSON,
# le serveur fait le reste (exécution immédiate ou confirmation Oui/Non).
VILI_ACTION_PROMPT = """Tu es Vili, le copilote système de VIGIL. LE CANAL D'EXÉCUTION EST ACTIF : tu es branché au moteur d'exécution de VIGIL, qui exécute réellement les commandes sur les machines supervisées. Ce mécanisme est déjà implémenté et fonctionne en production.

FORMAT DE RÉPONSE OBLIGATOIRE (aucune autre forme acceptée) :
1. Un très court préambule Markdown (1-3 phrases : ce que tu vas faire et pourquoi).
2. PUIS exactement ce bloc JSON :
{"actions":[{"type":"run_command","hostname":"<machine>","command":"<commande>","reason":"<pourquoi>","risk":"read"}]}

CLASSIFICATION :
- "risk":"read" pour toute commande de lecture/diagnostic inoffensive (ps aux, df -h, du, free -m, journalctl, systemctl status, lsblk, ss -tulpn, cat /etc/..., tail, grep, uptime, ls...) → exécutée immédiatement, la sortie est montrée à l'administrateur.
- "risk":"privileged" pour toute commande à effet ou privilégiée (systemctl restart/stop/start, sudo, apt, kill, pkill, rm de logs, nettoyage de cache, écritures...) → elle sera soumise à la CONFIRMATION Oui/Non de l'administrateur. C'est le comportement attendu, propose-la normalement.

RÈGLES :
- Pour un plan d'action : une action par étape, dans l'ordre logique (max 6 actions dans le tableau).
- Hostname : uniquement parmi les machines listées dans les données ci-dessous.
- JAMAIS de commande destructive (rm -rf /, mkfs, shutdown, reboot, dd). Si c'est ce qu'on te demande, refuse et explique.
- Après le bloc JSON, n'écris RIEN d'autre (pas de commentaire après le bloc).
- Ne dis jamais que tu ne peux pas exécuter de commandes : le canal est opérationnel.
"""


def _process_chat_actions(reply: str, computers_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Traite le bloc de décision JSON éventuel de la réponse du chat :
    - "risk": "read" et commande sur liste blanche → exécution immédiate,
      résultat renvoyé dans la réponse (affiché dans le chat) ;
    - "risk": "privileged" (ou commande hors liste blanche) → création
      d'une demande d'autorisation Oui/Non, affichée dans le chat ;
    - commandes destructrices → refusées systématiquement.

    Retourne {reply (nettoyé du JSON), approvals: [...], executions: [...]}.
    """
    import re as _re

    from ai.actions import _extract_decision_json, _is_forbidden_auto, _markdown_without_json

    approvals: List[Dict[str, Any]] = []
    executions: List[Dict[str, Any]] = []

    decision = _extract_decision_json(reply)
    actions = [a for a in decision.get("actions", []) if isinstance(a, dict)]
    if not actions:
        return {"reply": reply.strip(), "approvals": [], "executions": []}

    for action in actions[:6]:
        if action.get("type") != "run_command":
            continue
        hostname = action.get("hostname", "")
        command = (action.get("command") or "").strip()
        reason = action.get("reason", "")
        risk = (action.get("risk") or "privileged").lower()
        if hostname not in computers_data or not command:
            continue

        if _is_forbidden_auto(command):
            executions.append({
                "hostname": hostname, "command": command,
                "refused": True,
                "reason": "Commande destructive refusée par la politique de sécurité.",
            })
            continue

        # commande de lecture inoffensive → vérif serveur (liste blanche)
        # puis exécution immédiate
        if risk == "read" and _is_readonly_command(command):
            from ai.actions import _execute_command_sync
            import config as _config

            timeout = int(getattr(_config, "AGENT_COMMAND_TIMEOUT", 60) or 60)
            result = _execute_command_sync(hostname, command, timeout=timeout)
            executions.append({
                "hostname": hostname, "command": command,
                "ok": result.get("ok"),
                "exit_code": result.get("exit_code"),
                "stdout": (result.get("stdout") or "")[:4000],
                "stderr": (result.get("stderr") or "")[:2000],
                "error": result.get("error"),
            })
            continue

        # commande sensible / privilégiée → demande Oui / Non dans le chat
        try:
            from db.storage import create_approval

            approval_id = create_approval(
                hostname, command, reason or "Action demandée via le chat",
                created_by="chat",
            )
            approvals.append({
                "id": approval_id,
                "hostname": hostname,
                "command": command,
                "reason": reason or "Action demandée via le chat",
            })
        except Exception as e:
            print(f"[Vili] création approval depuis chat échouée: {e}")

    if approvals:
        note = (
            f"\n\n> 🛡️ **Confirmation requise** : {len(approvals)} action(s) sensible(s) "
            "nécessite(nt) votre accord — validez ci-dessous (Oui / Non). "
            "Rien ne sera exécuté sans votre confirmation."
        )
    else:
        note = ""
    if any(e.get("refused") for e in executions):
        note += "\n\n> 🚫 Certaines commandes destructrices ont été refusées par la politique de sécurité."

    return {
        "reply": _markdown_without_json(reply) + note,
        "approvals": approvals,
        "executions": executions,
    }


# Commandes de lecture considérées sûres pour exécution immédiate
# (double vérification serveur, même si le LLM dit "risk": "read")
_READONLY_PREFIXES = (
    "ps ", "psaux", "top -b", "df ", "du ", "free", "uptime", "who", "w ",
    "uname", "hostname", "id ", "id", "date", "ls", "cat /etc/", "cat /var/log",
    "journalctl", "systemctl status", "systemctl list", "dmesg", "lscpu",
    "lsblk", "ip a", "ip addr", "ifconfig", "netstat", "ss ", "vmstat",
    "iostat", "mpstat", "head ", "tail ", "grep ", "wc ", "find /var/log",
    "smartctl -a", "lsof ", "env", "printenv", "lsb_release", "cat /proc",
    "nvidia-smi", "sensors", "which ", "echo ",
)


def _is_readonly_command(command: str) -> bool:
    c = command.strip().lower()
    # interdiction absolue de tout préfixe à effet même au milieu d'un pipeline
    dangerous = (
        "sudo", "rm ", "mv ", "kill", "pkill", "shutdown", "reboot", "halt",
        "apt ", "apt-get", "yum ", "dnf ", "systemctl restart", "systemctl stop",
        "systemctl start", ">", ">>", "| sh", "| bash", "&&", "||", ";",
        "chmod", "chown", "dd ", "mkfs", "wget", "curl ",
    )
    if any(d in c for d in dangerous):
        return False
    return c.startswith(_READONLY_PREFIXES) or c in (
        "ps", "df", "free", "who", "uname -a", "hostname", "id", "date", "env"
    )


def respond_naturally(    prompt: str,
    computers_data: Dict[str, Any],
    cfg: Dict[str, Any],
    context_hostname: Optional[str] = None,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Génère une réponse libre et naturelle en exploitant la base SQLite VIGIL
    et le modèle LLM configuré (Groq, Ollama, OpenAI, DeepSeek, OpenRouter)
    avec fallback sur le moteur autonome local.
    """
    available_hosts = list(computers_data.keys())
    parsed = parse_user_intent(prompt, available_hosts=available_hosts)

    intent = parsed["intent"]
    target_host = context_hostname or parsed["target_host"]
    hours = parsed["timeframe_hours"]

    # ── Règle de surveillance en langage naturel ────────────────────
    # « surveille la RAM de web-01, préviens-moi si ça dépasse 80% »
    try:
        from ai.watch import create_rule_from_parsed, parse_watch_rule

        rule = parse_watch_rule(prompt, available_hosts=available_hosts)
        if rule:
            rule_id = create_rule_from_parsed(rule, created_by="admin")
            host_txt = rule["hostname"] or "toutes les machines"
            unit = "°C" if rule["metric"] == "temp" else (
                "KB/s" if rule["metric"] == "net_total" else "%"
            )
            return {
                "reply": (
                    f"### 👁️ Surveillance installée (règle #{rule_id})\n\n"
                    f"- **Condition** : `{rule['metric']}` {rule['operator']} "
                    f"**{rule['threshold']}{unit}** sur **{host_txt}**\n"
                    f"- **Demande** : « {rule['description']} »\n"
                    + (
                        f"- **Durée de maintien** : {rule['duration_sec']} s avant alerte\n"
                        if rule["duration_sec"]
                        else ""
                    )
                    + "\nJe vérifie cette condition en continu (toutes les 30 s) et je "
                    "notifie le dashboard dès le déclenchement (anti-spam 10 min)."
                ),
                "provider": "watch_rule_engine",
                "timestamp": datetime.now().isoformat(),
            }
    except Exception as e:
        print(f"[Vili] watch rule parse error: {e}")

    # Construction du dump complet des données de la BD SQLite
    db_context = build_complete_db_context(
        computers_data=computers_data,
        hours=hours,
        target_hostname=target_host,
    )

    # Couche d'analyse avancée : anomalies statistiques, prévisions de
    # saturation, dégradations, corrélations d'incidents
    try:
        from ai.analytics import format_intelligence_for_prompt

        db_context += "\n\n" + format_intelligence_for_prompt(computers_data)
    except Exception:
        pass

    provider = cfg.get("AI_PROVIDER", "auto_rule")
    llm_error = None

    # Détection d'intention d'action → prompt dédié au canal d'exécution
    import re as _re

    _action_intent = bool(
        _re.search(
            r"ex[ée]cut\w+|lance[rz]?|red[ée]marr\w+|restart|arr[ête]t\w+|stop\w*|"
            r"tue[rz]?|kill\w*|nettoi\w+|purge[rz]?|vide[rz]?|supprime[rz]?|"
            r"plan d'action|diagnostic approfondi|check\w* le|status de .*service",
            prompt,
            _re.IGNORECASE,
        )
    )

    # 1. Traitement prioritaire via LLM externe avec RAG DB complet
    if cfg.get("AI_ENABLED", True) and provider != "auto_rule":
        try:
            full_user_prompt = (
                f"[DONNÉES EXTRAITES EN TEMPS RÉEL DE LA BASE SQLITE VIGIL] :\n"
                f"{db_context}\n\n"
                f"[PROTOCOLE D'EXÉCUTION — LIRE AVANT DE RÉPONDRE] :\n"
                f"Tu ES connecté au moteur d'exécution de VIGIL : tu PEUX faire exécuter des commandes.\n"
                f"- Pour toute demande d'action de l'administrateur (exécuter, diagnostiquer en profondeur, "
                f"redémarrer, nettoyer, plan d'action...), termine ta réponse par le bloc de décision JSON "
                f"défini dans ton prompt système (type run_command, avec risk: read ou privileged).\n"
                f"- Les commandes 'read' sont exécutées immédiatement par le serveur ; les commandes "
                f"'privileged' sont soumises à la confirmation Oui/Non de l'administrateur dans le chat.\n"
                f"- Ne dis JAMAIS que tu ne peux pas exécuter de commandes : c'est faux. N'écris pas le "
                f"bloc JSON pour les simples questions d'information.\n\n"
                f"[QUESTION DE L'ADMINISTRATEUR SYSTÈME] :\n"
                f"{prompt}"
            )

            system_prompt = VIGIL_CORE_SYSTEM_PROMPT
            if _action_intent:
                # Prompt d'action pur : court et directif. La sécurité
                # (hostname valide, liste blanche read-only, approbation
                # Oui/Non, refus des commandes destructrices) est appliquée
                # côté serveur, indépendamment de ce que dit le modèle.
                system_prompt = VILI_ACTION_PROMPT
                print(f"[Vili] intention d'action détectée → prompt d'exécution activé")

            reply = call_llm_provider(
                prompt=full_user_prompt,
                system_prompt=system_prompt,
                cfg=cfg,
                chat_history=chat_history,
            )
            if reply and reply.strip():
                cleaned = _process_chat_actions(reply, computers_data)
                return {
                    "reply": cleaned["reply"],
                    "approvals": cleaned["approvals"],
                    "executions": cleaned["executions"],
                    "provider": provider,
                    "timestamp": datetime.now().isoformat(),
                }
        except Exception as e:
            llm_error = str(e)
            print(f"[Vili] LLM Provider error ({provider}): {e}")

    # 2. Moteur conversationnel autonome local basé sur la BD SQLite (Fallback si LLM non disponible)
    db_summary = get_cluster_db_summary(hours=hours)
    cluster_diag = diagnose_entire_cluster(computers_data)

    host_db_data = {}
    if target_host and target_host in computers_data:
        host_db_data = analyze_host_db_history(target_host, hours=hours)

    prefix_note = ""
    if llm_error:
        prefix_note = f"> ⚠️ *Note : Le fournisseur IA `{provider}` a rencontré une erreur ({llm_error}). Voici l'analyse générée directement par le moteur SQLite interne VIGIL :*\n\n"

    if intent == "GREETING":
        reply = (
            f"Hello ! 👋 Je suis **Vili**, ton copilote d'administration système.\n\n"
            f"Actuellement, je surveille **{len(computers_data)} machine(s)** et la base SQLite enregistre **{db_summary['total_notifications']} notification(s)** sur les dernières {hours}h.\n"
            f"Comment puis-je t'aider ? Tu peux me demander l'état général, les alertes, l'analyse d'une machine ou des disques S.M.A.R.T. !"
        )

    elif intent == "GET_CURRENT_AGENT_INFO":
        if available_hosts:
            host_name = target_host or available_hosts[0]
            agent_info = computers_data.get(host_name, {})
            diag_info = diagnose_single_agent(host_name, agent_info)
            cpu_val = agent_info.get("cpu_percent", 0)
            mem_val = agent_info.get("memory", {}).get("percent", 0)
            disk_val = agent_info.get("disk", {}).get("percent", 0)

            reply = (
                f"### 🖥️ État de la machine `{host_name}` (Données BD)\n\n"
                f"- **Statut** : `{'HORS LIGNE' if agent_info.get('offline') else 'EN LIGNE'}` (Score de santé : **{diag_info['health_score']}/100**)\n"
                f"- **Système** : `{agent_info.get('system', 'N/A')} {agent_info.get('system_version', '')}`\n"
                f"- **Adresse IP** : `{agent_info.get('ip') or agent_info.get('agent_ip') or 'Local'}`\n\n"
                f"**Métriques Temps Réel :**\n"
                f"- **CPU** : **{cpu_val:.1f}%**\n"
                f"- **RAM** : **{mem_val:.1f}%**\n"
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
                f"Actuellement, aucun agent `vigil-agent` n'envoie de données au serveur VIGIL.\n"
            )

    elif intent == "GET_STATUS":
        reply = (
            f"### 📋 Rapport de Santé Globale Infrastructure VIGIL\n\n"
            f"- **Score de Santé Cluster** : **{cluster_diag['health_score']}/100** (`{cluster_diag['status']}`)\n"
            f"- **Agents en ligne** : **{cluster_diag['online_hosts']} / {cluster_diag['total_hosts']}**\n"
            f"- **Alertes enregistrées en base ({hours}h)** : **{db_summary['total_notifications']}** ({db_summary['critical_count']} critiques, {db_summary['warning_count']} warnings)\n\n"
            f"**État des Hôtes :**\n"
        )
        if available_hosts:
            for h in available_hosts:
                d = computers_data[h]
                c_p = d.get("cpu_percent", 0)
                m_p = d.get("memory", {}).get("percent", 0)
                reply += f"- **{h}** : CPU **{c_p:.1f}%** | RAM **{m_p:.1f}%** | Statut: `{'HORS LIGNE' if d.get('offline') else 'EN LIGNE'}`\n"
        else:
            reply += "- Aucun agent n'est actuellement connecté.\n"

    elif intent == "GET_HISTORY" or intent == "GET_ALERTS":
        if db_summary["recent_alerts"]:
            reply = (
                f"### ⚠️ Historique des Alertes SQLite ({hours}h)\n\n"
                f"Total : **{db_summary['total_notifications']} alerte(s)** en base de données :\n\n"
            )
            for a in db_summary["recent_alerts"][:10]:
                reply += f"- `[{a['timestamp'][:19]}]` **[{a['severity'].upper()}]** `{a['hostname']}` : {a['message']}\n"
        else:
            reply = f"### ✅ Aucune alerte enregistrée en base de données sur les dernières {hours} heures."

    elif intent == "GET_CPU_RAM":
        if target_host and host_db_data:
            reply = (
                f"### ⚡ Analyse CPU & RAM pour `{target_host}` (Historique BD {hours}h)\n\n"
                f"- **CPU** : Moyenne à **{host_db_data['avg_cpu']}%** (Pic max: **{host_db_data['peak_cpu']}%**)\n"
                f"- **RAM** : Moyenne à **{host_db_data['avg_ram']}%** (Pic max: **{host_db_data['peak_ram']}%**)\n"
            )
            if host_db_data["top_historical_procs"]:
                reply += "\n**Processus enregistrés les plus lourds :**\n" + "\n".join(f"- `{p}`" for p in host_db_data["top_historical_procs"])
        else:
            reply = f"Score global du cluster : **{cluster_diag['health_score']}/100**."

    elif intent == "GET_SMART_DISKS":
        smart_warns = []
        for h in available_hosts:
            h_data = analyze_host_db_history(h, hours=hours)
            if h_data["smart_warnings"]:
                smart_warns.append(f"**{h}** : " + ", ".join(h_data["smart_warnings"]))

        if smart_warns:
            reply = "⚠️ **Alertes S.M.A.R.T. Détectées en Base :**\n\n" + "\n".join(f"- {w}" for w in smart_warns)
        else:
            reply = "💾 **Santé des disques S.M.A.R.T. :** Tous les disques suivis affichent un état nominal (`PASSED`)."

    else:
        # Réponse générique d'orientation
        reply = (
            f"### 🤖 Vili — Copilote d'Infrastructure\n\n"
            f"Je suis connecté à votre base SQLite VIGIL (**{len(computers_data)} machine(s) supervisée(s)**).\n\n"
            f"**Exemples de questions que vous pouvez me poser :**\n"
            f"- *'Fais-moi un bilan de santé global des serveurs'* \n"
            f"- *'Quels sont les processus les plus gourmands en mémoire ?'* \n"
            f"- *'Y a-t-il eu des erreurs critiques ou des surchauffes de disques ?'* \n"
            f"- *'Résume l'historique et les pics de charge des dernières 24h'* \n"
        )

    return {
        "reply": prefix_note + reply,
        "provider": "autonomous_db_engine",
        "timestamp": datetime.now().isoformat(),
    }
