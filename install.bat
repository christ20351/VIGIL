@echo off
setlocal enabledelayedexpansion
title Monitoring System v2.0 - Installation
color 0A

echo ==========================================
echo   Monitoring System v2.0 - Installation
echo ==========================================
echo.

:: Afficher la banniere MOTOR via script PowerShell (multi-couleur, evite problemes d'echappement)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\banner.ps1"

echo Que voulez-vous installer ?
echo 1) Serveur Central
echo 2) Agent de Monitoring
set /p choice="Votre choix (1 ou 2) : "

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou n'est pas dans le PATH
    echo Telechargez Python depuis https://www.python.org/downloads/
    pause
    exit /b 1
) else (
    echo [OK] Python est installe
)

if "%choice%"=="1" goto server
if "%choice%"=="2" goto agent
goto invalid

:server
    echo.
    echo ==========================================
    echo Configuration du SERVEUR CENTRAL
    echo ==========================================

    echo [INFO] Installation des dependances serveur...
    python -m pip install -r server\requirements.txt >nul 2>&1
    if errorlevel 1 (
        echo [ERREUR] Impossible d'installer les dependances serveur
        pause
        exit /b 1
    )

    if not exist "server\config.py" (
        (
            echo # ====================================
            echo # CONFIGURATION DU SERVEUR DE MONITORING v2.0
            echo # ====================================
            echo.
            echo # === CONFIGURATION SERVEUR ===
            echo # Interface d'ecoute ^(0.0.0.0 pour toutes les interfaces^)
            echo SERVER_HOST = "0.0.0.0"
            echo # Port du serveur web
            echo SERVER_PORT = 5000
            echo.
            echo # === SECURITE ===
            echo # IPs autorisees pour les agents ^(laissent vide pour accepter toutes^)
            echo ALLOWED_AGENT_IPS = [
            echo     # "192.168.1.10",
            echo     # "192.168.1.20",
            echo ]
            echo # IPs autorisees pour les clients web ^(laissent vide pour accepter toutes^)
            echo ALLOWED_CLIENT_IPS = [
            echo     # "192.168.1.100",
            echo     # "192.168.1.101",
            echo ]
            echo.
            echo # Activer l'authentification par token
            echo ENABLE_AUTH = False
            echo # Token secret pour l'authentification
            echo AUTH_TOKEN = "votre-token-secret-ici"
            echo.
            echo # === MONITORING ===
            echo TIMEOUT = 60  # Secondes avant de considerer un PC deconnecte
            echo PROCESS_LIMIT = 100  # Nombre de processus a monitorer
            echo NETWORK_CONN_LIMIT = 100  # Nombre de connexions reseau a envoyer
        ) > server\config.py
        echo [OK] server\config.py cree avec les parametres par defaut.
    ) else (
        echo [INFO] Configuration serveur existante trouvee.
    )
    set /p new_host="Modifier l'host du serveur? (vide pour garder) : "
    if not "!new_host!"=="" (
        python -c "import re,sys; v=sys.argv[1]; f=open('server/config.py','r'); c=f.read(); f.close(); c=re.sub(r'SERVER_HOST = \".+?\"', 'SERVER_HOST = \"'+v+'\"', c); f=open('server/config.py','w'); f.write(c); f.close()" "!new_host!"
        echo [OK] Host mis a jour.
    )

    set /p new_port="Modifier le port du serveur? (vide pour garder) : "
    if not "!new_port!"=="" (
        python -c "import re,sys; v=sys.argv[1]; f=open('server/config.py','r'); c=f.read(); f.close(); c=re.sub(r'SERVER_PORT = [0-9]+', 'SERVER_PORT = '+v, c); f=open('server/config.py','w'); f.write(c); f.close()" "!new_port!"
        echo [OK] Port mis a jour.
    )

    echo.
    set /p start="Voulez-vous demarrer le serveur maintenant ? (o/n) : "
    if /i "!start!"=="o" (
        powershell -NoProfile -ExecutionPolicy Bypass -Command "Write-Host '#    #   ###    ###    ###    #    #' -ForegroundColor Yellow; Write-Host '#    #    #    #       #     #    #' -ForegroundColor Yellow; Write-Host '#    #    #    # ###   #     #    #' -ForegroundColor Yellow; Write-Host ' #  #     #    #   #   #     #    #' -ForegroundColor Yellow; Write-Host '  ##     ###    ###   ###   #####' -ForegroundColor Yellow; Write-Host '' -ForegroundColor Green; Write-Host '       VIGIL - Monitoring System' -ForegroundColor Green"
        cd server
        python server.py --mode web
    ) else (
        echo.
        echo [OK] Installation terminee !
        echo Pour demarrer le serveur :
        echo   cd server
        echo   python server.py --mode web
    )

goto end

:agent
    echo.
    echo ==========================================
    echo Configuration de l'AGENT
    echo ==========================================

    echo [INFO] Installation des dependances agent...
    python -m pip install -r agent\requirements.txt >nul 2>&1
    if errorlevel 1 (
        echo [ERREUR] Impossible d'installer les dependances agent
        pause
        exit /b 1
    )

    if not exist "agent\config.py" (
        (
            echo # ====================================
            echo # CONFIGURATION DE L'AGENT DE MONITORING v2.0
            echo # ====================================
            echo.
            echo # === CONFIGURATION SERVEUR CIBLE ===
            echo # IP du serveur central ^(modifiez selon votre deploiement^)
            echo SERVER_IP = "192.168.188.120"
            echo # Port du serveur
            echo SERVER_PORT = 5000
            echo.
            echo # === CONFIGURATION AGENT ===
            echo # Intervalle d'envoi des donnees en secondes ^(1 pour temps reel^)
            echo UPDATE_INTERVAL = 1
            echo.
            echo # === SECURITE ^(optionnel^) ===
            echo # Activer l'authentification par token
            echo ENABLE_AUTH = False
            echo # Token secret pour l'authentification
            echo AUTH_TOKEN = "votre-token-secret-ici"
            echo.
            echo # === MONITORING ===
            echo TIMEOUT = 10  # Secondes avant de considerer un PC deconnecte
            echo PROCESS_LIMIT = 100  # Nombre de processus a monitorer
            echo NETWORK_CONN_LIMIT = 100  # Nombre de connexions reseau a envoyer
        ) > agent\config.py
        echo [OK] agent\config.py cree avec les parametres par defaut.
    ) else (
        echo [INFO] Configuration agent existante trouvee.
    )

    set /p server_ip="Entrez l'IP/hostname du serveur central (laissez vide pour garder l'actuel) : "
    if not "!server_ip!"=="" (
        python -c "import re,sys; v=sys.argv[1]; f=open('agent/config.py','r'); c=f.read(); f.close(); c=re.sub(r'SERVER_IP = \".+?\"', 'SERVER_IP = \"'+v+'\"', c); f=open('agent/config.py','w'); f.write(c); f.close()" "!server_ip!"
        echo [OK] IP du serveur mise a jour.
    )
    
    set /p server_port="Entrez le port du serveur central (laissez vide pour garder l'actuel) : "
    if not "!server_port!"=="" (
        python -c "import re,sys; v=sys.argv[1]; f=open('agent/config.py','r'); c=f.read(); f.close(); c=re.sub(r'SERVER_PORT = [0-9]+', 'SERVER_PORT = '+v, c); f=open('agent/config.py','w'); f.write(c); f.close()" "!server_port!"
        echo [OK] Port du serveur mis a jour.
    )
    
    set /p interval="Intervalle d'envoi en secondes (laissez vide pour garder l'actuel) : "
    if not "!interval!"=="" (
        python -c "import re,sys; v=sys.argv[1]; f=open('agent/config.py','r'); c=f.read(); f.close(); c=re.sub(r'UPDATE_INTERVAL = [0-9]+', 'UPDATE_INTERVAL = '+v, c); f=open('agent/config.py','w'); f.write(c); f.close()" "!interval!"
        echo [OK] Intervalle d'envoi mis a jour.
    )

    set /p start="Voulez-vous demarrer l'agent maintenant ? (o/n) : "
    if /i "!start!"=="o" (
        powershell -NoProfile -ExecutionPolicy Bypass -Command "Write-Host '#    #   ###    ###    ###    #    #' -ForegroundColor Yellow; Write-Host '#    #    #    #       #     #    #' -ForegroundColor Yellow; Write-Host '#    #    #    # ###   #     #    #' -ForegroundColor Yellow; Write-Host ' #  #     #    #   #   #     #    #' -ForegroundColor Yellow; Write-Host '  ##     ###    ###   ###   #####' -ForegroundColor Yellow; Write-Host '' -ForegroundColor Green; Write-Host '       VIGIL - Monitoring System' -ForegroundColor Green"
        cd agent
        python agent.py
    ) else (
        echo.
        echo [OK] Installation terminee !
        echo Pour demarrer l'agent :
        echo   cd agent
        echo   python agent.py
    )

goto end

:invalid
echo [ERREUR] Choix invalide
pause
exit /b 1

:end
echo.
echo ==========================================
echo Installation terminee avec succes !
echo ==========================================
rem Nettoyage : supprimer les repertoires __pycache__ dans le workspace
powershell -Command "Get-ChildItem -Path . -Recurse -Directory -Filter __pycache__ | ForEach-Object { Remove-Item $_.FullName -Recurse -Force }" >nul 2>&1
pause