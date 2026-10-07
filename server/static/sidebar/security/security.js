/* ─────────────────────────────────────────────────────────────
   VIGIL — security.js (Écran Sécurité : posture, événements, agents)
   ───────────────────────────────────────────────────────────── */

let securityRefreshTimer = null;

async function renderSecurityView() {
  const content = document.querySelector(".content");
  if (!content) return;

  content.innerHTML = `
    <div class="sec-container">
      <div class="sec-header-card">
        <div>
          <div class="sec-title"><i data-lucide="shield-check"></i> Centre de Sécurité</div>
          <div class="sec-subtitle">POSTURE, JOURNAL D'ÉVÉNEMENTS &amp; MACHINES CONNECTÉES</div>
        </div>
        <div class="sec-score-wrap">
          <svg class="sec-gauge" viewBox="0 0 120 120">
            <circle class="sec-gauge-bg" cx="60" cy="60" r="52"/>
            <circle class="sec-gauge-fill" id="sec-gauge-fill" cx="60" cy="60" r="52"/>
          </svg>
          <div class="sec-score-text">
            <span id="sec-score-value">--</span>
            <small>/100</small>
          </div>
        </div>
      </div>

      <div class="sec-body">
        <div class="sec-col-main">

          <div class="sec-card">
            <div class="sec-card-title"><i data-lucide="clipboard-check"></i> Contrôles de posture</div>
            <div id="sec-checks" class="sec-checks"><div class="sec-loading">Chargement…</div></div>
          </div>

          <div class="sec-card">
            <div class="sec-card-title">
              <i data-lucide="scroll-text"></i> Journal de sécurité
              <span class="sec-badge" id="sec-failures" title="Échecs sur la dernière heure">—</span>
            </div>
            <div id="sec-events" class="sec-events"><div class="sec-loading">Chargement…</div></div>
          </div>

        </div>

        <div class="sec-col-side">

          <div class="sec-card">
            <div class="sec-card-title"><i data-lucide="monitor-check"></i> Agents connectés</div>
            <div id="sec-agents" class="sec-agents"><div class="sec-loading">Chargement…</div></div>
          </div>

          <div class="sec-card sec-card-accent">
            <div class="sec-card-title">
              <i data-lucide="lightbulb"></i> Recommandations
              <button class="sec-btn" onclick="secGoToSettings()" title="Ouvrir les réglages de sécurité">
                <i data-lucide="settings"></i> Paramètres
              </button>
            </div>
            <div id="sec-recommendations" class="sec-recommendations"><div class="sec-loading">Chargement…</div></div>
          </div>

        </div>
      </div>
    </div>
  `;
  refreshIcons();
  await fetchSecurityStatus();

  // rafraîchissement automatique tant que la vue est affichée
  if (securityRefreshTimer) clearInterval(securityRefreshTimer);
  securityRefreshTimer = setInterval(() => {
    if (!document.getElementById("sec-score-value")) {
      clearInterval(securityRefreshTimer);
      securityRefreshTimer = null;
      return;
    }
    fetchSecurityStatus();
  }, 15000);
}

async function fetchSecurityStatus() {
  try {
    const res = await vigilFetch("/api/security/status");
    const data = await res.json();
    renderSecurityScore(data);
    renderSecurityChecks(data.checks || []);
    renderSecurityEvents(data.events || [], data.failures_last_hour || 0);
    renderSecurityAgents(data.agents || []);
    renderSecurityRecommendations(data.recommendations || []);
  } catch (e) {
    const el = document.getElementById("sec-events");
    if (el) el.innerHTML = `<div class="sec-loading">Erreur : ${e.message}</div>`;
  }
}

/* ── Jauge de score ─────────────────────────────────────────────── */
function renderSecurityScore(data) {
  const valueEl = document.getElementById("sec-score-value");
  const gauge = document.getElementById("sec-gauge-fill");
  if (!valueEl || !gauge) return;

  valueEl.textContent = data.score;
  const circumference = 2 * Math.PI * 52;
  const pct = Math.max(0, Math.min(100, data.score)) / 100;
  gauge.style.strokeDasharray = `${circumference}`;
  gauge.style.strokeDashoffset = `${circumference * (1 - pct)}`;
  gauge.className = `sec-gauge-fill ${data.level || "critical"}`;
  valueEl.parentElement.className = `sec-score-text ${data.level || "critical"}`;
}

/* ── Checklist de posture ───────────────────────────────────────── */
function renderSecurityChecks(checks) {
  const container = document.getElementById("sec-checks");
  if (!container) return;
  container.innerHTML = checks
    .map(
      (c) => `
      <div class="sec-check ${c.ok ? "ok" : "ko"}">
        <div class="sec-check-icon"><i data-lucide="${c.ok ? "check-circle-2" : "alert-triangle"}"></i></div>
        <div class="sec-check-body">
          <div class="sec-check-label">${_secEsc(c.label)} <span class="sec-check-weight">${c.weight} pts</span></div>
          ${!c.ok ? `<div class="sec-check-advice">${_secEsc(c.advice)}</div>` : ""}
        </div>
      </div>`,
    )
    .join("");
  refreshIcons();
}

/* ── Journal d'événements ───────────────────────────────────────── */
const _SEC_KIND_LABELS = {
  login_failed: "Connexion refusée",
  agent_auth_failed: "Agent refusé",
  ip_blocked: "IP bloquée",
  remote_command: "Commande distante",
  config_changed: "Réglages modifiés",
};

function renderSecurityEvents(events, failures) {
  const container = document.getElementById("sec-events");
  const badge = document.getElementById("sec-failures");
  if (badge) {
    badge.textContent = `${failures} échec(s)/1h`;
    badge.className = `sec-badge ${failures > 0 ? "warn" : ""}`;
  }
  if (!container) return;

  if (!events.length) {
    container.innerHTML = `<div class="sec-empty"><i data-lucide="shield"></i> Aucun événement de sécurité enregistré — c'est une bonne nouvelle.</div>`;
    refreshIcons();
    return;
  }

  container.innerHTML = events
    .map(
      (ev) => `
      <div class="sec-event sev-${ev.severity || "info"}">
        <div class="sec-event-dot"></div>
        <div class="sec-event-body">
          <div class="sec-event-msg">${_secEsc(ev.message)}</div>
          <div class="sec-event-meta">${_secEsc(_SEC_KIND_LABELS[ev.kind] || ev.kind)}${ev.source ? ` · ${_secEsc(ev.source)}` : ""} · ${new Date(ev.ts).toLocaleString()}</div>
        </div>
      </div>`,
    )
    .join("");
}

/* ── Agents ─────────────────────────────────────────────────────── */
function renderSecurityAgents(agents) {
  const container = document.getElementById("sec-agents");
  if (!container) return;
  if (!agents.length) {
    container.innerHTML = `<div class="sec-empty">Aucun agent connecté actuellement.</div>`;
    return;
  }
  container.innerHTML = agents
    .map(
      (a) => `
      <div class="sec-agent">
        <span class="sec-agent-dot ${a.online ? "on" : "off"}"></span>
        <div class="sec-agent-info">
          <div class="sec-agent-name">${_secEsc(a.hostname)}</div>
          <div class="sec-agent-ip">${_secEsc(a.local_ip || "IP inconnue")}</div>
        </div>
        <span class="sec-agent-status">${a.online ? "EN LIGNE" : "HORS LIGNE"}</span>
      </div>`,
    )
    .join("");
}

/* ── Recommandations ────────────────────────────────────────────── */
function renderSecurityRecommendations(recommendations) {
  const container = document.getElementById("sec-recommendations");
  if (!container) return;
  if (!recommendations.length) {
    container.innerHTML = `<div class="sec-empty"><i data-lucide="party-popper"></i> Posture exemplaire : toutes les protections recommandées sont actives.</div>`;
    refreshIcons();
    return;
  }
  container.innerHTML = `<ul>${recommendations.map((r) => `<li>${_secEsc(r)}</li>`).join("")}</ul>`;
}

/* ── Navigation vers les Paramètres ─────────────────────────────── */
function secGoToSettings() {
  for (const item of document.querySelectorAll(".nav-item")) {
    const t = (
      item.querySelector(".nav-text") || item
    ).textContent.trim().toLowerCase();
    if (t === "paramètres" || t === "parametres") {
      item.click();
      return;
    }
  }
}

function _secEsc(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
