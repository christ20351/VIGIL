# ====================================
# CONFIGURATION DU SERVEUR DE MONITORING v2.0
# ====================================

# === CONFIGURATION SERVEUR ===
# Interface d'ecoute (0.0.0.0 pour toutes les interfaces)
SERVER_HOST = "localhost"
# Port du serveur web
SERVER_PORT = 8000

# === SECURITE ===
# IPs autorisees pour les agents (laissent vide pour accepter toutes)
ALLOWED_AGENT_IPS = [
    # "192.168.1.10",
    # "192.168.1.20",
]
# IPs autorisees pour les clients web (laissent vide pour accepter toutes)
ALLOWED_CLIENT_IPS = [
    # "192.168.1.100",
    # "192.168.1.101",
]

# Activer l'authentification par token
ENABLE_AUTH = False
# Token secret pour l'authentification
AUTH_TOKEN = "votre-token-secret-ici"

# === MONITORING ===
TIMEOUT = 60  # Secondes avant de considerer un PC deconnecte
PROCESS_LIMIT = 100  # Nombre de processus a monitorer
NETWORK_CONN_LIMIT = 100  # Nombre de connexions reseau a envoyer
