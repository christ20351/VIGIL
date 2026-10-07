from datetime import datetime, timedelta

from fastapi.responses import JSONResponse


def register(app):
    @app.get("/api/history/{hostname}")
    def get_history(hostname: str, hours: int = 24, points: int = 250):
        """Retourne l'historique optimisé des métriques sur les dernières `hours` heures."""
        try:
            from db.storage import query_history_chart
        except ImportError:
            return JSONResponse({"error": "Storage non disponible"}, status_code=500)

        cutoff = None
        try:
            if hours and hours > 0:
                cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        except Exception:
            cutoff = None

        if cutoff:
            rows = query_history_chart(hostname, cutoff, max_points=points)
            return {"hostname": hostname, "history": rows}
        else:
            return JSONResponse({"error": "Invalid parameters"}, status_code=400)
