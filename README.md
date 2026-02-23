# 🖥️ Système de Monitoring Centralisé v2.0

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0-orange)](CHANGELOG.md)

Un système de monitoring puissant et simple pour surveiller plusieurs ordinateurs depuis une interface web centrale.

![Dashboard](docs/screenshots/dashboard.png)

---

## ✨ Fonctionnalités v2.0

### Monitoring Système
- 📊 **Métriques en temps réel** : CPU, RAM, Disque
- 🌐 **Trafic réseau** : Upload/Download avec vitesse instantanée
- 💻 **Vue détaillée** avec graphiques interactifs

### Surveillance Réseau Avancée
- 📡 **Protocoles réseau** : TCP (ESTABLISHED, LISTEN, TIME_WAIT, CLOSE_WAIT) et UDP
- 🔗 **Connexions actives** : Liste détaillée avec IP locales/distantes, états, PID
- 🌐 **Interfaces réseau** : IPv4, IPv6, vitesse, état actif/inactif

### Processus
- ⚙️ **Top 10 processus** par utilisation CPU
- 📈 **Détails complets** : PID, nom, CPU%, RAM%, état, utilisateur
- 🎯 **Visualisation** avec barres de progression

### Interface Moderne
- 🎨 **Design moderne** avec icônes de PC personnalisées
- 📊 **Graphiques interactifs** (Chart.js) : CPU, RAM, réseau, disque
- 📱 **Responsive** : s'adapte à tous les écrans
- 🎭 **Icônes distinctives** par PC avec badges de statut
- ⚡ **Animations fluides** et transitions

---

## 🎯 Architecture

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Agent     │─────▶│   Serveur   │◀─────│   Agent     │
│  (PC 1)     │  2s  │   Central   │  2s  │  (PC 2)     │
└─────────────┘      └─────────────┘      └─────────────┘
                            │
                            ▼
                     Interface Web
                   http://IP:5000
```

---

## 📋 Prérequis

- Python 3.7 ou supérieur
- Connexion réseau entre les machines
- Ports : 5000 (serveur)

---

## 🚀 Installation Rapide

### Option 1 : Script automatique (Recommandé)

**Linux/Mac :**
```bash
git clone https://github.com/christ20351/VIGIL.git
cd VIGIL
chmod +x install.sh
./install.sh
```

**Windows :**
```cmd
git clone https://github.com/christ20351/VIGIL.git
cd VIGIL
install.bat
```

### Option 2 : Installation manuelle

1. **Cloner le projet**
   ```bash
   git clone https://github.com/christ20351/VIGIL.git
   cd VIGIL
   ```

2. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurer**
   ```bash
   cp config.py server/config.py  # Pour le serveur
   cp config.py agent/config.py   # Pour les agents
   ```

4. **Modifier la configuration**
   - Éditez `agent/config.py`
   - Changez `SERVER_IP = "x.x.x.x"` avec l'IP de votre serveur

5. **Lancer**

   **Serveur :**
   ```bash
   cd server
   python server.py
   ```

   **Agent (Linux avec sudo pour accès réseau complet) :**
   ```bash
   cd agent
   sudo python agent.py
   ```

   **Agent (Windows - Exécuter en tant qu'Administrateur) :**
   ```cmd
   cd agent
   python agent.py
   ```

---

## 🔧 Configuration

### Serveur — `server/config.py`

| Paramètre | Défaut | Description |
|---|---|---|
| `SERVER_HOST` | `"0.0.0.0"` | Interface d'écoute (`0.0.0.0` = toutes) |
| `SERVER_PORT` | `5000` | Port du serveur web |
| `ALLOWED_AGENT_IPS` | `[]` | IPs autorisées pour les agents (vide = toutes) |
| `ALLOWED_CLIENT_IPS` | `[]` | IPs autorisées pour le navigateur (vide = toutes) |
| `ENABLE_AUTH` | `False` | Activer l'authentification par token |
| `AUTH_TOKEN` | `"..."` | Token secret si `ENABLE_AUTH = True` |
| `TIMEOUT` | `60` | Secondes avant de marquer un agent hors ligne |
| `PROCESS_LIMIT` | `100` | Nombre max de processus remontés |
| `NETWORK_CONN_LIMIT` | `100` | Nombre max de connexions réseau remontées |

### Agent — `agent/config.py`

| Paramètre | Défaut | Description |
|---|---|---|
| `SERVER_IP` | `"192.168.188.120"` | IP du serveur central à atteindre |
| `SERVER_PORT` | `5000` | Port du serveur central |
| `UPDATE_INTERVAL` | `1` | Intervalle d'envoi des données (secondes) |
| `ENABLE_AUTH` | `False` | Activer l'authentification par token |
| `AUTH_TOKEN` | `"..."` | Token secret si `ENABLE_AUTH = True` |
| `TIMEOUT` | `10` | Timeout de connexion vers le serveur |
| `PROCESS_LIMIT` | `100` | Nombre max de processus à collecter |
| `NETWORK_CONN_LIMIT` | `100` | Nombre max de connexions réseau à collecter |

---

## 📚 Guide de Déploiement

### Scénario : Entreprise avec 1 serveur + 20 PC

#### Étape 1 : Serveur Central

1. Choisir un PC toujours allumé
2. Installer le serveur :
   ```bash
   ./install.sh
   # Choisir option 1 (Serveur)
   ```
3. Noter l'IP affichée (ex: `x.x.x.x`)
4. Ouvrir le port du serveur que vous avez défini (ex : port 5000) :
   ```bash
   sudo ufw allow 5000/tcp  # Linux
   # ou dans Pare-feu Windows
   ```
5. Accéder à `http://x.x.x.x:5000`

#### Étape 2 : Agents

Sur chaque PC à surveiller :
```bash
./install.sh
# Choisir option 2 (Agent)
# Entrer l'IP du serveur : x.x.x.x
```

#### Étape 3 : Vérification

- Ouvrir `http://x.x.x.x:5000`
- Tous les PC doivent apparaître avec leurs icônes
- Cliquer sur "📊 Détails" pour voir les graphiques

---

## 🔧 Configuration Avancée

### Changer l'intervalle de mise à jour

Dans `agent/config.py` :
```python
UPDATE_INTERVAL = T  # Mise à jour toutes les T secondes
```

### Limiter les IPs autorisées

Dans `server/server.py`, ajouter avant `@app.route('/update')` :
```python
ALLOWED_IPS = ['x.x.x.x', 'w.w.w.w', 'y.y.y.y']
```