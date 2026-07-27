"""
VIGIL AI — SQLite Database Analytics & Metrics Trend Module
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from db.storage import query_history, query_notifications, count_notifications


def analyze_host_db_history(hostname: str, hours: int = 24) -> Dict[str, Any]:
    """Analyse l'historique SQLite des métriques pour un hôte spécifié."""
    since_iso = (datetime.now() - timedelta(hours=hours)).isoformat()
    rows = query_history(hostname, since_iso=since_iso, limit=1000)

    if not rows:
        return {
            "hostname": hostname,
            "sample_count": 0,
            "summary": f"Aucun historique SQLite trouvé pour {hostname} sur les {hours} derniers heures.",
            "avg_cpu": 0,
            "peak_cpu": 0,
            "avg_ram": 0,
            "peak_ram": 0,
            "smart_warnings": [],
            "top_historical_procs": [],
        }

    cpus, rams, disks = [], [], []
    proc_counter = {}
    smart_warnings = []

    for r in rows:
        data = r.get("data", {})
        if "cpu_percent" in data:
            cpus.append(data["cpu_percent"])
        if "memory" in data and "percent" in data["memory"]:
            rams.append(data["memory"]["percent"])
        if "disk" in data and "percent" in data["disk"]:
            disks.append(data["disk"]["percent"])

        # Analyse des processus enregistrés dans l'historique
        for p in data.get("processes", []):
            p_name = p.get("name")
            p_cpu = p.get("cpu_percent", 0)
            if p_name and p_cpu > 15:
                proc_counter[p_name] = proc_counter.get(p_name, 0) + 1

        # Analyse SMART historique
        smart = data.get("smart", {})
        for d in smart.get("disks", []) if isinstance(smart, dict) else []:
            if d.get("health") in ["FAILED", "WARNING"]:
                msg = f"Disque {d.get('device')} ({d.get('health')})"
                if msg not in smart_warnings:
                    smart_warnings.append(msg)

    avg_cpu = sum(cpus) / len(cpus) if cpus else 0
    peak_cpu = max(cpus) if cpus else 0
    avg_ram = sum(rams) / len(rams) if rams else 0
    peak_ram = max(rams) if rams else 0
    max_disk = max(disks) if disks else 0

    sorted_procs = sorted(proc_counter.items(), key=lambda x: x[1], reverse=True)
    top_procs = [f"{name} ({cnt} pics >15% CPU)" for name, cnt in sorted_procs[:5]]

    return {
        "hostname": hostname,
        "sample_count": len(rows),
        "period_hours": hours,
        "avg_cpu": round(avg_cpu, 1),
        "peak_cpu": round(peak_cpu, 1),
        "avg_ram": round(avg_ram, 1),
        "peak_ram": round(peak_ram, 1),
        "max_disk": round(max_disk, 1),
        "smart_warnings": smart_warnings,
        "top_historical_procs": top_procs,
    }


def get_cluster_db_summary(hours: int = 24) -> Dict[str, Any]:
    """Synthèse des alertes et événements enregistrés en base SQLite."""
    since_iso = (datetime.now() - timedelta(hours=hours)).isoformat()
    notifs = query_notifications(since_iso=since_iso, limit=200)

    critical_count = count_notifications(since_iso=since_iso, severity="critical")
    warning_count = count_notifications(since_iso=since_iso, severity="warning")

    recent_alerts = []
    for n in notifs[:10]:
        recent_alerts.append(f"[{n['timestamp'][:16]}] ({n.get('hostname','Cluster')}) {n.get('message')}")

    return {
        "period_hours": hours,
        "total_notifications": len(notifs),
        "critical_count": critical_count,
        "warning_count": warning_count,
        "recent_alerts": recent_alerts,
    }
