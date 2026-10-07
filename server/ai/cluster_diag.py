"""
VIGIL AI — Infrastructure Cluster Overview & Health Scoring Module
"""

from typing import Any, Dict
from ai.agent_diag import diagnose_single_agent
from ai.db_analytics import get_cluster_db_summary


def diagnose_entire_cluster(computers_data: Dict[str, Any]) -> Dict[str, Any]:
    """Synthétise l'état global du cluster avec l'historique d'alertes en base."""
    db_alerts = get_cluster_db_summary(hours=24)
    total_hosts = len(computers_data)

    if total_hosts == 0:
        return {
            "health_score": 100,
            "status": "NO_AGENTS",
            "summary": "Aucun agent actuellement connecté au serveur VIGIL.",
            "total_hosts": 0,
            "online_hosts": 0,
            "offline_hosts": 0,
            "critical_hosts": [],
            "db_alerts": db_alerts,
        }

    online_hosts, offline_hosts = 0, 0
    critical_hosts, warning_hosts = [], []
    host_diagnostics = []

    for host, data in computers_data.items():
        diag = diagnose_single_agent(host, data)
        if data.get("offline", False):
            offline_hosts += 1
        else:
            online_hosts += 1

        if diag["status"] == "CRITICAL":
            critical_hosts.append(host)
        elif diag["status"] == "WARNING":
            warning_hosts.append(host)

        host_diagnostics.append(diag)

    # Calcul du score global de santé
    penalty = (offline_hosts * 25) + (len(critical_hosts) * 20) + (len(warning_hosts) * 10) + (db_alerts["critical_count"] * 5)
    overall_score = max(0, 100 - penalty)
    status = "HEALTHY" if overall_score >= 80 else ("WARNING" if overall_score >= 50 else "CRITICAL")

    recommendations = []
    if offline_hosts > 0:
        recommendations.append(f"{offline_hosts} machine(s) sont déconnectées du serveur VIGIL.")
    if critical_hosts:
        recommendations.append(f"Intervention requise d'urgence sur : {', '.join(critical_hosts)}.")
    if db_alerts["critical_count"] > 0:
        recommendations.append(f"{db_alerts['critical_count']} alerte(s) critique(s) ont été enregistrées en base ces dernières 24h.")
    if not recommendations:
        recommendations.append("Cluster stable et performant.")

    summary = (
        f"Cluster VIGIL ({total_hosts} machine(s)) : {online_hosts} en ligne, {offline_hosts} hors ligne. "
        f"État global: {status} (Score de santé: {overall_score}/100). "
        f"Notifications 24h: {db_alerts['total_notifications']} ({db_alerts['critical_count']} critiques)."
    )

    return {
        "health_score": overall_score,
        "status": status,
        "summary": summary,
        "total_hosts": total_hosts,
        "online_hosts": online_hosts,
        "offline_hosts": offline_hosts,
        "critical_hosts": critical_hosts,
        "warning_hosts": warning_hosts,
        "recommendations": recommendations,
        "db_alerts": db_alerts,
        "host_diagnostics": host_diagnostics,
    }
