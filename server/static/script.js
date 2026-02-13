// script.js for Monitoring Dashboard



let computersData = {};
let modal = document.getElementById("modal");
let currentHostname = null;
let ws = null;
let reconnectInterval = null;

// Initialize
document.addEventListener("DOMContentLoaded", function () {
  // Connexion WebSocket uniquement
  initializeWebSocket();

  // Modal close
  document.querySelector(".close").onclick = function () {
    modal.style.display = "none";
  };

  window.onclick = function (event) {
    if (event.target == modal) {
      modal.style.display = "none";
    }
  };
});

function initializeWebSocket() {
  try {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = function () {
      console.log("✅ WebSocket connecté");
      // Les données initiales seront envoyées par le serveur via WebSocket
    };

    ws.onmessage = function (event) {
      try {
        const msg = JSON.parse(event.data);

        // Ancien format: broadcast en bloc
        if (msg.type === "update" && msg.data) {
          computersData = msg.data;
          updateStats();
          renderComputers();
        }

        // Nouveau format: mise à jour par agent WebSocket
        if (msg.type === "agent_update" && msg.hostname && msg.data) {
          computersData[msg.hostname] = msg.data;
          updateStats();
          renderComputers();

          // Si une modal est ouverte et c'est le même agent, mettre à jour
          // On restaure l'ancien comportement en appelant openModal(),
          // mais `openModal` respecte maintenant l'onglet actif.
          if (
            currentHostname === msg.hostname &&
            modal.style.display === "block"
          ) {
            openModal(msg.hostname);
          }
        }
      } catch (e) {
        console.error("WebSocket message parse error:", e);
      }
    };

    ws.onerror = function (error) {
      console.error("❌ WebSocket erreur:", error);
    };

    ws.onclose = function () {
      console.log("⚠️ WebSocket fermé");
      ws = null;
      // Pas de polling HTTP, seulement WebSocket
    };
  } catch (e) {
    console.error("WebSocket initialization error:", e);
    // Pas de fallback HTTP
  }
}

async function updateDataFetch() {
  try {
    const response = await fetch("/api/computers");
    computersData = await response.json();
    updateStats();
    renderComputers();
  } catch (error) {
    console.error("Error fetching data:", error);
  }
}

// Keep updateData as alias for backward compatibility
async function updateData() {
  return updateDataFetch();
}

function updateStats() {
  const total = Object.keys(computersData).length;
  const online = total; // Assuming all in data are online
  const offline = 0; // For now, no offline tracking
  const connections = total;

  document.getElementById("total-pcs").textContent = total;
  document.getElementById("online-pcs").textContent = online;
  document.getElementById("offline-pcs").textContent = offline;
  document.getElementById("total-connections").textContent = connections;
}

function renderComputers() {
  const grid = document.getElementById("computers-grid");
  const noComputers = document.getElementById("no-computers");

  if (Object.keys(computersData).length === 0) {
    grid.innerHTML = "";
    noComputers.style.display = "block";
    return;
  }

  noComputers.style.display = "none";
  grid.innerHTML = "";

  for (const [hostname, data] of Object.entries(computersData)) {
    const card = createComputerCard(hostname, data);
    grid.appendChild(card);
  }
}

function createComputerCard(hostname, data) {
  const card = document.createElement("div");
  card.className = "computer-card";
  card.onclick = () => openModal(hostname);

  const cpuPercent = data.cpu_percent || 0;
  const ramPercent = data.memory?.percent || 0;
  const ramUsed = data.memory?.used || 0;
  const ramTotal = data.memory?.total || 0;

  // Extract IP from interfaces
  let ipAddress = "N/A";
  if (data.interfaces) {
    for (const [interfaceName, interfaceData] of Object.entries(
      data.interfaces,
    )) {
      if (interfaceData.addresses) {
        for (const addr of interfaceData.addresses) {
          if (addr.type === "IPv4" && addr.address !== "127.0.0.1") {
            ipAddress = addr.address;
            break;
          }
        }
        if (ipAddress !== "N/A") break;
      }
    }
  }

  card.innerHTML = `
        <div class="computer-header">
            <h3>${hostname}</h3>
            <div class="status online">● En ligne</div>
        </div>
        <div class="computer-metrics">
            <div class="metric">
                <div class="metric-label">CPU</div>
                <div class="metric-value">${cpuPercent.toFixed(1)}%</div>
                <div class="progress-bar">
                    <div class="progress-fill cpu-fill" style="width: ${cpuPercent}%"></div>
                </div>
            </div>
            <div class="metric">
                <div class="metric-label">RAM</div>
                <div class="metric-value">${ramPercent.toFixed(1)}%</div>
                <div class="progress-bar">
                    <div class="progress-fill ram-fill" style="width: ${ramPercent}%"></div>
                </div>
            </div>
        </div>
        <div class="computer-info">
            <div class="info-item">
                <span class="info-label">OS:</span>
                <span class="info-value">${data.system || "N/A"}</span>
            </div>
            <div class="info-item">
                <span class="info-label">IP:</span>
                <span class="info-value">${ipAddress}</span>
            </div>
        </div>
    `;

  return card;
}

function openModal(hostname) {
  currentHostname = hostname;
  const data = computersData[hostname];
  document.getElementById("modal-title").textContent = `Détails - ${hostname}`;
  modal.style.display = "block";

  // Switch to overview tab on first open
  // If modal already open for this host, keep the current tab
  const activeContent = document.querySelector(".tab-content.active");
  if (!activeContent || activeContent.id === "tab-overview") {
    switchTab("overview");
  } else {
    // reload current tab content
    const tabName = activeContent.id.replace("tab-", "");
    loadTabContent(tabName);
  }
}

function updateModalContent(hostname) {
  // Ne change pas l'onglet actif, recharge seulement le contenu courant
  currentHostname = hostname;
  document.getElementById("modal-title").textContent = `Détails - ${hostname}`;
  const activeContent = document.querySelector(".tab-content.active");
  const tabName = activeContent
    ? activeContent.id.replace("tab-", "")
    : "overview";
  loadTabContent(tabName);
}

function switchTab(tabName) {
  // Update tab buttons
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.remove("active");
  });
  document
    .querySelector(`[onclick="switchTab('${tabName}')"]`)
    .classList.add("active");

  // Update tab content
  document.querySelectorAll(".tab-content").forEach((content) => {
    content.classList.remove("active");
  });
  document.getElementById(`tab-${tabName}`).classList.add("active");

  // Load tab content
  loadTabContent(tabName);
}

function loadTabContent(tabName) {
  const data = computersData[currentHostname];
  const content = document.getElementById(`tab-${tabName}`);

  if (!data) {
    content.innerHTML = "<p>Aucune donnée disponible</p>";
    return;
  }

  switch (tabName) {
    case "overview":
      content.innerHTML = generateOverviewContent(data);
      break;
    case "processes":
      content.innerHTML = generateProcessesContent(data);
      break;
    case "network":
      content.innerHTML = generateNetworkContent(data);
      break;
    case "protocols":
      content.innerHTML = generateProtocolsContent(data);
      break;
  }
}

function generateOverviewContent(data) {
  const cpuPercent = data.cpu_percent || 0;
  const ramPercent = data.memory?.percent || 0;
  const ramUsed = (data.memory?.used / 1024 ** 3 || 0).toFixed(2);
  const ramTotal = (data.memory?.total / 1024 ** 3 || 0).toFixed(2);

  return `
        <div class="overview-grid">
            <div class="overview-card">
                <h4>🔥 Processeur</h4>
                <div class="metric-large">
                    <div class="metric-value">${cpuPercent.toFixed(1)}%</div>
                    <div class="progress-bar large">
                        <div class="progress-fill cpu-fill" style="width: ${cpuPercent}%"></div>
                    </div>
                </div>
            </div>
            <div class="overview-card">
                <h4>🧠 Mémoire</h4>
                <div class="metric-large">
                    <div class="metric-value">${ramPercent.toFixed(1)}%</div>
                    <div class="progress-bar large">
                        <div class="progress-fill ram-fill" style="width: ${ramPercent}%"></div>
                    </div>
                    <div class="metric-text">${ramUsed} GB / ${ramTotal} GB</div>
                </div>
            </div>
            <div class="overview-card">
                <h4>💻 Système</h4>
                <div class="system-info">
                    <div class="info-item"><span class="info-label">OS:</span> <span class="info-value">${data.system || "N/A"}</span></div>
                    <div class="info-item"><span class="info-label">Version:</span> <span class="info-value">${data.system_version || "N/A"}</span></div>
                    <div class="info-item"><span class="info-label">Architecture:</span> <span class="info-value">${data.architecture || "N/A"}</span></div>
                </div>
            </div>
            <div class="overview-card">
                <h4>🌐 Réseau</h4>
                <div class="system-info">
                    <div class="info-item"><span class="info-label">IP:</span> <span class="info-value">${data.ip || "N/A"}</span></div>
                    <div class="info-item"><span class="info-label">Hostname:</span> <span class="info-value">${data.hostname || "N/A"}</span></div>
                    <div class="info-item"><span class="info-label">Dernière MAJ:</span> <span class="info-value">${data.timestamp || "N/A"}</span></div>
                </div>
            </div>
        </div>
    `;
}

function generateProcessesContent(data) {
  const processes = data.processes || [];
  if (processes.length === 0) {
    return "<p>Aucune information sur les processus disponible.</p>";
  }

  let html = '<div class="processes-table">';
  html += `
    <table class="proc-table">
      <thead>
        <tr>
          <th>Processus</th>
          <th>CPU %</th>
          <th>RAM %</th>
          <th>RAM (MB)</th>
          <th>IO Lus (MB)</th>
          <th>IO Écrits (MB)</th>
        </tr>
      </thead>
      <tbody>
  `;

  processes.slice(0, 20).forEach((process) => {
    const ramMB = ((process.memory_rss || 0) / 1024 ** 2).toFixed(2);
    const ioRead = ((process.io_read_bytes || 0) / 1024 ** 2).toFixed(2);
    const ioWrite = ((process.io_write_bytes || 0) / 1024 ** 2).toFixed(2);

    html += `
      <tr>
        <td title="${process.name || "N/A"}">${(process.name || "N/A").substring(0, 30)}</td>
        <td>${(process.cpu_percent || 0).toFixed(1)}%</td>
        <td>${(process.memory_percent || 0).toFixed(1)}%</td>
        <td>${ramMB}</td>
        <td>${ioRead}</td>
        <td>${ioWrite}</td>
      </tr>
    `;
  });

  html += `
      </tbody>
    </table>
  </div>
  `;
  return html;
}

function generateNetworkContent(data) {
  const network = data.network || {};
  return `
        <div class="network-info">
            <div class="network-card">
                <h4>📊 Statistiques réseau</h4>
                <div class="network-stats">
                    <div class="stat-item">
                        <span class="stat-label">⬇️ Débit reçu:</span>
                        <span class="stat-value">${(network.bytes_recv_per_sec / 1024).toFixed(2)} KB/s</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">⬆️ Débit envoyé:</span>
                        <span class="stat-value">${(network.bytes_sent_per_sec / 1024).toFixed(2)} KB/s</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">📦 Total reçu:</span>
                        <span class="stat-value">${(network.bytes_recv / 1024 ** 3).toFixed(2)} GB</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">📤 Total envoyé:</span>
                        <span class="stat-value">${(network.bytes_sent / 1024 ** 3).toFixed(2)} GB</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">🔌 Connexions actives:</span>
                        <span class="stat-value">${network.active_connections || 0}</span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function generateProtocolsContent(data) {
  const protocols = data.protocols || {};
  let html = '<div class="protocols-list">';

  // TCP
  if (protocols.tcp) {
    html += `
      <div class="protocol-item">
        <h4>🔵 TCP</h4>
        <div class="protocol-stats">
          <div class="stat-item">
            <span class="stat-label">Établies:</span>
            <span class="stat-value">${protocols.tcp.established || 0}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">En écoute:</span>
            <span class="stat-value">${protocols.tcp.listen || 0}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">TIME_WAIT:</span>
            <span class="stat-value">${protocols.tcp.time_wait || 0}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">CLOSE_WAIT:</span>
            <span class="stat-value">${protocols.tcp.close_wait || 0}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Connexions actives:</span>
            <span class="stat-value">${(protocols.tcp.connections || []).length}</span>
          </div>
        </div>
      </div>
    `;
  }

  // UDP
  if (protocols.udp) {
    html += `
      <div class="protocol-item">
        <h4>🟡 UDP</h4>
        <div class="protocol-stats">
          <div class="stat-item">
            <span class="stat-label">Total:</span>
            <span class="stat-value">${protocols.udp.total || 0}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Connexions actives:</span>
            <span class="stat-value">${(protocols.udp.connections || []).length}</span>
          </div>
        </div>
      </div>
    `;
  }

  // Total
  if (protocols.total !== undefined) {
    html += `
      <div class="protocol-item">
        <h4>📊 TOTAL</h4>
        <div class="protocol-stats">
          <div class="stat-item">
            <span class="stat-label">Connexions réseau:</span>
            <span class="stat-value">${protocols.total}</span>
          </div>
        </div>
      </div>
    `;
  }

  if (Object.keys(protocols).length === 0) {
    html += "<p>Aucune information sur les protocoles disponible.</p>";
  }

  html += "</div>";
  return html;
}
