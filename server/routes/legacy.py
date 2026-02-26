from fastapi.responses import FileResponse


def register(app):
    @app.get("/script.js")
    def legacy_script():
        """Ancien chemin pour compatibilité, redirige vers le statique"""
        return FileResponse("static/script.js")

    @app.get("/style.css")
    def legacy_style():
        """Ancien chemin pour compatibilité, redirige vers le statique"""
        return FileResponse("static/style.css")
