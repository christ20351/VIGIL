/* ─────────────────────────────────────────────────────────────
   VIGIL — script.js
   ───────────────────────────────────────────────────────────── */

// ─── DÉTECTION HORS-LIGNE ──────────────────────────────────────────
//
// window.CHARTJS_UNAVAILABLE  → mis à true par l'attribut onerror
//                               du <script> dans le HTML si le CDN
//                               Chart.js est inaccessible.
//
// window.LUCIDE_UNAVAILABLE   → mis à true si le CDN Lucide échoue.
//
// Ces deux flags sont définis dans le HTML AVANT ce script,
// donc on peut les lire ici dès le chargement.

const CHARTJS_OK = !window.CHARTJS_UNAVAILABLE && typeof Chart !== "undefined";
const LUCIDE_OK = !window.LUCIDE_UNAVAILABLE && typeof lucide !== "undefined";

// Wrapper Lucide : appelle createIcons() seulement si disponible,
// sinon remplace les <i data-lucide> par un carré neutre (CSS .icon-fallback)
function refreshIcons() {
  if (LUCIDE_OK) {
    lucide.createIcons();
  } else {
    document.querySelectorAll("i[data-lucide]").forEach((el) => {
      if (!el.dataset.replaced) {
        const span = document.createElement("span");
        span.className = "icon-fallback";
        el.replaceWith(span);
      }
    });
  }
}

// ─── STATE ────────────────────────────────────────────────────────
let computersData = {};
let currentHostname = null;
let ws = null;
let liveChart = null;

// filtres appliqués à la liste des processus (pourcentage)
let cpuFilter = 0;
let ramFilter = 0;

const MAX_POINTS = 40;
const chartHistory = {}; // { hostname: { cpu[], ram[], disk[], labels[] } }

// ─── INIT ─────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  refreshIcons();
  initWebSocket();

  document.getElementById("btn-close").onclick = closeModal;
  document.getElementById("modal").addEventListener("click", (e) => {
    if (e.target === document.getElementById("modal")) closeModal();
  });

  // Données de démo : retire ce bloc quand les vrais agents sont connectés
  injectDemoData();
});

// ─── DÉMO ─────────────────────────────────────────────────────────
function injectDemoData() {
  const hosts = ["WORKSTATION-01", "SERVER-PROD", "DEV-MACHINE", "LAPTOP-RH"];
  const oses = [
    "Windows 11 Pro",
    "Ubuntu 22.04 LTS",
    "Windows 10",
    "macOS Ventura",
  ];

  hosts.forEach((h, i) => {
    computersData[h] = makeFakeAgent(h, oses[i]);
    chartHistory[h] = { cpu: [], ram: [], disk: [], labels: [] };
  });

  updateStats();
  renderComputers();

  setInterval(() => {
    hosts.forEach((h) => {
      const d = computersData[h];
      d.cpu_percent = clamp(d.cpu_percent + rand(-8, 8), 2, 98);
      d.memory.percent = clamp(d.memory.percent + rand(-4, 4), 10, 95);
      d.disk.percent = clamp(d.disk.percent + rand(-1, 1), 10, 98);
      pushHistory(h, d);
    });
    renderComputers();

    if (
      currentHostname &&
      document.getElementById("modal").classList.contains("open")
    ) {
      const activeTab = document.querySelector(".tab-content.active");
      if (activeTab?.id === "tab-overview") renderOverview(currentHostname);
      updateLiveChart(currentHostname);
    }
  }, 1500);
}

function makeFakeAgent(hostname, os) {
  return {
    hostname,
    system: os,
    system_version: "22H2",
    architecture: "x86_64",
    cpu_percent: rand(10, 60),
    memory: { percent: rand(30, 80), used: 6.2e9, total: 16e9 },
    disk: { percent: rand(30, 75), used: 200e9, total: 512e9 },
    ip: `192.168.1.${rand(10, 200)}`,
    timestamp: new Date().toLocaleTimeString(),
    processes: Array.from({ length: 20 }, (_, i) => ({
      name: [
        "chrome.exe",
        "svchost.exe",
        "python.exe",
        "node.exe",
        "code.exe",
        "explorer.exe",
      ][i % 6],
      cpu_percent: rand(0, 20),
      memory_percent: rand(0, 10),
      memory_rss: rand(50, 800) * 1e6,
      io_read_bytes: rand(0, 500) * 1e6,
      io_write_bytes: rand(0, 200) * 1e6,
    })),
    network: {
      bytes_recv_per_sec: rand(100, 5000) * 1024,
      bytes_sent_per_sec: rand(50, 2000) * 1024,
      bytes_recv: rand(1, 50) * 1e9,
      bytes_sent: rand(1, 20) * 1e9,
      active_connections: rand(20, 120),
    },
    protocols: {
      tcp: {
        established: rand(10, 60),
        listen: rand(5, 20),
        time_wait: rand(0, 10),
        close_wait: rand(0, 5),
        connections: [],
      },
      udp: { total: rand(5, 30), connections: [] },
      total: rand(30, 100),
    },
    interfaces: {
      Ethernet: {
        addresses: [{ type: "IPv4", address: `192.168.1.${rand(10, 200)}` }],
      },
    },
  };
}

function rand(a, b) {
  return Math.floor(Math.random() * (b - a + 1)) + a;
}
function clamp(v, mn, mx) {
  return Math.min(Math.max(v, mn), mx);
}

// ─── WEBSOCKET ────────────────────────────────────────────────────
function initWebSocket() {
  try {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws`);

    ws.onopen = () => setWsStatus(true);
    ws.onclose = () => setWsStatus(false);
    ws.onerror = () => setWsStatus(false);

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);

        if (msg.type === "update" && msg.data) {
          computersData = msg.data;
          Object.keys(computersData).forEach((h) => {
            if (!chartHistory[h])
              chartHistory[h] = { cpu: [], ram: [], disk: [], labels: [] };
            pushHistory(h, computersData[h]);
          });
          updateStats();
          renderComputers();
        }

        if (msg.type === "agent_update" && msg.hostname && msg.data) {
          computersData[msg.hostname] = msg.data;
          if (!chartHistory[msg.hostname])
            chartHistory[msg.hostname] = {
              cpu: [],
              ram: [],
              disk: [],
              labels: [],
            };
          pushHistory(msg.hostname, msg.data);
          updateStats();
          renderComputers();

          if (
            currentHostname === msg.hostname &&
            document.getElementById("modal").classList.contains("open")
          ) {
            const active = document.querySelector(".tab-content.active");
            if (active?.id === "tab-overview") renderOverview(msg.hostname);
            updateLiveChart(msg.hostname);
          }
        }
      } catch {
        /* message malformé, on ignore */
      }
    };
  } catch {
    /* WebSocket non disponible */
  }
}

function setWsStatus(ok) {
  document.getElementById("ws-dot").className =
    "ws-dot" + (ok ? "" : " disconnected");
  document.getElementById("ws-label").textContent = ok
    ? "WebSocket actif"
    : "Déconnecté";
}

// ─── HISTORIQUE ───────────────────────────────────────────────────
function pushHistory(hostname, data) {
  const h = chartHistory[hostname];
  const now = new Date().toLocaleTimeString("fr", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  h.labels.push(now);
  h.cpu.push(+(data.cpu_percent || 0).toFixed(1));
  h.ram.push(+(data.memory?.percent || 0).toFixed(1));
  h.disk.push(+(data.disk?.percent || 0).toFixed(1));
  if (h.labels.length > MAX_POINTS) {
    h.labels.shift();
    h.cpu.shift();
    h.ram.shift();
    h.disk.shift();
  }
}

// ─── STATS TOPBAR ─────────────────────────────────────────────────
function updateStats() {
  const total = Object.keys(computersData).length;
  document.getElementById("total-pcs").textContent = total;
  document.getElementById("online-pcs").textContent = total;
  document.getElementById("offline-pcs").textContent = 0;
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
    let card = document.getElementById("card-" + hostname);
    if (!card) {
      card = document.createElement("div");
      card.className = "computer-card";
      card.id = "card-" + hostname;
      card.onclick = () => openModal(hostname);
      grid.appendChild(card);
    }
    card.innerHTML = buildCardHTML(hostname, computersData[hostname]);
  });

  // Supprimer les cartes d'agents déconnectés
  grid.querySelectorAll(".computer-card").forEach((c) => {
    if (!computersData[c.id.replace("card-", "")]) c.remove();
  });

  refreshIcons();
}

function buildCardHTML(hostname, data) {
  const cpu = (data.cpu_percent || 0).toFixed(1);
  const ram = (data.memory?.percent || 0).toFixed(1);
  const disk = (data.disk?.percent || 0).toFixed(1);

  // préférer l'adresse remontée par la configuration du serveur (agent_ip)
  let ip = data.agent_ip || "N/A";
  if (data.interfaces) {
    for (const iface of Object.values(data.interfaces)) {
      for (const addr of iface.addresses || []) {
        if (addr.type === "IPv4" && addr.address !== "127.0.0.1") {
          ip = ip === "N/A" ? addr.address : ip; // ne remplacer que si on n'a pas déjà d'IP
          break;
        }
      }
      if (ip !== "N/A" && ip !== data.agent_ip) break;
    }
  }

  return `
    <div class="card-header">
      <div class="card-host">
        <i data-lucide="monitor"></i>
        ${hostname}
      </div>
      <span class="badge online">EN LIGNE</span>
    </div>
    <div class="card-metrics">
      <div class="metric-row">
        <div class="metric-head">
          <span class="metric-name"><i data-lucide="cpu"></i> CPU</span>
          <span class="metric-pct" style="color:var(--cpu)">${cpu}%</span>
        </div>
        <div class="bar-track"><div class="bar-fill bar-cpu" style="width:${cpu}%"></div></div>
      </div>
      <div class="metric-row">
        <div class="metric-head">
          <span class="metric-name"><i data-lucide="memory-stick"></i> RAM</span>
          <span class="metric-pct" style="color:var(--ram)">${ram}%</span>
        </div>
        <div class="bar-track"><div class="bar-fill bar-ram" style="width:${ram}%"></div></div>
      </div>
      <div class="metric-row">
        <div class="metric-head">
          <span class="metric-name"><i data-lucide="hard-drive"></i> DISK</span>
          <span class="metric-pct" style="color:var(--disk)">${disk}%</span>
        </div>
        <div class="bar-track"><div class="bar-fill bar-disk" style="width:${disk}%"></div></div>
      </div>
    </div>
    <div class="card-footer">
      <div class="footer-item"><i data-lucide="globe"></i> ${ip}</div>
      <div class="footer-item"><i data-lucide="layers"></i> ${(data.system || "N/A").split(" ")[0]}</div>
    </div>
  `;
}

// ─── MODAL ────────────────────────────────────────────────────────
function openModal(hostname) {
  currentHostname = hostname;
  const data = computersData[hostname];
  document.getElementById("modal-title").textContent = hostname;
  document.getElementById("modal-ip").textContent = data.ip || "";
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

// ─── TABS ─────────────────────────────────────────────────────────
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

  // Bloc graphique : canvas si Chart.js OK, message hors-ligne sinon
  const chartBlock = CHARTJS_OK
    ? `<div class="chart-wrap"><canvas id="live-chart"></canvas></div>`
    : `<div class="chart-offline">
         <i data-lucide="wifi-off"></i>
         Graphiques indisponibles — Chart.js non chargé (mode hors ligne)
       </div>`;

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
        <div class="sysinfo-row"><span class="sysinfo-key">IP</span><span class="sysinfo-val">${data.ip || data.agent_ip || "N/A"}</span></div>
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

// ─── CHART.JS ─────────────────────────────────────────────────────
function initLiveChart(hostname) {
  if (liveChart) {
    liveChart.destroy();
    liveChart = null;
  }
  const canvas = document.getElementById("live-chart");
  if (!canvas || !CHARTJS_OK) return;

  const h = chartHistory[hostname] || {
    cpu: [],
    ram: [],
    disk: [],
    labels: [],
  };

  const mkDataset = (label, data, color) => ({
    label,
    data: [...data],
    borderColor: color,
    backgroundColor: color + "18",
    borderWidth: 1.5,
    pointRadius: 0,
    tension: 0.4,
    fill: true,
  });

  liveChart = new Chart(canvas, {
    type: "line",
    data: {
      labels: [...h.labels],
      datasets: [
        mkDataset("CPU", h.cpu, "#ff6b6b"),
        mkDataset("RAM", h.ram, "#4ecdc4"),
        mkDataset("DISK", h.disk, "#a78bfa"),
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          ticks: {
            color: "#5a6a85",
            font: { family: "JetBrains Mono", size: 10 },
            maxTicksLimit: 8,
            maxRotation: 0,
          },
          grid: { color: "rgba(255,255,255,0.04)" },
          border: { color: "rgba(255,255,255,0.08)" },
        },
        y: {
          min: 0,
          max: 100,
          ticks: {
            color: "#5a6a85",
            font: { family: "JetBrains Mono", size: 10 },
            callback: (v) => v + "%",
          },
          grid: { color: "rgba(255,255,255,0.04)" },
          border: { color: "rgba(255,255,255,0.08)" },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0d1117",
          borderColor: "#1e2636",
          borderWidth: 1,
          titleColor: "#5a6a85",
          bodyColor: "#e2e8f0",
          titleFont: { family: "JetBrains Mono", size: 10 },
          bodyFont: { family: "JetBrains Mono", size: 11 },
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y}%`,
          },
        },
      },
    },
  });
}

function updateLiveChart(hostname) {
  if (!liveChart || !CHARTJS_OK) return;
  const h = chartHistory[hostname];
  if (!h) return;
  liveChart.data.labels = [...h.labels];
  liveChart.data.datasets[0].data = [...h.cpu];
  liveChart.data.datasets[1].data = [...h.ram];
  liveChart.data.datasets[2].data = [...h.disk];
  liveChart.update("none");
}

// ─── PROCESSUS ────────────────────────────────────────────────────
function renderProcesses(data) {
  const procs = data.processes || [];
  // appliquer les filtres
  const filtered = procs.filter(
    (p) =>
      (p.cpu_percent || 0) >= cpuFilter && (p.memory_percent || 0) >= ramFilter,
  );

  document.getElementById("tab-processes").innerHTML = `
    <div class="proc-header">
      <span class="section-label">Processus actifs</span>
      <div class="proc-filters">
        <label>CPU ≥ <input type="number" id="filter-cpu" min="0" max="100" value="${cpuFilter}" style="width:50px"></label>
        <label>RAM ≥ <input type="number" id="filter-ram" min="0" max="100" value="${ramFilter}" style="width:50px"></label>
      </div>
      <span class="proc-count">${filtered.length} processus</span>
    </div>
    <table>
      <thead>
        <tr>
          <th>NOM</th><th>CPU %</th><th>RAM %</th><th>RAM (MB)</th><th>IO LUS</th><th>IO ÉCRITS</th>
        </tr>
      </thead>
      <tbody>
        ${filtered
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

  // lier les contrôles des seuils aux variables et rafraîchir au changement
  const cpuInput = document.getElementById("filter-cpu");
  const ramInput = document.getElementById("filter-ram");
  if (cpuInput) {
    cpuInput.oninput = () => {
      cpuFilter = Number(cpuInput.value) || 0;
      renderProcesses(data);
    };
  }
  if (ramInput) {
    ramInput.oninput = () => {
      ramFilter = Number(ramInput.value) || 0;
      renderProcesses(data);
    };
  }

  refreshIcons();
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
  // lier les contrôles de filtre pour rafraîchir la vue quand ils changent
  const cpuInput = document.getElementById("filter-cpu");
  const ramInput = document.getElementById("filter-ram");
  if (cpuInput) {
    cpuInput.oninput = () => {
      cpuFilter = Number(cpuInput.value) || 0;
      renderProcesses(data);
    };
  }
  if (ramInput) {
    ramInput.oninput = () => {
      ramFilter = Number(ramInput.value) || 0;
      renderProcesses(data);
    };
  }

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
