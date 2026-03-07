from fastapi.responses import JSONResponse


def register(app):
    @app.get("/api/computers")
    def get_computers():
        """API pour récupérer les données de tous les PC"""
        return app.state.computers_data

    @app.get("/api/computers/{hostname}")
    def get_computer(hostname: str):
        """API pour récupérer les données d'un PC spécifique"""
        if hostname in app.state.computers_data:
            return app.state.computers_data[hostname]
        return JSONResponse({"error": "Computer not found"}, status_code=404)

    # route additionnelle utilisée par le JS (fallback dans onglet SMART)
    @app.get("/api/computers/{hostname}/smart")
    def get_computer_smart(hostname: str):
        """Ne renvoie que le payload SMART d'un agent (vide si non disponible)."""
        if hostname in app.state.computers_data:
            data = app.state.computers_data[hostname]
            return {"smart": data.get("smart", {})}
        return JSONResponse({"error": "Computer not found"}, status_code=404)
