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

# === ALARMES ===
# seuils définis en pourcentage pour déclencher des notifications
CPU_ALERT_THRESHOLD = 70  # %
CPU_ALERT_DURATION = 25  # secondes au delà du seuil avant envoi
RAM_ALERT_THRESHOLD = 95  # %
DISK_ALERT_THRESHOLD = 90  # % (plein)


# bon je remarque plusieurs chose ,le server est toujours en cours mais sur la page html sa marque websocket deconnecte ,  pourtant le server continu a frecevoir les donnees de l'agent et je dois refresh la page pour que sa revient a websocket connecte c'est tres chiant et on perd un eu le flow du truc. Aussi faurait qu'on puisses voir l'historique des notification max les notif de 1h , 4h , 7h, 24h, 1j , 3j max bref un filtrage comme tu veux. Et quand o clique sur notifications et que on a aucune aucun historique de notif , et qu'on a pas encore recu de notif , on affiche un truc pour indique que y'a pas de notifications. Maintenant dans l'onglet parametres de la barre laterrale , on pourrait ici configurer le server ip, port ... et que ces modif se font aussi dans le fichier config.py du server donc fait nous un beau design de cette page la. Aussi au niveau du filtrage de l'historique de  l'activite c'est un peu trop lent lorsque qu'on a puis par exple sur 1 , sa met assez de temps  pour changer me graphe en fonction du filtrage regarde cela et essaye de faire un genre de loader pour l'attente.