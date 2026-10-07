#!/usr/bin/env bash
set -euo pipefail

# Script d'installation (équivalent de install.bat mais en Bash)

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "==========================================="
echo "  Monitoring System v2.0 - Installation"
echo "==========================================="
echo

# Try to display banner via PowerShell Core if available, ignore otherwise
if command -v pwsh >/dev/null 2>&1; then
    pwsh -NoProfile -ExecutionPolicy Bypass -File "${SCRIPT_DIR}/scripts/banner.ps1" || true
elif command -v powershell >/dev/null 2>&1; then
    powershell -NoProfile -ExecutionPolicy Bypass -File "${SCRIPT_DIR}/scripts/banner.ps1" || true
fi

echo "Que voulez-vous installer ?"
echo "1) Serveur Central"
echo "2) Agent de Monitoring"
read -rp "Votre choix (1 ou 2) : " choice

# Detect available python interpreter (python or python3)
if command -v python >/dev/null 2>&1; then
    PYTHON=python
elif command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
else
    echo "[ERREUR] Python n'est pas installe ou n'est pas dans le PATH"
    echo "Telechargez Python depuis https://www.python.org/downloads/"
    read -rp "Appuyez sur Entrée pour quitter..."
    exit 1
fi
echo "[OK] Utilisation de ${PYTHON}"

# Helper: install requirements in a venv and show errors
pip_install() {
  venv_python="$1"
  reqfile="$2"
  echo "Running: ${venv_python} -m pip install -r ${reqfile}"
  if ${venv_python} -m pip install -r "${reqfile}"; then
    return 0
  fi
  return 1
}

# Helper: create venv if not exists
setup_venv() {
  venv_path="$1"
  # Remove existing venv if pip is broken
  if [ -d "${venv_path}" ]; then
    if ! "${venv_path}/bin/python" -m pip --version >/dev/null 2>&1; then
      echo "[WARN] Venv existant a pip cassé, suppression..."
      rm -rf "${venv_path}"
    else
      echo "[OK] Venv pret: ${venv_path}"
      return 0
    fi
  fi
  
  if [ ! -d "${venv_path}" ]; then
    echo "[INFO] Creation de l'environnement virtuel..."
    ${PYTHON} -m venv "${venv_path}" --upgrade-deps || { echo "[ERREUR] Impossible de creer le venv"; return 1; }
  fi
  echo "[OK] Venv pret: ${venv_path}"
  return 0
}

server_flow() {
    local VENV_DIR="server/.venv"
    local VENV_PYTHON
    
    echo
    echo "==========================================="
    echo "Configuration du SERVEUR CENTRAL"
    echo "==========================================="

    if ! setup_venv "${VENV_DIR}"; then
        echo "[ERREUR] Impossible de creer le venv serveur"
        read -rp "Appuyez sur Entrée pour quitter..."
        exit 1
    fi

    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        VENV_PYTHON="${SCRIPT_DIR}/${VENV_DIR}/Scripts/python.exe"
    else
        VENV_PYTHON="${SCRIPT_DIR}/${VENV_DIR}/bin/python"
    fi

    echo "[INFO] Installation des dependances serveur..."
    if ! pip_install "${VENV_PYTHON}" server/requirements.txt; then
        echo "[ERREUR] Impossible d'installer les dependances serveur"
        echo "Voir la sortie ci-dessus pour les details. Essayez manuellement: ${VENV_PYTHON} -m pip install -r server/requirements.txt"
        read -rp "Appuyez sur Entrée pour quitter..."
        exit 1
    fi

    if [ ! -f "server/config.yaml" ]; then
        cat > server/config.yaml <<'YAML'
# configuration du serveur v2.0
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
YAML
        echo "[OK] server/config.yaml cree avec les parametres par defaut."
    else
        echo "[INFO] Configuration serveur existante trouvee."
    fi

    read -rp "Modifier l'host du serveur? (vide pour garder) : " new_host
    if [ -n "${new_host}" ]; then
        ${VENV_PYTHON} -c "import yaml,sys; path='server/config.yaml'; cfg=yaml.safe_load(open(path)) or {}; cfg['SERVER_HOST']=sys.argv[1]; open(path,'w').write(yaml.safe_dump(cfg))" "${new_host}"
        echo "[OK] Host mis a jour."
    fi

    read -rp "Modifier le port du serveur? (vide pour garder) : " new_port
    if [ -n "${new_port}" ]; then
        ${VENV_PYTHON} -c "import yaml,sys; path='server/config.yaml'; cfg=yaml.safe_load(open(path)) or {}; cfg['SERVER_PORT']=int(sys.argv[1]); open(path,'w').write(yaml.safe_dump(cfg))" "${new_port}"
        echo "[OK] Port mis a jour."
    fi

    read -rp "Activer l'authentification ? (o/n) : " auth_enable
    if [[ "${auth_enable,,}" == "o" || "${auth_enable,,}" == "y" ]]; then
        ${VENV_PYTHON} -c "import yaml,sys; path='server/config.yaml'; cfg=yaml.safe_load(open(path)) or {}; cfg['ENABLE_AUTH']=True; open(path,'w').write(yaml.safe_dump(cfg))"
        read -rp "Entrez un token secret (laisser vide pour generer) : " token
        if [ -z "${token}" ]; then
            token=$(${VENV_PYTHON} - <<'PY'
import secrets,string
print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(16)))
PY
)
            echo "Token genere : ${token}"
        fi
        ${VENV_PYTHON} -c "import yaml,sys; path='server/config.yaml'; cfg=yaml.safe_load(open(path)) or {}; cfg['AUTH_TOKEN']=sys.argv[1]; open(path,'w').write(yaml.safe_dump(cfg))" "${token}"
    fi

    echo
    read -rp "Voulez-vous demarrer le serveur maintenant ? (o/n) : " start
    if [[ "${start,,}" == "o" || "${start,,}" == "y" ]]; then
        echo "#    #   ###    ###    ###    #    #"
        echo "#    #    #    #       #     #    #"
        echo "#    #    #    # ###   #     #    #"
        echo " #  #     #    #   #   #     #    #"
        echo "  ##     ###    ###   ###   #####"
        echo
        echo "       VIGIL - Monitoring System"
        (cd server && ${VENV_PYTHON} server.py --mode web)
    else
        echo
        echo "[OK] Installation terminee !"
        echo "Pour demarrer le serveur :"
        echo "  source ${VENV_DIR}/bin/activate  # ou .venv\Scripts\activate.bat sur Windows"
        echo "  python server.py --mode web"
    fi
}

agent_flow() {
    local VENV_DIR="agent/.venv"
    local VENV_PYTHON
    
    echo
    echo "==========================================="
    echo "Configuration de l'AGENT"
    echo "==========================================="

    if ! setup_venv "${VENV_DIR}"; then
        echo "[ERREUR] Impossible de creer le venv agent"
        read -rp "Appuyez sur Entrée pour quitter..."
        exit 1
    fi

    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        VENV_PYTHON="${SCRIPT_DIR}/${VENV_DIR}/Scripts/python.exe"
    else
        VENV_PYTHON="${SCRIPT_DIR}/${VENV_DIR}/bin/python"
    fi

    echo "[INFO] Installation des dependances agent..."
    if ! pip_install "${VENV_PYTHON}" agent/requirements.txt; then
        echo "[ERREUR] Impossible d'installer les dependances agent"
        echo "Voir la sortie ci-dessus pour les details. Essayez manuellement: ${VENV_PYTHON} -m pip install -r agent/requirements.txt"
        read -rp "Appuyez sur Entrée pour quitter..."
        exit 1
    fi

    if [ ! -f "agent/config.yaml" ]; then
        cat > agent/config.yaml <<'YAML'
# configuration agent v2.0
SERVER_IP: "192.168.188.120"
SERVER_PORT: 5000

UPDATE_INTERVAL: 1

TIMEOUT: 10
PROCESS_LIMIT: 100
NETWORK_CONN_LIMIT: 100
YAML
        echo "[OK] agent/config.yaml cree avec les parametres par defaut."
    else
        echo "[INFO] Configuration agent existante trouvee."
    fi

    read -rp "Entrez l'IP/hostname du serveur central (laissez vide pour garder l'actuel) : " server_ip
    if [ -n "${server_ip}" ]; then
        ${VENV_PYTHON} -c "import yaml,sys; path='agent/config.yaml'; cfg=yaml.safe_load(open(path)) or {}; cfg['SERVER_IP']=sys.argv[1]; open(path,'w').write(yaml.safe_dump(cfg))" "${server_ip}"
        echo "[OK] IP du serveur mise a jour."
    fi

    read -rp "Entrez le port du serveur central (laissez vide pour garder l'actuel) : " server_port
    if [ -n "${server_port}" ]; then
        ${VENV_PYTHON} -c "import yaml,sys; path='agent/config.yaml'; cfg=yaml.safe_load(open(path)) or {}; cfg['SERVER_PORT']=int(sys.argv[1]); open(path,'w').write(yaml.safe_dump(cfg))" "${server_port}"
        echo "[OK] Port du serveur mis a jour."
    fi

    read -rp "Intervalle d'envoi en secondes (laissez vide pour garder l'actuel) : " interval
    if [ -n "${interval}" ]; then
        ${VENV_PYTHON} -c "import yaml,sys; path='agent/config.yaml'; cfg=yaml.safe_load(open(path)) or {}; cfg['UPDATE_INTERVAL']=int(sys.argv[1]); open(path,'w').write(yaml.safe_dump(cfg))" "${interval}"
        echo "[OK] Intervalle d'envoi mis a jour."
    fi

    read -rp "Voulez-vous demarrer l'agent maintenant ? (o/n) : " start
    if [[ "${start,,}" == "o" || "${start,,}" == "y" ]]; then
        echo "#    #   ###    ###    ###    #    #"
        echo "#    #    #    #       #     #    #"
        echo "#    #    #    # ###   #     #    #"
        echo " #  #     #    #   #   #     #    #"
        echo "  ##     ###    ###   ###   #####"
        echo
        echo "       VIGIL - Monitoring System"
        (cd agent && ${VENV_PYTHON} agent.py)
    else
        echo
        echo "[OK] Installation terminee !"
        echo "Pour demarrer l'agent :"
        echo "  source ${VENV_DIR}/bin/activate  # ou .venv\Scripts\activate.bat sur Windows"
        echo "  ${PYTHON} agent.py"
    fi
}

invalid_choice() {
    echo "[ERREUR] Choix invalide"
    read -rp "Appuyez sur Entrée pour quitter..."
    exit 1
}

case "${choice}" in
    1) server_flow ;;
    2) agent_flow ;;
    *) invalid_choice ;;
esac

echo
echo "==========================================="
echo "Installation terminee avec succes !"
echo "==========================================="

# Nettoyage : supprimer les repertoires __pycache__ via Python
if command -v ${PYTHON} >/dev/null 2>&1; then
    ${PYTHON} - <<'PY'
import os,shutil
for root, dirs, files in os.walk('.', topdown=False):
        for d in dirs:
                if d == '__pycache__':
                        shutil.rmtree(os.path.join(root, d), ignore_errors=True)
PY
fi

read -rp "Appuyez sur Entrée pour terminer..."