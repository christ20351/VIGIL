/**
 * VIGIL — settings.js
 * Page des paramètres du serveur — cohérente avec le dashboard
 */

function renderSettingsView() {
  vigilFetch("/api/settings")
    .then((res) => res.json())
    .then((cfg) => {
      const fmtArr = (arr) => (Array.isArray(arr) ? arr.join(", ") : "");

      document.querySelector(".content").innerHTML = `
        <div class="settings-container">

          <!-- En-tête -->
          <div class="settings-header">
            <div class="settings-header-left">
              <div class="settings-title">Paramètres du serveur</div>
              <div class="settings-sub">CONFIGURATION GLOBALE — VIGIL v2.0</div>
            </div>
            <div class="settings-actions" id="settings-actions-top">
              <button class="settings-btn settings-btn-secondary" id="btn-reset" type="button">
                <i data-lucide="rotate-ccw"></i>
                <span class="btn-label">Réinitialiser</span>
              </button>
              <button class="settings-btn settings-btn-primary" id="btn-save-top" type="button">
                <i data-lucide="save"></i>
                <span class="btn-label">Enregistrer</span>
                <span class="settings-btn-spinner"></span>
              </button>
            </div>
          </div>

          <form id="settings-form" novalidate>
            <div class="settings-grid">

              <!-- ── SERVEUR ── -->
              <div class="settings-section">
                <div class="settings-section-header">
                  <svg class="settings-section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
                  </svg>
                  <span class="settings-section-title">Serveur</span>
                </div>
                <div class="settings-section-body">

                  <div class="settings-field">
                    <label class="settings-label" for="SERVER_HOST">Hôte d'écoute</label>
                    <div class="settings-input-wrap">
                      <svg class="settings-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
                        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                      </svg>
                      <input class="settings-input" id="SERVER_HOST" type="text" name="SERVER_HOST"
                             value="${cfg.SERVER_HOST || ""}" placeholder="0.0.0.0" />
                    </div>
                    <span class="settings-hint">0.0.0.0 pour écouter sur toutes les interfaces</span>
                  </div>

                  <div class="settings-field">
                    <label class="settings-label" for="SERVER_PORT">Port</label>
                    <div class="settings-input-wrap">
                      <svg class="settings-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
                        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
                      </svg>
                      <input class="settings-input" id="SERVER_PORT" type="number" name="SERVER_PORT"
                             value="${cfg.SERVER_PORT || ""}" placeholder="5000" min="1" max="65535" />
                    </div>
                  </div>

                  <div class="settings-field">
                    <label class="settings-label" for="TIMEOUT">Timeout agent (s)</label>
                    <div class="settings-input-wrap">
                      <svg class="settings-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                      </svg>
                      <input class="settings-input" id="TIMEOUT" type="number" name="TIMEOUT"
                             value="${cfg.TIMEOUT || 60}" placeholder="60" min="1" />
                    </div>
                    <span class="settings-hint">Secondes avant de marquer un agent hors ligne</span>
                  </div>

                </div>
              </div>

              <!-- ── SÉCURITÉ ── -->
              <div class="settings-section">
                <div class="settings-section-header">
                  <svg class="settings-section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                  </svg>
                  <span class="settings-section-title">Sécurité</span>
                </div>
                <div class="settings-section-body">

                  <div class="settings-toggle-row">
                    <div class="settings-toggle-info">
                      <span class="settings-toggle-label">Authentification par token</span>
                      <span class="settings-toggle-desc">Exige un token sur chaque requête agent</span>
                    </div>
                    <label class="settings-switch">
                      <input type="checkbox" name="ENABLE_AUTH" id="ENABLE_AUTH" ${cfg.ENABLE_AUTH ? "checked" : ""} />
                      <span class="settings-switch-slider"></span>
                    </label>
                  </div>

                  <div class="settings-field">
                    <label class="settings-label" for="AUTH_TOKEN">Token secret</label>
                    <div class="settings-input-wrap">
                      <svg class="settings-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                      </svg>
                      <input class="settings-input" id="AUTH_TOKEN" type="password" name="AUTH_TOKEN"
                             placeholder="Laisser vide pour conserver l'actuel"
                             autocomplete="new-password"
                             oncopy="return false" oncut="return false" />
                      <button type="button" class="settings-pwd-toggle" id="toggle-token">
                        <svg id="token-eye" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                          <circle cx="12" cy="12" r="3"/>
                        </svg>
                      </button>
                    </div>
                    <span class="settings-hint">Vide = token actuel conservé</span>
                  </div>

                  <div class="settings-field">
                    <label class="settings-label" for="ALLOWED_AGENT_IPS">IPs agents autorisées</label>
                    <textarea class="settings-textarea" id="ALLOWED_AGENT_IPS" name="ALLOWED_AGENT_IPS"
                              placeholder="192.168.1.10, 192.168.1.20 — vide = toutes autorisées"
                              rows="3">${fmtArr(cfg.ALLOWED_AGENT_IPS)}</textarea>
                    <span class="settings-hint">Séparer par des virgules — vide = toutes acceptées</span>
                  </div>

                  <div class="settings-field">
                    <label class="settings-label" for="ALLOWED_CLIENT_IPS">IPs navigateurs autorisées</label>
                    <textarea class="settings-textarea" id="ALLOWED_CLIENT_IPS" name="ALLOWED_CLIENT_IPS"
                              placeholder="192.168.1.100, 192.168.1.101 — vide = toutes autorisées"
                              rows="3">${fmtArr(cfg.ALLOWED_CLIENT_IPS)}</textarea>
                    <span class="settings-hint">Séparer par des virgules — vide = toutes acceptées</span>
                  </div>

                </div>
              </div>

              <!-- ── MONITORING ── -->
              <div class="settings-section">
                <div class="settings-section-header">
                  <svg class="settings-section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                  </svg>
                  <span class="settings-section-title">Monitoring</span>
                </div>
                <div class="settings-section-body">

                  <div class="settings-field">
                    <label class="settings-label" for="PROCESS_LIMIT">Limite processus</label>
                    <div class="settings-input-wrap">
                      <svg class="settings-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>
                        <line x1="9" y1="2" x2="9" y2="4"/><line x1="15" y1="2" x2="15" y2="4"/>
                        <line x1="9" y1="20" x2="9" y2="22"/><line x1="15" y1="20" x2="15" y2="22"/>
                      </svg>
                      <input class="settings-input" id="PROCESS_LIMIT" type="number" name="PROCESS_LIMIT"
                             value="${cfg.PROCESS_LIMIT || 100}" placeholder="100" min="1" max="500" />
                    </div>
                    <span class="settings-hint">Nombre max de processus remontés par agent</span>
                  </div>

                  <div class="settings-field">
                    <label class="settings-label" for="NETWORK_CONN_LIMIT">Limite connexions réseau</label>
                    <div class="settings-input-wrap">
                      <svg class="settings-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="2" y="2" width="6" height="6" rx="1"/><rect x="16" y="16" width="6" height="6" rx="1"/>
                        <rect x="2" y="16" width="6" height="6" rx="1"/>
                        <path d="M5 8v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8"/><line x1="19" y1="8" x2="19" y2="16"/>
                      </svg>
                      <input class="settings-input" id="NETWORK_CONN_LIMIT" type="number" name="NETWORK_CONN_LIMIT"
                             value="${cfg.NETWORK_CONN_LIMIT || 100}" placeholder="100" min="1" max="1000" />
                    </div>
                    <span class="settings-hint">Nombre max de connexions réseau remontées</span>
                  </div>

                </div>
              </div>

              <!-- ── ALARMES ── -->
              <div class="settings-section">
                <div class="settings-section-header">
                  <svg class="settings-section-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                    <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                  </svg>
                  <span class="settings-section-title">Alarmes</span>
                </div>
                <div class="settings-section-body">

                  <div class="settings-field">
                    <label class="settings-label" for="CPU_ALERT_THRESHOLD">Seuil CPU (%)</label>
                    <div class="settings-input-wrap">
                      <svg class="settings-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>
                      </svg>
                      <input class="settings-input" id="CPU_ALERT_THRESHOLD" type="number" name="CPU_ALERT_THRESHOLD"
                             value="${cfg.CPU_ALERT_THRESHOLD || 90}" placeholder="90" min="1" max="100" />
                    </div>
                  </div>

                  <div class="settings-field">
                    <label class="settings-label" for="CPU_ALERT_DURATION">Durée CPU (s)</label>
                    <div class="settings-input-wrap">
                      <svg class="settings-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                      </svg>
                      <input class="settings-input" id="CPU_ALERT_DURATION" type="number" name="CPU_ALERT_DURATION"
                             value="${cfg.CPU_ALERT_DURATION || 30}" placeholder="30" min="1" />
                    </div>
                    <span class="settings-hint">Déclenche l'alarme après N secondes en surcharge</span>
                  </div>

                  <div class="settings-field">
                    <label class="settings-label" for="RAM_ALERT_THRESHOLD">Seuil RAM (%)</label>
                    <div class="settings-input-wrap">
                      <svg class="settings-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="6" y1="3" x2="6" y2="15"/><line x1="18" y1="3" x2="18" y2="15"/>
                        <line x1="3" y1="7" x2="21" y2="7"/><line x1="3" y1="11" x2="21" y2="11"/>
                        <rect x="2" y="15" width="20" height="4" rx="2"/>
                      </svg>
                      <input class="settings-input" id="RAM_ALERT_THRESHOLD" type="number" name="RAM_ALERT_THRESHOLD"
                             value="${cfg.RAM_ALERT_THRESHOLD || 90}" placeholder="90" min="1" max="100" />
                    </div>
                  </div>

                  <div class="settings-field">
                    <label class="settings-label" for="DISK_ALERT_THRESHOLD">Seuil DISK (%)</label>
                    <div class="settings-input-wrap">
                      <svg class="settings-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <ellipse cx="12" cy="5" rx="9" ry="3"/>
                        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
                        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
                      </svg>
                      <input class="settings-input" id="DISK_ALERT_THRESHOLD" type="number" name="DISK_ALERT_THRESHOLD"
                             value="${cfg.DISK_ALERT_THRESHOLD || 85}" placeholder="85" min="1" max="100" />
                    </div>
                  </div>

                </div>
              </div>

            </div><!-- /.settings-grid -->

            <!-- Bouton bas de page -->
            <div class="settings-actions">
              <button class="settings-btn settings-btn-secondary" id="btn-reset-bottom" type="button">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4"/></svg>
                <span class="btn-label">Réinitialiser</span>
              </button>
              <button class="settings-btn settings-btn-primary" id="btn-save-bottom" type="submit">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                <span class="btn-label">Enregistrer les paramètres</span>
                <span class="settings-btn-spinner"></span>
              </button>
            </div>

          </form>
        </div>

        <!-- Toast notification -->
        <div class="settings-toast" id="settings-toast">
          <span class="toast-dot"></span>
          <span id="toast-text"></span>
        </div>
      `;

      refreshIcons();
      initSettingsHandlers(cfg);
    });
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

  const handleSubmit = (e) => {
    e.preventDefault();

    // Activer état loading sur les deux boutons primaires
    document
      .querySelectorAll(".settings-btn-primary")
      .forEach((b) => b.classList.add("loading"));

    const data = {};
    new FormData(form).forEach((v, k) => {
      if (k === "AUTH_TOKEN") {
        if (v === "") return; // conserver l'actuel si vide
        data[k] = v;
        return;
      }
      if (k === "ENABLE_AUTH") {
        data[k] = document.getElementById("ENABLE_AUTH").checked;
      } else if (k === "ALLOWED_AGENT_IPS" || k === "ALLOWED_CLIENT_IPS") {
        data[k] = v
          .split(",")
          .map((s) => s.trim())
          .filter((s) => s);
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
