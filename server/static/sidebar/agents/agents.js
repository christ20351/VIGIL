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
}

// ─── GRILLE AGENTS ────────────────────────────────────────────────
function renderComputers() {
  const grid = document.getElementById("computers-grid");
  const empty = document.getElementById("no-computers");
  const keys = Object.keys(computersData);

  if (!keys.length) {
    grid.innerHTML = "";
    empty.style.display = "flex";
    refreshIcons();
    return;
  }
  empty.style.display = "none";

  keys.forEach((hostname) => {
    const data = computersData[hostname];
    if (!data) {
      console.warn("skipping renderComputers: no data for", hostname);
      return;
    }
    let card = document.getElementById("card-" + hostname);
    if (!card) {
      card = document.createElement("div");
      card.className = "computer-card";
      card.id = "card-" + hostname;
      card.onclick = () => openModal(hostname);
      grid.appendChild(card);
    }
    card.innerHTML = buildCardHTML(hostname, data);
    card.classList.toggle("offline", !!data.offline);
  });

  // Supprimer les cartes d'agents disparus
  grid.querySelectorAll(".computer-card").forEach((c) => {
    if (!computersData[c.id.replace("card-", "")]) c.remove();
  });

  refreshIcons();
  setTimeout(animateAllAgentStats, 60);
}

function buildCardHTML(hostname, data) {
  if (!data) {
    console.warn("buildCardHTML called with no data for", hostname);
    return '<div class="computer-card">données manquantes</div>';
  }
  const cpu = (data.cpu_percent || 0).toFixed(1);
  const ram = (data.memory?.percent || 0).toFixed(1);
  const disk = (data.disk?.percent || 0).toFixed(1);

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
  const systemName = (data.system || "").split(" ")[0] || "N/A";

  const offlineSince =
    data.offline && data.offline_since
      ? `<div class="agent-offline-since">Depuis le ${new Date(data.offline_since).toLocaleString("fr")}</div>`
      : "";

  return `
    <div class="agent-icon-wrapper">
      <img src="/static/images/host-${data.offline ? "offline" : "online"}.svg" class="agent-icon" alt="host" onerror="this.style.display='none'">
    </div>
    <div class="agent-details">
      <div class="agent-host">${hostname}</div>
      <div class="agent-ip"><i data-lucide="globe"></i> ${ip}</div>
      <div class="agent-system"><i data-lucide="layers"></i> ${systemName}</div>
      <div class="agent-status ${statusClass}">${statusText}</div>
      ${offlineSince}
      <div class="agent-stats">
        <div class="stat-row">
          <div class="stat-label">CPU</div>
          <div class="bar-track"><div class="bar-fill bar-cpu" data-percent="${cpu}"></div></div>
          <div class="stat-value">${cpu}%</div>
        </div>
        <div class="stat-row">
          <div class="stat-label">RAM</div>
          <div class="bar-track"><div class="bar-fill bar-ram" data-percent="${ram}"></div></div>
          <div class="stat-value">${ram}%</div>
        </div>
        <div class="stat-row">
          <div class="stat-label">DD</div>
          <div class="bar-track"><div class="bar-fill bar-disk" data-percent="${disk}"></div></div>
          <div class="stat-value">${disk}%</div>
        </div>
      </div>
    </div>
  `;
}

// Animation décalée des barres au chargement
function animateAllAgentStats() {
  document.querySelectorAll(".computer-card").forEach((card, cardIndex) => {
    card.querySelectorAll(".agent-stats .bar-fill").forEach((f, i) => {
      const p = f.dataset.percent || "0";
      f.style.width = "0%";
      setTimeout(
        () => {
          f.style.width = p + "%";
        },
        80 + cardIndex * 40 + i * 120,
      );
    });
  });
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
  switchTab("overview");
}

function closeModal() {
  document.getElementById("modal").classList.remove("open");
  if (liveChart) {
    liveChart.destroy();
    liveChart = null;
  }
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
      renderProcesses(data);
      break;
    case "network":
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
      renderProtocols(data);
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
  const ramUsed = ((data.memory?.used || 0) / 1e9).toFixed(1);
  const ramTotal = ((data.memory?.total || 0) / 1e9).toFixed(1);
  const diskUsed = ((data.disk?.used || 0) / 1e9).toFixed(0);
  const diskTotal = ((data.disk?.total || 0) / 1e9).toFixed(0);

  const chartBlock = CHARTJS_OK
    ? `<div class="chart-wrap"><canvas id="live-chart"></canvas></div>`
    : `<div class="chart-offline">Graphiques indisponibles — mode hors ligne</div>`;

  document.getElementById("tab-overview").innerHTML = `
    <div class="overview-grid">
      <div class="ov-card">
        <div class="ov-card-title"><i data-lucide="cpu"></i> PROCESSEUR</div>
        <div class="ov-big" style="color:var(--cpu)">${cpu}<span style="font-size:1rem;color:var(--muted)">%</span></div>
        <div class="ov-bar-wrap">
          <div class="ov-bar-track"><div class="ov-bar-fill bar-cpu" style="width:${cpu}%"></div></div>
        </div>
        <div class="ov-sub">Utilisation temps réel</div>
      </div>
      <div class="ov-card">
        <div class="ov-card-title"><i data-lucide="memory-stick"></i> MÉMOIRE RAM</div>
        <div class="ov-big" style="color:var(--ram)">${ram}<span style="font-size:1rem;color:var(--muted)">%</span></div>
        <div class="ov-bar-wrap">
          <div class="ov-bar-track"><div class="ov-bar-fill bar-ram" style="width:${ram}%"></div></div>
        </div>
        <div class="ov-sub">${ramUsed} GB / ${ramTotal} GB utilisés</div>
      </div>
      <div class="ov-card">
        <div class="ov-card-title"><i data-lucide="hard-drive"></i> STOCKAGE</div>
        <div class="ov-big" style="color:var(--disk)">${disk}<span style="font-size:1rem;color:var(--muted)">%</span></div>
        <div class="ov-bar-wrap">
          <div class="ov-bar-track"><div class="ov-bar-fill bar-disk" style="width:${disk}%"></div></div>
        </div>
        <div class="ov-sub">${diskUsed} GB / ${diskTotal} GB utilisés</div>
      </div>
      <div class="ov-card">
        <div class="ov-card-title"><i data-lucide="info"></i> SYSTÈME</div>
        <div class="sysinfo-row"><span class="sysinfo-key">OS</span><span class="sysinfo-val">${data.system || "N/A"}</span></div>
        <div class="sysinfo-row"><span class="sysinfo-key">VERSION</span><span class="sysinfo-val">${data.system_version || "N/A"}</span></div>
        <div class="sysinfo-row"><span class="sysinfo-key">ARCH</span><span class="sysinfo-val">${data.architecture || "N/A"}</span></div>
        <div class="sysinfo-row"><span class="sysinfo-key">IP</span><span class="sysinfo-val">${data.ip || "N/A"}</span></div>
        <div class="sysinfo-row"><span class="sysinfo-key">MAJ</span><span class="sysinfo-val">${data.timestamp || "N/A"}</span></div>
      </div>
    </div>

    <div class="chart-card">
      <div class="chart-header">
        <div class="chart-title"><i data-lucide="activity"></i> ACTIVITÉ EN TEMPS RÉEL</div>
        <div class="chart-legend">
          <div class="legend-item"><div class="legend-dot" style="background:var(--cpu)"></div> CPU</div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--ram)"></div> RAM</div>
          <div class="legend-item"><div class="legend-dot" style="background:var(--disk)"></div> DISK</div>
        </div>
      </div>
      ${chartBlock}
    </div>
  `;

  refreshIcons();
  if (CHARTJS_OK) initLiveChart(hostname);
}

// ─── PROCESSUS ────────────────────────────────────────────────────
function renderProcesses(data) {
  const procs = data.processes || [];
  document.getElementById("tab-processes").innerHTML = `
    <div class="proc-header">
      <span class="section-label">Processus actifs</span>
      <span class="proc-count">${procs.length} processus</span>
    </div>
    <table>
      <thead>
        <tr>
          <th>NOM</th><th>CPU %</th><th>RAM %</th><th>RAM (MB)</th><th>IO LUS</th><th>IO ÉCRITS</th>
        </tr>
      </thead>
      <tbody>
        ${procs
          .slice(0, 30)
          .map(
            (p) => `
          <tr>
            <td class="td-name" title="${p.name || ""}">${p.name || "N/A"}</td>
            <td class="td-cpu">${(p.cpu_percent || 0).toFixed(1)}%</td>
            <td class="td-ram">${(p.memory_percent || 0).toFixed(1)}%</td>
            <td>${((p.memory_rss || 0) / 1e6).toFixed(1)} MB</td>
            <td>${((p.io_read_bytes || 0) / 1e6).toFixed(1)} MB</td>
            <td>${((p.io_write_bytes || 0) / 1e6).toFixed(1)} MB</td>
          </tr>`,
          )
          .join("")}
      </tbody>
    </table>
  `;
}

// ─── RÉSEAU ───────────────────────────────────────────────────────
function renderNetwork(data) {
  const net = data.network || {};
  const fmt = (v) => (isNaN(v) ? "0" : v);
  document.getElementById("tab-network").innerHTML = `
    <div class="net-grid">
      <div class="net-card">
        <div class="net-card-title"><i data-lucide="arrow-down-circle"></i> DÉBIT ENTRANT</div>
        <div class="net-stat"><span class="net-key">DÉBIT/s</span><span class="net-val" style="color:var(--green)">${fmt((net.bytes_recv_per_sec / 1024).toFixed(1))} KB/s</span></div>
        <div class="net-stat"><span class="net-key">TOTAL REÇU</span><span class="net-val">${fmt((net.bytes_recv / 1e9).toFixed(2))} GB</span></div>
      </div>
      <div class="net-card">
        <div class="net-card-title"><i data-lucide="arrow-up-circle"></i> DÉBIT SORTANT</div>
        <div class="net-stat"><span class="net-key">DÉBIT/s</span><span class="net-val" style="color:var(--cpu)">${fmt((net.bytes_sent_per_sec / 1024).toFixed(1))} KB/s</span></div>
        <div class="net-stat"><span class="net-key">TOTAL ENVOYÉ</span><span class="net-val">${fmt((net.bytes_sent / 1e9).toFixed(2))} GB</span></div>
      </div>
      <div class="net-card">
        <div class="net-card-title"><i data-lucide="zap"></i> CONNEXIONS</div>
        <div class="net-stat"><span class="net-key">ACTIVES</span><span class="net-val" style="color:var(--accent)">${net.active_connections || 0}</span></div>
      </div>
    </div>
  `;
  refreshIcons();
}

// ─── PROTOCOLES ───────────────────────────────────────────────────
function renderProtocols(data) {
  const proto = data.protocols || {};
  let html = '<div class="proto-grid">';

  if (proto.tcp)
    html += `
    <div class="proto-card">
      <div class="proto-title" style="color:var(--accent)"><i data-lucide="radio"></i> TCP</div>
      <div class="proto-stat"><span class="proto-key">Établies</span><span class="proto-val" style="color:var(--green)">${proto.tcp.established || 0}</span></div>
      <div class="proto-stat"><span class="proto-key">En écoute</span><span class="proto-val">${proto.tcp.listen || 0}</span></div>
      <div class="proto-stat"><span class="proto-key">TIME_WAIT</span><span class="proto-val" style="color:var(--yellow)">${proto.tcp.time_wait || 0}</span></div>
      <div class="proto-stat"><span class="proto-key">CLOSE_WAIT</span><span class="proto-val" style="color:var(--red)">${proto.tcp.close_wait || 0}</span></div>
    </div>`;

  if (proto.udp)
    html += `
    <div class="proto-card">
      <div class="proto-title" style="color:var(--yellow)"><i data-lucide="radio-tower"></i> UDP</div>
      <div class="proto-stat"><span class="proto-key">Total</span><span class="proto-val">${proto.udp.total || 0}</span></div>
      <div class="proto-stat"><span class="proto-key">Connexions actives</span><span class="proto-val">${(proto.udp.connections || []).length}</span></div>
    </div>`;

  if (proto.total !== undefined)
    html += `
    <div class="proto-card">
      <div class="proto-title" style="color:var(--muted)"><i data-lucide="bar-chart-2"></i> TOTAL</div>
      <div class="proto-stat"><span class="proto-key">Connexions réseau</span><span class="proto-val" style="color:var(--accent)">${proto.total}</span></div>
    </div>`;

  html += "</div>";
  document.getElementById("tab-protocols").innerHTML = html;
  refreshIcons();
}
