#!/bin/bash

echo "=========================================="
echo "  Monitoring System v2.0 - Installation"
echo "=========================================="
echo ""

# Couleurs pour affichage
COLOR_GREEN='\033[0;32m'
COLOR_RED='\033[0;31m'
COLOR_YELLOW='\033[1;33m'
NC='\033[0m'

# Banniere VIGIL
echo -e "${COLOR_YELLOW}"
echo '#    #   ###    ###    ###    #    #'
echo '#    #    #    #       #     #    #'
echo '#    #    #    # ###   #     #    #'
echo ' #  #     #    #   #   #     #    #'
echo '  ##     ###    ###   ###   #####'
echo -e "${COLOR_GREEN}"
echo '       VIGIL - Monitoring System'
echo -e "${NC}"

echo "Que voulez-vous installer ?"
echo "1) Serveur Central"
echo "2) Agent de Monitoring"
read -p "Votre choix (1 ou 2) : " choice

if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${COLOR_RED}[ERREUR] Python3 n'est pas installe. Installez Python3 puis relancez ce script.${NC}"
    exit 1
fi
echo -e "${COLOR_GREEN}[OK] Python3 est installe.${NC}"

# ==========================================
# Fonctions utilitaires
# ==========================================

update_string_value() {
    local file="$1"
    local key="$2"
    local value="$3"
    sed -i "s/${key} = \"[^\"]*\"/${key} = \"${value}\"/" "$file"
}

update_int_value() {
    local file="$1"
    local key="$2"
    local value="$3"
    sed -i "s/^${key} = [0-9]*/${key} = ${value}/" "$file"
}

ask_string() {
    local prompt="$1"
    local file="$2"
    local key="$3"
    read -p "$prompt" value
    if [ -n "$value" ]; then
        update_string_value "$file" "$key" "$value"
        echo -e "${COLOR_GREEN}[OK] $key mis a jour.${NC}"
    fi
}

ask_int() {
    local prompt="$1"
    local file="$2"
    local key="$3"
    read -p "$prompt" value
    if [ -n "$value" ]; then
        if [[ "$value" =~ ^[0-9]+$ ]]; then
            update_int_value "$file" "$key" "$value"
            echo -e "${COLOR_GREEN}[OK] $key mis a jour.${NC}"
        else
            echo -e "${COLOR_RED}[ERREUR] La valeur doit etre un nombre entier positif.${NC}"
        fi
    fi
}

# ==========================================
if [ "$choice" == "1" ]; then
    echo ""
    echo "=========================================="
    echo "  Configuration du SERVEUR CENTRAL"
    echo "=========================================="

    echo -e "${COLOR_YELLOW}[INFO] Installation des dependances serveur...${NC}"
    pip3 install -r server/requirements.txt --quiet >/dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo -e "${COLOR_RED}[ERREUR] Impossible d'installer les dependances serveur.${NC}"
        exit 1
    fi
    echo -e "${COLOR_GREEN}[OK] Dependances installees.${NC}"

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
# IPs autorisees pour les agents (laissez vide pour accepter toutes)
ALLOWED_AGENT_IPS = [
    # "192.168.1.10",
    # "192.168.1.20",
]
# IPs autorisees pour les clients web (laissez vide pour accepter toutes)
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
        echo -e "${COLOR_GREEN}[OK] server/config.py cree avec les parametres par defaut.${NC}"
    else
        echo -e "${COLOR_YELLOW}[INFO] Configuration serveur existante trouvee.${NC}"
    fi

    ask_string "Modifier l'host du serveur ? (vide pour garder l'actuel) : " "server/config.py" "SERVER_HOST"
    ask_int    "Modifier le port du serveur ? (vide pour garder l'actuel) : " "server/config.py" "SERVER_PORT"

    echo ""
    read -p "Demarrer le serveur maintenant ? (o/n) : " start_now
    if [[ "$start_now" =~ ^[oO]$ ]]; then
        echo -e "${COLOR_GREEN}[INFO] Demarrage du serveur...${NC}"
        python3 server/server.py --mode web
    else
        echo ""
        echo -e "${COLOR_GREEN}[OK] Installation terminee !${NC}"
        echo "Pour demarrer le serveur :"
        echo "  cd server && python3 server.py --mode web"
    fi

# ==========================================
elif [ "$choice" == "2" ]; then
    echo ""
    echo "=========================================="
    echo "  Configuration de l'AGENT"
    echo "=========================================="

    echo -e "${COLOR_YELLOW}[INFO] Installation des dependances agent...${NC}"
    pip3 install -r agent/requirements.txt --quiet >/dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo -e "${COLOR_RED}[ERREUR] Impossible d'installer les dependances agent.${NC}"
        exit 1
    fi
    echo -e "${COLOR_GREEN}[OK] Dependances installees.${NC}"

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
        echo -e "${COLOR_GREEN}[OK] agent/config.py cree avec les parametres par defaut.${NC}"
    else
        echo -e "${COLOR_YELLOW}[INFO] Configuration agent existante trouvee.${NC}"
    fi

    ask_string "Entrez l'IP/hostname du serveur central (vide pour garder l'actuel) : " "agent/config.py" "SERVER_IP"
    ask_int    "Entrez le port du serveur central (vide pour garder l'actuel) : "         "agent/config.py" "SERVER_PORT"
    ask_int    "Intervalle d'envoi en secondes (vide pour garder l'actuel) : "            "agent/config.py" "UPDATE_INTERVAL"

    echo ""
    read -p "Demarrer l'agent maintenant ? (o/n) : " start_now
    if [[ "$start_now" =~ ^[oO]$ ]]; then
        echo -e "${COLOR_GREEN}[INFO] Demarrage de l'agent...${NC}"
        sudo python3 agent/agent.py
    else
        echo ""
        echo -e "${COLOR_GREEN}[OK] Installation terminee !${NC}"
        echo "Pour demarrer l'agent :"
        echo "  cd agent && sudo python3 agent.py"
    fi

else
    echo -e "${COLOR_RED}[ERREUR] Choix invalide.${NC}"
    exit 1
fi

echo ""
echo "=========================================="
echo -e "${COLOR_GREEN}  Installation terminee avec succes !${NC}"
echo "=========================================="

# Nettoyage : supprimer les dossiers __pycache__
find . -type d -name "__pycache__" -exec rm -rf {} + >/dev/null 2>&1 || true