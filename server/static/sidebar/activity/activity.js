/**
 * VIGIL — activity.js
 * Onglet Activité : notifications groupées + graphique historique
 */

let activityChart = null;
let currentNotifSeverity = null; // 'error'|'warning'|'info' or null
let currentNotifPage = 1;
let currentNotifTotal = 0;
let currentNotifPages = 0;
let currentNotifHours = 12;
const NOTIFS_PER_PAGE = 20;

// ─── HELPERS SÉVÉRITÉ ─────────────────────────────────────────────
function notifSeverityClass(msg) {
  const t = (msg || "").toLowerCase();
  if (
    t.includes("critique") ||
    t.includes("disque plein") ||
    t.includes("hors ligne")
  )
    return "sev-error";
  if (t.includes("élevé") || t.includes("alerte") || t.includes("échec"))
    return "sev-warning";
  return "sev-info";
}

// ─── FILTER HELPERS ───────────────────────────────────────────────
function setNotifSeverity(sev) {
  currentNotifSeverity = sev || null;
  currentNotifPage = 1;
  renderNotificationsView(currentNotifHours, true);
}

function setNotifHours(h) {
  currentNotifHours = h;
  currentNotifPage = 1;
  renderNotificationsView(h, true);
}

function goToNotifPage(p) {
  // Calculer le nombre de pages avec le total actuel
  let maxPages = currentNotifPages;
  if (maxPages === 0 && currentNotifTotal > 0) {
    maxPages = Math.ceil(currentNotifTotal / NOTIFS_PER_PAGE);
  }
  if (p >= 1 && p <= maxPages) {
    currentNotifPage = p;
    renderNotificationsView(currentNotifHours, false);
  }
}

function notifBadgeLabel(sevClass) {
  if (sevClass === "sev-error") return "CRITIQUE";
  if (sevClass === "sev-warning") return "ALERTE";
  return "INFO";
}

function notifIconName(sevClass) {
  if (sevClass === "sev-error") return "alert-octagon";
  if (sevClass === "sev-warning") return "alert-triangle";
  return "info";
}

// ─── VUE NOTIFICATIONS ────────────────────────────────────────────
function renderNotificationsView(hours = 12, markRead = false) {
  currentNotifHours = hours;
  if (currentAbortController) currentAbortController.abort();
  currentAbortController = new AbortController();

  if (markRead) {
    lastSeenNotifTime = Date.now();
  }
  updateNotifBadge();
  showLoader();

  (async () => {
    let allNotifications = [];
    try {
      const params = new URLSearchParams();
      params.set("hours", hours && hours > 0 ? String(hours) : "0");
      if (currentNotifSeverity) params.set("severity", currentNotifSeverity);
      const res = await vigilFetch(
        `/api/notifications?${params.toString()}`,
        { signal: currentAbortController.signal },
      );
      const json = await res.json();
      allNotifications =
        json?.notifications?.map((n) => ({
          timestamp: n.timestamp,
          hostname: n.hostname,
          message: n.message,
          severity: n.severity || notifSeverityClass(n.message).replace("sev-", ""),
        })) || [];
      currentNotifTotal = json?.total || allNotifications.length;
    } catch (e) {
      if (e.name === "AbortError") return;
      allNotifications = [];
    }

    currentNotifPages = Math.ceil(currentNotifTotal / NOTIFS_PER_PAGE) || 1;
    const startIdx = (currentNotifPage - 1) * NOTIFS_PER_PAGE;
    const list = allNotifications.slice(startIdx, startIdx + NOTIFS_PER_PAGE);

    // compteurs par sévérité (sur l'ensemble de la période)
    const count = { error: 0, warning: 0, info: 0 };
    allNotifications.forEach((a) => {
      const s = count[a.severity] !== undefined ? a.severity : "info";
      count[s]++;
    });

    // ── filtres : plage + sévérité dans une barre unique ──
    const ranges = [
      { label: "1 h", val: 1 },
      { label: "4 h", val: 4 },
      { label: "24 h", val: 24 },
      { label: "2 j", val: 48 },
      { label: "3 j", val: 72 },
      { label: "Tout", val: 0 },
    ];
    const rangeHTML = ranges
      .map(
        (r) =>
          `<button onclick="setNotifHours(${r.val})" class="nj-filter ${r.val === hours ? "active" : ""}">${r.label}</button>`,
      )
      .join("");
    const sevOptions = [
      { label: "Toutes", val: "", icon: "layers" },
      { label: "Critiques", val: "error", icon: "alert-octagon" },
      { label: "Alertes", val: "warning", icon: "alert-triangle" },
      { label: "Infos", val: "info", icon: "info" },
    ];
    const sevHTML = sevOptions
      .map(
        (s) =>
          `<button onclick="setNotifSeverity('${s.val}')" class="nj-filter ${s.val === (currentNotifSeverity || "") ? "active" : ""}"><i data-lucide="${s.icon}"></i>${s.label}</button>`,
      )
      .join("");

    // ── entête + stats + filtres ──
    let html = `
      <div class="notifications-container">
        <div class="activity-header">
          <div class="activity-header-left">
            <div class="activity-title">Journal des notifications</div>
            <div class="activity-sub">ALERTES SYSTÈME ET ÉVÉNEMENTS SUPERVISÉS</div>
          </div>
          <div class="nj-stats">
            <div class="nj-stat sev-error"><i data-lucide="alert-octagon"></i><div><div class="nj-stat-val">${count.error}</div><div class="nj-stat-label">Critiques</div></div></div>
            <div class="nj-stat sev-warning"><i data-lucide="alert-triangle"></i><div><div class="nj-stat-val">${count.warning}</div><div class="nj-stat-label">Alertes</div></div></div>
            <div class="nj-stat sev-info"><i data-lucide="info"></i><div><div class="nj-stat-val">${count.info}</div><div class="nj-stat-label">Infos</div></div></div>
            <div class="nj-stat"><i data-lucide="list"></i><div><div class="nj-stat-val">${currentNotifTotal}</div><div class="nj-stat-label">Total</div></div></div>
          </div>
        </div>

        <div class="nj-toolbar">
          <div class="nj-filters">${sevHTML}</div>
          <div class="nj-filters">${rangeHTML}</div>
        </div>
    `;

    if (!list.length) {
      html += `
        <div class="notif-empty">
          <i data-lucide="bell-off"></i>
          <div class="notif-empty-title">Aucune notification</div>
          <div class="notif-empty-sub">Aucun événement sur la période sélectionnée</div>
        </div>`;
    } else {
      // groupement par jour
      const groups = {};
      list.forEach((a) => {
        const date = a.timestamp
          ? new Date(a.timestamp).toLocaleDateString("fr", {
              weekday: "long",
              day: "numeric",
              month: "long",
            })
          : "Sans date";
        (groups[date] = groups[date] || []).push(a);
      });

      Object.keys(groups).forEach((date) => {
        html += `<div class="notif-day"><div class="notif-day-label">${date}</div>`;
        groups[date].forEach((a) => {
          const sevClass = `sev-${a.severity || "info"}`;
          const iconName = notifIconName(sevClass);
          const when = a.timestamp
            ? new Date(a.timestamp).toLocaleTimeString("fr", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })
            : "";
          html += `
            <div class="nj-item ${sevClass}">
              <div class="nj-item-icon"><i data-lucide="${iconName}"></i></div>
              <div class="nj-item-body">
                <div class="nj-item-msg">${(a.message || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>
                <div class="nj-item-meta">
                  ${a.hostname ? `<span class="nj-item-host"><i data-lucide="server"></i>${a.hostname}</span>` : ""}
                  <span class="nj-item-time">${when}</span>
                  <span class="nj-item-ago">${timeAgo(a.timestamp)}</span>
                </div>
              </div>
            </div>`;
        });
        html += `</div>`;
      });
    }

    // ── pagination ──
    const prevDisabled = currentNotifPage <= 1;
    const nextDisabled = currentNotifPage >= currentNotifPages;
    const pageBtns = [];
    for (let i = 1; i <= Math.min(currentNotifPages, 5); i++) {
      pageBtns.push(
        `<button onclick="goToNotifPage(${i})" class="nj-page-btn ${i === currentNotifPage ? "active" : ""}">${i}</button>`,
      );
    }
    html += `
      <div class="nj-pagination">
        <button onclick="goToNotifPage(${currentNotifPage - 1})" class="nj-page-btn" ${prevDisabled ? "disabled" : ""}><i data-lucide="chevron-left"></i></button>
        <div class="nj-page-info">Page ${currentNotifPage} / ${currentNotifPages || 1}</div>
        <div class="nj-page-buttons">${pageBtns.join("")}</div>
        <button onclick="goToNotifPage(${currentNotifPage + 1})" class="nj-page-btn" ${nextDisabled ? "disabled" : ""}><i data-lucide="chevron-right"></i></button>
      </div>
    </div>`;

    document.querySelector(".content").innerHTML = html;
    refreshIcons();
    hideLoader();
  })();
}

// ─── VUE GRAPHIQUE ────────────────────────────────────────────────
async function renderActivityView() {
  if (currentAbortController) currentAbortController.abort();
  currentAbortController = new AbortController();

  const hosts = Object.keys(computersData);

  const chartBlock = CHARTJS_OK
    ? `<div class="chart-wrap"><canvas id="activity-chart"></canvas></div>`
    : `<div class="chart-offline">
         <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
           <line x1="1" y1="1" x2="23" y2="23"/>
           <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/>
           <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/>
         </svg>
         Graphiques indisponibles — Chart.js non chargé (mode hors ligne)
       </div>`;

  const optionsHTML = hosts
    .map((h) => `<option value="${h}">${h}</option>`)
    .join("");

  document.querySelector(".content").innerHTML = `
    <div class="activity-container">

      <div class="activity-header">
        <div class="activity-header-left">
          <div class="activity-title">Activité des agents</div>
          <div class="activity-sub">HISTORIQUE CPU / RAM / DISQUE</div>
        </div>
      </div>

      <div class="activity-controls">
        <div class="activity-select-wrap">
          <span class="activity-select-label">Agent</span>
          <select class="activity-select" id="activity-host">${optionsHTML}</select>
        </div>
        <div class="history-controls">
          <button onclick="activityChangeRange(1)">1h</button>
          <button onclick="activityChangeRange(4)">4h</button>
          <button onclick="activityChangeRange(24)" class="active">24h</button>
          <button onclick="activityChangeRange(168)">7j</button>
        </div>
      </div>

      <div class="activity-chart-card">
        <div class="activity-chart-header">
          <div class="activity-chart-title">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
            Métriques en temps réel
          </div>
          <div class="activity-legend">
            <div class="activity-legend-item">
              <div class="activity-legend-dot" style="background:var(--cpu)"></div> CPU
            </div>
            <div class="activity-legend-item">
              <div class="activity-legend-dot" style="background:var(--ram)"></div> RAM
            </div>
            <div class="activity-legend-item">
              <div class="activity-legend-dot" style="background:var(--disk)"></div> DISK
            </div>
          </div>
        </div>
        <div class="activity-chart-body">
          ${chartBlock}
        </div>
      </div>

    </div>
  `;

  const select = document.getElementById("activity-host");
  if (select) {
    select.onchange = async () => {
      showLoader();
      await fetchHistory(select.value, currentActivityHours);
      initActivityChart(select.value);
      requestAnimationFrame(() => hideLoader());
    };
    if (hosts.length) {
      select.value = hosts[0];
      showLoader();
      await fetchHistory(hosts[0], currentActivityHours);
      initActivityChart(hosts[0]);
      requestAnimationFrame(() => hideLoader());
    }
  }
}

async function activityChangeRange(hours) {
  currentActivityHours = hours;

  // Mettre à jour le bouton actif
  document
    .querySelectorAll(".activity-container .history-controls button")
    .forEach((b) => {
      const labels = { 1: "1h", 4: "4h", 24: "24h", 168: "7j" };
      b.classList.toggle(
        "active",
        b.textContent.trim() === (labels[hours] || hours + "h"),
      );
    });

  const sel = document.getElementById("activity-host");
  if (sel?.value) {
    showLoader();
    await fetchHistory(sel.value, hours);
    updateActivityChart(sel.value);
    requestAnimationFrame(() => hideLoader());
  }
}

// ─── CHART ACTIVITÉ ───────────────────────────────────────────────
function initActivityChart(hostname) {
  if (!CHARTJS_OK) return;
  if (activityChart) {
    activityChart.destroy();
    activityChart = null;
  }
  const canvas = document.getElementById("activity-chart");
  if (!canvas) return;

  const h = historyCache[hostname] || {
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

  activityChart = new Chart(canvas, {
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
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          ticks: {
            color: "#5a6a85",
            font: { family: "JetBrains Mono", size: 11 },
            maxTicksLimit: 10,
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
            font: { family: "JetBrains Mono", size: 11 },
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
          titleFont: { family: "JetBrains Mono", size: 11 },
          bodyFont: { family: "JetBrains Mono", size: 12 },
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y}%`,
          },
        },
      },
    },
  });
}

function updateActivityChart(hostname) {
  if (!activityChart) return;
  const h = historyCache[hostname] || {
    cpu: [],
    ram: [],
    disk: [],
    labels: [],
  };
  activityChart.data.labels = [...h.labels];
  activityChart.data.datasets[0].data = [...h.cpu];
  activityChart.data.datasets[1].data = [...h.ram];
  activityChart.data.datasets[2].data = [...h.disk];
  activityChart.update("none");
}

// ─── CHART HISTORIQUE (modal agent) ───────────────────────────────
let historyChart = null;

async function fetchHistoryAndRenderHistory(hostname, hours = 24, btnEl = null) {
  if (btnEl) {
    document
      .querySelectorAll(".history-controls button")
      .forEach((b) => b.classList.remove("active"));
    btnEl.classList.add("active");
  }
  showLoader();
  try {
    await fetchHistory(hostname, hours);
    if (!historyChart) initHistoryChart(hostname);
    updateHistoryChart(hostname);
  } finally {
    hideLoader();
  }
}

function renderHistory(hostname) {
  document.getElementById("tab-history").innerHTML = `
    <div class="history-container">
      <div class="history-controls">
        <button onclick="fetchHistoryAndRenderHistory('${hostname}', 1, this)">1h</button>
        <button onclick="fetchHistoryAndRenderHistory('${hostname}', 4, this)">4h</button>
        <button onclick="fetchHistoryAndRenderHistory('${hostname}', 24, this)" class="active">24h</button>
        <button onclick="fetchHistoryAndRenderHistory('${hostname}', 168, this)">7j</button>
      </div>
      <div class="activity-chart-card">
        <div class="activity-chart-header">
          <div class="activity-chart-title">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
            Historique — ${hostname}
          </div>
          <div class="activity-legend">
            <div class="activity-legend-item"><div class="activity-legend-dot" style="background:var(--cpu)"></div> CPU</div>
            <div class="activity-legend-item"><div class="activity-legend-dot" style="background:var(--ram)"></div> RAM</div>
            <div class="activity-legend-item"><div class="activity-legend-dot" style="background:var(--disk)"></div> DISK</div>
          </div>
        </div>
        <div class="activity-chart-body">
          ${
            CHARTJS_OK
              ? `<div class="chart-wrap"><canvas id="history-chart"></canvas></div>`
              : `<div class="chart-offline">Graphiques indisponibles — mode hors ligne</div>`
          }
        </div>
      </div>
    </div>
  `;
  fetchHistoryAndRenderHistory(hostname, 24);
}

function initHistoryChart(hostname) {
  if (!CHARTJS_OK) return;
  if (historyChart) {
    historyChart.destroy();
    historyChart = null;
  }
  const canvas = document.getElementById("history-chart");
  if (!canvas) return;

  const h = historyCache[hostname] || {
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

  historyChart = new Chart(canvas, {
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
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          ticks: {
            color: "#5a6a85",
            font: { family: "JetBrains Mono", size: 11 },
            maxTicksLimit: 10,
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
            font: { family: "JetBrains Mono", size: 11 },
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
          titleFont: { family: "JetBrains Mono", size: 11 },
          bodyFont: { family: "JetBrains Mono", size: 12 },
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y}%`,
          },
        },
      },
    },
  });
}

function updateHistoryChart(hostname) {
  if (!historyChart) return;
  const h = historyCache[hostname] || {
    cpu: [],
    ram: [],
    disk: [],
    labels: [],
  };
  historyChart.data.labels = [...h.labels];
  historyChart.data.datasets[0].data = [...h.cpu];
  historyChart.data.datasets[1].data = [...h.ram];
  historyChart.data.datasets[2].data = [...h.disk];
  historyChart.update("none");
}
