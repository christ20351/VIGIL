#!/bin/bash

echo "=========================================="
echo "  Monitoring System v2.0 - Installation"
echo "=========================================="
echo ""

# Simple install script that installs dependencies per component
set -e

# Couleurs pour affichage
COLOR_GREEN='\033[0;32m'
COLOR_RED='\033[0;31m'
COLOR_YELLOW='\033[1;33m'
NC='\033[0m'

# Afficher la bannière MOTOR en vert
echo -e "${COLOR_GREEN}+-----------+\n|  V I G I L  |\n+-----------+\n\n       VIGIL — Monitoring lightweight${NC}"

echo "Que voulez-vous installer ?"
echo "1) Serveur Central"
echo "2) Agent de Monitoring"
read -p "Votre choix (1 ou 2) : " choice

if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${COLOR_RED}Python3 n'est pas installé. Installez Python3 puis relancez ce script.${NC}"
    exit 1
fi

if [ "$choice" == "1" ]; then
    echo -e "${COLOR_YELLOW}Installation des dépendances du serveur...${NC}"
    pip3 install -r server/requirements.txt --quiet > /dev/null 2>&1 || { echo -e "${COLOR_RED}Erreur lors de l'installation des dépendances serveur${NC}"; exit 1; }

    # Create default server config if missing, or update existing
    if [ ! -f server/config.py ]; then
        cat > server/config.py << 'PYCONF'
# ====================================
# CONFIGURATION DU SERVEUR DE MONITORING v2.0
# ====================================

# === CONFIGURATION SERVEUR ===
# Interface d'ecoute (0.0.0.0 pour toutes les interfaces)
SERVER_HOST = "0.0.0.0"
# Port du serveur web
SERVER_PORT = 5000

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
PYCONF
        echo -e "${COLOR_GREEN}[OK] Fichier server/config.py cree avec les parametres par defaut.${NC}"
    else
        echo -e "${COLOR_YELLOW}Configuration serveur existante trouvée.${NC}"
        read -p "Voulez-vous modifier l'host du serveur ? (actuellement $(grep 'SERVER_HOST' server/config.py | cut -d'"' -f2), laissez vide pour garder) : " new_host
        if [ -n "$new_host" ]; then
            sed -i "s/SERVER_HOST = \".*\"/SERVER_HOST = \"$new_host\"/" server/config.py
            echo -e "${COLOR_GREEN}Host mis à jour.${NC}"
        fi
        read -p "Voulez-vous modifier le port du serveur ? (actuellement $(grep 'SERVER_PORT' server/config.py | grep -o '[0-9]\+'), laissez vide pour garder) : " new_port
        if [ -n "$new_port" ] && [[ "$new_port" =~ ^[0-9]+$ ]]; then
            sed -i "s/SERVER_PORT = [0-9]\+/SERVER_PORT = $new_port/" server/config.py
            echo -e "${COLOR_GREEN}Port mis à jour.${NC}"
        fi
    fi

    echo ""
    read -p "Démarrer le serveur maintenant ? (o/n) : " start_now
    if [[ "$start_now" =~ ^[oO]$ ]]; then
        python3 server/server.py --mode web
    else
        echo "Pour démarrer le serveur : cd server && python3 server.py --mode web"
    fi

elif [ "$choice" == "2" ]; then
    echo -e "${COLOR_YELLOW}Installation des dépendances de l'agent...${NC}"
    pip3 install -r agent/requirements.txt --quiet > /dev/null 2>&1 || { echo -e "${COLOR_RED}Erreur lors de l'installation des dépendances agent${NC}"; exit 1; }

    # Create default agent config if missing, or update existing
    if [ ! -f agent/config.py ]; then
        cat > agent/config.py << 'PYCONF'
# ====================================
# CONFIGURATION DE L'AGENT DE MONITORING v2.0
# ====================================

# === CONFIGURATION SERVEUR CIBLE ===
# IP du serveur central (modifiez selon votre deploiement)
SERVER_IP = "192.168.188.120"
# Port du serveur
SERVER_PORT = 5000

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
PYCONF
        echo -e "${COLOR_GREEN}[OK] Fichier agent/config.py cree avec les parametres par defaut.${NC}"
        read -p "Entrez l'IP/hostname du serveur central (défaut: 192.168.188.120) : " server_ip
        server_ip=${server_ip:-192.168.188.120}
        read -p "Intervalle d'envoi en secondes (défaut 1) : " interval
        interval=${interval:-1}
        sed -i "s/SERVER_IP = \".*\"/SERVER_IP = \"$server_ip\"/" agent/config.py
        sed -i "s/UPDATE_INTERVAL = [0-9]\+/UPDATE_INTERVAL = $interval/" agent/config.py
    else
        echo -e "${COLOR_YELLOW}Configuration agent existante trouvée.${NC}"
        read -p "Entrez l'IP/hostname du serveur central (actuellement $(grep 'SERVER_IP' agent/config.py | cut -d'"' -f2), laissez vide pour garder) : " server_ip
        if [ -n "$server_ip" ]; then
            sed -i "s/SERVER_IP = \".*\"/SERVER_IP = \"$server_ip\"/" agent/config.py
            echo -e "${COLOR_GREEN}IP du serveur mise à jour.${NC}"
        fi
        read -p "Intervalle d'envoi en secondes (actuellement $(grep 'UPDATE_INTERVAL' agent/config.py | grep -o '[0-9]\+'), laissez vide pour garder) : " interval
        if [ -n "$interval" ] && [[ "$interval" =~ ^[0-9]+$ ]]; then
            sed -i "s/UPDATE_INTERVAL = [0-9]\+/UPDATE_INTERVAL = $interval/" agent/config.py
            echo -e "${COLOR_GREEN}Intervalle mis à jour.${NC}"
        fi
    fi

    read -p "Démarrer l'agent maintenant ? (o/n) : " start_now
    if [[ "$start_now" =~ ^[oO]$ ]]; then
        sudo python3 agent/agent.py
    else
        echo "Pour démarrer l'agent : cd agent && sudo python3 agent.py"
    fi

else
    echo -e "${COLOR_RED}Choix invalide.${NC}"
    exit 1
fi

echo -e "${COLOR_GREEN}Installation terminée.${NC}"

# Nettoyage silencieux : supprimer les dossiers __pycache__
find . -type d -name "__pycache__" -exec rm -rf {} + >/dev/null 2>&1 || true