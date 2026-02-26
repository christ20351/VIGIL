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

# helpers pour mettre à jour un fichier YAML en utilisant Python
update_yaml() {
    local file="$1"
    local key="$2"
    local value="$3"
    python3 - "$file" "$key" "$value" <<'PYCODE'
import sys, yaml
path, key, val = sys.argv[1], sys.argv[2], sys.argv[3]
# try convert to int or bool
if val.isdigit():
    val = int(val)
elif val.lower() in ("true","false"):
    val = val.lower() == "true"
with open(path) as f:
    data = yaml.safe_load(f) or {}
# ensure arrays are kept
if key in data and isinstance(data[key], list) and isinstance(val, str) and "," in val:
    data[key] = [x.strip() for x in val.split(",") if x.strip()]
else:
    data[key] = val
with open(path, "w") as f:
    yaml.safe_dump(data, f)
PYCODE
}

ask_string() {
    local prompt="$1"
    local file="$2"
    local key="$3"
    read -p "$prompt" value
    if [ -n "$value" ]; then
        update_yaml "$file" "$key" "$value"
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
            update_yaml "$file" "$key" "$value"
            echo -e "${COLOR_GREEN}[OK] $key mis a jour.${NC}"
        else
            echo -e "${COLOR_RED}[ERREUR] La valeur doit etre un nombre entier positif.${NC}"
        fi
    fi
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

    if [ ! -f server/config.yaml ]; then
        cat > server/config.yaml << 'YML'
# configuration du serveur de monitoring v2.0
SERVER_HOST: "0.0.0.0"
SERVER_PORT: 5000

ALLOWED_AGENT_IPS: []
ALLOWED_CLIENT_IPS: []

ENABLE_AUTH: false
AUTH_TOKEN: "votre-token-secret-ici"

TIMEOUT: 60
PROCESS_LIMIT: 100
NETWORK_CONN_LIMIT: 100

CPU_ALERT_THRESHOLD: 70
CPU_ALERT_DURATION: 25
RAM_ALERT_THRESHOLD: 95
DISK_ALERT_THRESHOLD: 90
YML
        echo -e "${COLOR_GREEN}[OK] server/config.yaml cree avec les parametres par defaut.${NC}"
    else
        echo -e "${COLOR_YELLOW}[INFO] Configuration serveur existante trouvee.${NC}"
    fi

    ask_string "Modifier l'host du serveur ? (vide pour garder l'actuel) : " "server/config.yaml" "SERVER_HOST"
    ask_int    "Modifier le port du serveur ? (vide pour garder l'actuel) : " "server/config.yaml" "SERVER_PORT"
    # option auth
    read -p "Activer l'authentification ? (o/n) : " enable_auth
    if [[ "$enable_auth" =~ ^[oO]$ ]]; then
        update_yaml "server/config.yaml" "ENABLE_AUTH" "true"
        read -p "Entrez un token secret (vide pour générer) : " tok
        if [ -z "$tok" ]; then
            tok=$(head -c16 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c16)
            echo "Token généré : $tok"
        fi
        update_yaml "server/config.yaml" "AUTH_TOKEN" "$tok"
    fi

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

    if [ ! -f agent/config.yaml ]; then
        cat > agent/config.yaml << 'YML'
# configuration de l'agent v2.0
SERVER_IP: "192.168.188.120"
SERVER_PORT: 5000

UPDATE_INTERVAL: 1

TIMEOUT: 10
PROCESS_LIMIT: 100
NETWORK_CONN_LIMIT: 100
YML
        echo -e "${COLOR_GREEN}[OK] agent/config.yaml cree avec les parametres par defaut.${NC}"
    else
        echo -e "${COLOR_YELLOW}[INFO] Configuration agent existante trouvee.${NC}"
    fi

    ask_string "Entrez l'IP/hostname du serveur central (vide pour garder l'actuel) : " "agent/config.yaml" "SERVER_IP"
    ask_int    "Entrez le port du serveur central (vide pour garder l'actuel) : "         "agent/config.yaml" "SERVER_PORT"
    ask_int    "Intervalle d'envoi en secondes (vide pour garder l'actuel) : "            "agent/config.yaml" "UPDATE_INTERVAL"

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