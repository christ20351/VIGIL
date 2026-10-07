"""
Storage des métriques historiques — SQLite ou PostgreSQL.

Le backend est choisi via config.yaml :
    DB_BACKEND: sqlite   (défaut, zéro configuration)
    DB_BACKEND: postgres (avec DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD)

L'API publique est identique quel que soit le backend. Écritures batchées
(file + thread writer) pour ne jamais bloquer la boucle d'événements. Les
lignes standards sont allégées ; les lignes « détail » complètes sont
écrites à la cadence METRICS_DETAIL_INTERVAL.
"""

import json
import os
import queue
import sqlite3
import threading
import time
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────
#  Paramètres de stockage (synchronisés depuis config.yaml)
# ─────────────────────────────────────────────────────────────
METRICS_STORAGE_INTERVAL = 5
METRICS_DETAIL_INTERVAL = 60


def configure(storage_interval: int, detail_interval: int):
    """Appelé au démarrage du serveur pour synchroniser les réglages config."""
    global METRICS_STORAGE_INTERVAL, METRICS_DETAIL_INTERVAL
    METRICS_STORAGE_INTERVAL = max(1, int(storage_interval or 5))
    METRICS_DETAIL_INTERVAL = max(1, int(detail_interval or 60))


# Sections volumineuses : retirées des lignes standards, conservées
# uniquement dans les lignes "détail" (cadence METRICS_DETAIL_INTERVAL).
_HEAVY_KEYS = ("processes", "interfaces", "smart")
_PROTO_HEAVY_KEYS = ("connections", "listening_ports")


def _slim_payload(data: dict) -> dict:
    """Retire les sections lourdes d'un payload de métriques."""
    slim = {k: v for k, v in data.items() if k not in _HEAVY_KEYS}
    protocols = data.get("protocols")
    if isinstance(protocols, dict):
        p = dict(protocols)
        tcp = p.get("tcp")
        if isinstance(tcp, dict):
            p["tcp"] = {k: v for k, v in tcp.items() if k not in _PROTO_HEAVY_KEYS}
        udp = p.get("udp")
        if isinstance(udp, dict):
            p["udp"] = {k: v for k, v in udp.items() if k not in _PROTO_HEAVY_KEYS}
        p.pop("listening_ports", None)
        slim["protocols"] = p
    return slim


# ================================================================
#  BACKENDS
# ================================================================


class _SqliteBackend:
    """Backend SQLite (fichier local, WAL, un seul verrou global)."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10.0)
        self.conn.row_factory = sqlite3.Row
        for pragma in (
            "PRAGMA journal_mode=WAL",
            "PRAGMA synchronous=NORMAL",
            "PRAGMA cache_size=10000",
            "PRAGMA temp_store=MEMORY",
            "PRAGMA busy_timeout=5000",
        ):
            self.conn.execute(pragma)
        self.conn.commit()

    # -- primitives ------------------------------------------------
    def execute_write(self, sql: str, params: tuple = ()) -> int:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur.rowcount

    def fetch_all(self, sql: str, params: tuple = ()):
        with self.lock:
            cur = self.conn.execute(sql, params)
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def fetch_one(self, sql: str, params: tuple = ()):
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def executemany_write(self, sql: str, seq):
        with self.lock:
            self.conn.executemany(sql, seq)
            self.conn.commit()

    # -- DDL -------------------------------------------------------
    def init_db(self):
        with self.lock:
            c = self.conn.cursor()
            c.execute(
                "CREATE TABLE IF NOT EXISTS metrics ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " hostname TEXT NOT NULL,"
                " ts TEXT NOT NULL,"
                " data TEXT NOT NULL)"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_metrics_host_ts ON metrics(hostname, ts)"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS notifications ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " hostname TEXT,"
                " ts TEXT NOT NULL,"
                " message TEXT NOT NULL,"
                " severity TEXT)"
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_notifications_ts ON notifications(ts)")
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_notifications_host_ts ON notifications(hostname, ts)"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS ai_diagnostics ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " hostname TEXT,"
                " ts TEXT NOT NULL,"
                " title TEXT NOT NULL,"
                " severity TEXT NOT NULL,"
                " summary TEXT NOT NULL,"
                " details_json TEXT,"
                " resolved INTEGER DEFAULT 0)"
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_ai_diag_ts ON ai_diagnostics(ts)")
            c.execute(
                "CREATE TABLE IF NOT EXISTS watch_rules ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " description TEXT NOT NULL,"
                " hostname TEXT,"
                " metric TEXT NOT NULL,"
                " operator TEXT NOT NULL,"
                " threshold REAL NOT NULL,"
                " duration_sec INTEGER DEFAULT 0,"
                " active INTEGER DEFAULT 1,"
                " created_by TEXT DEFAULT 'admin',"
                " created_at TEXT,"
                " last_fired TEXT)"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS ai_approvals ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " hostname TEXT NOT NULL,"
                " command TEXT NOT NULL,"
                " reason TEXT,"
                " status TEXT DEFAULT 'pending',"
                " ts TEXT NOT NULL,"
                " decided_at TEXT,"
                " decided_by TEXT,"
                " result_json TEXT,"
                " created_by TEXT DEFAULT 'vili')"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_approvals_status ON ai_approvals(status)"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS agent_meta ("
                " hostname TEXT PRIMARY KEY,"
                " group_name TEXT DEFAULT '',"
                " maintenance_until TEXT,"
                " updated_at TEXT)"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS inventory ("
                " hostname TEXT PRIMARY KEY,"
                " ts TEXT NOT NULL,"
                " data_json TEXT NOT NULL)"
            )
            self.conn.commit()
        self._migrate()

    def _migrate(self):
        """Évolutions de schéma pour les bases existantes (best effort)."""
        migrations = [
            ("notifications", "details_json", "ALTER TABLE notifications ADD COLUMN details_json TEXT"),
        ]
        with self.lock:
            for table, column, ddl in migrations:
                try:
                    cols = [r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
                    if column not in cols:
                        self.conn.execute(ddl)
                except Exception:
                    pass
            self.conn.commit()

    # -- spécifique SQLite -----------------------------------------
    def insert_metrics_batch(self, rows):
        self.executemany_write(
            "INSERT INTO metrics (hostname, ts, data) VALUES (?, ?, ?)", rows
        )

    def insert_returning_id(self, sql: str, params: tuple) -> int:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur.lastrowid or 0

    def chunked_delete(self, table: str, where: str, params: tuple, chunk: int = 5000):
        while True:
            with self.lock:
                cur = self.conn.execute(
                    f"DELETE FROM {table} WHERE rowid IN "
                    f"(SELECT rowid FROM {table} WHERE {where} LIMIT {chunk})",
                    params,
                )
                deleted = cur.rowcount
                self.conn.commit()
            if deleted < chunk:
                # rend les pages libérées à l'OS (auto_vacuum incrémental,
                # no-op si auto_vacuum est désactivé)
                with self.lock:
                    self.conn.execute("PRAGMA incremental_vacuum(1000)")
                    self.conn.commit()
                break

    def checkpoint(self):
        with self.lock:
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def compact(self) -> bool:
        try:
            self.checkpoint()
            with self.lock:
                self.conn.commit()
                self.conn.execute("VACUUM")
            return True
        except Exception as e:
            print(f"[STORAGE] sqlite vacuum error: {e}")
            return False

    def analyze(self):
        pass


class _PostgresBackend:
    """Backend PostgreSQL (psycopg2). Méme API que le backend SQLite."""

    def __init__(self, host: str, port: int, dbname: str, user: str, password: str):
        import psycopg2
        import psycopg2.extras

        self._psycopg2 = psycopg2
        self.lock = threading.Lock()
        self.conn = psycopg2.connect(
            host=host, port=port, dbname=dbname, user=user, password=password,
            connect_timeout=5,
        )
        self.conn.autocommit = False

    # -- primitives ------------------------------------------------
    def execute_write(self, sql: str, params: tuple = ()) -> int:
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                rowcount = cur.rowcount
            self.conn.commit()
            return rowcount

    def fetch_all(self, sql: str, params: tuple = ()):
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = cur.fetchall()
            self.conn.commit()
        return [dict(zip(cols, r)) for r in rows]

    def fetch_one(self, sql: str, params: tuple = ()):
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def executemany_write(self, sql: str, seq):
        with self.lock:
            with self.conn.cursor() as cur:
                cur.executemany(sql, seq)
            self.conn.commit()

    # -- DDL -------------------------------------------------------
    def init_db(self):
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS metrics ("
                    " id BIGSERIAL PRIMARY KEY,"
                    " hostname TEXT NOT NULL,"
                    " ts TEXT NOT NULL,"
                    " data TEXT NOT NULL)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_metrics_host_ts ON metrics(hostname, ts)"
                )
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS notifications ("
                    " id BIGSERIAL PRIMARY KEY,"
                    " hostname TEXT,"
                    " ts TEXT NOT NULL,"
                    " message TEXT NOT NULL,"
                    " severity TEXT)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_notifications_ts ON notifications(ts)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_notifications_host_ts"
                    " ON notifications(hostname, ts)"
                )
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS ai_diagnostics ("
                    " id BIGSERIAL PRIMARY KEY,"
                    " hostname TEXT,"
                    " ts TEXT NOT NULL,"
                    " title TEXT NOT NULL,"
                    " severity TEXT NOT NULL,"
                    " summary TEXT NOT NULL,"
                    " details_json TEXT,"
                    " resolved INTEGER DEFAULT 0)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_ai_diag_ts ON ai_diagnostics(ts)"
                )
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS watch_rules ("
                    " id BIGSERIAL PRIMARY KEY,"
                    " description TEXT NOT NULL,"
                    " hostname TEXT,"
                    " metric TEXT NOT NULL,"
                    " operator TEXT NOT NULL,"
                    " threshold DOUBLE PRECISION NOT NULL,"
                    " duration_sec INTEGER DEFAULT 0,"
                    " active INTEGER DEFAULT 1,"
                    " created_by TEXT DEFAULT 'admin',"
                    " created_at TEXT,"
                    " last_fired TEXT)"
                )
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS ai_approvals ("
                    " id BIGSERIAL PRIMARY KEY,"
                    " hostname TEXT NOT NULL,"
                    " command TEXT NOT NULL,"
                    " reason TEXT,"
                    " status TEXT DEFAULT 'pending',"
                    " ts TEXT NOT NULL,"
                    " decided_at TEXT,"
                    " decided_by TEXT,"
                    " result_json TEXT,"
                    " created_by TEXT DEFAULT 'vili')"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_approvals_status ON ai_approvals(status)"
                )
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS agent_meta ("
                    " hostname TEXT PRIMARY KEY,"
                    " group_name TEXT DEFAULT '',"
                    " maintenance_until TEXT,"
                    " updated_at TEXT)"
                )
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS inventory ("
                    " hostname TEXT PRIMARY KEY,"
                    " ts TEXT NOT NULL,"
                    " data_json TEXT NOT NULL)"
                )
            self.conn.commit()
        self._migrate()

    def _migrate(self):
        """Évolutions de schéma pour les bases existantes (best effort)."""
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'notifications' AND column_name = 'details_json'"
                )
                if not cur.fetchone():
                    cur.execute("ALTER TABLE notifications ADD COLUMN details_json TEXT")
            self.conn.commit()

    # -- spécifique PostgreSQL -------------------------------------
    def insert_metrics_batch(self, rows):
        self.executemany_write(
            "INSERT INTO metrics (hostname, ts, data) VALUES (%s, %s, %s)", rows
        )

    def insert_returning_id(self, sql: str, params: tuple) -> int:
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute(sql + " RETURNING id", params)
                row = cur.fetchone()
            self.conn.commit()
            return row[0] if row else 0

    def chunked_delete(self, table: str, where: str, params: tuple, chunk: int = 5000):
        where = where.replace("?", "%s")
        while True:
            with self.lock:
                with self.conn.cursor() as cur:
                    cur.execute(
                        f"DELETE FROM {table} WHERE ctid IN "
                        f"(SELECT ctid FROM {table} WHERE {where} LIMIT {chunk})",
                        params,
                    )
                    deleted = cur.rowcount
                self.conn.commit()
            if deleted < chunk:
                break

    def checkpoint(self):
        pass  # pas de WAL côté application

    def compact(self) -> bool:
        try:
            self.analyze()
            return True
        except Exception as e:
            print(f"[STORAGE] postgres analyze error: {e}")
            return False

    def analyze(self):
        self.execute_write("ANALYZE")


def _get_sqlite_db_path() -> str:
    """
    Retourne le chemin absolu de metrics.db selon le contexte :
    - Binaire PyInstaller → dossier du .exe  (sys.executable)
    - Script Python normal → dossier db/ du package
    """
    import sys

    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(__file__)
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "metrics.db")


def _build_backend():
    """Construit le backend selon config.yaml, avec repli SQLite sûr."""
    try:
        import config as _config

        backend = (getattr(_config, "DB_BACKEND", "sqlite") or "sqlite").lower()
        if backend == "postgres":
            import psycopg2  # noqa: F401 — vérifie la dispo du driver

            return _PostgresBackend(
                host=getattr(_config, "DB_HOST", "localhost"),
                port=int(getattr(_config, "DB_PORT", 5432) or 5432),
                dbname=getattr(_config, "DB_NAME", "vigil"),
                user=getattr(_config, "DB_USER", "vigil"),
                password=getattr(_config, "DB_PASSWORD", "") or "",
            ), "postgres"
    except ImportError:
        print("[STORAGE] psycopg2 absent — repli sur SQLite")
    except Exception as e:
        print(f"[STORAGE] PostgreSQL indisponible ({e}) — repli sur SQLite")
    return _SqliteBackend(_get_sqlite_db_path()), "sqlite"


_backend, BACKEND_NAME = _build_backend()
DB_PATH = _get_sqlite_db_path()  # informatif (chemin SQLite)
_lock = _backend.lock  # compat import autonome


def _translate(sql: str) -> str:
    """Convertit les placeholders ? en %s pour PostgreSQL."""
    if BACKEND_NAME == "postgres":
        return sql.replace("?", "%s")
    return sql


def init_db():
    """Crée les tables nécessaires si elles n'existent pas."""
    try:
        _backend.init_db()
    except Exception as e:
        print(f"[STORAGE] init_db error: {e}")


# Always ensure database tables exist on module import
init_db()


# ================================================================
#  FILE D'ÉCRITURE BATCHÉE
# ================================================================

_write_queue: "queue.Queue[tuple | None]" = queue.Queue(maxsize=100_000)
_writer_started = False
_writer_lock = threading.Lock()

# Dernière écriture par hôte : {hostname: (mono_ts, is_detail)}
_last_write: dict = {}
# Dernière ligne "détail" complète par hôte : {hostname: mono_ts}
_last_detail: dict = {}


def _writer_loop():
    insert_sql = _translate(
        "INSERT INTO metrics (hostname, ts, data) VALUES (?, ?, ?)"
    )
    while True:
        batch = []
        try:
            item = _write_queue.get(timeout=2.0)
            if item is None:  # signal d'arrêt
                break
            batch.append(item)
            while len(batch) < 500:
                try:
                    item2 = _write_queue.get_nowait()
                    if item2 is None:
                        break
                    batch.append(item2)
                except queue.Empty:
                    break
        except queue.Empty:
            continue

        try:
            _backend.insert_metrics_batch(
                [(h, ts, json.dumps(d, separators=(",", ":"))) for h, ts, d in batch]
            )
        except Exception as e:
            print(f"[STORAGE] batch write error: {e}")


def _ensure_writer():
    global _writer_started
    with _writer_lock:
        if not _writer_started:
            threading.Thread(target=_writer_loop, daemon=True, name="DbWriter").start()
            _writer_started = True


def insert_metric(hostname: str, data: dict, force: bool = False):
    """
    Programme l'écriture d'une ligne de métriques (non bloquant).

    - Cadence la sortie à METRICS_STORAGE_INTERVAL par hôte.
    - Lignes standards allégées (_slim_payload) ; ligne « détail »
      complète toutes les METRICS_DETAIL_INTERVAL.
    - force=True écrit une ligne complète immédiatement (1er message).
    """
    _ensure_writer()
    now = time.monotonic()
    is_detail = False

    if not force:
        last = _last_write.get(hostname)
        if last is not None:
            last_ts, _ = last
            if now - last_ts < METRICS_STORAGE_INTERVAL:
                return  # trop tôt pour ce hôte
            is_detail = (
                now - last_ts >= METRICS_DETAIL_INTERVAL
                or now - _last_detail.get(hostname, 0) >= METRICS_DETAIL_INTERVAL
            )
    else:
        is_detail = True

    if is_detail:
        _last_detail[hostname] = now
    _last_write[hostname] = (now, is_detail)

    payload = data if is_detail else _slim_payload(data)
    try:
        _write_queue.put_nowait((hostname, datetime.now().isoformat(), payload))
    except queue.Full:
        # File saturée (serveur surchargé) : on abandonne cette ligne
        # plutôt que de bloquer la boucle d'événements.
        pass


def flush(timeout: float = 5.0) -> None:
    """Attend que la file d'écriture soit vide (arrêt propre / tests)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _write_queue.empty():
            return
        time.sleep(0.05)


# ================================================================
#  REQUÊTES (identiques quel que soit le backend)
# ================================================================


def query_history(hostname: str, since_iso: str, limit: int = 1000):
    """Récupère les métriques de `hostname` enregistrées après `since_iso`."""
    rows = _backend.fetch_all(
        _translate(
            "SELECT ts, data FROM metrics WHERE hostname = ? AND ts >= ?"
            " ORDER BY ts DESC LIMIT ?"
        ),
        (hostname, since_iso, limit),
    )
    result = []
    for row in rows:
        try:
            d = json.loads(row["data"])
        except Exception:
            d = {}
        result.append({"timestamp": row["ts"], "data": d})
    result.reverse()
    return result


def query_history_chart(hostname: str, since_iso: str, max_points: int = 200):
    """
    Récupération rapide pour graphiques : sous-échantillonnage en SQL
    (modulo sur l'id auto-incrémenté).
    """
    row = _backend.fetch_one(
        _translate(
            "SELECT count(*) AS cnt FROM metrics WHERE hostname = ? AND ts >= ?"
        ),
        (hostname, since_iso),
    )
    total_rows = row["cnt"] if row else 0
    if not total_rows:
        return []

    if total_rows > max_points:
        step = max(1, total_rows // max_points)
        rows = _backend.fetch_all(
            _translate(
                "SELECT ts, data FROM metrics WHERE hostname = ? AND ts >= ?"
                " AND (id % ?) = 0 ORDER BY ts ASC"
            ),
            (hostname, since_iso, step),
        )
    else:
        rows = _backend.fetch_all(
            _translate(
                "SELECT ts, data FROM metrics WHERE hostname = ? AND ts >= ?"
                " ORDER BY ts ASC"
            ),
            (hostname, since_iso),
        )

    result = []
    for row in rows:
        try:
            d = json.loads(row["data"])
        except Exception:
            d = {}
        result.append({
            "timestamp": row["ts"],
            "data": {
                "cpu_percent": d.get("cpu_percent", 0),
                "memory": {
                    "percent": d.get("memory", {}).get("percent", 0) if isinstance(d.get("memory"), dict) else 0,
                    "used": d.get("memory", {}).get("used", 0) if isinstance(d.get("memory"), dict) else 0,
                    "total": d.get("memory", {}).get("total", 0) if isinstance(d.get("memory"), dict) else 0,
                },
                "disk": {
                    "percent": d.get("disk", {}).get("percent", 0) if isinstance(d.get("disk"), dict) else 0,
                    "used": d.get("disk", {}).get("used", 0) if isinstance(d.get("disk"), dict) else 0,
                    "total": d.get("disk", {}).get("total", 0) if isinstance(d.get("disk"), dict) else 0,
                },
            }
        })
    return result


def prune_older_than(days: int = 30, notification_days: int = 90):
    """
    Supprime les données plus anciennes que la rétention configurée,
    par lots de 5000 lignes (notifications et diagnostics IA inclus).
    """
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    notif_cutoff = (datetime.now() - timedelta(days=notification_days)).isoformat()

    try:
        _backend.chunked_delete("metrics", "ts < ?", (cutoff,))
        _backend.chunked_delete("notifications", "ts < ?", (notif_cutoff,))
        _backend.chunked_delete("ai_diagnostics", "ts < ?", (notif_cutoff,))
        _backend.checkpoint()
    except Exception as e:
        print(f"[STORAGE] prune error: {e}")


def vacuum_db() -> bool:
    """
    Maintenance : VACUUM (SQLite) ou ANALYZE (PostgreSQL). Opération
    potentiellement longue — appelée via l'endpoint de maintenance.
    """
    try:
        flush()
        return _backend.compact()
    except Exception as e:
        print(f"[STORAGE] compact error: {e}")
        return False


def insert_notification(
    hostname: str, message: str, severity: str = "info", details: dict = None
):
    """
    Insère une notification/alerte. `details` (optionnel) contient le
    contexte enrichi capturé au moment de l'alerte (processus lourds,
    débit réseau...) — utilisé par Vili pour l'analyse de cause racine.
    """
    details_json = None
    if details:
        try:
            details_json = json.dumps(details, ensure_ascii=False)
        except Exception:
            details_json = None
    _backend.execute_write(
        _translate(
            "INSERT INTO notifications (hostname, ts, message, severity, details_json)"
            " VALUES (?, ?, ?, ?, ?)"
        ),
        (hostname, datetime.now().isoformat(), message, severity, details_json),
    )


def count_notifications(
    hostname: str = None,
    since_iso: str = None,
    severity: str = None,
):
    """Compte le total de notifications avec filtres appliqués."""
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

    sql = "SELECT COUNT(*) AS cnt FROM notifications"
    if where:
        sql += " WHERE " + " AND ".join(where)
    row = _backend.fetch_one(_translate(sql), tuple(params))
    return row["cnt"] if row else 0


def query_notifications(
    hostname: str = None,
    since_iso: str = None,
    limit: int = 500,
    severity: str = None,
    offset: int = 0,
):
    """Récupère les notifications avec options de filtrage et pagination."""
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

    sql = "SELECT ts, hostname, message, severity, details_json FROM notifications"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = _backend.fetch_all(_translate(sql), tuple(params))

    result = []
    for r in rows:
        try:
            details = json.loads(r["details_json"]) if r.get("details_json") else None
        except Exception:
            details = None
        result.append(
            {
                "timestamp": r["ts"],
                "hostname": r["hostname"],
                "message": r["message"],
                "severity": r["severity"],
                "details": details,
            }
        )
    result.reverse()
    return result


# ================================================================
#  API POUR LES MODULES IA (persistance des rapports autonomes)
# ================================================================


def insert_returning_id(sql: str, params: tuple) -> int:
    """INSERT avec retour d'id (utilisé par ai.autonomous_db)."""
    return _backend.insert_returning_id(_translate(sql), params)


def fetch_all(sql: str, params: tuple = ()):
    """SELECT générique dictionnaire (utilisé par ai.autonomous_db)."""
    return _backend.fetch_all(_translate(sql), params)


def execute_write(sql: str, params: tuple = ()) -> int:
    """UPDATE/DELETE générique (utilisé par ai.autonomous_db)."""
    return _backend.execute_write(_translate(sql), params)


def insert_metrics_batch(rows):
    """Insertion en masse [(hostname, ts, data_dict_str), ...] (tests/imports)."""
    _backend.insert_metrics_batch(rows)


def chunked_delete(table: str, where: str, params: tuple, chunk: int = 5000):
    """Suppression par lots au niveau module (utilisé par les tests)."""
    _backend.chunked_delete(table, where, params, chunk)


# ================================================================
#  RÈGLES DE SURVEILLANCE EN LANGAGE NATUREL (watch rules)
# ================================================================


def insert_watch_rule(
    description: str, metric: str, operator: str, threshold: float,
    hostname: str = None, duration_sec: int = 0, created_by: str = "admin",
) -> int:
    return _backend.insert_returning_id(
        "INSERT INTO watch_rules (description, hostname, metric, operator, threshold,"
        " duration_sec, active, created_by, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
        (description, hostname, metric, operator, float(threshold),
         int(duration_sec or 0), created_by, datetime.now().isoformat()),
    )


def list_watch_rules(active_only: bool = False) -> List[dict]:
    sql = "SELECT id, description, hostname, metric, operator, threshold," \
          " duration_sec, active, created_by, created_at, last_fired FROM watch_rules"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY id DESC"
    return _backend.fetch_all(sql, ())


def delete_watch_rule(rule_id: int) -> bool:
    return _backend.execute_write(
        "DELETE FROM watch_rules WHERE id = ?", (rule_id,)
    ) > 0


def set_watch_rule_fired(rule_id: int):
    _backend.execute_write(
        "UPDATE watch_rules SET last_fired = ? WHERE id = ?",
        (datetime.now().isoformat(), rule_id),
    )


# ================================================================
#  DEMANDES D'AUTORISATION DE COMMANDES (Vili → admin : Oui / Non)
# ================================================================


def create_approval(
    hostname: str, command: str, reason: str = "", created_by: str = "vili"
) -> int:
    """Enregistre une demande d'exécution en attente de décision admin."""
    return _backend.insert_returning_id(
        "INSERT INTO ai_approvals (hostname, command, reason, status, ts, created_by)"
        " VALUES (?, ?, ?, 'pending', ?, ?)",
        (hostname, command, reason or "", datetime.now().isoformat(), created_by),
    )


def list_approvals(status: str = None, limit: int = 50):
    sql = (
        "SELECT id, hostname, command, reason, status, ts, decided_at, decided_by,"
        " result_json, created_by FROM ai_approvals"
    )
    params = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = _backend.fetch_all(_translate(sql), tuple(params))
    out = []
    for r in rows:
        try:
            result = json.loads(r["result_json"]) if r.get("result_json") else None
        except Exception:
            result = None
        r["result"] = result
        out.append(r)
    return out


def get_approval(approval_id: int):
    rows = list_approvals(limit=1000)
    for r in rows:
        if r["id"] == approval_id:
            return r
    return None


def decide_approval(approval_id: int, approved: bool, decided_by: str = "admin") -> bool:
    """Enregistre la décision admin. Ne touche qu'aux demandes encore en attente."""
    return _backend.execute_write(
        _translate(
            "UPDATE ai_approvals SET status = ?, decided_at = ?, decided_by = ?"
            " WHERE id = ? AND status = 'pending'"
        ),
        ("approved" if approved else "refused", datetime.now().isoformat(), decided_by, approval_id),
    ) > 0


def save_approval_result(approval_id: int, result: dict):
    try:
        result_json = json.dumps(result, ensure_ascii=False)
    except Exception:
        result_json = None
    _backend.execute_write(
        "UPDATE ai_approvals SET result_json = ? WHERE id = ?",
        (result_json, approval_id),
    )


# ================================================================
#  MÉTADONNÉES AGENTS (groupes / fenêtres de maintenance)
# ================================================================


def get_agent_meta(hostname: str) -> dict:
    row = _backend.fetch_one(
        "SELECT hostname, group_name, maintenance_until FROM agent_meta WHERE hostname = ?",
        (hostname,),
    )
    return row or {"hostname": hostname, "group_name": "", "maintenance_until": None}


def set_agent_group(hostname: str, group_name: str):
    now = datetime.now().isoformat()
    _backend.execute_write(
        _translate(
            "INSERT INTO agent_meta (hostname, group_name, updated_at)"
            " VALUES (?, ?, ?)"
            " ON CONFLICT(hostname) DO UPDATE SET"
            " group_name = excluded.group_name, updated_at = excluded.updated_at"
            if BACKEND_NAME == "sqlite"
            else
            "INSERT INTO agent_meta (hostname, group_name, updated_at)"
            " VALUES (%s, %s, %s)"
            " ON CONFLICT(hostname) DO UPDATE SET"
            " group_name = excluded.group_name, updated_at = excluded.updated_at"
        ),
        (hostname, group_name or "", now),
    )


def set_maintenance(hostname: str, until_iso: str = None):
    now = datetime.now().isoformat()
    _backend.execute_write(
        _translate(
            "INSERT INTO agent_meta (hostname, maintenance_until, updated_at)"
            " VALUES (?, ?, ?)"
            " ON CONFLICT(hostname) DO UPDATE SET"
            " maintenance_until = excluded.maintenance_until, updated_at = excluded.updated_at"
            if BACKEND_NAME == "sqlite"
            else
            "INSERT INTO agent_meta (hostname, maintenance_until, updated_at)"
            " VALUES (%s, %s, %s)"
            " ON CONFLICT(hostname) DO UPDATE SET"
            " maintenance_until = excluded.maintenance_until, updated_at = excluded.updated_at"
        ),
        (hostname, until_iso, now),
    )


def is_in_maintenance(hostname: str) -> bool:
    """True si une fenêtre de maintenance est active pour cet hôte."""
    row = _backend.fetch_one(
        "SELECT maintenance_until FROM agent_meta WHERE hostname = ?",
        (hostname,),
    )
    if not row or not row.get("maintenance_until"):
        return False
    try:
        until = datetime.fromisoformat(row["maintenance_until"])
        return datetime.now() < until
    except Exception:
        return False


def list_groups() -> list:
    """Liste des groupes distincts utilisés."""
    rows = _backend.fetch_all(
        "SELECT DISTINCT group_name AS name FROM agent_meta"
        " WHERE group_name IS NOT NULL AND group_name != '' ORDER BY name",
        (),
    )
    return [r["name"] for r in rows]


# ================================================================
#  INVENTAIRE MATÉRIEL & LOGICIEL
# ================================================================


def upsert_inventory(hostname: str, data: dict):
    """Enregistre l'inventaire d'un agent (1 ligne par machine)."""
    _backend.execute_write(
        _translate(
            "INSERT INTO inventory (hostname, ts, data_json) VALUES (?, ?, ?)"
            " ON CONFLICT(hostname) DO UPDATE SET"
            " ts = excluded.ts, data_json = excluded.data_json"
            if BACKEND_NAME == "sqlite"
            else
            "INSERT INTO inventory (hostname, ts, data_json) VALUES (%s, %s, %s)"
            " ON CONFLICT(hostname) DO UPDATE SET"
            " ts = excluded.ts, data_json = excluded.data_json"
        ),
        (hostname, datetime.now().isoformat(),
         json.dumps(data, ensure_ascii=False)),
    )


def get_inventory(hostname: str):
    row = _backend.fetch_one(
        "SELECT hostname, ts, data_json FROM inventory WHERE hostname = ?",
        (hostname,),
    )
    if not row:
        return None
    try:
        data = json.loads(row["data_json"])
    except Exception:
        data = {}
    return {"hostname": row["hostname"], "ts": row["ts"], "data": data}


def list_inventory():
    rows = _backend.fetch_all(
        "SELECT hostname, ts, data_json FROM inventory ORDER BY hostname", ()
    )
    out = []
    for r in rows:
        try:
            data = json.loads(r["data_json"])
        except Exception:
            data = {}
        out.append({"hostname": r["hostname"], "ts": r["ts"], "data": data})
    return out
