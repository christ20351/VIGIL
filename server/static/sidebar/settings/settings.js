/**
 * VIGIL — settings.js
 * Écran Paramètres : navigation à sections, suivi des modifications,
 * enregistrement Ctrl+S. Cohérent avec le design system VIGIL.
 */

function renderSettingsView() {
  vigilFetch("/api/settings")
    .then((res) => res.json())
    .then((cfg) => {
      const fmtArr = (arr) => (Array.isArray(arr) ? arr.join(", ") : "");

      document.querySelector(".content").innerHTML = `
        <div class="settings-app">

          <!-- Barre d'actions collante -->
          <div class="settings-topbar">
            <div class="settings-topbar-left">
              <div class="settings-topbar-title">
                <span class="settings-topbar-ico"><i data-lucide="settings-2"></i></span>
                Paramètres du serveur
              </div>
              <div class="settings-topbar-sub">La configuration est appliquée immédiatement après enregistrement</div>
            </div>
            <div class="settings-dirty" id="settings-dirty" hidden>
              <span class="dirty-dot"></span> Modifications non enregistrées
            </div>
            <div class="settings-actions">
              <button class="settings-btn settings-btn-secondary" id="btn-reset" type="button" title="Restaurer la dernière sauvegarde">
                <i data-lucide="rotate-ccw"></i>
                <span class="btn-label">Réinitialiser</span>
              </button>
              <button class="settings-btn settings-btn-primary" id="btn-save-top" type="button" title="Enregistrer (Ctrl+S)">
                <i data-lucide="save"></i>
                <span class="btn-label">Enregistrer</span>
                <span class="settings-btn-spinner"></span>
              </button>
            </div>
          </div>

          <div class="settings-layout">
            <!-- Rail de navigation -->
            <nav class="settings-rail" id="settings-rail" aria-label="Sections des paramètres"></nav>

            <form id="settings-form" class="settings-panes" novalidate>

              <!-- ── SERVEUR ── -->
              <section class="set-section" id="sec-serveur">
                <header class="set-head">
                  <div class="set-icon"><i data-lucide="server"></i></div>
                  <div class="set-head-text">
                    <h2>Serveur</h2>
                    <p>Écoute réseau et cycle de vie des agents</p>
                  </div>
                </header>
                <div class="set-body set-grid-2">
                  <div class="set-field">
                    <label class="set-label" for="SERVER_HOST">Hôte d'écoute</label>
                    <input class="set-input" id="SERVER_HOST" type="text" name="SERVER_HOST"
                           value="${cfg.SERVER_HOST || ""}" placeholder="0.0.0.0" />
                    <span class="set-hint">0.0.0.0 pour écouter sur toutes les interfaces</span>
                  </div>
                  <div class="set-field">
                    <label class="set-label" for="SERVER_PORT">Port</label>
                    <input class="set-input" id="SERVER_PORT" type="number" name="SERVER_PORT"
                           value="${cfg.SERVER_PORT || ""}" placeholder="5000" min="1" max="65535" />
                    <span class="set-hint">Port HTTP du dashboard et de l'API agents</span>
                  </div>
                  <div class="set-field">
                    <label class="set-label" for="TIMEOUT">Timeout agent <em>secondes</em></label>
                    <input class="set-input" id="TIMEOUT" type="number" name="TIMEOUT"
                           value="${cfg.TIMEOUT || 60}" placeholder="60" min="1" />
                    <span class="set-hint">Délai avant de marquer un agent hors ligne</span>
                  </div>
                </div>
              </section>

              <!-- ── SÉCURITÉ ── -->
              <section class="set-section" id="sec-securite">
                <header class="set-head">
                  <div class="set-icon"><i data-lucide="shield"></i></div>
                  <div class="set-head-text">
                    <h2>Sécurité</h2>
                    <p>Authentification, accès et commandes à distance</p>
                  </div>
                </header>
                <div class="set-body set-stack">
                  <div class="set-field">
                    <label class="set-label" for="AUTH_TOKEN">Token secret des agents</label>
                    <div class="set-input-group">
                      <input class="set-input" id="AUTH_TOKEN" type="password" name="AUTH_TOKEN"
                             placeholder="Laisser vide pour conserver l'actuel"
                             autocomplete="new-password" oncopy="return false" oncut="return false" />
                      <button type="button" class="set-input-btn" id="toggle-token" title="Afficher / masquer">
                        <svg id="token-eye" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                        </svg>
                      </button>
                    </div>
                    <span class="set-hint">Vide = token actuel conservé</span>
                  </div>

                  <label class="set-toggle">
                    <div class="set-toggle-text">
                      <span class="set-toggle-label">Authentification activée</span>
                      <span class="set-toggle-desc">Exige un token sur chaque requête agent — fortement recommandé</span>
                    </div>
                    <span class="set-switch">
                      <input type="checkbox" name="ENABLE_AUTH" id="ENABLE_AUTH" ${cfg.ENABLE_AUTH ? "checked" : ""} />
                      <span class="set-switch-slider"></span>
                    </span>
                  </label>

                  <label class="set-toggle">
                    <div class="set-toggle-text">
                      <span class="set-toggle-label">Commandes à distance sur les agents</span>
                      <span class="set-toggle-desc">Terminal du dashboard → agents. Dangereux sans auth sur un réseau ouvert</span>
                    </div>
                    <span class="set-switch">
                      <input type="checkbox" name="AGENT_COMMANDS_ENABLED" id="AGENT_COMMANDS_ENABLED" ${cfg.AGENT_COMMANDS_ENABLED ? "checked" : ""} />
                      <span class="set-switch-slider"></span>
                    </span>
                  </label>

                  <div class="set-grid-2">
                    <div class="set-field">
                      <label class="set-label" for="AGENT_COMMAND_TIMEOUT">Timeout commandes <em>secondes</em></label>
                      <input class="set-input" id="AGENT_COMMAND_TIMEOUT" type="number" name="AGENT_COMMAND_TIMEOUT"
                             value="${cfg.AGENT_COMMAND_TIMEOUT ?? 60}" placeholder="60" min="5" max="600" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="LOGIN_MAX_ATTEMPTS">Max tentatives de login</label>
                      <input class="set-input" id="LOGIN_MAX_ATTEMPTS" type="number" name="LOGIN_MAX_ATTEMPTS"
                             value="${cfg.LOGIN_MAX_ATTEMPTS ?? 10}" placeholder="10" min="1" />
                      <span class="set-hint">Par IP sur 5 min avant blocage temporaire</span>
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="SESSION_TTL_HOURS">Durée de session <em>heures</em></label>
                      <input class="set-input" id="SESSION_TTL_HOURS" type="number" name="SESSION_TTL_HOURS"
                             value="${cfg.SESSION_TTL_HOURS ?? 168}" placeholder="168" min="0" />
                      <span class="set-hint">0 = illimitée — défaut 168 h (7 jours)</span>
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="COOKIE_SECURE">Cookies Secure</label>
                      <div class="set-toggle-inline">
                        <span class="set-switch set-switch-sm">
                          <input type="checkbox" name="COOKIE_SECURE" id="COOKIE_SECURE" ${cfg.COOKIE_SECURE ? "checked" : ""} />
                          <span class="set-switch-slider"></span>
                        </span>
                        <span class="set-hint" style="margin:0;">Uniquement derrière un reverse-proxy TLS</span>
                      </div>
                    </div>
                  </div>

                  <div class="set-field">
                    <label class="set-label" for="ALLOWED_AGENT_IPS">IPs agents autorisées</label>
                    <textarea class="set-input set-textarea" id="ALLOWED_AGENT_IPS" name="ALLOWED_AGENT_IPS" rows="2"
                              placeholder="192.168.1.10, 192.168.1.20 — vide = toutes autorisées">${fmtArr(cfg.ALLOWED_AGENT_IPS)}</textarea>
                  </div>
                  <div class="set-field">
                    <label class="set-label" for="ALLOWED_CLIENT_IPS">IPs navigateurs autorisées</label>
                    <textarea class="set-input set-textarea" id="ALLOWED_CLIENT_IPS" name="ALLOWED_CLIENT_IPS" rows="2"
                              placeholder="192.168.1.100, 192.168.1.101 — vide = toutes autorisées">${fmtArr(cfg.ALLOWED_CLIENT_IPS)}</textarea>
                  </div>
                </div>
              </section>

              <!-- ── ALARMES ── -->
              <section class="set-section" id="sec-alarmes">
                <header class="set-head">
                  <div class="set-icon"><i data-lucide="bell-ring"></i></div>
                  <div class="set-head-text">
                    <h2>Alarmes</h2>
                    <p>Seuils de déclenchement des alertes</p>
                  </div>
                </header>
                <div class="set-body set-grid-2">
                  <div class="set-field">
                    <label class="set-label" for="CPU_ALERT_THRESHOLD">Seuil CPU <em>%</em></label>
                    <input class="set-input" id="CPU_ALERT_THRESHOLD" type="number" name="CPU_ALERT_THRESHOLD"
                           value="${cfg.CPU_ALERT_THRESHOLD || 90}" placeholder="90" min="1" max="100" />
                  </div>
                  <div class="set-field">
                    <label class="set-label" for="CPU_ALERT_DURATION">Durée CPU <em>secondes</em></label>
                    <input class="set-input" id="CPU_ALERT_DURATION" type="number" name="CPU_ALERT_DURATION"
                           value="${cfg.CPU_ALERT_DURATION || 30}" placeholder="30" min="1" />
                    <span class="set-hint">Alarme après N secondes en surcharge</span>
                  </div>
                  <div class="set-field">
                    <label class="set-label" for="RAM_ALERT_THRESHOLD">Seuil RAM <em>%</em></label>
                    <input class="set-input" id="RAM_ALERT_THRESHOLD" type="number" name="RAM_ALERT_THRESHOLD"
                           value="${cfg.RAM_ALERT_THRESHOLD || 90}" placeholder="90" min="1" max="100" />
                  </div>
                  <div class="set-field">
                    <label class="set-label" for="DISK_ALERT_THRESHOLD">Seuil disque <em>%</em></label>
                    <input class="set-input" id="DISK_ALERT_THRESHOLD" type="number" name="DISK_ALERT_THRESHOLD"
                           value="${cfg.DISK_ALERT_THRESHOLD || 85}" placeholder="85" min="1" max="100" />
                  </div>
                </div>
              </section>

              <!-- ── S.M.A.R.T. ── -->
              <section class="set-section" id="sec-smart">
                <header class="set-head">
                  <div class="set-icon"><i data-lucide="hard-drive"></i></div>
                  <div class="set-head-text">
                    <h2>Disques S.M.A.R.T.</h2>
                    <p>Santé des disques via smartctl</p>
                  </div>
                </header>
                <div class="set-body set-stack">
                  <label class="set-toggle">
                    <div class="set-toggle-text">
                      <span class="set-toggle-label">Monitoring S.M.A.R.T. activé</span>
                      <span class="set-toggle-desc">Surveille température, secteurs réalloués et santé globale</span>
                    </div>
                    <span class="set-switch">
                      <input type="checkbox" name="HDD_SMART_ENABLED" id="HDD_SMART_ENABLED" ${cfg.HDD_SMART_ENABLED ? "checked" : ""} />
                      <span class="set-switch-slider"></span>
                    </span>
                  </label>
                  <div class="set-grid-2">
                    <div class="set-field">
                      <label class="set-label" for="HDD_TEMP_WARNING">Température avertissement <em>°C</em></label>
                      <input class="set-input" id="HDD_TEMP_WARNING" type="number" name="HDD_TEMP_WARNING"
                             value="${cfg.HDD_TEMP_WARNING || 45}" placeholder="45" min="20" max="100" />
                      <span class="set-hint">Alerte jaune au-dessus de ce seuil</span>
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="HDD_TEMP_CRITICAL">Température critique <em>°C</em></label>
                      <input class="set-input" id="HDD_TEMP_CRITICAL" type="number" name="HDD_TEMP_CRITICAL"
                             value="${cfg.HDD_TEMP_CRITICAL || 55}" placeholder="55" min="20" max="100" />
                      <span class="set-hint">Alerte rouge au-dessus de ce seuil</span>
                    </div>
                  </div>
                </div>
              </section>

              <!-- ── MONITORING ── -->
              <section class="set-section" id="sec-monitoring">
                <header class="set-head">
                  <div class="set-icon"><i data-lucide="activity"></i></div>
                  <div class="set-head-text">
                    <h2>Monitoring</h2>
                    <p>Volume de données remontées par les agents</p>
                  </div>
                </header>
                <div class="set-body set-grid-2">
                  <div class="set-field">
                    <label class="set-label" for="PROCESS_LIMIT">Limite processus</label>
                    <input class="set-input" id="PROCESS_LIMIT" type="number" name="PROCESS_LIMIT"
                           value="${cfg.PROCESS_LIMIT || 100}" placeholder="100" min="1" max="500" />
                    <span class="set-hint">Nombre max de processus par relevé</span>
                  </div>
                  <div class="set-field">
                    <label class="set-label" for="NETWORK_CONN_LIMIT">Limite connexions réseau</label>
                    <input class="set-input" id="NETWORK_CONN_LIMIT" type="number" name="NETWORK_CONN_LIMIT"
                           value="${cfg.NETWORK_CONN_LIMIT || 100}" placeholder="100" min="1" max="1000" />
                    <span class="set-hint">Nombre max de connexions par relevé</span>
                  </div>
                </div>
              </section>

              <!-- ── PERFORMANCE & STOCKAGE ── -->
              <section class="set-section" id="sec-perf">
                <header class="set-head">
                  <div class="set-icon"><i data-lucide="database-zap"></i></div>
                  <div class="set-head-text">
                    <h2>Performance &amp; stockage</h2>
                    <p>Cadence d'enregistrement et rétention en base</p>
                  </div>
                </header>
                <div class="set-body set-stack">
                  <div class="set-grid-2">
                    <div class="set-field">
                      <label class="set-label" for="METRICS_STORAGE_INTERVAL">Pas d'enregistrement <em>secondes</em></label>
                      <input class="set-input" id="METRICS_STORAGE_INTERVAL" type="number" name="METRICS_STORAGE_INTERVAL"
                             value="${cfg.METRICS_STORAGE_INTERVAL ?? 5}" placeholder="5" min="1" max="3600" />
                      <span class="set-hint">Intervalle min. entre deux lignes par machine</span>
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="METRICS_DETAIL_INTERVAL">Pas des lignes détail <em>secondes</em></label>
                      <input class="set-input" id="METRICS_DETAIL_INTERVAL" type="number" name="METRICS_DETAIL_INTERVAL"
                             value="${cfg.METRICS_DETAIL_INTERVAL ?? 60}" placeholder="60" min="5" max="86400" />
                      <span class="set-hint">Archivage du détail complet (processus, S.M.A.R.T.)</span>
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="RETENTION_DAYS">Rétention métriques <em>jours</em></label>
                      <input class="set-input" id="RETENTION_DAYS" type="number" name="RETENTION_DAYS"
                             value="${cfg.RETENTION_DAYS ?? 30}" placeholder="30" min="1" max="3650" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="NOTIFICATION_RETENTION_DAYS">Rétention notifications <em>jours</em></label>
                      <input class="set-input" id="NOTIFICATION_RETENTION_DAYS" type="number" name="NOTIFICATION_RETENTION_DAYS"
                             value="${cfg.NOTIFICATION_RETENTION_DAYS ?? 90}" placeholder="90" min="1" max="3650" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="PRUNE_INTERVAL_MINUTES">Intervalle de purge <em>minutes</em></label>
                      <input class="set-input" id="PRUNE_INTERVAL_MINUTES" type="number" name="PRUNE_INTERVAL_MINUTES"
                             value="${cfg.PRUNE_INTERVAL_MINUTES ?? 60}" placeholder="60" min="5" max="1440" />
                    </div>
                  </div>
                  <label class="set-toggle">
                    <div class="set-toggle-text">
                      <span class="set-toggle-label">Diffuser le détail complet aux navigateurs</span>
                      <span class="set-toggle-desc">Payload complet chaque seconde — déconseillé au-delà de 5 machines</span>
                    </div>
                    <span class="set-switch">
                      <input type="checkbox" name="BROADCAST_FULL_DETAIL" id="BROADCAST_FULL_DETAIL" ${cfg.BROADCAST_FULL_DETAIL ? "checked" : ""} />
                      <span class="set-switch-slider"></span>
                    </span>
                  </label>
                </div>
              </section>

              <!-- ── BASE DE DONNÉES ── -->
              <section class="set-section" id="sec-bdd">
                <header class="set-head">
                  <div class="set-icon"><i data-lucide="database"></i></div>
                  <div class="set-head-text">
                    <h2>Base de données</h2>
                    <p>Backend de stockage des métriques</p>
                  </div>
                </header>
                <div class="set-body set-stack">
                  <div class="set-grid-2">
                    <div class="set-field">
                      <label class="set-label" for="DB_BACKEND">Backend</label>
                      <select class="set-input" id="DB_BACKEND" name="DB_BACKEND">
                        <option value="sqlite" ${cfg.DB_BACKEND !== "postgres" ? "selected" : ""}>SQLite — local, zéro configuration</option>
                        <option value="postgres" ${cfg.DB_BACKEND === "postgres" ? "selected" : ""}>PostgreSQL — recommandé en production</option>
                      </select>
                      <span class="set-hint">Prend effet au redémarrage du serveur</span>
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="DB_HOST">Hôte PostgreSQL</label>
                      <input class="set-input" id="DB_HOST" type="text" name="DB_HOST"
                             value="${cfg.DB_HOST || "localhost"}" placeholder="localhost" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="DB_PORT">Port PostgreSQL</label>
                      <input class="set-input" id="DB_PORT" type="number" name="DB_PORT"
                             value="${cfg.DB_PORT ?? 5432}" placeholder="5432" min="1" max="65535" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="DB_NAME">Nom de la base</label>
                      <input class="set-input" id="DB_NAME" type="text" name="DB_NAME"
                             value="${cfg.DB_NAME || "vigil"}" placeholder="vigil" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="DB_USER">Utilisateur</label>
                      <input class="set-input" id="DB_USER" type="text" name="DB_USER"
                             value="${cfg.DB_USER || "vigil"}" placeholder="vigil" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="DB_PASSWORD">Mot de passe PostgreSQL</label>
                      <input class="set-input" id="DB_PASSWORD" type="password" name="DB_PASSWORD"
                             placeholder="Laisser vide pour conserver l'actuel" autocomplete="new-password" />
                      <span class="set-hint">Jamais affiché en clair</span>
                    </div>
                  </div>
                </div>
              </section>

              <!-- ── ALERTES SORTANTES & FÉDÉRATION ── -->
              <section class="set-section" id="sec-alerting">
                <header class="set-head">
                  <div class="set-icon"><i data-lucide="megaphone"></i></div>
                  <div class="set-head-text">
                    <h2>Alertes sortantes &amp; Fédération</h2>
                    <p>Webhook, email SMTP et multi-sites</p>
                  </div>
                </header>
                <div class="set-body set-stack">

                  <label class="set-toggle">
                    <div class="set-toggle-text">
                      <span class="set-toggle-label">Webhook activé</span>
                      <span class="set-toggle-desc">Pousse chaque alerte vers Slack, Teams, n8n… (JSON POST)</span>
                    </div>
                    <span class="set-switch">
                      <input type="checkbox" name="ALERT_WEBHOOK_ENABLED" id="ALERT_WEBHOOK_ENABLED" ${cfg.ALERT_WEBHOOK_ENABLED ? "checked" : ""} />
                      <span class="set-switch-slider"></span>
                    </span>
                  </label>

                  <div class="set-field set-field-wide">
                    <label class="set-label" for="ALERT_WEBHOOK_URL">URL du webhook</label>
                    <input class="set-input" id="ALERT_WEBHOOK_URL" type="text" name="ALERT_WEBHOOK_URL"
                           value="${cfg.ALERT_WEBHOOK_URL || ""}" placeholder="https://hooks.slack.com/services/…" />
                  </div>

                  <label class="set-toggle">
                    <div class="set-toggle-text">
                      <span class="set-toggle-label">Email activé (SMTP)</span>
                      <span class="set-toggle-desc">Envoie chaque alerte par email aux destinataires ci-dessous</span>
                    </div>
                    <span class="set-switch">
                      <input type="checkbox" name="ALERT_EMAIL_ENABLED" id="ALERT_EMAIL_ENABLED" ${cfg.ALERT_EMAIL_ENABLED ? "checked" : ""} />
                      <span class="set-switch-slider"></span>
                    </span>
                  </label>

                  <div class="set-grid-2">
                    <div class="set-field">
                      <label class="set-label" for="ALERT_SMTP_HOST">Serveur SMTP</label>
                      <input class="set-input" id="ALERT_SMTP_HOST" type="text" name="ALERT_SMTP_HOST"
                             value="${cfg.ALERT_SMTP_HOST || ""}" placeholder="smtp.gmail.com" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="ALERT_SMTP_PORT">Port</label>
                      <input class="set-input" id="ALERT_SMTP_PORT" type="number" name="ALERT_SMTP_PORT"
                             value="${cfg.ALERT_SMTP_PORT ?? 587}" placeholder="587" min="1" max="65535" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="ALERT_SMTP_USER">Utilisateur SMTP</label>
                      <input class="set-input" id="ALERT_SMTP_USER" type="text" name="ALERT_SMTP_USER"
                             value="${cfg.ALERT_SMTP_USER || ""}" placeholder="alertes@entreprise.com" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="ALERT_SMTP_PASSWORD">Mot de passe SMTP</label>
                      <input class="set-input" id="ALERT_SMTP_PASSWORD" type="password" name="ALERT_SMTP_PASSWORD"
                             placeholder="Laisser vide pour conserver l'actuel" autocomplete="new-password" />
                      <span class="set-hint">Jamais affiché en clair</span>
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="ALERT_EMAIL_FROM">Expéditeur</label>
                      <input class="set-input" id="ALERT_EMAIL_FROM" type="text" name="ALERT_EMAIL_FROM"
                             value="${cfg.ALERT_EMAIL_FROM || ""}" placeholder="vigil@entreprise.com" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="ALERT_EMAIL_TO">Destinataires <em>séparés par des virgules</em></label>
                      <input class="set-input" id="ALERT_EMAIL_TO" type="text" name="ALERT_EMAIL_TO"
                             value="${cfg.ALERT_EMAIL_TO || ""}" placeholder="admin@entreprise.com,exploit@entreprise.com" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="ALERT_MIN_SEVERITY">Sévérité minimale dispatchée</label>
                      <select class="set-input" id="ALERT_MIN_SEVERITY" name="ALERT_MIN_SEVERITY">
                        <option value="info" ${cfg.ALERT_MIN_SEVERITY === "info" ? "selected" : ""}>Info et plus</option>
                        <option value="warning" ${cfg.ALERT_MIN_SEVERITY === "warning" ? "selected" : ""}>Warning et plus (recommandé)</option>
                        <option value="error" ${cfg.ALERT_MIN_SEVERITY === "error" ? "selected" : ""}>Erreurs uniquement</option>
                      </select>
                    </div>
                  </div>

                  <div style="display:flex; gap:10px;">
                    <button class="fleet-btn" type="button" id="btn-test-webhook"><i data-lucide="send"></i> Tester le webhook</button>
                    <button class="fleet-btn" type="button" id="btn-test-email"><i data-lucide="mail"></i> Tester l'email</button>
                  </div>

                  <hr style="border:none; border-top:1px solid var(--border); margin:8px 0;" />

                  <div class="set-grid-2">
                    <div class="set-field">
                      <label class="set-label" for="FEDERATION_SITE_NAME">Nom de ce site (fédération)</label>
                      <input class="set-input" id="FEDERATION_SITE_NAME" type="text" name="FEDERATION_SITE_NAME"
                             value="${cfg.FEDERATION_SITE_NAME || "Site local"}" placeholder="Agence Lyon" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="FEDERATION_TOKEN_INPUT">Token de fédération</label>
                      <input class="set-input" id="FEDERATION_TOKEN_INPUT" type="password" name="FEDERATION_TOKEN"
                             placeholder="Laisser vide pour conserver l'actuel" autocomplete="new-password" />
                      <span class="set-hint">Secret partagé exigé par /api/federation/summary</span>
                    </div>
                    <div class="set-field set-field-wide">
                      <label class="set-label" for="FEDERATION_PEERS_TEXT">Peers (sites distants) <em>un par ligne : nom | url | token</em></label>
                      <textarea class="set-input" id="FEDERATION_PEERS_TEXT" name="FEDERATION_PEERS_TEXT" rows="3"
                                placeholder="Agence Lyon | http://10.0.0.20:5000 | secret-partage">${(cfg.FEDERATION_PEERS || []).map((p) => `${p.name || ""} | ${p.url || ""} | ${p.token || ""}`).join("\n")}</textarea>
                      <span class="set-hint">La vue Parc &amp; Sites → Fédération agrège ces serveurs</span>
                    </div>
                  </div>

                </div>
              </section>

              <!-- ── IA & COPILOTE ── -->
              <section class="set-section" id="sec-ia">
                <header class="set-head">
                  <div class="set-icon set-icon-ai"><i data-lucide="bot"></i></div>
                  <div class="set-head-text">
                    <h2>IA &amp; Copilote</h2>
                    <p>Moteur, modèle et autonomie de Vili</p>
                  </div>
                </header>
                <div class="set-body set-stack">
                  <label class="set-toggle">
                    <div class="set-toggle-text">
                      <span class="set-toggle-label">Assistance IA activée</span>
                      <span class="set-toggle-desc">Diagnostics intelligents et copilote VIGIL</span>
                    </div>
                    <span class="set-switch">
                      <input type="checkbox" name="AI_ENABLED" id="AI_ENABLED" ${cfg.AI_ENABLED !== false ? "checked" : ""} />
                      <span class="set-switch-slider"></span>
                    </span>
                  </label>

                  <div class="set-grid-2">
                    <div class="set-field">
                      <label class="set-label" for="AI_PROVIDER">Fournisseur</label>
                      <select class="set-input" id="AI_PROVIDER" name="AI_PROVIDER">
                        <option value="auto_rule" ${cfg.AI_PROVIDER === "auto_rule" ? "selected" : ""}>Détection auto (Ollama local / RAG BD)</option>
                        <option value="glm" ${cfg.AI_PROVIDER === "glm" ? "selected" : ""}>GLM — Z.ai (glm-5.3, recommandé)</option>
                        <option value="ollama" ${cfg.AI_PROVIDER === "ollama" ? "selected" : ""}>Ollama — modèle local</option>
                        <option value="groq" ${cfg.AI_PROVIDER === "groq" ? "selected" : ""}>Groq Cloud — Llama 3.3 70B ultra-rapide</option>
                        <option value="openrouter" ${cfg.AI_PROVIDER === "openrouter" ? "selected" : ""}>OpenRouter — modèles gratuits</option>
                        <option value="deepseek" ${cfg.AI_PROVIDER === "deepseek" ? "selected" : ""}>DeepSeek API</option>
                        <option value="openai" ${cfg.AI_PROVIDER === "openai" ? "selected" : ""}>OpenAI / API compatible</option>
                      </select>
                      <span class="set-hint">Le choix pré-remplit modèle et endpoint ci-dessous</span>
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="AI_MODEL">Nom du modèle</label>
                      <input class="set-input" id="AI_MODEL" type="text" name="AI_MODEL"
                             value="${cfg.AI_MODEL || "llama3"}" placeholder="llama3 ou gpt-4o-mini" />
                    </div>
                    <div class="set-field set-field-wide">
                      <label class="set-label" for="AI_ENDPOINT">URL endpoint API</label>
                      <input class="set-input" id="AI_ENDPOINT" type="text" name="AI_ENDPOINT"
                             value="${cfg.AI_ENDPOINT || "http://localhost:11434"}" placeholder="http://localhost:11434" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="AI_API_KEY">Clé API</label>
                      <input class="set-input" id="AI_API_KEY" type="password" name="AI_API_KEY"
                             placeholder="Laisser vide pour conserver l'actuelle" autocomplete="new-password"
                             oncopy="return false" oncut="return false" />
                      <span class="set-hint">Jamais affichée en clair</span>
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="AI_TIMEOUT">Timeout appels <em>secondes</em></label>
                      <input class="set-input" id="AI_TIMEOUT" type="number" name="AI_TIMEOUT"
                             value="${cfg.AI_TIMEOUT ?? 60}" placeholder="60" min="5" max="600" />
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="AI_RATE_LIMIT_PER_MIN">Limite requêtes / min / IP</label>
                      <input class="set-input" id="AI_RATE_LIMIT_PER_MIN" type="number" name="AI_RATE_LIMIT_PER_MIN"
                             value="${cfg.AI_RATE_LIMIT_PER_MIN ?? 20}" placeholder="20" min="0" />
                      <span class="set-hint">0 = illimité — protège votre quota</span>
                    </div>
                    <div class="set-field">
                      <label class="set-label" for="AI_SCAN_INTERVAL">Cycle autonome Vili <em>secondes</em></label>
                      <input class="set-input" id="AI_SCAN_INTERVAL" type="number" name="AI_SCAN_INTERVAL"
                             value="${cfg.AI_SCAN_INTERVAL ?? 300}" placeholder="300" min="60" max="86400" />
                      <span class="set-hint">Rythme d'analyse complète de l'infrastructure</span>
                    </div>
                    <div class="set-field set-field-wide">
                      <label class="set-label" for="AI_AUTONOMOUS_ACTIONS">Autonomie de Vili</label>
                      <select class="set-input" id="AI_AUTONOMOUS_ACTIONS" name="AI_AUTONOMOUS_ACTIONS">
                        <option value="off" ${cfg.AI_AUTONOMOUS_ACTIONS === "off" ? "selected" : ""}>Analyse + notifications uniquement</option>
                        <option value="propose" ${cfg.AI_AUTONOMOUS_ACTIONS === "propose" ? "selected" : ""}>Propose des commandes (exécution en 1 clic)</option>
                        <option value="auto" ${cfg.AI_AUTONOMOUS_ACTIONS === "auto" ? "selected" : ""}>Exécute automatiquement les actions correctives</option>
                      </select>
                      <span class="set-hint">Mode auto : garde-fous anti-destructeurs actifs</span>
                    </div>
                  </div>

                  <div>
                    <button class="settings-btn settings-btn-secondary" id="btn-test-ai" type="button">
                      <i data-lucide="zap"></i> Tester la connexion IA
                    </button>
                  </div>
                </div>
              </section>

              <!-- Pied du formulaire -->
              <div class="settings-actions settings-actions-bottom">
                <span class="settings-bottom-note"><i data-lucide="keyboard"></i> Ctrl+S pour enregistrer</span>
                <div>
                  <button class="settings-btn settings-btn-secondary" id="btn-reset-bottom" type="button">
                    <i data-lucide="rotate-ccw"></i>
                    <span class="btn-label">Réinitialiser</span>
                  </button>
                  <button class="settings-btn settings-btn-primary" id="btn-save-bottom" type="submit">
                    <i data-lucide="save"></i>
                    <span class="btn-label">Enregistrer les paramètres</span>
                    <span class="settings-btn-spinner"></span>
                  </button>
                </div>
              </div>

            </form>
          </div>
        </div>

        <!-- Toast notification -->
        <div class="settings-toast" id="settings-toast">
          <span class="toast-dot"></span>
          <span id="toast-text"></span>
        </div>
      `;

      refreshIcons();
      initSettingsHandlers(cfg);
      initSettingsChrome();
    });
}

/* ─── CHROME : rail de navigation, scrollspy, suivi des modifications ─── */
const SETTINGS_NAV = [
  { id: "sec-serveur",    label: "Serveur",             icon: "server" },
  { id: "sec-securite",   label: "Sécurité",            icon: "shield" },
  { id: "sec-alarmes",    label: "Alarmes",             icon: "bell-ring" },
  { id: "sec-smart",      label: "Disques S.M.A.R.T.",  icon: "hard-drive" },
  { id: "sec-monitoring", label: "Monitoring",          icon: "activity" },
  { id: "sec-perf",       label: "Performance",         icon: "database-zap" },
  { id: "sec-bdd",        label: "Base de données",     icon: "database" },
  { id: "sec-ia",         label: "IA & Copilote",       icon: "bot" },
];

function initSettingsChrome() {
  const rail = document.getElementById("settings-rail");
  const form = document.getElementById("settings-form");
  if (!rail || !form) return;

  // 1. Construire le rail
  rail.innerHTML = SETTINGS_NAV.map(
    (n) => `
    <button type="button" class="settings-nav-item" data-target="${n.id}">
      <i data-lucide="${n.icon}"></i><span>${n.label}</span>
    </button>`,
  ).join("");
  refreshIcons();

  const navBtns = [...rail.querySelectorAll(".settings-nav-item")];

  navBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.target);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  // 2. Scrollspy : met en évidence la section visible
  const sections = SETTINGS_NAV.map((n) => document.getElementById(n.id)).filter(Boolean);
  const setActive = (id) => {
    navBtns.forEach((b) => b.classList.toggle("active", b.dataset.target === id));
  };
  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((e) => e.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (visible) setActive(visible.target.id);
    },
    { rootMargin: "-80px 0px -60% 0px", threshold: 0 },
  );
  sections.forEach((s) => observer.observe(s));
  setActive(sections[0]?.id);

  // 3. Suivi des modifications (badge + bouton Enregistrer pulsé)
  const dirty = document.getElementById("settings-dirty");
  const markDirty = () => {
    if (dirty) dirty.hidden = false;
    document
      .querySelectorAll(".settings-app .settings-btn-primary")
      .forEach((b) => b.classList.add("has-changes"));
  };
  const clearDirty = () => {
    if (dirty) dirty.hidden = true;
    document
      .querySelectorAll(".settings-app .settings-btn-primary")
      .forEach((b) => b.classList.remove("has-changes"));
  };
  form.addEventListener("input", markDirty);
  form.addEventListener("change", markDirty);
  window.__settingsClearDirty = clearDirty;

  // 4. Raccourci Ctrl+S tant que la vue est affichée
  if (window.__settingsKeyHandler) {
    document.removeEventListener("keydown", window.__settingsKeyHandler);
  }
  window.__settingsKeyHandler = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      if (!document.getElementById("settings-form")) return;
      e.preventDefault();
      document.getElementById("btn-save-top")?.click();
    }
  };
  document.addEventListener("keydown", window.__settingsKeyHandler);
}

// ─── HANDLERS ──────────────────────────────────────────────────────
function initSettingsHandlers(originalCfg) {
  // Toggle affichage token
  const tokenInput = document.getElementById("AUTH_TOKEN");
  const toggleToken = document.getElementById("toggle-token");
  const tokenEye = document.getElementById("token-eye");

  if (tokenInput) {
    // Protections copier/coller
    ["copy", "cut", "contextmenu"].forEach((ev) =>
      tokenInput.addEventListener(ev, (e) => e.preventDefault()),
    );
  }

  if (toggleToken && tokenInput) {
    toggleToken.addEventListener("click", () => {
      const hidden = tokenInput.type === "password";
      tokenInput.type = hidden ? "text" : "password";
      tokenEye.innerHTML = hidden
        ? `<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
           <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
           <line x1="1" y1="1" x2="23" y2="23"/>`
        : `<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
           <circle cx="12" cy="12" r="3"/>`;
    });
  }

  // Bouton test IA
  const btnTestAi = document.getElementById("btn-test-ai");
  if (btnTestAi) {
    btnTestAi.addEventListener("click", () => {
      showSettingsToast("Vérification de la connexion IA...", "info");
      vigilFetch("/api/ai/status")
        .then((res) => res.json())
        .then((res) => {
          if (res.status === "ok") {
            showSettingsToast(`Connecté — ${res.message}`, "success");
          } else {
            showSettingsToast(res.message || "Connexion impossible", "error");
          }
        })
        .catch((e) => {
          showSettingsToast(`Erreur réseau: ${e.message}`, "error");
        });
    });
  }

  // Tests des canaux d'alertes sortantes (envoient la config SAISIE d'abord)
  ["btn-test-webhook", "btn-test-email"].forEach((id) => {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.addEventListener("click", async () => {
      showSettingsToast("Envoi du test…", "info");
      try {
        // sauvegarder la configuration courante avant de tester
        await handleSubmit(new Event("submit"));
        const endpoint =
          id === "btn-test-webhook"
            ? "/api/settings/test-webhook"
            : "/api/settings/test-email";
        const res = await vigilFetch(endpoint, { method: "POST" });
        const d = await res.json().catch(() => ({}));
        if (res.ok) showSettingsToast(d.message || "Test envoyé ✅", "success");
        else showSettingsToast(d.error || "Échec du test — voir logs serveur", "error");
      } catch (e) {
        showSettingsToast(`Erreur : ${e.message}`, "error");
      }
    });
  });

  // Boutons réinitialiser
  ["btn-reset", "btn-reset-bottom"].forEach((id) => {
    const btn = document.getElementById(id);
    if (btn)
      btn.addEventListener("click", () => {
        if (
          confirm(
            "Réinitialiser la configuration à l'état précédent ? (annule la dernière sauvegarde)",
          )
        ) {
          // call reset endpoint
          vigilFetch("/api/settings/reset", { method: "POST" })
            .then((res) => {
              if (res.ok) {
                showSettingsToast("Configuration restaurée", "success");
                renderSettingsView();
              } else {
                showSettingsToast("Aucun backup disponible", "error");
              }
            })
            .catch(() => {
              showSettingsToast("Erreur réseau", "error");
            });
        }
      });
  });

  // Soumission du formulaire
  const form = document.getElementById("settings-form");
  if (!form) return;

  // Auto-remplissage Endpoint & Modèle lors de la sélection du Provider
  const providerSelect = document.getElementById("AI_PROVIDER");
  if (providerSelect) {
    providerSelect.addEventListener("change", (e) => {
      const val = e.target.value;
      const modelInput = document.getElementById("AI_MODEL");
      const endpointInput = document.getElementById("AI_ENDPOINT");
      if (val === "glm") {
        if (modelInput) modelInput.value = "glm-5.3";
        if (endpointInput) endpointInput.value = "https://api.z.ai/api/paas/v4";
      } else if (val === "groq") {
        if (modelInput) modelInput.value = "openai/gpt-oss-20b";
        if (endpointInput) endpointInput.value = "https://api.groq.com/openai";
      } else if (val === "openrouter") {
        if (modelInput) modelInput.value = "meta-llama/llama-3.2-3b-instruct:free";
        if (endpointInput) endpointInput.value = "https://openrouter.ai/api";
      } else if (val === "deepseek") {
        if (modelInput) modelInput.value = "deepseek-chat";
        if (endpointInput) endpointInput.value = "https://api.deepseek.com";
      } else if (val === "openai") {
        if (modelInput) modelInput.value = "gpt-4o-mini";
        if (endpointInput) endpointInput.value = "https://api.openai.com";
      } else if (val === "ollama") {
        if (modelInput) modelInput.value = "llama3";
        if (endpointInput) endpointInput.value = "http://localhost:11434";
      }
    });
  }

  const handleSubmit = (e) => {
    e.preventDefault();

    // Activer état loading sur les deux boutons primaires
    document
      .querySelectorAll(".settings-btn-primary")
      .forEach((b) => b.classList.add("loading"));

    const data = {};
    // cases à cocher : absentes du FormData quand décochées → on les force
    [
      "ENABLE_AUTH", "AI_ENABLED", "HDD_SMART_ENABLED", "COOKIE_SECURE",
      "BROADCAST_FULL_DETAIL", "AGENT_COMMANDS_ENABLED",
      "ALERT_WEBHOOK_ENABLED", "ALERT_EMAIL_ENABLED", "ALERT_SMTP_TLS",
    ].forEach((k) => {
      data[k] = document.getElementById(k)?.checked || false;
    });
    new FormData(form).forEach((v, k) => {
      if (
        k === "AUTH_TOKEN" || k === "AI_API_KEY" || k === "DB_PASSWORD" ||
        k === "ALERT_SMTP_PASSWORD" || k === "FEDERATION_TOKEN"
      ) {
        if (v === "") return; // conserver l'actuel si vide
        if (v.includes("...")) return; // valeur masquée
        data[k] = v;
        return;
      }
      if (
        k === "ENABLE_AUTH" ||
        k === "AI_ENABLED" ||
        k === "HDD_SMART_ENABLED" ||
        k === "COOKIE_SECURE" ||
        k === "BROADCAST_FULL_DETAIL" ||
        k === "AGENT_COMMANDS_ENABLED" ||
        k === "ALERT_WEBHOOK_ENABLED" ||
        k === "ALERT_EMAIL_ENABLED" ||
        k === "ALERT_SMTP_TLS"
      ) {
        return; // déjà traité par les cases à cocher ci-dessus
      } else if (k === "ALLOWED_AGENT_IPS" || k === "ALLOWED_CLIENT_IPS") {
        data[k] = v
          .split(",")
          .map((s) => s.trim())
          .filter((s) => s);
      } else if (k === "FEDERATION_PEERS_TEXT") {
        // une ligne par peer : nom | url | token
        data.FEDERATION_PEERS = v
          .split("\n")
          .map((l) => l.trim())
          .filter((l) => l && l.includes("|"))
          .map((l) => {
            const [name, url, token] = l.split("|").map((s) => s.trim());
            return { name, url, token: token || "" };
          })
          .filter((p) => p.url);
      } else if (v !== "" && !isNaN(v)) {
        data[k] = Number(v);
      } else {
        data[k] = v;
      }
    });

    vigilFetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    })
      .then(async (res) => {
        document
          .querySelectorAll(".settings-btn-primary")
          .forEach((b) => b.classList.remove("loading"));
        if (!res.ok) {
          let err = null;
          try {
            err = await res.json();
          } catch {}
          const msg = err && err.error ? err.error : `Erreur ${res.status}`;
          showSettingsToast(msg, "error");
        } else {
          showSettingsToast("Paramètres enregistrés avec succès", "success");
          if (typeof window.__settingsClearDirty === "function")
            window.__settingsClearDirty();
        }
      })
      .catch(() => {
        document
          .querySelectorAll(".settings-btn-primary")
          .forEach((b) => b.classList.remove("loading"));
        showSettingsToast("Erreur réseau", "error");
      });
  };

  form.addEventListener("submit", handleSubmit);
  document
    .getElementById("btn-save-top")
    ?.addEventListener("click", handleSubmit);
}

// ─── TOAST ─────────────────────────────────────────────────────────
function showSettingsToast(message, type = "success") {
  const toast = document.getElementById("settings-toast");
  const text = document.getElementById("toast-text");
  if (!toast || !text) return;

  text.textContent = message;
  toast.className = `settings-toast ${type}`;

  // Forcer reflow pour relancer l'animation si déjà visible
  void toast.offsetWidth;
  toast.classList.add("show");

  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(() => toast.classList.remove("show"), 3500);
}
