/**
 * VIGIL — smart.js
 * Onglet S.M.A.R.T. dans la modal agent
 */

// ─── POINT D'ENTRÉE PRINCIPAL ────────────────────────────────────
function updateSmartHealthTab(hostname) {
  console.log("[SMART] updateSmartHealthTab called for", hostname);

  const container = document.getElementById("tab-smart");
  if (!container) return;

  container.innerHTML = `
    <div style="display:flex;align-items:center;gap:10px;padding:20px;color:var(--muted)">
      <i data-lucide="loader"></i> Chargement des données S.M.A.R.T...
    </div>`;
  refreshIcons();

  // ── 1. Essayer d'abord les données déjà en mémoire (temps réel) ──
  const localData = computersData[hostname];
  const localSmart = localData && localData.smart;

  // Si on a reçu un objet agent (même si smart.available est false), on l'affiche immédiatement.
  // la présence d'un agent signifie que le WebSocket a déjà poussé des métriques.
  if (localData) {
    console.log("[SMART] Using local computersData for", hostname, localSmart);
    renderSmartTab(container, localSmart || {});
    return;
  }

  // ── 2. Fallback : appel API si l'agent n'a pas encore envoyé de métriques ──
  //    (anciennement déclenché quand localSmart.available était false, ce qui
  //    provoquait une requête inutile et une erreur 404 car la route n'existait
  //    pas).
  fetch(`/api/computers/${encodeURIComponent(hostname)}/smart`)
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((resp) => {
      console.log("[SMART] API response for", hostname, resp);
      const smart = (resp && resp.smart) || {};
      renderSmartTab(container, smart);
    })
    .catch((err) => {
      console.error("[SMART] fetch error", err);
      // ne pas afficher un message d'erreur bloquant, juste indiquer l'état
      container.innerHTML = `
        <div class="smart-unavailable">
          <div class="smart-icon">⚠️</div>
          <h3>Erreur de récupération</h3>
          <p>Impossible de contacter l'API SMART.</p>
          <p class="smart-hint">${err.message}</p>
        </div>`;
    });
}

// ─── RENDU PRINCIPAL ─────────────────────────────────────────────
function renderSmartTab(container, smart) {
  console.log("[SMART] renderSmartTab called with", smart);
  container.innerHTML = "";

  // Pas de données disponibles
  if (!smart || !smart.available) {
    container.innerHTML = `
      <div class="smart-unavailable">
        <div class="smart-icon">💾</div>
        <h3>Aucune donnée S.M.A.R.T. disponible</h3>
        <p>L'agent ne rapporte pas d'informations S.M.A.R.T.</p>
        <p class="smart-hint">Vérifiez que l'agent tourne avec les droits administrateur.</p>
        <code>sudo ./vigil-agent  (Linux)</code>
        <code>Exécuter en tant qu'Administrateur  (Windows)</code>
      </div>`;
    refreshIcons();
    return;
  }

  const disks = smart.disks || [];
  const alerts = smart.alerts || [];
  const hasAlert = alerts.length > 0;

  // ── Header ────────────────────────────────────────────────────
  const header = document.createElement("div");
  header.className = "smart-header";
  header.innerHTML = `
    <div class="smart-title">
      <i data-lucide="hard-drive"></i>
      <span>Santé S.M.A.R.T.</span>
    </div>
    <div class="smart-summary">
      <div class="smart-stat">
        <span class="label">Disques</span>
        <span class="value">${disks.length}</span>
      </div>
      <div class="smart-stat ${hasAlert ? "alert-count-active" : "alert-count-ok"}">
        <span class="label">Alertes</span>
        <span class="value">${alerts.length}</span>
      </div>
      <div class="smart-stat">
        <span class="label">Statut global</span>
        <span class="value" style="color:${_globalHealthColor(disks)}">${_globalHealthText(disks)}</span>
      </div>
    </div>
  `;
  container.appendChild(header);

  // ── Alertes actives ───────────────────────────────────────────
  if (hasAlert) {
    const alertBox = document.createElement("div");
    alertBox.className = "smart-alerts";
    alertBox.innerHTML = `
      <div class="alert-title">
        <i data-lucide="alert-triangle"></i>
        ${alerts.length} alerte${alerts.length > 1 ? "s" : ""} détectée${alerts.length > 1 ? "s" : ""}
      </div>
      ${alerts
        .map(
          (a) => `
        <div class="smart-alert alert-${(a.level || "warning").toLowerCase()}">
          <div class="alert-icon">${a.level === "CRITICAL" ? "🔴" : "🟡"}</div>
          <div class="alert-content">
            <div class="alert-type">${a.level || "WARNING"}</div>
            <div class="alert-message">${a.message || ""}</div>
            ${a.disk ? `<div class="alert-detail">Disque : ${a.disk}</div>` : ""}
          </div>
        </div>`,
        )
        .join("")}
    `;
    container.appendChild(alertBox);
  }

  // ── Cartes disques ────────────────────────────────────────────
  const diskList = document.createElement("div");
  diskList.className = "smart-container";

  if (!disks.length) {
    diskList.innerHTML = `<p style="color:var(--muted);padding:12px">Aucun disque détecté.</p>`;
  }

  disks.forEach((d) => {
    const card = document.createElement("div");
    card.className = "smart-disk-card";

    const health = d.health || "UNKNOWN";
    const temp = d.temperature;
    const hours = d.power_on_hours;
    const sectors = d.reallocated_sectors || 0;
    const healthClass =
      health === "PASSED" ? "ok" : health === "FAILED" ? "critical" : "unknown";

    // Calcul couleur / pourcentage température
    const tempWarn = 45;
    const tempCrit = 55;
    let tempClass = "ok";
    let tempPct = 0;
    if (temp !== null && temp !== undefined) {
      tempPct = Math.min(100, Math.round((temp / 70) * 100));
      tempClass =
        temp >= tempCrit ? "critical" : temp >= tempWarn ? "warning" : "ok";
    }

    // Disponibilité
    if (!d.available) {
      card.innerHTML = `
        <div class="disk-header">
          <div class="disk-info">
            <div class="disk-name">${d.disk || "??"}</div>
            <div class="disk-meta">Données indisponibles</div>
          </div>
          <div class="disk-status">
            <div class="health-status unknown">INCONNU</div>
          </div>
        </div>`;
      diskList.appendChild(card);
      return;
    }

    card.innerHTML = `
      <div class="disk-header">
        <div class="disk-info">
          <div class="disk-name">${d.disk || "??"}</div>
          <div class="disk-meta">
            ${d.model ? `<span>${d.model}</span>` : ""}
            ${d.serial ? `<span style="color:var(--muted)"> · ${d.serial}</span>` : ""}
            ${d.protocol ? `<span style="color:var(--muted)"> · ${d.protocol}</span>` : ""}
          </div>
        </div>
        <div class="disk-status">
          <div class="health-status ${healthClass}">
            <span class="health-icon">${health === "PASSED" ? "✓" : health === "FAILED" ? "✗" : "?"}</span>
            ${health}
          </div>
        </div>
      </div>

      <div class="disk-metrics">

        <div class="metric-item">
          <div class="metric-label">Température</div>
          <div class="metric-value temp-${tempClass}">
            ${
              temp !== null && temp !== undefined
                ? `<span class="temp-value">${temp}°C</span>
                 <div class="temp-gauge">
                   <div class="temp-bar" style="width:${tempPct}%"></div>
                 </div>`
                : "<span style='color:var(--muted)'>N/A</span>"
            }
          </div>
        </div>

        <div class="metric-item">
          <div class="metric-label">Heures de fonctionnement</div>
          <div class="metric-value">
            ${
              hours !== null && hours !== undefined
                ? `${hours.toLocaleString("fr")} h
                 <span style="font-size:11px;color:var(--muted)">
                   (≈ ${Math.round(hours / 24)} jours)
                 </span>`
                : "<span style='color:var(--muted)'>N/A</span>"
            }
          </div>
        </div>

        <div class="metric-item">
          <div class="metric-label">Secteurs réalloués</div>
          <div class="metric-value ${sectors > 0 ? "warning" : "ok"}">
            ${sectors}
            ${
              sectors > 0
                ? "<span style='font-size:11px;color:var(--yellow)'> ⚠️ Attention</span>"
                : "<span style='font-size:11px;color:var(--muted)'> OK</span>"
            }
          </div>
        </div>

        <div class="metric-item">
          <div class="metric-label">État de santé</div>
          <div class="metric-value ${healthClass}">
            ${
              health === "PASSED"
                ? "✅ Disque sain"
                : health === "FAILED"
                  ? "❌ Défaillant"
                  : "❓ Inconnu"
            }
          </div>
        </div>

      </div>
    `;

    diskList.appendChild(card);
  });

  container.appendChild(diskList);

  // ── Statut global OK ──────────────────────────────────────────
  if (!hasAlert && disks.length > 0) {
    const okBanner = document.createElement("div");
    okBanner.className = "smart-status-ok";
    okBanner.innerHTML = `
      <i data-lucide="shield-check"></i>
      Tous les disques sont en bonne santé — Aucune alerte détectée
    `;
    container.appendChild(okBanner);
  }

  refreshIcons();
}

// ─── HELPERS ─────────────────────────────────────────────────────
function _globalHealthText(disks) {
  if (!disks.length) return "N/A";
  if (disks.some((d) => d.available && d.health === "FAILED"))
    return "CRITIQUE";
  if (disks.some((d) => d.available && d.health === "UNKNOWN"))
    return "INCONNU";
  return "BON";
}

function _globalHealthColor(disks) {
  const text = _globalHealthText(disks);
  if (text === "CRITIQUE") return "var(--red)";
  if (text === "INCONNU") return "var(--yellow)";
  return "var(--green)";
}
