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
