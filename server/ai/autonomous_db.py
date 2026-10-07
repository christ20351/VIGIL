"""
Vili — Persistance des rapports et actions de l'IA autonome
(Fonctionne sur SQLite comme sur PostgreSQL via db.storage)
"""

import json
from datetime import datetime
from typing import Any, Dict, List

from db import storage


def save_autonomous_ai_report(
    hostname: str, title: str, severity: str, summary: str, details: Dict[str, Any]
) -> int:
    """Enregistre un rapport de diagnostic autonome généré par l'IA en tâche de fond."""
    return storage.insert_returning_id(
        "INSERT INTO ai_diagnostics (hostname, ts, title, severity, summary, details_json, resolved)"
        " VALUES (?, ?, ?, ?, ?, ?, 0)",
        (hostname, datetime.now().isoformat(), title, severity, summary,
         json.dumps(details, ensure_ascii=False)),
    )


def query_autonomous_ai_reports(limit: int = 50, unresolved_only: bool = False) -> List[Dict[str, Any]]:
    """Récupère les derniers rapports autonomes générés par l'IA."""
    sql = "SELECT id, hostname, ts, title, severity, summary, details_json, resolved FROM ai_diagnostics"
    if unresolved_only:
        sql += " WHERE resolved = 0"
    sql += " ORDER BY ts DESC LIMIT ?"
    rows = storage.fetch_all(sql, (limit,))

    res = []
    for r in rows:
        try:
            details = json.loads(r["details_json"]) if r["details_json"] else {}
        except Exception:
            details = {}
        if not isinstance(details, dict):
            details = {}
        res.append({
            "id": r["id"],
            "hostname": r["hostname"],
            "timestamp": r["ts"],
            "title": r["title"],
            "severity": r["severity"],
            "summary": r["summary"],
            "details": details,
            "resolved": bool(r["resolved"]),
        })
    return res


def mark_ai_report_resolved(report_id: int) -> bool:
    """Marque une fiche d'incident IA comme acquittée/résolue."""
    return storage.execute_write(
        "UPDATE ai_diagnostics SET resolved = 1 WHERE id = ?", (report_id,)
    ) > 0
