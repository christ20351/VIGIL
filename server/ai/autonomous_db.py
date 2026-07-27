"""
VIGIL AI — SQLite Persistence for Autonomous AI Diagnostic Reports (< 80 lines)
"""

import json
from datetime import datetime
from typing import Any, Dict, List
from db.storage import _conn, _lock


def save_autonomous_ai_report(
    hostname: str, title: str, severity: str, summary: str, details: Dict[str, Any]
) -> int:
    """Enregistre un rapport de diagnostic autonome généré par l'IA en tâche de fond."""
    with _lock:
        c = _conn.cursor()
        c.execute(
            """
            INSERT INTO ai_diagnostics (hostname, ts, title, severity, summary, details_json, resolved)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (hostname, datetime.now().isoformat(), title, severity, summary, json.dumps(details, ensure_ascii=False)),
        )
        _conn.commit()
        return c.lastrowid


def query_autonomous_ai_reports(limit: int = 50, unresolved_only: bool = False) -> List[Dict[str, Any]]:
    """Récupère les derniers rapports autonomes générés par l'IA."""
    with _lock:
        c = _conn.cursor()
        sql = "SELECT id, hostname, ts, title, severity, summary, details_json, resolved FROM ai_diagnostics"
        if unresolved_only:
            sql += " WHERE resolved = 0"
        sql += " ORDER BY ts DESC LIMIT ?"
        c.execute(sql, (limit,))
        rows = c.fetchall()

    res = []
    for r in rows:
        try:
            details = json.loads(r["details_json"])
        except Exception:
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
    with _lock:
        c = _conn.cursor()
        c.execute("UPDATE ai_diagnostics SET resolved = 1 WHERE id = ?", (report_id,))
        _conn.commit()
        return c.rowcount > 0
