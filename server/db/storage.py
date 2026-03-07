"""
SQLite storage for historical metrics
"""

import json
import os
import sqlite3
import sys
import threading
from datetime import datetime, timedelta


def _get_db_path() -> str:
    """
    Retourne le chemin absolu de metrics.db selon le contexte :
    - Binaire PyInstaller → dossier du .exe  (sys.executable)
    - Script Python normal → dossier db/ à côté de storage.py
    """
    if getattr(sys, "frozen", False):
        # Binaire PyInstaller → à côté du .exe
        base = os.path.dirname(sys.executable)
    else:
        # Dev classique → dans le dossier db/
        base = os.path.dirname(__file__)

    # Créer le dossier si besoin (cas binaire où db/ n'existe pas encore)
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "metrics.db")


DB_PATH = _get_db_path()

# connexion partagée (check_same_thread=False car nous écrivons depuis différents threads)
_conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
_conn.row_factory = sqlite3.Row

# Optimisation SQLite pour meilleures performances
_conn.execute("PRAGMA journal_mode=WAL")
_conn.execute("PRAGMA synchronous=NORMAL")
_conn.execute("PRAGMA cache_size=10000")
_conn.execute("PRAGMA temp_store=MEMORY")
_conn.execute("PRAGMA query_only=OFF")
_conn.commit()

_lock = threading.Lock()


def init_db():
    """Crée les tables nécessaires si elles n'existent pas."""
    with _lock:
        c = _conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hostname TEXT NOT NULL,
                ts TEXT NOT NULL,
                data TEXT NOT NULL
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_host_ts ON metrics(hostname, ts)"
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hostname TEXT,
                ts TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_notifications_ts ON notifications(ts)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_notifications_host_ts ON notifications(hostname, ts)"
        )
        _conn.commit()


def insert_metric(hostname: str, data: dict):
    """Insère une nouvelle ligne de métriques pour `hostname`."""
    with _lock:
        c = _conn.cursor()
        c.execute(
            "INSERT INTO metrics (hostname, ts, data) VALUES (?, ?, ?)",
            (hostname, datetime.now().isoformat(), json.dumps(data)),
        )
        _conn.commit()


def query_history(hostname: str, since_iso: str, limit: int = 1000):
    """Récupère les métriques de `hostname` enregistrées après `since_iso`."""
    with _lock:
        c = _conn.cursor()
        c.execute(
            "SELECT ts, data FROM metrics WHERE hostname = ? AND ts >= ? ORDER BY ts DESC LIMIT ?",
            (hostname, since_iso, limit),
        )
        rows = c.fetchall()
    result = []
    for row in rows:
        try:
            d = json.loads(row["data"])
        except Exception:
            d = {}
        result.append({"timestamp": row["ts"], "data": d})
    result.reverse()
    return result


def prune_older_than(days: int = 30):
    """Supprime les métriques plus anciennes que `days` jours."""
    cutoff = datetime.now() - timedelta(days=days)
    with _lock:
        c = _conn.cursor()
        c.execute("DELETE FROM metrics WHERE ts < ?", (cutoff.isoformat(),))
        _conn.commit()


def insert_notification(hostname: str, message: str, severity: str = "info"):
    """Insère une notification/alerte dans la table `notifications`."""
    with _lock:
        c = _conn.cursor()
        c.execute(
            "INSERT INTO notifications (hostname, ts, message, severity) VALUES (?, ?, ?, ?)",
            (hostname, datetime.now().isoformat(), message, severity),
        )
        _conn.commit()


def count_notifications(
    hostname: str = None,
    since_iso: str = None,
    severity: str = None,
):
    """Compte le total de notifications avec filtres appliqués."""
    with _lock:
        c = _conn.cursor()
        where = []
        params = []
        if hostname:
            where.append("hostname = ?")
            params.append(hostname)
        if since_iso:
            where.append("ts >= ?")
            params.append(since_iso)
        if severity:
            where.append("severity = ?")
            params.append(severity)

        sql = "SELECT COUNT(*) as cnt FROM notifications"
        if where:
            sql += " WHERE " + " AND ".join(where)
        c.execute(sql, tuple(params))
        row = c.fetchone()
    return row["cnt"] if row else 0


def query_notifications(
    hostname: str = None,
    since_iso: str = None,
    limit: int = 500,
    severity: str = None,
    offset: int = 0,
):
    """Récupère les notifications avec options de filtrage et pagination."""
    with _lock:
        c = _conn.cursor()
        where = []
        params = []
        if hostname:
            where.append("hostname = ?")
            params.append(hostname)
        if since_iso:
            where.append("ts >= ?")
            params.append(since_iso)
        if severity:
            where.append("severity = ?")
            params.append(severity)

        sql = "SELECT ts, hostname, message, severity FROM notifications"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY ts DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        c.execute(sql, tuple(params))
        rows = c.fetchall()

    result = []
    for row in rows:
        result.append(
            {
                "timestamp": row["ts"],
                "hostname": row["hostname"],
                "message": row["message"],
                "severity": row["severity"],
            }
        )
    result.reverse()
    return result
