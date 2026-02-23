# ====================================
# CONFIGURATION DE L'AGENT DE MONITORING v2.0
# ====================================

# === CONFIGURATION SERVEUR CIBLE ===
# IP du serveur central (modifiez selon votre deploiement)
SERVER_IP = "localhost"
# Port du serveur
SERVER_PORT = 8000

# === CONFIGURATION AGENT ===
# Intervalle d'envoi des donnees en secondes (1 pour temps reel)
UPDATE_INTERVAL = 1

# === SECURITE (optionnel) ===
# Activer l'authentification par token
ENABLE_AUTH = False
# Token secret pour l'authentification
AUTH_TOKEN = "votre-token-secret-ici"

# === MONITORING ===
TIMEOUT = 10  # Secondes avant de considerer un PC deconnecte
PROCESS_LIMIT = 100  # Nombre de processus a monitorer
NETWORK_CONN_LIMIT = 100  # Nombre de connexions reseau a envoyer



