# Installation et Configuration du Système de Monitoring

## Prérequis

- Python 3.13.12+
- pip ou uv

## Installation

### 1. Serveur

```bash
cd server
pip install -r requirements.txt
            ou
uv pip install requirements.txt
```

### 2. Agent

```bash
cd agent
pip install -r requirements.txt
            ou
uv pip install requirements.txt
```

## Configuration

### Configuration Serveur (`server/config.yaml`)

- `SERVER_HOST` : Interface d'écoute (0.0.0.0 pour toutes)
- `SERVER_PORT` : Port du serveur web
- `ALLOWED_AGENT_IPS` : Liste des IPs autorisées pour les agents (vide = toutes)
- `ALLOWED_CLIENT_IPS` : Liste des IPs autorisées pour les clients web (vide = toutes)

### Configuration Agent (`agent/config.yaml`)

- `SERVER_IP` : Adresse IP du serveur central
- `SERVER_PORT` : Port du serveur
- `UPDATE_INTERVAL` : Fréquence d'envoi des données (en secondes)

## Déploiement

### Démarrage du Serveur

```bash
cd server
python server.py --mode web
```

### Démarrage de l'Agent

Sur chaque machine à monitorer :

```bash
cd agent
python agent.py
```

**Note** : L'admin système peut modifier directement les fichiers `config.yaml` pour configurer l'application selon ses besoins.

## Ports utilisés

- Serveur : Port configuré (défaut 5000)
- Agent : Port 8080 (pour le ping de fallback)
