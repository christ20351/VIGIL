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

    if not exist "server\config.yaml" (
        (
            echo # configuration du serveur v2.0
            echo SERVER_HOST: "0.0.0.0"
            echo SERVER_PORT: 5000
            echo.
            echo ALLOWED_AGENT_IPS: []
            echo ALLOWED_CLIENT_IPS: []
            echo.
            echo ENABLE_AUTH: false
            echo AUTH_TOKEN: "votre-token-secret-ici"
            echo.
            echo TIMEOUT: 60
            echo PROCESS_LIMIT: 100
            echo NETWORK_CONN_LIMIT: 100
            echo.
            echo CPU_ALERT_THRESHOLD: 70
            echo CPU_ALERT_DURATION: 25
            echo RAM_ALERT_THRESHOLD: 95
            echo DISK_ALERT_THRESHOLD: 90
        ) > server\config.yaml
        echo [OK] server\config.yaml cree avec les parametres par defaut.
    ) else (
        echo [INFO] Configuration serveur existante trouvee.
    )
    set /p new_host="Modifier l'host du serveur? (vide pour garder) : "
    if not "!new_host!"=="" (
        python -c "import yaml,sys; path='server/config.yaml'; cfg=yaml.safe_load(open(path)) or {}; cfg['SERVER_HOST']=sys.argv[1]; open(path,'w').write(yaml.safe_dump(cfg))" "!new_host!"
        echo [OK] Host mis a jour.
    )

    set /p new_port="Modifier le port du serveur? (vide pour garder) : "
    if not "!new_port!"=="" (
        python -c "import yaml,sys; path='server/config.yaml'; cfg=yaml.safe_load(open(path)) or {}; cfg['SERVER_PORT']=int(sys.argv[1]); open(path,'w').write(yaml.safe_dump(cfg))" "!new_port!"
        echo [OK] Port mis a jour.
    )

    rem authentication settings for server only
    set /p auth_enable="Activer l'authentification ? (o/n) : "
    if /i "!auth_enable!"=="o" (
        python -c "import yaml,sys; path='server/config.yaml'; cfg=yaml.safe_load(open(path)) or {}; cfg['ENABLE_AUTH']=True; open(path,'w').write(yaml.safe_dump(cfg))"
        set /p token="Entrez un token secret (laisser vide pour generer) : "
        if "!token!"=="" (
            :: generer un token alphanumerique via Python (moins de paren-problems)
            for /f "delims=" %%A in ('python -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(16)))"') do set token=%%A
            echo Token genere : !token!
        )
        python -c "import yaml,sys; path='server/config.yaml'; cfg=yaml.safe_load(open(path)) or {}; cfg['AUTH_TOKEN']=sys.argv[1]; open(path,'w').write(yaml.safe_dump(cfg))" "!token!"
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

    if not exist "agent\config.yaml" (
        (
            echo # configuration agent v2.0
            echo SERVER_IP: "192.168.188.120"
            echo SERVER_PORT: 5000
            echo.
            echo UPDATE_INTERVAL: 1
            echo.
            echo TIMEOUT: 10
            echo PROCESS_LIMIT: 100
            echo NETWORK_CONN_LIMIT: 100
        ) > agent\config.yaml
        echo [OK] agent\config.yaml cree avec les parametres par defaut.
    ) else (
        echo [INFO] Configuration agent existante trouvee.
    )

    set /p server_ip="Entrez l'IP/hostname du serveur central (laissez vide pour garder l'actuel) : "
    if not "!server_ip!"=="" (
        python -c "import yaml,sys; path='agent/config.yaml'; cfg=yaml.safe_load(open(path)) or {}; cfg['SERVER_IP']=sys.argv[1]; open(path,'w').write(yaml.safe_dump(cfg))" "!server_ip!"
        echo [OK] IP du serveur mise a jour.
    )
    
    set /p server_port="Entrez le port du serveur central (laissez vide pour garder l'actuel) : "
    if not "!server_port!"=="" (
        python -c "import yaml,sys; path='agent/config.yaml'; cfg=yaml.safe_load(open(path)) or {}; cfg['SERVER_PORT']=int(sys.argv[1]); open(path,'w').write(yaml.safe_dump(cfg))" "!server_port!"
        echo [OK] Port du serveur mis a jour.
    )
    
    set /p interval="Intervalle d'envoi en secondes (laissez vide pour garder l'actuel) : "
    if not "!interval!"=="" (
        python -c "import yaml,sys; path='agent/config.yaml'; cfg=yaml.safe_load(open(path)) or {}; cfg['UPDATE_INTERVAL']=int(sys.argv[1]); open(path,'w').write(yaml.safe_dump(cfg))" "!interval!"
        echo [OK] Intervalle d'envoi mis a jour.
    )

    rem (no auth for agent)
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