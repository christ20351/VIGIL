/**
 * VIGIL — agents.js
 * Grille des agents, modal de détail, historique
 */

// ─── STATS TOPBAR ─────────────────────────────────────────────────
function updateStats() {
  const total = Object.keys(computersData).length;
  const offline = Object.values(computersData).filter((d) => d.offline).length;
  const online = total - offline;

  document.getElementById("total-pcs").textContent = total;
  document.getElementById("online-pcs").textContent = online;
  document.getElementById("offline-pcs").textContent = offline;
  document.getElementById("total-connections").textContent = total;

  // compteurs des puces de filtre + résumé de la barre d'outils
  const set = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.textContent = v;
  };
  set("chip-count-all", total);
  set("chip-count-online", online);
  set("chip-count-offline", offline);
  const count = document.getElementById("agents-count");
  if (count) {
    if (!total) {
      count.innerHTML = "En attente du premier agent…";
    } else if (offline) {
      count.innerHTML = `<strong>${online}</strong>/<strong>${total}</strong> agents en ligne · <span class="lvl-crit">${offline} hors ligne</span>`;
    } else {
      count.innerHTML = `<strong>${total}</strong> agent${total > 1 ? "s" : ""} supervisé${total > 1 ? "s" : ""} · <span class="lvl-ok">parc nominal</span>`;
    }
  }
}

// ─── RECHERCHE & FILTRES ──────────────────────────────────────────
let agentSearchQuery = "";
let agentStatusFilter = "all"; // 'all' | 'online' | 'offline'

function onAgentSearch(q) {
  agentSearchQuery = (q || "").toLowerCase().trim();
  renderComputers();
}

function setAgentFilter(f) {
  agentStatusFilter = f || "all";
  document
    .querySelectorAll(".filter-chips .chip")
    .forEach((c) => c.classList.remove("active"));
  const chip = document.getElementById("chip-" + agentStatusFilter);
  if (chip) chip.classList.add("active");
  renderComputers();
}

function agentMatchesFilters(hostname, data) {
  if (agentStatusFilter === "online" && data.offline) return false;
  if (agentStatusFilter === "offline" && !data.offline) return false;
  if (agentSearchQuery) {
    const hay = [
      hostname,
      data.agent_ip || data.ip || "",
      data.system || "",
    ]
      .join(" ")
      .toLowerCase();
    if (!hay.includes(agentSearchQuery)) return false;
  }
  return true;
}

// Niveau de charge : sert à colorer barres, valeurs et liseré de carte
function metricLevel(v) {
  return v >= 85 ? "crit" : v >= 65 ? "warn" : "ok";
}
const METRIC_LEVEL_ORDER = { ok: 0, warn: 1, crit: 2 };

// ─── GRILLE AGENTS ────────────────────────────────────────────────
function renderComputers() {
  const grid = document.getElementById("computers-grid");
  const empty = document.getElementById("no-computers");
  if (!grid) return;
  const keys = Object.keys(computersData);

  // Filtrage recherche + statut
  const visibleKeys = keys.filter((h) => {
    const d = computersData[h];
    return d && agentMatchesFilters(h, d);
  });

  // Tri parlant : hors ligne en dernier, puis charge décroissante
  // (les machines « chaudes » remontent en premier)
  visibleKeys.sort((a, b) => {
    const da = computersData[a];
    const db = computersData[b];
    if (!!da.offline !== !!db.offline) return da.offline ? 1 : -1;
    const hot = (d) =>
      Math.max(d.cpu_percent || 0, d.memory?.percent || 0, d.disk?.percent || 0);
    return hot(db) - hot(a);
  });

  if (!keys.length) {
    grid.innerHTML = "";
    empty.style.display = "flex";
    refreshIcons();
    return;
  }
  empty.style.display = "none";

  // Supprimer les cartes disparues ou filtrées
  const visibleSet = new Set(visibleKeys);
  grid.querySelectorAll(".computer-card").forEach((c) => {
    if (!visibleSet.has(c.id.replace("card-", ""))) c.remove();
  });
  grid.querySelectorAll(".no-match").forEach((n) => n.remove());

  if (!visibleKeys.length) {
    grid.innerHTML = `
      <div class="no-match">
        <i data-lucide="search-x"></i>
        <div>Aucun agent ne correspond à la recherche / au filtre actif.</div>
      </div>`;
    refreshIcons();
    return;
  }

  let needsIcons = false;
  visibleKeys.forEach((hostname) => {
    const data = computersData[hostname];
    if (!data) return;
    let card = document.getElementById("card-" + hostname);
    const isNew = !card;
    if (isNew) {
      card = document.createElement("div");
      card.className = "computer-card";
      card.id = "card-" + hostname;
      card.onclick = () => openModal(hostname);
      grid.appendChild(card);
    }
    const wasOffline = card.dataset.offline === "1";
    const isOffline = !!data.offline;
    // réapplique l'ordre trié (hors ligne en dernier, charge décroissante)
    grid.appendChild(card);
    if (isNew || wasOffline !== isOffline) {
      // reconstruction complète : nouvelle carte ou changement en/hors ligne
      card.innerHTML = buildCardHTML(hostname, data);
      needsIcons = true;
      // animation d'entrée réservée aux cartes nouvellement créées
      if (isNew) {
        card.querySelectorAll(".bar-fill").forEach((f, i) => {
          const p = f.dataset.percent || "0";
          f.style.width = "0%";
          setTimeout(() => {
            f.style.width = p + "%";
          }, 120 + i * 130);
        });
      }
    } else {
      // flux live : mise à jour ciblée, sans reconstruire le DOM
      updateCardLive(card, data);
    }
    card.dataset.offline = isOffline ? "1" : "0";
    card.classList.toggle("offline", isOffline);
    // liseré de santé : reflet immédiat de l'état de charge
    card.classList.remove("lvl-ok", "lvl-warn", "lvl-crit");
    if (!data.offline) {
      const worst = Math.max(
        METRIC_LEVEL_ORDER[metricLevel(data.cpu_percent || 0)],
        METRIC_LEVEL_ORDER[metricLevel(data.memory?.percent || 0)],
        METRIC_LEVEL_ORDER[metricLevel(data.disk?.percent || 0)],
      );
      card.classList.add(["lvl-ok", "lvl-warn", "lvl-crit"][worst]);
    }
  });

  if (needsIcons) refreshIcons();
}

// ─── MISE À JOUR LIVE D'UNE CARTE ─────────────────────────────────
// Met à jour barres, statut et dernier relevé d'une carte existante
// sans reconstruire son HTML (fluide malgré le flux WS 1×/s).
function updateCardLive(card, data) {
  const cpu = (data.cpu_percent || 0).toFixed(1);
  const ram = (data.memory?.percent || 0).toFixed(1);
  const disk = (data.disk?.percent || 0).toFixed(1);
  [
    ["cpu", cpu],
    ["ram", ram],
    ["disk", disk],
  ].forEach(([cls, v]) => {
    const vNum = +v;
    const lvl = data.offline ? "ok" : metricLevel(vNum);
    const fill = card.querySelector(".bar-" + cls);
    if (!fill) return;
    fill.dataset.percent = v;
    fill.style.width = v + "%";
    fill.classList.remove("lvl-ok", "lvl-warn", "lvl-crit");
    fill.classList.add("lvl-" + lvl);
    const val = fill.closest(".stat-row")?.querySelector(".stat-value");
    if (val) {
      val.textContent = v + "%";
      val.classList.remove("lvl-ok", "lvl-warn", "lvl-crit");
      val.classList.add("lvl-" + lvl);
    }
  });
  const statusEl = card.querySelector(".agent-status");
  if (statusEl) {
    const statusText = data.offline ? "HORS LIGNE" : "EN LIGNE";
    if (statusEl.textContent !== statusText) statusEl.textContent = statusText;
  }
  const lastSeenEl = card.querySelector(".agent-lastseen-txt");
  if (lastSeenEl && data.timestamp) {
    lastSeenEl.textContent = "Dernier relevé : " + formatTimestamp(data.timestamp);
  }
}

// Icône Lucide selon la famille d'OS, pour une identification visuelle rapide
function osGlyph(system) {
  const s = (system || "").toLowerCase();
  if (s.includes("windows")) return "app-window";
  if (s.includes("linux") || s.includes("ubuntu") || s.includes("debian"))
    return "terminal";
  if (s.includes("mac") || s.includes("darwin") || s.includes("macos"))
    return "laptop";
  return "monitor";
}

// Affiche l'horodatage de façon lisible (sinon renvoie la valeur brute)
function formatTimestamp(ts) {
  const d = new Date(ts);
  return isNaN(d.getTime()) ? String(ts) : d.toLocaleTimeString("fr");
}

function buildCardHTML(hostname, data) {
  if (!data) {
    console.warn("buildCardHTML called with no data for", hostname);
    return '<div class="computer-card">données manquantes</div>';
  }
  const cpu = (data.cpu_percent || 0).toFixed(1);
  const ram = (data.memory?.percent || 0).toFixed(1);
  const disk = (data.disk?.percent || 0).toFixed(1);
  const cpuLvl = data.offline ? "ok" : metricLevel(+cpu);
  const ramLvl = data.offline ? "ok" : metricLevel(+ram);
  const diskLvl = data.offline ? "ok" : metricLevel(+disk);

  // Résolution IP
  let ip = data.agent_ip || "N/A";
  if (data.interfaces) {
    for (const iface of Object.values(data.interfaces)) {
      for (const addr of iface.addresses || []) {
        if (addr.type === "IPv4" && addr.address !== "127.0.0.1") {
          ip = ip === "N/A" ? addr.address : ip;
          break;
        }
      }
      if (ip !== "N/A" && ip !== data.agent_ip) break;
    }
  }

  const statusText = data.offline ? "HORS LIGNE" : "EN LIGNE";
  const statusClass = data.offline ? "offline" : "online";
  const systemName = data.system || "Système inconnu";
  const glyph = osGlyph(systemName);

  // badges groupe / maintenance (cache rafraîchi par fleet.js)
  let fleetBadges = "";
  const meta = (window.fleetMeta && window.fleetMeta.hosts) ? window.fleetMeta.hosts[hostname] : null;
  if (meta && meta.group) {
    fleetBadges += ` <span class="fleet-badge group">${escapeHtml(meta.group)}</span>`;
  }
  if (meta && meta.maintenance_until && new Date(meta.maintenance_until) > new Date()) {
    fleetBadges += ` <span class="fleet-badge maint">maintenance</span>`;
  }
  const overallLvl = data.offline
    ? "crit"
    : ["lvl-ok", "lvl-warn", "lvl-crit"][
        Math.max(
          METRIC_LEVEL_ORDER[cpuLvl],
          METRIC_LEVEL_ORDER[ramLvl],
          METRIC_LEVEL_ORDER[diskLvl],
        )
      ];

  const offlineSince =
    data.offline && data.offline_since
      ? `<div class="agent-offline-since"><i data-lucide="clock"></i> Hors ligne depuis le ${new Date(data.offline_since).toLocaleString("fr")}</div>`
      : "";

  const lastSeen = data.timestamp
    ? `<div class="agent-lastseen"><i data-lucide="radar"></i> <span class="agent-lastseen-txt">Dernier relevé : ${formatTimestamp(data.timestamp)}</span></div>`
    : "";

  return `
    <div class="agent-card-head">
      <div class="agent-glyph ${overallLvl}">
        <i data-lucide="${glyph}"></i>
      </div>
      <div class="agent-id">
        <div class="agent-host" title="${escapeHtml(hostname)}">${escapeHtml(hostname)}${fleetBadges}</div>
        <div class="agent-system"><i data-lucide="layers"></i> ${escapeHtml(systemName)}</div>
      </div>
      <div class="agent-status ${statusClass}">${statusText}</div>
    </div>
    <div class="agent-ip"><i data-lucide="globe"></i> ${escapeHtml(ip)}</div>
    ${offlineSince}
    <div class="agent-stats">
      ${metricBarHtml("CPU", "cpu", cpuLvl, cpu)}
      ${metricBarHtml("RAM", "ram", ramLvl, ram)}
      ${metricBarHtml("Disque", "disk", diskLvl, disk)}
    </div>
    ${lastSeen}
  `;
}

// ─── BARRES DE MÉTRIQUES ──────────────────────────────────────────
// Largeur finale posée inline : les rafraîchissements WS (1×/s) sont
// instantanés et sans scintillement.
function metricBarHtml(label, cls, lvl, pct) {
  return `
    <div class="stat-row">
      <div class="stat-label">${label}</div>
      <div class="bar-track"><div class="bar-fill stat-fill bar-${cls} lvl-${lvl}" data-percent="${pct}" style="width:${pct}%"></div></div>
      <div class="stat-value lvl-${lvl}">${pct}%</div>
    </div>`;
}

// ─── MODAL ────────────────────────────────────────────────────────
function openModal(hostname) {
  currentHostname = hostname;
  const data = computersData[hostname];
  document.getElementById("modal-title").textContent = hostname;
  document.getElementById("modal-ip").textContent = data.ip || "";

  const statusEl = document.getElementById("modal-status");
  if (statusEl) {
    statusEl.textContent = data.offline ? "HORS LIGNE" : "EN LIGNE";
    statusEl.className = "modal-status" + (data.offline ? " offline" : "");
  }
  document.getElementById("modal").classList.add("open");
  // charger le détail complet (processus, interfaces, connexions) puis le
  // rafraîchir périodiquement tant que la modale est ouverte
  if (typeof startDetailPolling === "function") startDetailPolling(hostname);
  switchTab("overview");
}

function closeModal() {
  document.getElementById("modal").classList.remove("open");
  if (liveChart) {
    liveChart.destroy();
    liveChart = null;
  }
  if (typeof stopDetailPolling === "function") stopDetailPolling();
  currentHostname = null;
}

// ─── TABS MODAL ───────────────────────────────────────────────────
function switchTab(name) {
  document
    .querySelectorAll(".tab")
    .forEach((t) => t.classList.remove("active"));
  document
    .querySelector(`[onclick="switchTab('${name}')"]`)
    .classList.add("active");
  document
    .querySelectorAll(".tab-content")
    .forEach((c) => c.classList.remove("active"));
  document.getElementById("tab-" + name).classList.add("active");

  if (liveChart) {
    liveChart.destroy();
    liveChart = null;
  }

  const data = computersData[currentHostname];
  if (!data) return;

  switch (name) {
    case "overview":
      renderOverview(currentHostname);
      break;
    case "processes":
      // le détail des processus n'est pas dans le flux WS allégé
      if (typeof fetchHostDetail === "function") fetchHostDetail(currentHostname);
      renderProcesses(data);
      break;
    case "network":
      if (typeof fetchHostDetail === "function") fetchHostDetail(currentHostname);
      renderNetwork(data);
      break;
    case "smart":
      console.log(`[SMART] switchTab -> smart for ${currentHostname}`);
      if (!currentHostname) {
        const container = document.getElementById("tab-smart");
        if (container) container.innerHTML = "<p>Aucun agent sélectionné.</p>";
      } else {
        try {
          updateSmartHealthTab(currentHostname);
        } catch (e) {
          console.warn("[SMART] error calling updateSmartHealthTab", e);
        }
      }
      break;
    case "history":
      renderHistory(currentHostname);
      break;
    case "protocols":
      if (typeof fetchHostDetail === "function") fetchHostDetail(currentHostname);
      renderProtocols(data);
      break;
    case "terminal":
      renderTerminal(currentHostname);
      break;
  }
  refreshIcons();
}

// ─── OVERVIEW ─────────────────────────────────────────────────────
function renderOverview(hostname) {
  const data = computersData[hostname];
  const cpu = (data.cpu_percent || 0).toFixed(1);
  const ram = (data.memory?.percent || 0).toFixed(1);
  const disk = (data.disk?.percent || 0).toFixed(1);
  const cpuLvl = data.offline ? "ok" : metricLevel(+cpu);
  const ramLvl = data.offline ? "ok" : metricLevel(+ram);
  const diskLvl = data.offline ? "ok" : metricLevel(+disk);
  const ramUsed = ((data.memory?.used || 0) / 1e9).toFixed(1);
  const ramTotal = ((data.memory?.total || 0) / 1e9).toFixed(1);
  const diskUsed = ((data.disk?.used || 0) / 1e9).toFixed(0);
  const diskTotal = ((data.disk?.total || 0) / 1e9).toFixed(0);

  const chartBlock = CHARTJS_OK
    ? `<div class="chart-wrap"><canvas id="live-chart"></canvas></div>`
    : `<div class="chart-offline"><i data-lucide="wifi-off"></i> Graphiques indisponibles — mode hors ligne</div>`;

  document.getElementById("tab-overview").innerHTML = `
    <div class="overview-grid">
      <div class="ov-card">
        <div class="ov-card-title"><i data-lucide="cpu"></i> Processeur</div>
        <div class="ov-big lvl-${cpuLvl}">${cpu}<span style="font-size:1rem;color:var(--muted)">%</span></div>
        <div class="ov-bar-wrap">
          <div class="ov-bar-track"><div class="ov-bar-fill lvl-${cpuLvl}" style="width:${cpu}%"></div></div>
        </div>
        <div class="ov-sub">Utilisation temps réel</div>
      </div>
      <div class="ov-card">
        <div class="ov-card-title"><i data-lucide="memory-stick"></i> Mémoire vive</div>
        <div class="ov-big lvl-${ramLvl}">${ram}<span style="font-size:1rem;color:var(--muted)">%</span></div>
        <div class="ov-bar-wrap">
          <div class="ov-bar-track"><div class="ov-bar-fill lvl-${ramLvl}" style="width:${ram}%"></div></div>
        </div>
        <div class="ov-sub">${ramUsed} GB / ${ramTotal} GB utilisés</div>
      </div>
      <div class="ov-card">
        <div class="ov-card-title"><i data-lucide="hard-drive"></i> Stockage</div>
        <div class="ov-big lvl-${diskLvl}">${disk}<span style="font-size:1rem;color:var(--muted)">%</span></div>
        <div class="ov-bar-wrap">
          <div class="ov-bar-track"><div class="ov-bar-fill lvl-${diskLvl}" style="width:${disk}%"></div></div>
        </div>
        <div class="ov-sub">${diskUsed} GB / ${diskTotal} GB utilisés</div>
      </div>
      <div class="ov-card">
        <div class="ov-card-title"><i data-lucide="info"></i> Système</div>
        <div class="sysinfo-row"><span class="sysinfo-key">OS</span><span class="sysinfo-val">${data.system || "N/A"}</span></div>
        <div class="sysinfo-row"><span class="sysinfo-key">Version</span><span class="sysinfo-val">${data.system_version || "N/A"}</span></div>
        <div class="sysinfo-row"><span class="sysinfo-key">Arch</span><span class="sysinfo-val">${data.architecture || "N/A"}</span></div>
        <div class="sysinfo-row"><span class="sysinfo-key">IP</span><span class="sysinfo-val">${data.ip || data.agent_ip || "N/A"}</span></div>
        <div class="sysinfo-row"><span class="sysinfo-key">Dernier relevé</span><span class="sysinfo-val">${data.timestamp || "N/A"}</span></div>
        ${
          data.offline && data.offline_since
            ? `<div class="sysinfo-row"><span class="sysinfo-key">Hors ligne depuis</span><span class="sysinfo-val">${new Date(data.offline_since).toLocaleString()}</span></div>`
            : ""
        }
        <div style="margin-top:0.85rem; text-align:center;">
          <button class="btn-ai-diagnose" onclick="triggerAgentAiDiagnosis('${hostname}')">
            <i data-lucide="bot"></i> Lancer le diagnostic IA
          </button>
        </div>
      </div>
    </div>

    <div class="chart-card">
      <div class="chart-header">
        <div class="chart-title"><i data-lucide="activity"></i> Activité en temps réel</div>
        <div class="chart-legend">
          <div class="legend-item"><div class="legend-dot" style="background:var(--cpu)"></div> CPU</div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--ram)"></div> RAM</div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--disk)"></div> Disque</div>
        </div>
      </div>
      ${chartBlock}
    </div>
  `;

  refreshIcons();
  if (CHARTJS_OK) initLiveChart(hostname);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

let procSearchQuery = "";
let procSortKey = "cpu_percent";
let procSortAsc = false;
let cpuFilter = 0;
let ramFilter = 0;

function setProcSort(key) {
  if (procSortKey === key) {
    procSortAsc = !procSortAsc;
  } else {
    procSortKey = key;
    procSortAsc = false;
  }
  const data = computersData[currentHostname];
  if (data) renderProcesses(data);
}

// ─── PROCESSUS ────────────────────────────────────────────────────
function renderProcesses(data) {
  const procs = data.processes || [];
  const query = (procSearchQuery || "").toLowerCase().trim();

  // Filtrer par recherche (nom, pid, user) et seuils CPU / RAM
  let filtered = procs.filter((p) => {
    const nameMatch =
      !query ||
      (p.name && p.name.toLowerCase().includes(query)) ||
      (p.username && p.username.toLowerCase().includes(query)) ||
      String(p.pid).includes(query);
    const cpuMatch = (p.cpu_percent || 0) >= cpuFilter;
    const ramMatch = (p.memory_percent || 0) >= ramFilter;
    return nameMatch && cpuMatch && ramMatch;
  });

  // Tri dynamique
  filtered.sort((a, b) => {
    let valA = a[procSortKey] ?? 0;
    let valB = b[procSortKey] ?? 0;
    if (typeof valA === "string") {
      valA = valA.toLowerCase();
      valB = (valB || "").toLowerCase();
      return procSortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    return procSortAsc ? valA - valB : valB - valA;
  });

  const arrow = (key) =>
    procSortKey === key
      ? `<span class="sort-arrow">${procSortAsc ? "▲" : "▼"}</span>`
      : "";

  const container = document.getElementById("tab-processes");
  if (!container) return;

  container.innerHTML = `
    <div class="proc-controls">
      <div class="proc-search-wrap">
        <i data-lucide="search"></i>
        <input
          type="text"
          id="proc-search"
          class="proc-search-input"
          placeholder="Rechercher un processus (nom, pid, utilisateur…)"
          value="${escapeHtml(procSearchQuery)}"
        />
      </div>
      <div class="proc-filters" style="display:flex; align-items:center; gap:8px;">
        <label style="font-size:0.75rem; color:var(--muted);">CPU ≥ <input type="number" id="filter-cpu" min="0" max="100" value="${cpuFilter}" style="width:48px; background:var(--bg3); border:1px solid var(--border); color:var(--text); padding:2px 4px; border-radius:4px;"></label>
        <label style="font-size:0.75rem; color:var(--muted);">RAM ≥ <input type="number" id="filter-ram" min="0" max="100" value="${ramFilter}" style="width:48px; background:var(--bg3); border:1px solid var(--border); color:var(--text); padding:2px 4px; border-radius:4px;"></label>
      </div>
      <span class="proc-count">${filtered.length} / ${procs.length} processus</span>
    </div>

    <div style="overflow-x:auto;">
      <table>
        <thead>
          <tr>
            <th class="th-sortable" onclick="setProcSort('pid')">PID ${arrow("pid")}</th>
            <th class="th-sortable" onclick="setProcSort('name')">NOM DU PROCESSUS ${arrow("name")}</th>
            <th class="th-sortable" onclick="setProcSort('username')">UTILISATEUR ${arrow("username")}</th>
            <th class="th-sortable" onclick="setProcSort('cpu_percent')">CPU % ${arrow("cpu_percent")}</th>
            <th class="th-sortable" onclick="setProcSort('memory_percent')">RAM % ${arrow("memory_percent")}</th>
            <th class="th-sortable" onclick="setProcSort('memory_rss')">RAM (MB) ${arrow("memory_rss")}</th>
            <th class="th-sortable" onclick="setProcSort('io_read_bytes')">I/O LUS ${arrow("io_read_bytes")}</th>
            <th class="th-sortable" onclick="setProcSort('io_write_bytes')">I/O ÉCRITS ${arrow("io_write_bytes")}</th>
            <th>STATUT</th>
          </tr>
        </thead>
        <tbody>
          ${
            filtered.length === 0
              ? `<tr><td colspan="9" style="text-align:center; padding:24px; color:var(--muted)">Aucun processus correspondant</td></tr>`
              : filtered
                  .map(
                    (p) => `
              <tr>
                <td><code>${p.pid || "—"}</code></td>
                <td class="td-name" title="${escapeHtml(p.name || "")}"><strong style="color:var(--text)">${escapeHtml(p.name || "N/A")}</strong></td>
                <td><span style="color:var(--muted)">${escapeHtml(p.username || "N/A")}</span></td>
                <td class="td-cpu">${(p.cpu_percent || 0).toFixed(1)}%</td>
                <td class="td-ram">${(p.memory_percent || 0).toFixed(1)}%</td>
                <td>${((p.memory_rss || 0) / 1e6).toFixed(1)} MB</td>
                <td>${((p.io_read_bytes || 0) / 1e6).toFixed(1)} MB</td>
                <td>${((p.io_write_bytes || 0) / 1e6).toFixed(1)} MB</td>
                <td><span class="badge" style="font-size:0.62rem">${escapeHtml(p.status || "active")}</span></td>
              </tr>
            `,
                  )
                  .join("")
          }
        </tbody>
      </table>
    </div>
  `;

  // Attach search and filter listeners
  const searchInput = document.getElementById("proc-search");
  if (searchInput) {
    searchInput.oninput = (e) => {
      procSearchQuery = e.target.value;
      renderProcesses(data);
      const s = document.getElementById("proc-search");
      if (s) {
        s.focus();
        s.setSelectionRange(s.value.length, s.value.length);
      }
    };
  }
  const cpuInput = document.getElementById("filter-cpu");
  const ramInput = document.getElementById("filter-ram");
  if (cpuInput)
    cpuInput.oninput = () => {
      cpuFilter = Number(cpuInput.value) || 0;
      renderProcesses(data);
    };
  if (ramInput)
    ramInput.oninput = () => {
      ramFilter = Number(ramInput.value) || 0;
      renderProcesses(data);
    };

  refreshIcons();
}

// ─── RÉSEAU ───────────────────────────────────────────────────────
function renderNetwork(data) {
  const net = data.network || {};
  const ifaces = data.interfaces || {};
  const fmt = (v) => (isNaN(v) ? "0" : v);

  let ifacesHTML = "";
  const ifaceKeys = Object.keys(ifaces);

  if (ifaceKeys.length > 0) {
    ifacesHTML = `
      <div class="ifaces-section-title"><i data-lucide="network"></i> Interfaces Réseau Détaillées (${ifaceKeys.length})</div>
      <div class="ifaces-grid">
        ${ifaceKeys
          .map((name) => {
            const iface = ifaces[name] || {};
            const isUp = iface.is_up;
            const statusClass = isUp ? "up" : "down";
            const statusText = isUp ? "ACTIVE (UP)" : "INACTIVE (DOWN)";
            const mac = iface.mac || "N/A";
            const speed = iface.speed ? `${iface.speed} Mbps` : "N/A";
            const mtu = iface.mtu ? `${iface.mtu} octets` : "N/A";
            const duplex = iface.duplex || "N/A";
            const ipv4Addrs = (iface.addresses || []).filter(
              (a) => a.type === "IPv4",
            );
            const ipv6Addrs = (iface.addresses || []).filter(
              (a) => a.type === "IPv6",
            );

            const rxMb = iface.bytes_recv
              ? (iface.bytes_recv / 1e6).toFixed(1) + " MB"
              : "—";
            const txMb = iface.bytes_sent
              ? (iface.bytes_sent / 1e6).toFixed(1) + " MB"
              : "—";
            const pktsRx = iface.packets_recv
              ? iface.packets_recv.toLocaleString()
              : "—";
            const pktsTx = iface.packets_sent
              ? iface.packets_sent.toLocaleString()
              : "—";
            const errs = (iface.errin || 0) + (iface.errout || 0);
            const drops = (iface.dropin || 0) + (iface.dropout || 0);

            return `
            <div class="iface-card">
              <div class="iface-header">
                <div class="iface-name"><i data-lucide="wifi"></i> ${name}</div>
                <span class="iface-pill ${statusClass}">${statusText}</span>
              </div>
              <div class="iface-detail-row">
                <span class="iface-key">Adresse MAC</span>
                <span class="iface-val"><code>${mac}</code></span>
              </div>
              <div class="iface-detail-row">
                <span class="iface-key">Vitesse / MTU</span>
                <span class="iface-val">${speed} | MTU: ${mtu}</span>
              </div>
              <div class="iface-detail-row">
                <span class="iface-key">Mode Duplex</span>
                <span class="iface-val">${duplex}</span>
              </div>
              ${ipv4Addrs
                .map(
                  (a) => `
                <div class="iface-detail-row">
                  <span class="iface-key">IPv4</span>
                  <span class="iface-val" style="color:var(--accent)"><code>${a.address}</code></span>
                </div>
              `,
                )
                .join("")}
              ${ipv6Addrs
                .slice(0, 1)
                .map(
                  (a) => `
                <div class="iface-detail-row">
                  <span class="iface-key">IPv6</span>
                  <span class="iface-val" title="${a.address}"><code>${a.address.slice(0, 18)}...</code></span>
                </div>
              `,
                )
                .join("")}
              <div class="iface-detail-row">
                <span class="iface-key">Trafic RX / TX</span>
                <span class="iface-val">↓${rxMb} | ↑${txMb}</span>
              </div>
              <div class="iface-detail-row">
                <span class="iface-key">Paquets RX / TX</span>
                <span class="iface-val">${pktsRx} / ${pktsTx}</span>
              </div>
              ${
                errs > 0 || drops > 0
                  ? `
                <div class="iface-detail-row" style="color:var(--red)">
                  <span class="iface-key" style="color:var(--red)">Erreurs / Drops</span>
                  <span class="iface-val">${errs} errs / ${drops} drops</span>
                </div>
              `
                  : `
                <div class="iface-detail-row">
                  <span class="iface-key">Erreurs</span>
                  <span class="iface-val" style="color:var(--green)">0 (Sain)</span>
                </div>
              `
              }
            </div>
          `;
          })
          .join("")}
      </div>
    `;
  }

  const container = document.getElementById("tab-network");
  if (!container) return;

  container.innerHTML = `
    <div class="net-grid">
      <div class="net-card">
        <div class="net-card-title"><i data-lucide="arrow-down-circle"></i> DÉBIT ENTRANT (DOWNLOAD)</div>
        <div class="net-stat"><span class="net-key">Débit Actuel</span><span class="net-val" style="color:var(--green)">${fmt((net.bytes_recv_per_sec / 1024).toFixed(1))} KB/s</span></div>
        <div class="net-stat"><span class="net-key">Total Reçu</span><span class="net-val">${fmt((net.bytes_recv / 1e9).toFixed(2))} GB</span></div>
        <div class="net-stat"><span class="net-key">Paquets Reçus</span><span class="net-val">${(net.packets_recv || 0).toLocaleString()}</span></div>
      </div>
      <div class="net-card">
        <div class="net-card-title"><i data-lucide="arrow-up-circle"></i> DÉBIT SORTANT (UPLOAD)</div>
        <div class="net-stat"><span class="net-key">Débit Actuel</span><span class="net-val" style="color:var(--cpu)">${fmt((net.bytes_sent_per_sec / 1024).toFixed(1))} KB/s</span></div>
        <div class="net-stat"><span class="net-key">Total Envoyé</span><span class="net-val">${fmt((net.bytes_sent / 1e9).toFixed(2))} GB</span></div>
        <div class="net-stat"><span class="net-key">Paquets Envoyés</span><span class="net-val">${(net.packets_sent || 0).toLocaleString()}</span></div>
      </div>
      <div class="net-card" style="grid-column: 1 / -1;">
        <div class="net-card-title"><i data-lucide="zap"></i> ACTIVITÉ CONNEXIONS RÉSEAU</div>
        <div style="display:flex; justify-content:space-around; padding:8px 0;">
          <div style="text-align:center"><div style="color:var(--muted); font-size:0.7rem;">TCP Établies</div><div style="font-size:1.4rem; font-weight:700; color:var(--green);">${data.protocols?.tcp?.established || net.active_connections || 0}</div></div>
          <div style="text-align:center"><div style="color:var(--muted); font-size:0.7rem;">Ports en Écoute</div><div style="font-size:1.4rem; font-weight:700; color:var(--accent);">${data.protocols?.tcp?.listen || (data.protocols?.listening_ports || []).length || 0}</div></div>
          <div style="text-align:center"><div style="color:var(--muted); font-size:0.7rem;">Sockets UDP</div><div style="font-size:1.4rem; font-weight:700; color:var(--yellow);">${data.protocols?.udp?.total || 0}</div></div>
        </div>
      </div>
    </div>
    ${ifacesHTML}
  `;
  refreshIcons();
}

// ─── PROTOCOLES ───────────────────────────────────────────────────
function renderProtocols(data) {
  const proto = data.protocols || {};
  const listening = proto.listening_ports || [];
  const connections = proto.tcp?.connections || [];

  let html = `
    <div class="proto-grid">
      <div class="proto-card">
        <div class="proto-title" style="color:var(--accent)"><i data-lucide="radio"></i> TCP</div>
        <div class="proto-stat"><span class="proto-key">Établies (ESTABLISHED)</span><span class="proto-val" style="color:var(--green)">${proto.tcp?.established || 0}</span></div>
        <div class="proto-stat"><span class="proto-key">En écoute (LISTEN)</span><span class="proto-val">${proto.tcp?.listen || 0}</span></div>
        <div class="proto-stat"><span class="proto-key">TIME_WAIT</span><span class="proto-val" style="color:var(--yellow)">${proto.tcp?.time_wait || 0}</span></div>
        <div class="proto-stat"><span class="proto-key">CLOSE_WAIT</span><span class="proto-val" style="color:var(--red)">${proto.tcp?.close_wait || 0}</span></div>
        <div class="proto-stat"><span class="proto-key">SYN_SENT / FIN_WAIT</span><span class="proto-val">${(proto.tcp?.syn_sent || 0) + (proto.tcp?.fin_wait || 0)}</span></div>
      </div>

      <div class="proto-card">
        <div class="proto-title" style="color:var(--yellow)"><i data-lucide="radio-tower"></i> UDP</div>
        <div class="proto-stat"><span class="proto-key">Total flux UDP</span><span class="proto-val">${proto.udp?.total || 0}</span></div>
        <div class="proto-stat"><span class="proto-key">Sockets UDP actifs</span><span class="proto-val">${(proto.udp?.connections || []).length}</span></div>
      </div>

      <div class="proto-card">
        <div class="proto-title" style="color:var(--muted)"><i data-lucide="bar-chart-2"></i> TOTAL SOCKETS</div>
        <div class="proto-stat"><span class="proto-key">Total Connexions</span><span class="proto-val" style="color:var(--accent)">${proto.total || 0}</span></div>
        <div class="proto-stat"><span class="proto-key">Ports LISTEN recensés</span><span class="proto-val">${listening.length}</span></div>
      </div>
    </div>
  `;

  // Tableau des ports en écoute avec processus et PID
  if (listening.length > 0) {
    html += `
      <div class="ports-section">
        <div class="ifaces-section-title"><i data-lucide="server"></i> Ports en Écoute Locale (LISTEN)</div>
        <div style="overflow-x:auto;">
          <table>
            <thead>
              <tr>
                <th>PORT</th>
                <th>PROTOCOLE</th>
                <th>ADRESSE IP D'ÉCOUTE</th>
                <th>PROCESSUS ASSOCIÉ</th>
                <th>PID</th>
              </tr>
            </thead>
            <tbody>
              ${listening
                .map(
                  (p) => `
                <tr>
                  <td><span class="port-badge">:${p.port}</span></td>
                  <td><strong>${p.protocol}</strong></td>
                  <td><code>${p.ip}</code></td>
                  <td><span class="proc-tag">${p.process || "N/A"}</span></td>
                  <td><code>${p.pid || "—"}</code></td>
                </tr>
              `,
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // Tableau des connexions actives
  if (connections.length > 0) {
    html += `
      <div class="ports-section">
        <div class="ifaces-section-title"><i data-lucide="activity"></i> Connexions TCP Établies (ESTABLISHED)</div>
        <div style="overflow-x:auto;">
          <table>
            <thead>
              <tr>
                <th>ADRESSE LOCALE</th>
                <th>ADRESSE DISTANTE</th>
                <th>STATUT</th>
                <th>PROCESSUS</th>
                <th>PID</th>
              </tr>
            </thead>
            <tbody>
              ${connections
                .map(
                  (c) => `
                <tr>
                  <td><code>${c.local_addr}</code></td>
                  <td><code>${c.remote_addr}</code></td>
                  <td><span class="badge online">${c.status || "ESTABLISHED"}</span></td>
                  <td><span class="proc-tag">${c.process || "N/A"}</span></td>
                  <td><code>${c.pid || "—"}</code></td>
                </tr>
              `,
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  const container = document.getElementById("tab-protocols");
  if (container) {
    container.innerHTML = html;
  }
  refreshIcons();
}

// ─── TERMINAL DISTANT ─────────────────────────────────────────────
// Exécute des commandes système sur l'agent sélectionné, directement
// depuis le dashboard. Sorties et historique conservés par machine.
const terminalHistory = {}; // hostname -> [{command, stdout, stderr, exit_code, ts}]

function renderTerminal(hostname) {
  const container = document.getElementById("tab-terminal");
  if (!container) return;
  const offline = computersData[hostname]?.offline;
  const hist = terminalHistory[hostname] || [];

  const logsHtml = hist
    .map(
      (h) => `
    <div class="term-entry">
      <div class="term-cmd"><span class="term-prompt">${escapeHtml(hostname)}</span>:${escapeHtml(h.command)}</div>
      ${h.stdout ? `<pre class="term-out">${escapeHtml(h.stdout)}</pre>` : ""}
      ${h.stderr ? `<pre class="term-err">${escapeHtml(h.stderr)}</pre>` : ""}
      ${h.exit_code != null && h.exit_code !== 0 ? `<div class="term-exit">exit code: ${h.exit_code}</div>` : ""}
    </div>`,
    )
    .join("");

  container.innerHTML = `
    <div class="terminal-box">
      <div class="term-header">
        <i data-lucide="terminal"></i>
        <span>Terminal distant — ${escapeHtml(hostname)}</span>
        ${offline ? '<span class="term-warn">⚠ agent hors ligne</span>' : ""}
      </div>
      <div class="term-body" id="term-body">${logsHtml || '<div class="term-empty">Aucune commande exécutée. Les commandes s\'exécutent avec les droits du service agent.</div>'}</div>
      <div class="term-input-row">
        <span class="term-prompt">$</span>
        <input type="text" id="term-input" class="term-input" placeholder="Commande système à exécuter sur ${escapeHtml(hostname)}…"
               autocomplete="off" spellcheck="false" ${offline ? "disabled" : ""} />
        <button class="term-run" id="term-run" ${offline ? "disabled" : ""}>
          <i data-lucide="play"></i> Exécuter
        </button>
      </div>
    </div>
  `;
  refreshIcons();

  const input = document.getElementById("term-input");
  const body = document.getElementById("term-body");
  if (body) body.scrollTop = body.scrollHeight;

  const run = async () => {
    const command = (input?.value || "").trim();
    if (!command) return;
    input.value = "";
    await runRemoteCommand(hostname, command);
  };

  document.getElementById("term-run")?.addEventListener("click", run);
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      run();
    }
  });
}

async function runRemoteCommand(hostname, command) {
  const body = document.getElementById("term-body");
  const runBtn = document.getElementById("term-run");
  if (runBtn) runBtn.disabled = true;
  try {
    const entry = { command, stdout: "", stderr: "… exécution en cours", exit_code: null };
    terminalHistory[hostname] = [...(terminalHistory[hostname] || []), entry];
    if (body) {
      const div = document.createElement("div");
      div.className = "term-entry";
      div.innerHTML = `<div class="term-cmd"><span class="term-prompt">${escapeHtml(hostname)}</span>:${escapeHtml(command)}</div><pre class="term-err">… exécution en cours</pre>`;
      body.appendChild(div);
      body.scrollTop = body.scrollHeight;
    }

    const res = await vigilFetch(
      `/api/computers/${encodeURIComponent(hostname)}/command`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command }),
      },
    );
    const data = await res.json().catch(() => ({}));
    entry.exit_code = data.exit_code;
    if (data.ok) {
      entry.stdout = data.stdout || "";
      entry.stderr = data.stderr || "";
    } else {
      entry.stderr = data.error || "Échec de la commande.";
    }
    renderTerminal(hostname);
  } catch (e) {
    terminalHistory[hostname] = [
      ...(terminalHistory[hostname] || []),
      { command, stdout: "", stderr: e.message, exit_code: -1 },
    ];
    renderTerminal(hostname);
  } finally {
    if (runBtn) runBtn.disabled = false;
  }
}
