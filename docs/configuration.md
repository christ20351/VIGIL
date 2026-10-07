# ⚙️ Configuration VIGIL — Référence administrateur

Tous les réglages sont modifiables **à chaud** depuis l'interface web
(Paramètres → Enregistrer) ou en éditant `server/config.yaml` (rechargé
automatiquement, sans redémarrage). Rien n'est figé dans le code.

> 🤖 L'assistant IA de VIGIL s'appelle **Vili** (modèle GLM de Z.ai par
> défaut). Vili lit toutes les données de la base, notifie le dashboard
> administrateur et peut agir sur les machines (voir « Autonomie Vili »).

---

## 🌐 Réseau & serveur

| Clé | Défaut | Description |
|---|---|---|
| `SERVER_HOST` | `0.0.0.0` | Interface d'écoute |
| `SERVER_PORT` | `5000` | Port HTTP/WS |
| `ALLOWED_AGENT_IPS` | `[]` | Liste blanche IP des agents (vide = toutes) |
| `ALLOWED_CLIENT_IPS` | `[]` | Liste blanche IP des navigateurs (vide = toutes) |

## 🔐 Sécurité

| Clé | Défaut | Description |
|---|---|---|
| `ENABLE_AUTH` | `false` | Active l'authentification (login web + token agents) |
| `AUTH_TOKEN` | — | Token secret partagé serveur ↔ agents. **Obligatoire dès que `ENABLE_AUTH=true`** : un agent sans token valide est refusé |
| `SESSION_TTL_HOURS` | `168` | Durée de vie des sessions web (0 = illimité) |
| `COOKIE_SECURE` | `false` | Cookies `Secure` — activer uniquement derrière HTTPS/TLS |
| `LOGIN_MAX_ATTEMPTS` | `10` | Échecs de login tolérés par IP / 5 min avant blocage |

> ⚠️ La clé `AI_API_KEY` n'est **jamais** renvoyée en clair par l'API
> (masquée `gsk_...XXXX`). Laisser le champ vide dans l'interface conserve
> la clé actuelle.

## ⚡ Performance & stockage

| Clé | Défaut | Description |
|---|---|---|
| `METRICS_STORAGE_INTERVAL` | `5` | Pas minimum entre deux lignes BD par machine (1 = tout stocker) |
| `METRICS_DETAIL_INTERVAL` | `60` | Fréquence d'une ligne « détail » complète (processus, SMART…) |
| `RETENTION_DAYS` | `30` | Rétention des métriques |
| `NOTIFICATION_RETENTION_DAYS` | `90` | Rétention des notifications et diagnostics IA |
| `PRUNE_INTERVAL_MINUTES` | `60` | Intervalle entre deux purges |
| `BROADCAST_FULL_DETAIL` | `false` | `false` = flux navigateur allégé (recommandé au-delà de ~5 machines) ; `true` = payload complet chaque seconde |
| `TIMEOUT` | `60` | Secondes de silence WebSocket avant marquage hors-ligne d'un agent |

Endpoint de maintenance : `POST /api/settings/vacuum` — compacte la base
(VACUUM) pour récupérer l'espace disque après de grosses purges.

## 🗄️ Base de données (SQLite / PostgreSQL)

| Clé | Défaut | Description |
|---|---|---|
| `DB_BACKEND` | `sqlite` | `sqlite` (local) ou `postgres` (production) |
| `DB_HOST` / `DB_PORT` | `localhost` / `5432` | Accès PostgreSQL |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `vigil` / `vigil` / — | Identifiants (mot de passe jamais affiché en clair) |

Migration PostgreSQL :

```bash
# 1. Créer la base et l'utilisateur (sur le serveur PG)
createuser vigil && createdb vigil -O vigil

# 2. Installer le driver dans le venv serveur
sudo server/.venv/bin/pip install psycopg2-binary

# 3. Dans Paramètres → Base de données : choisir PostgreSQL,
#    renseigner hôte/base/utilisateur/mot de passe puis redémarrer.
```

Le schéma est créé automatiquement au démarrage. Si PostgreSQL est
indisponible, le serveur **repli automatique sur SQLite** (message dans
les logs) — aucune perte de données, la base locale continue d'écrire.

## 🖥️ Terminal distant (dashboard → agents)

| Clé | Défaut | Description |
|---|---|---|
| `AGENT_COMMANDS_ENABLED` | `false` | Active l'exécution de commandes système depuis l'onglet **Terminal** de chaque machine |
| `AGENT_COMMAND_TIMEOUT` | `60` | Durée max d'exécution (s) |

Onglet **Terminal** dans la fiche d'un agent : tapez une commande, elle
s'exécute sur la machine avec les droits du service agent (root si
installé en service système) et la sortie s'affiche dans le dashboard.

> ⚠️ **Sécurité** : activez impérativement `ENABLE_AUTH` avant d'ouvrir
> les commandes à distance sur un réseau non totalement maîtrisé — sinon
> n'importe qui sur le réseau peut exécuter des commandes sur vos machines.

## 🤖 Autonomie de Vili

| Clé | Défaut | Description |
|---|---|---|
| `AI_SCAN_INTERVAL` | `300` | Rythme des cycles d'analyse complète (s) |
| `AI_AUTONOMOUS_ACTIONS` | `propose` | `off` / `propose` / `auto` (voir ci-dessous) |

À chaque cycle, Vili analyse **toutes** les données (métriques live,
historiques, alertes, incidents) puis :

- `off` — notifie le dashboard (analyses et alertes précoces) ;
- `propose` — suggère en plus des **commandes correctives**, exécutables
  en un clic depuis les rapports IA ;
- `auto` — exécute lui-même ses commandes sur les agents (résultat
  notifié sur le dashboard). Garde-fous intégrés : commandes
  destructrices (rm -rf /, mkfs, shutdown, reboot…) automatiquement
  converties en simples propositions, 5 actions max par cycle,
- le cycle rapide règle-based (30 s) reste actif en parallèle, même
  sans LLM configuré.

## 🚨 Seuils d'alerte

| Clé | Défaut | Description |
|---|---|---|
| `CPU_ALERT_THRESHOLD` / `CPU_ALERT_DURATION` | `90` / `25` | CPU % et durée de maintien avant alerte |
| `RAM_ALERT_THRESHOLD` | `95` | RAM % |
| `DISK_ALERT_THRESHOLD` | `90` | Disque % |
| `HDD_SMART_ENABLED` | `true` | Surveillance S.M.A.R.T. |
| `HDD_TEMP_WARNING` / `HDD_TEMP_CRITICAL` | `45` / `55` | Seuils température disques (°C) |

## 🤖 IA & Copilote

| Clé | Défaut | Description |
|---|---|---|
| `AI_ENABLED` | `true` | Active les fonctions IA |
| `AI_PROVIDER` | `auto_rule` | `glm`, `ollama`, `groq`, `openrouter`, `deepseek`, `openai` ou `auto_rule` |
| `AI_MODEL` | selon provider | GLM : `glm-4.6`, `glm-4.5-air`… |
| `AI_ENDPOINT` | selon provider | GLM/Z.ai : `https://api.z.ai/api/paas/v4` |
| `AI_API_KEY` | — | Clé du fournisseur (GLM : clé de l'abonnement Z.ai) |
| `AI_TIMEOUT` | `60` | Timeout des appels LLM (s) |
| `AI_RATE_LIMIT_PER_MIN` | `20` | Max requêtes chat IA / IP / min (0 = illimité) |

### Configurer GLM (Z.ai)

1. Interface → **Paramètres → IA & Copilote**
2. Provider : **GLM — Z.ai**
3. Coller la clé de l'abonnement dans « Clé API » (laisser vide pour
   conserver l'actuelle)
4. Modèle : `glm-4.6` (défaut) ou `glm-4.5-air` (plus rapide)
5. **Tester la connexion IA** puis Enregistrer

## 🧠 Intelligence Vili (AIOps)

| Clé | Défaut | Description |
|---|---|---|
| `ANOMALY_Z_THRESHOLD` | `3.0` | Écart (σ) au-delà duquel une valeur est anormale vs baseline horaire |
| `FORECAST_WINDOW_HOURS` | `48` | Fenêtre d'apprentissage des prévisions de saturation |
| `STORM_MIN_HOSTS` | `3` | Machines distinctes alertant ensemble → tempête d'incidents |
| `STORM_WINDOW_MIN` | `10` | Fenêtre (min) de corrélation des alertes |
| `WATCH_RULE_COOLDOWN` | `600` | Anti-spam des règles de surveillance (s) |
| `DAILY_REPORT_ENABLED` | `true` | Rapport quotidien automatique de Vili |
| `DAILY_REPORT_HOUR` | `8` | Heure d'envoi du rapport quotidien |

### Ce que fait la couche d'intelligence

- **Baselines apprises** : Vili apprend le comportement normal de chaque
  machine par créneau de 6 h (CPU, RAM, réseau) et détecte les écarts
  statistiques (« cette machine fait 60 % de CPU à 3 h du matin alors
  que sa normale est 20 % »).
- **Prévisions de saturation** : régression sur la fenêtre configurée →
  « disque plein dans ~0,7 jour au rythme actuel », affiché dans le
  panneau Intelligence et notifié si l'échéance est < 24 h.
- **Détections de dégradation** : moyenne 6 h vs 48 h précédentes.
- **Corrélation d'incidents** : plusieurs machines alertant ensemble →
  cause racine commune probable.
- **Scan réactif** : dès qu'une anomalie/tempête/saturation urgente est
  détectée, Vili est convoqué immédiatement (cooldown 15 min) sans
  attendre le cycle complet.

### Règles de surveillance en langage naturel

Tape dans le chat Vili : *« surveille la RAM de web-01 et préviens-moi
si ça dépasse 80 % pendant 5 minutes »*. La règle est installée, évaluée
toutes les 30 s, avec anti-spam. Liste et suppression : onglet IA, ou
API `GET/DELETE /api/ai/watch/{id}`.

### Rapport quotidien

Généré chaque jour à `DAILY_REPORT_HOUR` : synthèse exécutive,
incidents 24 h, anomalies/tendances, prévisions, recommandations
priorisées. Disponible dans les rapports IA ; déclenchable à la main
(bouton « Générer le rapport quotidien »).

## 🛡️ Écran Sécurité

`GET /api/security/status` expose la posture : score /100 (jauge),
6 contrôles pondérés (auth, commandes sans auth, listes blanches,
sessions, HTTPS), journal des événements (connexions refusées, agents
rejetés, commandes distantes exécutées) et machines connectées.
Événements retenus en mémoire (`SECURITY_EVENT_LOG_SIZE`, 200 par
défaut).

## 🖥️ Côté agent (`agent/agent_config.json`)

| Clé | Défaut | Description |
|---|---|---|
| `UPDATE_INTERVAL` | `1` | Rythme d'envoi des métriques cœur (CPU/RAM/disque/réseau) |
| `PROCESSES_INTERVAL` | `10` | Rythme de collecte des processus |
| `CONNECTIONS_INTERVAL` | `10` | Rythme de collecte des connexions réseau |
| `INTERFACES_INTERVAL` | `30` | Rythme de collecte des interfaces |
| `SMART_INTERVAL` | `300` | Rythme d'interrogation S.M.A.R.T. (smartctl) |
| `LOG_EVERY` | `10` | 1 ligne de console sur N cycles |
| `PRIVILEGED_EXECUTION` | `true` | Exécute les commandes distantes en mode privilégié : préfixe `sudo -n` sous Linux/macOS si l'agent n'est pas root. Nécessite un sudoers NOPASSWD pour l'utilisateur de l'agent, ou un agent lancé via sudo. Sous Windows, lancer l'agent en session Administrateur. Mettre `false` pour exécuter avec les droits de l'agent uniquement. |

Le serveur recolle automatiquement les dernières valeurs connues : la vue
temps réel reste complète même avec des collectes espacées.

## 🗺️ Parc & Sites — architecture distribuée

### Groupes de machines

Affectez chaque machine à un groupe/site (ex : Production, DMZ, Agence
Lyon) depuis l'onglet **Parc & Sites → Groupes** (ou
`POST /api/computers/{host}/group {"group": "..."}` — stocké dans la
table `agent_meta`).

### Inventaire automatique

Chaque agent remonte son profil (OS, noyau, CPU, RAM, disques, IP/MAC,
uptime, version agent) au démarrage puis toutes les 6 h
(`INVENTORY_INTERVAL` dans `agent_config.json`). Consultation et **export
CSV** : Parc & Sites → Inventaire. API : `/api/inventory`,
`/api/inventory/export/csv`.

### Fenêtres de maintenance

Silence les alertes d'une machine pendant N minutes
(`POST /api/computers/{host}/maintenance {"minutes": 60}`,
`DELETE` pour annuler) : plus d'insertion, de diffusion ni de dispatch
sortant pendant la fenêtre. Badge « maintenance » sur la carte.

### Alertes sortantes (Paramètres → Alertes sortantes & Fédération)

- **Webhook** : `ALERT_WEBHOOK_ENABLED` + `ALERT_WEBHOOK_URL` — chaque
  alerte est poussée en JSON (`{event, hostname, message, severity,
  timestamp}`) vers Slack/Teams/n8n… via une file non bloquante.
- **Email** : `ALERT_EMAIL_ENABLED` + serveur SMTP, port, TLS,
  identifiants, expéditeur et destinataires (séparés par des virgules).
- **Sévérité minimale** : `ALERT_MIN_SEVERITY` (info/warning/error).
- Boutons « Tester le webhook / l'email » : sauvegardent la config
  puis envoient un message de test.

### Fédération multi-sites

1. Sur **chaque serveur distant** : `FEDERATION_TOKEN` (secret partagé)
   et `FEDERATION_SITE_NAME`.
2. Sur le **serveur central** : `FEDERATION_PEERS` — une ligne par site :
   `nom | url | token` (Paramètres, ou config.yaml en YAML liste).
3. La vue **Parc & Sites → Fédération** agrège les machines de tous les
   sites (état, CPU/RAM/disque, alertes 24 h, groupes) avec compteurs
   globaux. Endpoint exposé par chaque site : `GET /api/federation/summary`
   avec le header `X-Fed-Token`.
