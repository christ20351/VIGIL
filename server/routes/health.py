from datetime import datetime


def register(app):
    @app.get("/health")
    def health():
        """Endpoint de santé pour vérifier que le serveur fonctionne"""
        return {
            "status": "ok",
            "computers_count": len(app.state.computers_data),
            "timestamp": datetime.now().isoformat(),
        }
