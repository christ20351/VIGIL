from datetime import datetime, timedelta

from fastapi.responses import JSONResponse


def register(app):
    @app.get("/api/notifications")
    def get_notifications(
        hours: int = 12,
        hostname: str = None,
        severity: str = None,
    ):
        """Retourne TOUTES les notifications persistées sur les dernières `hours` heures.
        La pagination est gérée côté client.
        """
        try:
            from db.storage import query_notifications
        except ImportError:
            return JSONResponse({"error": "Storage non disponible"}, status_code=500)

        cutoff = None
        try:
            if hours and hours > 0:
                cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        except Exception:
            cutoff = None

        # Récupérer TOUTES les notifications (pas de limite côté serveur)
        rows = query_notifications(
            hostname, cutoff, limit=999999, severity=severity, offset=0
        )
        return {
            "notifications": rows,
            "total": len(rows),
        }
