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

- ⚙️ **Top 30 processus** par utilisation CPU
- 📈 **Détails complets** : PID, nom, CPU%, RAM%, état, utilisateur
- 🎯 **Visualisation** avec barres de progression

### Interface Moderne

- 🎨 **Design moderne** avec icônes de PC personnalisées
- 📊 **Graphiques interactifs** (Chart.js) : CPU, RAM, réseau, disque
- 📱 **Responsive** : s'adapte à tous les écrans
- 🎭 **Icônes distinctives** par PC avec badges de statut (hors ligne/ en ligne)
- 🕒 **Onglet Historique** pour visualiser les 24 h+
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

- Python 3.13.12 ou supérieur
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

> ⚠️ **Important** : le fichier de données `metrics.db` n'est **pas** inclus
> dans le dépôt. Il est généré automatiquement dans `server/db/metrics.db`
> lors du premier démarrage du serveur. Chaque utilisateur/clône aura sa
> propre base vide, et le fichier est ignoré par Git grâce au
> `.gitignore` ci‑dessous.
>
> Si vous avez commis ce fichier par mégarde et que le `git push` est refusé
> parce qu'il est trop volumineux, procédez ainsi avant de réessayer :
>
> ```bash
> git rm --cached server/db/metrics.db     # arrête le suivi sans supprimer
> git commit -m "Remove local database file"
> # nettoyer l'historique si nécessaire (ex : avec git-filter-repo ou BFG)
> # e.g. git filter-repo --path server/db/metrics.db --invert-paths
> git push --force origin main            # pousse l'historique modifié
> ```
>
> Ces commandes supprimeront le fichier de l'historique Git et débloqueront
> la mise à jour du dépôt distant. Vous pouvez ensuite démarrer le serveur
> normalement et un nouveau `metrics.db` vide sera créé localement.

---

## 🔧 Configuration

### Serveur — `server/config.py`

| Paramètre              | Défaut      | Description                                                              |
| ---------------------- | ----------- | ------------------------------------------------------------------------ |
| `SERVER_HOST`          | `"0.0.0.0"` | Interface d'écoute (`0.0.0.0` = toutes)                                  |
| `SERVER_PORT`          | `5000`      | Port du serveur web                                                      |
| `ALLOWED_AGENT_IPS`    | `[]`        | IPs autorisées pour les agents (vide = toutes)                           |
| `ALLOWED_CLIENT_IPS`   | `[]`        | IPs autorisées pour le navigateur (vide = toutes)                        |
| `ENABLE_AUTH`          | `False`     | Activer l'authentification par token                                     |
| `AUTH_TOKEN`           | `"..."`     | Token secret si `ENABLE_AUTH = True`                                     |
| `TIMEOUT`              | `60`        | Secondes avant de marquer un agent hors ligne (carte conservée en rouge) |
| `CPU_ALERT_THRESHOLD`  | `90`        | Seuil CPU (%) pour générer une alerte (voir aussi CPU_ALERT_DURATION)    |
| `CPU_ALERT_DURATION`   | `30`        | Durée en secondes au-delà du seuil CPU pour déclencher l'alerte          |
| `RAM_ALERT_THRESHOLD`  | `95`        | Seuil RAM (%) déclenchant une alerte instantanée                         |
| `DISK_ALERT_THRESHOLD` | `100`       | Seuil disque (%) déclenchant une alerte instantanée                      |

### Accès à l'historique

Vous pouvez interroger les métriques enregistrées dans la base SQLite via l'API :

```
GET /api/history/{hostname}?hours=24
```

Le paramètre `hours` fixe la durée (en heures) de l'historique retourné. La réponse contient un tableau `history` de points horodatés utilisé par l'interface Web pour tracer les courbes CPU/RAM/DISK.

> Exemple : `/api/history/WORKSTATION-01?hours=72` renverra les derniers trois jours de données.

L'interface principale du dashboard propose désormais deux contrôles importants dans la barre latérale :

- **Activité** : permet de visualiser l'historique d'un agent sans ouvrir la modale (1 h/4 h/24 h/7 j).
- **Notifications** : affiche toutes les alertes reçues, organisées par agent et par jour. Les messages envoyés par le serveur sont archivés jusqu'à ce que la page soit rafraîchie.

Ces deux vues remplacent dynamiquement le contenu principal et un clic sur **Dashboard** ou **Agents** revient à l'affichage de la grille habituelle.

_Lorsque le serveur ne reçoit plus de métriques pendant la durée de `TIMEOUT`, l'agent est simplement marqué comme **hors ligne** : sa carte reste visible, un badge rouge apparaît et le serveur envoie une alerte aux clients connectés._

| `PROCESS_LIMIT` | `100` | Nombre max de processus remontés |
| `NETWORK_CONN_LIMIT` | `100` | Nombre max de connexions réseau remontées |

### Agent — `agent/config.py`

| Paramètre            | Défaut              | Description                                 |
| -------------------- | ------------------- | ------------------------------------------- |
| `SERVER_IP`          | `"192.168.188.120"` | IP du serveur central à atteindre           |
| `SERVER_PORT`        | `5000`              | Port du serveur central                     |
| `UPDATE_INTERVAL`    | `1`                 | Intervalle d'envoi des données (secondes)   |
| `ENABLE_AUTH`        | `False`             | Activer l'authentification par token        |
| `AUTH_TOKEN`         | `"..."`             | Token secret si `ENABLE_AUTH = True`        |
| `TIMEOUT`            | `10`                | Timeout de connexion vers le serveur        |
| `PROCESS_LIMIT`      | `100`               | Nombre max de processus à collecter         |
| `NETWORK_CONN_LIMIT` | `100`               | Nombre max de connexions réseau à collecter |

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
