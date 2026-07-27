from datetime import datetime, timedelta

from fastapi.responses import JSONResponse


def register(app):
    @app.get("/api/history/{hostname}")
    def get_history(hostname: str, hours: int = 24):
        """Retourne l'historique des métriques sur les dernières `hours` heures.

        Exemple: /api/history/WORKSTATION-01?hours=72
        """
        try:
            from db.storage import query_history
        except ImportError:
            return JSONResponse({"error": "Storage non disponible"}, status_code=500)

        cutoff = None
        try:
            if hours and hours > 0:
                cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        except Exception:
            cutoff = None

        if cutoff:
            rows = query_history(hostname, cutoff)
            return {"hostname": hostname, "history": rows}
        else:
            return JSONResponse({"error": "Invalid parameters"}, status_code=400)
