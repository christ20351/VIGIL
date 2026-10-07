"""
Vili — Règles de surveillance en langage naturel (« watch rules »).

L'admin (ou Vili lui-même) peut demander :
  « surveille la RAM de web-01 et préviens-moi si ça dépasse 80 % »
La règle est traduite en condition structurée, persistée en base, puis
évaluée en continu par la boucle rapide de Vili — notifications internes
sur le dashboard avec cooldown anti-spam.
"""

import re
import time
from typing import Any, Dict, List, Optional

import config
from db import storage

# état de satisfaction de durée par règle : {rule_id: (depuis_mono, last_fired_mono)}
_rule_state: Dict[int, Dict[str, float]] = {}

_METRIC_PATTERNS = [
    # (regex, metric, libellé)
    (r"\b(cpu|processeur|proco)\b", "cpu", "CPU"),
    (r"\b(ram|m[ée]moire|memory)\b", "ram", "RAM"),
    (r"\b(disque|dis k|disk|stockage)\b", "disk", "Disque"),
    (r"\b(r[ée]seau|network|bande passante|trafic)\b", "net_total", "Réseau"),
    (r"\b(temp[ée]rature|temperature)\b", "temp", "Température"),
]

_HOST_PATTERNS = [
    r"(?:sur|de|de la machine|pour|host|h[ôo]te)\s+([A-Za-z0-9_.\-]+)",
    r"([A-Za-z0-9_.\-]+)\s+(?:d[ée]passe|depasse|exc[èe]de|monte)",
]


def parse_watch_rule(text: str, available_hosts: List[str] = None) -> Optional[Dict[str, Any]]:
    """
    Extrait une règle de surveillance d'une phrase en français/anglais.
    Retourne {description, metric, operator, threshold, hostname, duration_sec}
    ou None si la phrase n'exprime pas de règle surveillable.
    """
    if not text:
        return None
    t = text.lower()
    if not re.search(r"surveill|pr[ée]viens|previens|alerte|notifie|watch|monitor|pr[ée]vient", t):
        return None

    # métrique
    metric = label = None
    for pattern, m, lab in _METRIC_PATTERNS:
        if re.search(pattern, t):
            metric, label = m, lab
            break
    if not metric:
        return None

    # seuil (%, Ko/s, °C) — priorité au nombre portant une unité
    # (« 80 % », « 50 degrés », « 200 kb/s »), sinon le dernier nombre
    # (évite de confondre avec « web-01 »)
    unit = ""
    m = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(%|po[u]?rcent|degr[ée]s?|°|kb/s|kbps|mo/s|mb/s|gb/s)",
        t,
    )
    if not m:
        candidates = re.findall(r"(\d+(?:[.,]\d+)?)", t)
        if not candidates:
            return None
        threshold = float(candidates[-1].replace(",", "."))
    else:
        threshold = float(m.group(1).replace(",", "."))
        unit = m.group(2)

    # opérateur
    if re.search(r"d[ée]passe|depasse|sup[ée]rieur|above|plus de|exc[èe]de|monte", t):
        operator = ">"
    elif re.search(r"inf[ée]rieur|below|moins de|descend", t):
        operator = "<"
    else:
        operator = ">"

    # hôte ciblé (doit exister parmi les agents connus)
    hostname = None
    for pat in _HOST_PATTERNS:
        for cand in re.findall(pat, t):
            cand = cand.strip(" .,;:!'\"")
            if available_hosts and cand in available_hosts:
                hostname = cand
                break
            # préfixe : « web » correspond à « web-01 »
            if available_hosts:
                matches = [h for h in available_hosts if h.lower().startswith(cand.lower()) and len(cand) >= 3]
                if len(matches) == 1:
                    hostname = matches[0]
                    break
        if hostname:
            break

    # durée de maintien (« pendant 5 minutes »)
    duration_sec = 0
    dm = re.search(r"pendant\s+(\d+)\s*(min|minute|s|sec|seconde)", t)
    if dm:
        duration_sec = int(dm.group(1)) * (60 if dm.group(2).startswith("min") else 1)

    if metric == "net_total":
        u = (unit or "").lower()
        if u in ("mo/s", "mb/s", "gb/s"):
            threshold *= 1024.0 * (1024.0 if u == "gb/s" else 1.0)
    if metric == "cpu" and threshold <= 1.0 and unit:
        threshold *= 100.0

    return {
        "description": text.strip()[:200],
        "metric": metric,
        "metric_label": label,
        "operator": operator,
        "threshold": threshold,
        "hostname": hostname,  # None = toutes les machines
        "duration_sec": duration_sec,
    }


def _live_value(metric: str, data: Dict[str, Any]) -> Optional[float]:
    """Valeur live d'une métrique pour un hôte."""
    try:
        if metric == "cpu":
            return data.get("cpu_percent")
        if metric == "ram":
            return (data.get("memory") or {}).get("percent")
        if metric == "disk":
            return (data.get("disk") or {}).get("percent")
        if metric == "net_total":
            net = data.get("network") or {}
            return (net.get("bytes_recv_per_sec", 0) + net.get("bytes_sent_per_sec", 0)) / 1024.0
        if metric == "temp":
            # température max parmi les disques SMART
            smart = data.get("smart") or {}
            temps = [
                d.get("temperature")
                for d in smart.get("disks", [])
                if isinstance(d.get("temperature"), (int, float))
            ]
            return max(temps) if temps else None
    except Exception:
        return None
    return None


def evaluate_watch_rules(computers_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Évalue toutes les règles actives contre les données live.
    Notifie le dashboard pour chaque règle déclenchée (cooldown par règle).
    Retourne la liste des déclenchements.
    """
    from websocket_handler import notify_dashboard_sync

    cooldown = int(getattr(config, "WATCH_RULE_COOLDOWN", 600) or 600)
    now = time.monotonic()
    fired: List[Dict[str, Any]] = []

    try:
        rules = storage.list_watch_rules(active_only=True)
    except Exception:
        return []

    for rule in rules:
        rid = rule["id"]
        targets = []
        if rule.get("hostname"):
            if rule["hostname"] in computers_data:
                targets = [(rule["hostname"], computers_data[rule["hostname"]])]
        else:
            targets = [(h, d) for h, d in computers_data.items() if isinstance(d, dict) and not d.get("offline")]

        for host, data in targets:
            value = _live_value(rule["metric"], data)
            if value is None:
                continue

            ok = value > rule["threshold"] if rule["operator"] == ">" else value < rule["threshold"]
            state = _rule_state.setdefault(rid, {"since": 0.0, "fired": 0.0})

            if not ok:
                state["since"] = 0.0
                continue

            # durée de maintien exigée
            if rule.get("duration_sec") and rule["duration_sec"] > 0:
                if state["since"] == 0.0:
                    state["since"] = now
                    continue
                if now - state["since"] < rule["duration_sec"]:
                    continue

            if now - state["fired"] < cooldown:
                continue  # déjà notifié récemment

            state["fired"] = now
            state["since"] = 0.0
            unit = "°C" if rule["metric"] == "temp" else ("KB/s" if rule["metric"] == "net_total" else "%")
            message = (
                f"👁️ Règle « {rule['description'][:80]} » déclenchée : "
                f"{rule.get('metric', rule['metric'])} de {host} à "
                f"{value:.1f}{unit} ({rule['operator']} {rule['threshold']}{unit})"
            )
            notify_dashboard_sync(host, message, "warning")
            try:
                storage.set_watch_rule_fired(rid)
            except Exception:
                pass
            fired.append({"rule_id": rid, "hostname": host, "value": value})

    return fired


def create_rule_from_parsed(parsed: Dict[str, Any], created_by: str = "admin") -> int:
    """Persiste une règle issue du parseur (ou de Vili)."""
    return storage.insert_watch_rule(
        description=parsed["description"],
        metric=parsed["metric"],
        operator=parsed["operator"],
        threshold=parsed["threshold"],
        hostname=parsed.get("hostname"),
        duration_sec=parsed.get("duration_sec") or 0,
        created_by=created_by,
    )


def format_watch_rules_for_prompt() -> str:
    """Liste les règles actives pour le contexte de Vili."""
    try:
        rules = storage.list_watch_rules(active_only=True)
    except Exception:
        return ""
    if not rules:
        return ""
    lines = ["### RÈGLES DE SURVEILLANCE ACTIVES (demandées par l'admin)"]
    for r in rules:
        host = r.get("hostname") or "toutes les machines"
        lines.append(
            f"- [{r['id']}] {r['metric']} {r['operator']} {r['threshold']} sur {host}"
            f" — « {r['description'][:70]} »"
            + (f" (dernier déclenchement: {r['last_fired'][:19]})" if r.get("last_fired") else "")
        )
    return "\n".join(lines)
