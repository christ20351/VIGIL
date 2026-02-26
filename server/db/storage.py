"""
SQLite storage for historical metrics
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta

# chemin de la base de données situé dans le dossier `db` à côté de
# ce module. Utiliser un chemin absolu permet de ne pas dépendre du
# répertoire de travail courant lors du démarrage du serveur.
DB_PATH = os.path.join(os.path.dirname(__file__), "metrics.db")

# connexion partagée (check_same_thread=False car nous écrivons depuis différents threads)
_conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
_conn.row_factory = sqlite3.Row

# Optimisation SQLite pour meilleures performances
_conn.execute(
    "PRAGMA journal_mode=WAL"
)  # Write-Ahead Logging pour meilleure concurrence
_conn.execute("PRAGMA synchronous=NORMAL")  # moins strict (à utiliser avec WAL)
_conn.execute("PRAGMA cache_size=10000")  # augmenter cache
_conn.execute("PRAGMA temp_store=MEMORY")  # temp tables en mémoire
_conn.execute("PRAGMA query_only=OFF")  # mode normal
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
        # index sur hostname et ts pour accélérer les requêtes temporelles
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_host_ts ON metrics(hostname, ts)"
        )
        # table des notifications / alertes
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
    """Récupère les métriques de `hostname` enregistrées après `since_iso`.

    Retourne une liste d'objets {timestamp, data}.
    Limité à `limit` résultats pour éviter de charger trop de données.
    """
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
    # réinverser pour que l'ordre soit croissant (on a trié DESC pour les plus récents en premier)
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
    """Compte le total de notifications avec filtres appliqués (sans limite/offset)."""
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
    """Récupère les notifications avec options de filtrage et pagination.

    - `hostname` facultatif pour filtrer par agent
    - `since_iso` facultatif (ISO timestamp) pour ne récupérer que les notifications postérieures à cette date.
    - `severity` facultatif pour filtrer par sévérité ('error'|'warning'|'info').
    - `limit` nombre d'éléments à retourner
    - `offset` décalage (pour pagination)

    Retourne une liste d'objets {timestamp, hostname, message, severity} triés par ts DESC (plus récentes en premier).
    """
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
        print(
            f"🔍 query_notifications: limit={limit}, offset={offset}, SQL={sql}, params={params}"
        )
        c.execute(sql, tuple(params))
        rows = c.fetchall()
        print(f"📊 query_notifications returned {len(rows)} rows")

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
    # réinverser pour affichage chronologique (plus anciennes en premier)
    result.reverse()
    return result
