"""
VIGIL AI — SQLite Database Analytics & Complete Context Builder Module
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from db.storage import query_history, query_notifications, count_notifications
from ai.autonomous_db import query_autonomous_ai_reports


def analyze_host_db_history(hostname: str, hours: int = 24) -> Dict[str, Any]:
    """Analyse l'historique SQLite des métriques pour un hôte spécifié."""
    since_iso = (datetime.now() - timedelta(hours=hours)).isoformat()
    rows = query_history(hostname, since_iso=since_iso, limit=1000)

    if not rows:
        return {
            "hostname": hostname,
            "sample_count": 0,
            "summary": f"Aucun historique SQLite trouvé pour {hostname} sur les {hours} dernières heures.",
            "avg_cpu": 0,
            "peak_cpu": 0,
            "avg_ram": 0,
            "peak_ram": 0,
            "max_disk": 0,
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
                msg = f"Disque {d.get('disk') or d.get('device')} ({d.get('health')})"
                if msg not in smart_warnings:
                    smart_warnings.append(msg)

    avg_cpu = sum(cpus) / len(cpus) if cpus else 0
    peak_cpu = max(cpus) if cpus else 0
    avg_ram = sum(rams) / len(rams) if rams else 0
    peak_ram = max(rams) if rams else 0
    max_disk = max(disks) if disks else 0

    sorted_procs = sorted(proc_counter.items(), key=lambda x: x[1], reverse=True)
    top_procs = [f"{name} ({cnt} pics >15% CPU)" for name, cnt in sorted_procs[:7]]

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
    error_count = count_notifications(since_iso=since_iso, severity="error")

    recent_alerts = []
    for n in notifs[:25]:
        recent_alerts.append({
            "timestamp": n.get("timestamp"),
            "hostname": n.get("hostname") or "Cluster",
            "severity": n.get("severity", "info"),
            "message": n.get("message"),
        })

    return {
        "period_hours": hours,
        "total_notifications": len(notifs),
        "critical_count": critical_count,
        "error_count": error_count,
        "warning_count": warning_count,
        "recent_alerts": recent_alerts,
    }


def build_complete_db_context(
    computers_data: Dict[str, Any],
    hours: int = 24,
    target_hostname: Optional[str] = None,
) -> str:
    """
    Construit un rapport textuel complet et structuré de la base de données VIGIL
    (état temps réel + historique SQLite + alertes + SMART + incidents IA autonomes).
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cluster_summary = get_cluster_db_summary(hours=hours)
    autonomous_reports = query_autonomous_ai_reports(limit=10, unresolved_only=False)

    lines = []
    lines.append(f"=== DONNÉES DE LA BASE DE DONNÉES VIGIL (Date/Heure serveur: {now_str}) ===")
    lines.append(f"Période d'analyse historique: {hours} dernières heures\n")

    # 1. Hôtes supervisés et statut actuel
    lines.append("## 1. ÉTAT DES MACHINES SUPERVISÉES (TEMPS RÉEL)")
    if not computers_data:
        lines.append("- Aucun agent actuellement connecté au serveur VIGIL.")
    else:
        for host, data in computers_data.items():
            offline = data.get("offline", False)
            status_str = "HORS LIGNE" if offline else "EN LIGNE"
            ip = data.get("ip") or data.get("agent_ip") or "Inconnue"
            os_info = f"{data.get('system', '')} {data.get('system_version', '')} ({data.get('architecture', '')})".strip()
            cpu = data.get("cpu_percent", 0)
            mem = data.get("memory", {})
            mem_pct = mem.get("percent", 0)
            mem_used_gb = round(mem.get("used", 0) / 1e9, 2)
            mem_tot_gb = round(mem.get("total", 0) / 1e9, 2)
            disk = data.get("disk", {})
            disk_pct = disk.get("percent", 0)
            disk_used_gb = round(disk.get("used", 0) / 1e9, 1)
            disk_tot_gb = round(disk.get("total", 0) / 1e9, 1)
            net = data.get("network", {})
            net_recv = round(net.get("bytes_recv_per_sec", 0) / 1024, 1)
            net_sent = round(net.get("bytes_sent_per_sec", 0) / 1024, 1)
            tcp_conn = data.get("protocols", {}).get("tcp", {}).get("established", 0)

            lines.append(f"### Machine: {host} [{status_str}]")
            lines.append(f"- Système: {os_info} | IP: {ip} | Dernière MAJ: {data.get('timestamp') or data.get('last_seen', 'N/A')}")
            if offline and data.get("offline_since"):
                lines.append(f"- Déconnecté depuis: {data.get('offline_since')}")
            lines.append(f"- CPU: {cpu:.1f}% | RAM: {mem_pct:.1f}% ({mem_used_gb} GB / {mem_tot_gb} GB) | Disque: {disk_pct:.1f}% ({disk_used_gb} GB / {disk_tot_gb} GB)")
            lines.append(f"- Réseau: RX={net_recv} KB/s, TX={net_sent} KB/s | Connexions TCP actives: {tcp_conn}")

            # Données S.M.A.R.T.
            smart = data.get("smart", {})
            if isinstance(smart, dict) and smart.get("available"):
                disks_info = []
                for d in smart.get("disks", []):
                    disks_info.append(f"{d.get('disk')}: Santé={d.get('health', 'N/A')}, Temp={d.get('temperature', 'N/A')}°C")
                lines.append(f"- S.M.A.R.T. Disques: {', '.join(disks_info) if disks_info else 'Aucun disque S.M.A.R.T.'}")
                if smart.get("alerts"):
                    smart_alerts = [f"[{a.get('level')}] {a.get('disk')}: {a.get('message')}" for a in smart.get("alerts", [])]
                    lines.append(f"  * Alertes S.M.A.R.T.: {'; '.join(smart_alerts)}")

            # Processus les plus gourmands en mémoire et CPU
            procs = data.get("processes", [])
            if procs:
                top_procs = sorted(procs, key=lambda p: (p.get("cpu_percent", 0) + p.get("memory_percent", 0)), reverse=True)[:6]
                proc_str_list = [f"{p.get('name')} (CPU {p.get('cpu_percent', 0):.1f}%, RAM {p.get('memory_percent', 0):.1f}%, RSS {round(p.get('memory_rss', 0)/1e6, 1)}MB)" for p in top_procs]
                lines.append(f"- Top Processus Actifs: {'; '.join(proc_str_list)}")

            # Analyse historique de cette machine
            h_data = analyze_host_db_history(host, hours=hours)
            lines.append(f"- Historique BD {hours}h: CPU moy={h_data['avg_cpu']}%, Pic CPU={h_data['peak_cpu']}% | RAM moy={h_data['avg_ram']}%, Pic RAM={h_data['peak_ram']}%")
            if h_data["top_historical_procs"]:
                lines.append(f"  * Processus ayant causé des pics historiques: {', '.join(h_data['top_historical_procs'])}")
            if h_data["smart_warnings"]:
                lines.append(f"  * Avertissements SMART historiques: {', '.join(h_data['smart_warnings'])}")
            lines.append("")

    # 2. Alertes et Notifications SQLite
    lines.append(f"## 2. HISTORIQUE DES NOTIFICATIONS ET ALERTES BD (Table `notifications`, {hours}h)")
    lines.append(f"- Total alertes enregistrées: {cluster_summary['total_notifications']} (Critiques: {cluster_summary['critical_count']}, Erreurs: {cluster_summary['error_count']}, Avertissements: {cluster_summary['warning_count']})")
    if cluster_summary["recent_alerts"]:
        lines.append("Dernières alertes enregistrées :")
        for alt in cluster_summary["recent_alerts"]:
            lines.append(f"  - [{alt['timestamp']}] [{alt['severity'].upper()}] ({alt['hostname']}) : {alt['message']}")
    else:
        lines.append("  - Aucune alerte enregistrée en base sur cette période.")
    lines.append("")

    # 3. Rapports d'incidents autonomes IA
    lines.append("## 3. RAPPORTS D'INCIDENTS IA AUTONOMES (Table `ai_diagnostics`)")
    if autonomous_reports:
        for r in autonomous_reports[:5]:
            status = "RÉSOLU" if r["resolved"] else "ACTIF / NON RÉSOLU"
            lines.append(f"- [{r['timestamp']}] [{r['severity'].upper()}] ({r['hostname']}) {r['title']} [{status}] : {r['summary']}")
    else:
        lines.append("- Aucun rapport d'incident autonome en base de données.")

    return "\n".join(lines)
