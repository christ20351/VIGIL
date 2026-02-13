## 📖 Documentation (README.md)

```markdown
# 🖥️ Système de Monitoring Centralisé v2.0

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0-orange)](CHANGELOG.md)

Un système de monitoring puissant et simple pour surveiller plusieurs ordinateurs depuis une interface web centrale.

![Dashboard](docs/screenshots/dashboard.png)

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

## 📋 Prérequis

- Python 3.7 ou supérieur
- Connexion réseau entre les machines
- Ports : 5000 (serveur)

## 🚀 Installation Rapide

### Option 1 : Script automatique (Recommandé)

**Linux/Mac :**
```bash
git clone https://github.com/votreusername/monitoring-system.git
cd monitoring-system
chmod +x install.sh
./install.sh

**Windows :**
```cmd
git clone https://github.com/votreusername/monitoring-system.git
cd monitoring-system
install.bat
```

### Option 2 : Installation manuelle

1. **Cloner le projet**
   ```bash
   git clone https://github.com/votreusername/monitoring-system.git
   cd monitoring-system
   ```

2. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurer**
   ```bash
   cp config.example.py server/config.py  # Pour le serveur
   cp config.example.py agent/config.py   # Pour les agents
   ```

4. **Modifier la configuration**
   - Éditez `agent/config.py`
   - Changez `SERVER_IP = "192.168.1.10"` avec l'IP de votre serveur

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

## 📚 Guide de Déploiement

### Scénario : Entreprise avec 1 serveur + 20 PC

#### Étape 1 : Serveur Central

1. Choisir un PC toujours allumé
2. Installer le serveur :
   ```bash
   ./install.sh
   # Choisir option 1 (Serveur)
   ```
3. Noter l'IP affichée (ex: `192.168.1.100`)
4. Ouvrir le port 5000 :
   ```bash
   sudo ufw allow 5000/tcp  # Linux
   # ou dans Pare-feu Windows
   ```
5. Accéder à `http://192.168.1.100:5000`

#### Étape 2 : Agents

Sur chaque PC à surveiller :
```bash
./install.sh
# Choisir option 2 (Agent)
# Entrer l'IP du serveur : 192.168.1.100
```

#### Étape 3 : Vérification

- Ouvrir `http://192.168.1.100:5000`
- Tous les PC doivent apparaître avec leurs icônes
- Cliquer sur "📊 Détails" pour voir les graphiques

## 🔧 Configuration Avancée

### Changer l'intervalle de mise à jour

Dans `agent/config.py` :
```python
UPDATE_INTERVAL = 5  # Mise à jour toutes les 5 secondes
```

### Limiter les IPs autorisées

Dans `server/server.py`, ajouter avant `@app.route('/update')` :
```python
ALLOWED_IPS = ['192.168.1.20', '192.168.1.21', '192.168.1.22']
