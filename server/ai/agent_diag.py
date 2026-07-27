"""
VIGIL AI — Agent Machine Diagnostic Module
"""

from typing import Any, Dict
from ai.db_analytics import analyze_host_db_history


def diagnose_single_agent(hostname: str, agent_live_data: Dict[str, Any]) -> Dict[str, Any]:
    """Combine les métriques live et l'historique de la base SQLite pour diagnostiquer l'agent."""
    db_history = analyze_host_db_history(hostname, hours=24)

    issues, recommendations, warnings = [], [], []
    score = 100

    if not agent_live_data or agent_live_data.get("offline", False):
        return {
            "hostname": hostname,
            "health_score": 0,
            "status": "OFFLINE",
            "summary": f"L'agent {hostname} est HORS LIGNE (déconnecté).",
            "issues": ["Agent déconnecté ou service arrêté"],
            "recommendations": ["Relancer vigil-agent et tester le ping network."],
            "db_history": db_history,
        }

    cpu_live = agent_live_data.get("cpu_percent", 0)
    ram_live = agent_live_data.get("memory", {}).get("percent", 0)
    disk_live = agent_live_data.get("disk", {}).get("percent", 0)

    # Analyse CPU (Live + Pics 24h)
    if cpu_live >= 90:
        issues.append(f"CPU en surchauffe critique ({cpu_live:.1f}%)")
        score -= 25
    elif db_history["peak_cpu"] >= 90:
        warnings.append(f"Pics CPU récurrents enregistrés en base ({db_history['peak_cpu']}% sur 24h)")
        score -= 10

    # Analyse RAM
    if ram_live >= 90:
        issues.append(f"Mémoire RAM saturée ({ram_live:.1f}%)")
        score -= 25
    elif db_history["avg_ram"] >= 80:
        warnings.append(f"Charge RAM élevée en continu (Moyenne 24h: {db_history['avg_ram']}%)")
        score -= 10

    # Analyse Disque
    if disk_live >= 90:
        issues.append(f"Espace disque saturé ({disk_live:.1f}%)")
        score -= 20
        recommendations.append("Nettoyer les journaux (/var/log ou %TEMP%) et purger les packages obsolètes.")

    # Analyse SMART
    smart_warns = db_history.get("smart_warnings", [])
    if smart_warns:
        issues.extend(smart_warns)
        score -= 30
        recommendations.append("Sauvegarder immédiatement les données et remplacer les disques défaillants.")

    score = max(0, score)
    status = "HEALTHY" if score >= 80 else ("WARNING" if score >= 50 else "CRITICAL")

    summary = (
        f"Diagnostic de {hostname} : État {status} (Score de santé BD: {score}/100). "
        f"Moyenne CPU 24h: {db_history['avg_cpu']}%, Pic: {db_history['peak_cpu']}%. "
        f"Moyenne RAM 24h: {db_history['avg_ram']}%."
    )

    return {
        "hostname": hostname,
        "health_score": score,
        "status": status,
        "summary": summary,
        "issues": issues,
        "warnings": warnings,
        "recommendations": recommendations,
        "db_history": db_history,
    }
