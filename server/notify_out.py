"""
VIGIL — Notifications sortantes (webhook + email SMTP).

File d'attente + worker thread : jamais bloquant pour le serveur.
Routage par sévérité minimale (ALERT_MIN_SEVERITY). Tout est configurable
à chaud dans config.yaml / Paramètres.
"""

import json
import queue
import smtplib
import threading
from datetime import datetime
from email.mime.text import MIMEText

_config_ref = None  # module config (injection au setup pour éviter les cycles)

_queue: "queue.Queue" = queue.Queue(maxsize=1000)
_started = False
_lock = threading.Lock()

_SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2, "critical": 3}


def setup(config_module):
    global _config_ref, _started
    _config_ref = config_module
    with _lock:
        if _started:
            return
        threading.Thread(target=_worker, daemon=True, name="OutboundNotifier").start()
        _started = True


def _cfg(name, default=None):
    if _config_ref is None:
        return default
    return getattr(_config_ref, name, default)


def dispatch_alert(hostname: str, message: str, severity: str = "warning"):
    """
    Point d'entrée unique : met l'alerte en file pour les canaux sortants.
    Respecte ALERT_MIN_SEVERITY et les fenêtres de maintenance.
    """
    try:
        from db.storage import is_in_maintenance

        if is_in_maintenance(hostname):
            return
    except Exception:
        pass

    min_sev = (_cfg("ALERT_MIN_SEVERITY") or "warning").lower()
    if _SEVERITY_ORDER.get(severity, 1) < _SEVERITY_ORDER.get(min_sev, 1):
        return

    payload = {
        "event": "vigil_alert",
        "hostname": hostname,
        "message": message,
        "severity": severity,
        "timestamp": datetime.now().isoformat(),
    }
    if _cfg("ALERT_WEBHOOK_ENABLED"):
        _queue.put_nowait(("webhook", payload)) if _queue.qsize() < 1000 else None
    if _cfg("ALERT_EMAIL_ENABLED"):
        _queue.put_nowait(("email", payload)) if _queue.qsize() < 1000 else None


def _worker():
    while True:
        try:
            channel, payload = _queue.get(timeout=2.0)
        except queue.Empty:
            continue
        try:
            if channel == "webhook":
                _send_webhook(payload)
            elif channel == "email":
                _send_email(payload)
        except Exception as e:
            print(f"[NOTIFY-OUT] échec {channel}: {e}")


def _send_webhook(payload: dict):
    import urllib.request

    url = (_cfg("ALERT_WEBHOOK_URL") or "").strip()
    if not url:
        return
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json",
                 "User-Agent": "VIGIL-Alerts/2.1"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status >= 300:
            print(f"[NOTIFY-OUT] webhook HTTP {resp.status}")


def _send_email(payload: dict):
    host = (_cfg("ALERT_SMTP_HOST") or "").strip()
    if not host:
        return
    port = int(_cfg("ALERT_SMTP_PORT") or 587 or 587)
    user = (_cfg("ALERT_SMTP_USER") or "").strip()
    password = (_cfg("ALERT_SMTP_PASSWORD") or "").strip()
    use_tls = bool(_cfg("ALERT_SMTP_TLS", True))
    sender = (_cfg("ALERT_EMAIL_FROM") or user or "vigil@localhost").strip()
    recipients = [
        r.strip()
        for r in (_cfg("ALERT_EMAIL_TO") or "").split(",")
        if r.strip()
    ]
    if not recipients:
        return

    sev = payload.get("severity", "warning").upper()
    body = (
        f"VIGIL — Alerte {sev}\n\n"
        f"Machine  : {payload.get('hostname')}\n"
        f"Message  : {payload.get('message')}\n"
        f"Horodatage : {payload.get('timestamp')}\n\n"
        f"— VIGIL Monitoring"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"[VIGIL][{sev}] {payload.get('hostname')} — {payload.get('message', '')[:80]}"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    with smtplib.SMTP(host, port, timeout=15) as smtp:
        if use_tls:
            smtp.starttls()
        if user and password:
            smtp.login(user, password)
        smtp.sendmail(sender, recipients, msg.as_string())


def send_test_webhook() -> str:
    """Envoi synchrone d'un test (bouton Paramètres)."""
    _send_webhook({
        "event": "vigil_test",
        "hostname": "-",
        "message": "Test du canal webhook VIGIL — si vous lisez ceci, le canal fonctionne ✅",
        "severity": "info",
        "timestamp": datetime.now().isoformat(),
    })
    return "Webhook de test envoyé."


def send_test_email() -> str:
    _send_email({
        "hostname": "-",
        "message": "Test du canal email VIGIL — si vous lisez ceci, le canal fonctionne ✅",
        "severity": "info",
        "timestamp": datetime.now().isoformat(),
    })
    return "Email de test envoyé."
