"""
Journal d'événements de sécurité VIGIL (en mémoire, anneau borné).

Alimente l'écran Sécurité du dashboard : agents refusés, tokens invalides,
échecs de login, commandes distantes exécutées, IP bannies...
"""

import threading
import time
from collections import deque
from datetime import datetime
from typing import Optional

_lock = threading.Lock()
_events: deque = deque(maxlen=200)
_last_blocked_log: dict = {}  # {source: timestamp} — anti-spam des refus répétés

SEV_COLORS = {"info": "info", "warning": "warning", "critical": "critical"}


def log_security_event(
    kind: str,
    message: str,
    severity: str = "info",
    source: Optional[str] = None,
):
    """Enregistre un événement de sécurité (thread-safe, anneau borné)."""
    with _lock:
        _events.append(
            {
                "ts": datetime.now().isoformat(),
                "kind": kind,
                "message": message,
                "severity": severity,
                "source": source,
            }
        )


def log_blocked_once(source: str, message: str, cooldown_sec: int = 60) -> bool:
    """Journalise un refus lié à une IP (anti force-brute ou liste blanche)
    au plus une fois par « cooldown » et par source, pour ne pas inonder
    le journal quand une IP insistante retente en boucle.

    « source » doit discriminer l'origine (ex. "login:1.2.3.4",
    "web:1.2.3.4", "agent:1.2.3.4")."""
    now = time.time()
    with _lock:
        if now - _last_blocked_log.get(source, 0) < cooldown_sec:
            return False
        _last_blocked_log[source] = now
    log_security_event("ip_blocked", message, severity="warning", source=source)
    return True


def get_security_events(limit: int = 100) -> list:
    with _lock:
        events = list(_events)
    return list(reversed(events))[:limit]


def count_recent_failures(window_sec: int = 3600) -> int:
    """Nombre d'événements d'échec (login/token) sur la fenêtre donnée."""
    cutoff = time.time() - window_sec
    with _lock:
        return sum(
            1
            for e in _events
            if e["kind"] in ("login_failed", "agent_auth_failed", "ip_blocked")
            and _parse_ts(e["ts"]) >= cutoff
        )


def _parse_ts(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso).timestamp()
    except Exception:
        return 0.0
