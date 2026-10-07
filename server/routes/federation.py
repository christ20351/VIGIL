"""
VIGIL — Fédération multi-sites.

Chaque serveur expose /api/federation/summary (protégé par token partagé,
header X-Fed-Token). Un serveur central configuré avec FEDERATION_PEERS
agrège les sites dans /api/federation/overview → vue « Parc & Sites ».
"""

from datetime import datetime, timedelta

import config
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse


def _local_summary() -> dict:
    hosts = []
    from db.storage import count_notifications, get_agent_meta

    since = (datetime.now() - timedelta(hours=24)).isoformat()
    for hostname, d in (getattr(app_state, "computers_data", {}) or {}).items():
        meta = get_agent_meta(hostname)
        try:
            alerts = count_notifications(hostname=hostname, since_iso=since)
        except Exception:
            alerts = 0
        hosts.append({
            "hostname": hostname,
            "group": meta.get("group_name") or "",
            "online": not d.get("offline", False),
            "in_maintenance": _in_maintenance_safe(hostname),
            "cpu": d.get("cpu_percent"),
            "ram": (d.get("memory") or {}).get("percent"),
            "disk": (d.get("disk") or {}).get("percent"),
            "alerts_24h": alerts,
        })
    return {
        "site": (config.FEDERATION_SITE_NAME or "Site local"),
        "version": "2.1",
        "generated_at": datetime.now().isoformat(),
        "hosts": hosts,
    }


def _in_maintenance_safe(hostname: str) -> bool:
    try:
        from db.storage import is_in_maintenance

        return is_in_maintenance(hostname)
    except Exception:
        return False


app_state = None  # injecté au register


def register(app: FastAPI):

    global app_state
    app_state = app.state

    @app.get("/api/federation/summary")
    def federation_summary(x_fed_token: str = Header(default="")):
        """Résumé de CE site pour un serveur central. Exige FEDERATION_TOKEN."""
        expected = (config.FEDERATION_TOKEN or "").strip()
        if not expected:
            raise HTTPException(
                status_code=403,
                detail="Fédération désactivée : définissez FEDERATION_TOKEN.",
            )
        import hmac as _hmac

        if not _hmac.compare_digest(str(x_fed_token), expected):
            raise HTTPException(status_code=401, detail="Token de fédération invalide.")
        return _local_summary()

    @app.get("/api/federation/overview")
    def federation_overview():
        """Vue centrale : site local + tous les peers configurés (fetch parallèle)."""
        local = _local_summary()
        peers_cfg = list(getattr(config, "FEDERATION_PEERS", []) or [])

        import concurrent.futures

        peers_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(_fetch_peer_sync, p) for p in peers_cfg]
            for f in concurrent.futures.as_completed(futures):
                peers_results.append(f.result())
        peers_results.sort(key=lambda r: r.get("peer_name") or "")

        online = sum(1 for h in local["hosts"] if h["online"]) + sum(
            1 for p in peers_results for h in p.get("hosts", []) if h.get("online")
        )
        total = len(local["hosts"]) + sum(len(p.get("hosts", [])) for p in peers_results)

        return {
            "local": local,
            "peers": peers_results,
            "totals": {"online": online, "hosts": total},
        }


def _fetch_peer_sync(peer) -> dict:
    import json as _json
    import urllib.request

    url = (peer.get("url") or "").rstrip("/") + "/api/federation/summary"
    token = peer.get("token") or ""
    name = peer.get("name") or peer.get("url")
    try:
        req = urllib.request.Request(url, headers={"X-Fed-Token": token})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
        data["peer_status"] = "ok"
        data["peer_name"] = peer.get("name") or data.get("site", peer.get("url"))
        return data
    except Exception as e:
        return {
            "peer_name": name,
            "peer_status": f"injoignable ({e})",
            "site": name,
            "hosts": [],
        }
