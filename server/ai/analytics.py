"""
Vili — Moteur d'analyse avancée (couche d'intelligence AIOps).

Analyse poussée calculée depuis l'historique de la base :
- Baselines apprises par créneau horaire (comportement normal de chaque
  machine selon l'heure) → détection d'anomalies par z-score ;
- Prévision de saturation (régression linéaire) : « disque plein dans
  X jours au rythme actuel » ;
- Tendances de dégradation (comparaison fenêtre récente vs référence) ;
- Corrélation d'incidents : tempêtes d'alertes simultanées multi-agents.

Tout est en Python pur (aucune dépendance), avec cache court pour ne pas
recalculer à chaque appel.
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import config
from db.storage import fetch_all, query_notifications

# cache du rapport d'intelligence (évite de recalculer à chaque appel)
_cache: Dict[str, Any] = {"ts": 0.0, "report": None}
_cache_lock = threading.Lock()
_CACHE_TTL = 60  # secondes


def _cfg(name: str, default):
    try:
        return getattr(config, name, default)
    except Exception:
        return default


# ================================================================
#  SÉRIES TEMPORELLES DEPUIS LA BASE
# ================================================================


def _host_series(hostname: str, hours: int) -> List[Dict[str, Any]]:
    """Série temporelle (ts, cpu, ram, disk, net) d'un hôte depuis la BD."""
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    try:
        rows = fetch_all(
            "SELECT ts, data FROM metrics WHERE hostname = ? AND ts >= ? ORDER BY ts ASC",
            (hostname, since),
        )
    except Exception:
        return []
    out = []
    for r in rows:
        try:
            import json

            d = json.loads(r["data"])
        except Exception:
            continue
        try:
            ts = datetime.fromisoformat(r["ts"])
        except Exception:
            continue
        out.append({
            "ts": ts,
            "cpu": d.get("cpu_percent"),
            "ram": (d.get("memory") or {}).get("percent"),
            "disk": (d.get("disk") or {}).get("percent"),
            "net": ((d.get("network") or {}).get("bytes_recv_per_sec", 0)
                    + (d.get("network") or {}).get("bytes_sent_per_sec", 0)) / 1024.0,
        })
    return out


def _clean(series: List[float]) -> List[float]:
    return [v for v in series if isinstance(v, (int, float))]


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return (sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5


# ================================================================
#  1. BASELINES PAR CRÉNEAU HORAIRE + DÉTECTION D'ANOMALIES
# ================================================================

# 4 créneaux de 6h : assez robuste même avec peu d'historique
_BUCKETS = [(0, 6), (6, 12), (12, 18), (18, 24)]


def _bucket_of(dt: datetime) -> int:
    return dt.hour // 6


def compute_baselines(hostname: str, hours: int = 168) -> Dict[str, Any]:
    """
    Apprend le comportement normal de l'hôte par créneau de 6h :
    moyenne + écart-type de CPU, RAM, réseau. Retourne
    {bucket: {metric: {mean, std, n}}}.
    """
    series = _host_series(hostname, hours)
    if len(series) < 20:
        return {}

    by_bucket: Dict[int, Dict[str, List[float]]] = {}
    for point in series:
        b = _bucket_of(point["ts"])
        slot = by_bucket.setdefault(b, {"cpu": [], "ram": [], "net": []})
        if isinstance(point["cpu"], (int, float)):
            slot["cpu"].append(point["cpu"])
        if isinstance(point["ram"], (int, float)):
            slot["ram"].append(point["ram"])
        if isinstance(point["net"], (int, float)):
            slot["net"].append(point["net"])

    baselines = {}
    for b, slot in by_bucket.items():
        baselines[b] = {
            metric: {"mean": _mean(vals), "std": _std(vals), "n": len(vals)}
            for metric, vals in slot.items()
            if len(vals) >= 10
        }
    return baselines


def detect_anomalies(computers_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Compare les valeurs live aux baselines apprises pour l'heure courante.
    Un z-score > ANOMALY_Z_THRESHOLD (défaut 3.0) signale une anomalie :
    « cette machine fait quelque chose d'inhabituel pour cette heure ».
    """
    z_threshold = float(_cfg("ANOMALY_Z_THRESHOLD", 3.0) or 3.0)
    anomalies: List[Dict[str, Any]] = []

    now_bucket = _bucket_of(datetime.now())
    for host, data in computers_data.items():
        if not isinstance(data, dict) or data.get("offline"):
            continue
        baselines = compute_baselines(host)
        slot = baselines.get(now_bucket)
        if not slot:
            continue  # pas assez d'historique pour ce créneau

        live = {
            "cpu": ("CPU", data.get("cpu_percent")),
            "ram": ("RAM", (data.get("memory") or {}).get("percent")),
            "net": ("Réseau", ((data.get("network") or {}).get("bytes_recv_per_sec", 0)
                    + (data.get("network") or {}).get("bytes_sent_per_sec", 0)) / 1024.0),
        }
        for metric, (label, value) in live.items():
            base = slot.get(metric)
            if not base or not isinstance(value, (int, float)) or base["std"] < 0.5:
                continue
            z = (value - base["mean"]) / base["std"]
            if abs(z) >= z_threshold:
                anomalies.append({
                    "hostname": host,
                    "metric": label,
                    "value": round(value, 1),
                    "baseline_mean": round(base["mean"], 1),
                    "z_score": round(z, 1),
                    "direction": "hausse" if z > 0 else "baisse",
                    "detail": (
                        f"{label} à {value:.1f} contre une normale de "
                        f"{base['mean']:.1f} pour ce créneau horaire "
                        f"(écart {abs(z):.1f}σ en {('hausse' if z > 0 else 'baisse')})"
                    ),
                })
    return anomalies


# ================================================================
#  2. PRÉVISION DE SATURATION (RÉGRESSION LINÉAIRE)
# ================================================================


def _linear_slope_per_day(points: List[tuple]) -> Optional[float]:
    """Pente (%/jour) par régression des moindres carrés. points=(t_heures, valeur)."""
    n = len(points)
    if n < 10:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mx, my = _mean(xs), _mean(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None
    slope_per_hour = sum((x - mx) * (y - my) for x, y in points) / denom
    return slope_per_hour * 24.0


def forecast_saturation(hostname: str, threshold: float = 90.0) -> List[Dict[str, Any]]:
    """
    Prévoit la date de saturation disque/RAM au rythme actuel.
    Retourne des prévisions {metric, current, slope_per_day, days_left}.
    """
    window = int(_cfg("FORECAST_WINDOW_HOURS", 48) or 48)
    series = _host_series(hostname, hours=window)
    t0 = series[0]["ts"] if series else None
    if t0 is None:
        return []

    forecasts = []
    for metric, label, thr in (("disk", "Disque", threshold), ("ram", "RAM", 95.0)):
        points = [
            ((p["ts"] - t0).total_seconds() / 3600.0, p[metric])
            for p in series
            if isinstance(p[metric], (int, float))
        ]
        if len(points) < 10:
            continue
        current = points[-1][1]
        slope = _linear_slope_per_day(points)
        if slope is None or slope <= 0.05:
            continue  # pas de croissance détectée
        days_left = max(0.0, (thr - current) / slope)
        forecasts.append({
            "hostname": hostname,
            "metric": label,
            "current": round(current, 1),
            "slope_per_day": round(slope, 2),
            "days_left": round(days_left, 1),
            "detail": (
                f"{label} à {current:.1f}% et en croissance de "
                f"{slope:.2f} pt/jour → seuil {thr:.0f}% atteint dans "
                f"~{days_left:.1f} jour(s) si la tendance se maintient"
            ),
        })
    return forecasts


# ================================================================
#  3. TENDANCE DE DÉGRADATION
# ================================================================


def detect_degradation(hostname: str) -> Optional[Dict[str, Any]]:
    """Compare les 6 dernières heures aux 48 précédentes (CPU/RAM)."""
    series = _host_series(hostname, hours=54)
    if len(series) < 30:
        return None
    cutoff = datetime.now() - timedelta(hours=6)
    recent = [p for p in series if p["ts"] >= cutoff]
    older = [p for p in series if p["ts"] < cutoff]
    if len(recent) < 10 or len(older) < 10:
        return None

    degradations = []
    for metric, label in (("cpu", "CPU"), ("ram", "RAM")):
        r = _mean(_clean([p[metric] for p in recent]))
        o = _mean(_clean([p[metric] for p in older]))
        if o > 1 and r - o > 10:  # +10 points de moyenne = dégradation nette
            degradations.append(f"{label} {o:.0f}% → {r:.0f}%")

    if degradations:
        return {
            "hostname": hostname,
            "detail": "Dégradation continue : " + " ; ".join(degradations)
                      + " (moyennes 6h vs 48h précédentes)",
        }
    return None


# ================================================================
#  4. CORRÉLATION D'INCIDENTS (TEMPÊTES D'ALERTES)
# ================================================================


def detect_incident_storms() -> List[Dict[str, Any]]:
    """
    Regroupe les alertes récentes : si ≥ STORM_MIN_HOSTS machines
    différentes alertent dans la même fenêtre, c'est probablement un
    problème d'infrastructure commun (réseau, alim, hyperviseur...).
    """
    window_min = int(_cfg("STORM_WINDOW_MIN", 10) or 10)
    min_hosts = int(_cfg("STORM_MIN_HOSTS", 3) or 3)
    since = (datetime.now() - timedelta(minutes=window_min)).isoformat()
    notifs = query_notifications(since_iso=since, limit=200)

    by_host: Dict[str, List[Dict]] = {}
    for n in notifs:
        host = n.get("hostname") or "?"
        if n.get("severity") in ("error", "critical", "warning"):
            by_host.setdefault(host, []).append(n)

    storms = []
    if len(by_host) >= min_hosts:
        hosts = sorted(by_host)
        total = sum(len(v) for v in by_host.values())
        storms.append({
            "hosts": hosts,
            "alerts_count": total,
            "detail": (
                f"{total} alertes sur {len(hosts)} machines en {window_min} min "
                f"({', '.join(hosts[:6])}) — cause racine commune probable "
                f"(réseau, hyperviseur, alimentation ?)"
            ),
        })
    return storms


# ================================================================
#  RAPPORT D'INTELLIGENCE GLOBAL (avec cache)
# ================================================================


def get_intelligence_report(computers_data: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
    """Agrège anomalies, prévisions, dégradations et tempêtes (cache 60 s)."""
    with _cache_lock:
        if not force and _cache["report"] and time.time() - _cache["ts"] < _CACHE_TTL:
            return _cache["report"]

    anomalies = []
    forecasts = []
    degradations = []
    for host, data in list(computers_data.items()):
        if not isinstance(data, dict):
            continue
        anomalies.extend(detect_anomalies({host: data}))
        forecasts.extend(forecast_saturation(host))
        deg = detect_degradation(host)
        if deg:
            degradations.append(deg)

    storms = detect_incident_storms()

    # tri : prévisions les plus urgentes d'abord
    forecasts.sort(key=lambda f: f["days_left"])

    report = {
        "generated_at": datetime.now().isoformat(),
        "anomalies": anomalies,
        "forecasts": forecasts,
        "degradations": degradations,
        "storms": storms,
        "summary": {
            "anomalies_count": len(anomalies),
            "forecasts_count": len(forecasts),
            "urgent_forecast": (
                f"{forecasts[0]['detail']}" if forecasts else None
            ),
            "storm_detected": bool(storms),
        },
    }
    with _cache_lock:
        _cache["ts"] = time.time()
        _cache["report"] = report
    return report


def format_intelligence_for_prompt(computers_data: Dict[str, Any]) -> str:
    """Section texte injectée dans le contexte de Vili (chat + cycles)."""
    rep = get_intelligence_report(computers_data)
    lines = ["### ANALYSE AVANCÉE VILI (automatique)"]
    s = rep["summary"]
    if not (s["anomalies_count"] or s["forecasts_count"] or rep["degradations"] or rep["storms"]):
        lines.append("- Aucune anomalie statistique, saturation prévue ni corrélation d'incident détectée.")
    for a in rep["anomalies"][:8]:
        lines.append(f"- 📈 Anomalie {a['hostname']}: {a['detail']}")
    for f in rep["forecasts"][:8]:
        lines.append(f"- ⏳ Saturation prévue {f['hostname']}: {f['detail']}")
    for d in rep["degradations"][:5]:
        lines.append(f"- 📉 Tendance {d['hostname']}: {d['detail']}")
    for st in rep["storms"]:
        lines.append(f"- ⛈️ Corrélation: {st['detail']}")
    return "\n".join(lines)
