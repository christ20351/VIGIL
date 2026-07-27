"""
VIGIL AI — Natural Language Intent & Entity Classifier (< 90 lines)
"""

import re
from typing import Any, Dict, List, Optional


def parse_user_intent(prompt: str, available_hosts: List[str] = None) -> Dict[str, Any]:
    """Analyse une phrase en langage naturel français et extrait l'intention et les entités (hôtes, temps)."""
    p_low = prompt.lower().strip()
    available_hosts = available_hosts or []

    # 1. Extraction d'un hôte ciblé si mentionné dans la phrase
    target_host = None
    for h in available_hosts:
        if h.lower() in p_low:
            target_host = h
            break

    # 2. Extraction du timeframe (heures)
    timeframe_hours = 24
    if any(w in p_low for w in ["hier", "nuit", "24h", "24 h", "journée"]):
        timeframe_hours = 24
    elif any(w in p_low for w in ["dernière heure", "1h", "1 h"]):
        timeframe_hours = 1
    elif any(w in p_low for w in ["4h", "4 h"]):
        timeframe_hours = 4

    # 3. Classification de l'intention
    if any(w in p_low for w in ["salut", "bonjour", "cc", "coucou", "qui es tu", "hello"]):
        intent = "GREETING"
    elif any(w in p_low for w in ["ce qui se passe", "qu'est ce qui ce passe", "que se passe", "agent actu", "machine actu", "actuellement", "qu'est ce qu'il a", "que fait", "mon agent"]):
        intent = "GET_CURRENT_AGENT_INFO"
    elif any(w in p_low for w in ["historique", "base", "sqlite", "hier", "passé", "tendance"]):
        intent = "GET_HISTORY"
    elif any(w in p_low for w in ["alerte", "notification", "critique", "incident", "warning", "problème", "panne"]):
        intent = "GET_ALERTS"
    elif any(w in p_low for w in ["cpu", "ram", "mémoire", "memoire", "charge", "pic", "processus", "rame", "ralenti"]):
        intent = "GET_CPU_RAM"
    elif any(w in p_low for w in ["disque", "smart", "panne", "stockage", "température", "disk", "sda", "sdb"]):
        intent = "GET_SMART_DISKS"
    elif any(w in p_low for w in ["statut", "etat", "état", "santé", "sante", "resume", "résumé", "rapport", "health"]):
        intent = "GET_STATUS"
    else:
        intent = "SYSADMIN_ADVICE"

    return {
        "intent": intent,
        "target_host": target_host,
        "timeframe_hours": timeframe_hours,
        "raw_prompt": prompt,
    }
