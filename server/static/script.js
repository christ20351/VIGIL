/* ─────────────────────────────────────────────────────────────
   VIGIL — script.js
   ───────────────────────────────────────────────────────────── */

// ─── DÉTECTION HORS-LIGNE ──────────────────────────────────────────
//
// Vérifie la disponibilité de Chart.js et Lucide en temps réel
// Support offline complet avec versions locales ou CDN

let CHARTJS_OK = typeof Chart !== "undefined" && Chart.version;
// rendu instantané des graphiques : pas d'animation (les mises à jour 1×/s
// et les changements de plage deviennent immédiats)
if (CHARTJS_OK) {
  try {
    Chart.defaults.animation = false;
  } catch {
    /* Chart.js trop ancien : on garde le comportement par défaut */
  }
}
let LUCIDE_OK = typeof lucide !== "undefined" && lucide.createIcons;

// Retry mechanism pour charger les CDN avec délai
function waitForLibraries(timeout = 5000) {
  return new Promise((resolve) => {
    const startTime = Date.now();
    const checkInterval = setInterval(() => {
      CHARTJS_OK = typeof Chart !== "undefined" && Chart.version;
      LUCIDE_OK = typeof lucide !== "undefined" && lucide.createIcons;

      if ((CHARTJS_OK && LUCIDE_OK) || Date.now() - startTime > timeout) {
        clearInterval(checkInterval);
        resolve();
      }
    }, 100);
  });
}

// Wrapper Lucide : appelle createIcons() seulement si disponible,
// sinon remplace les <i data-lucide> par un carré neutre (CSS .icon-fallback)
function refreshIcons() {
  if (typeof lucide !== "undefined" && lucide.createIcons) {
    try {
      lucide.createIcons();
    } catch (e) {
      console.warn("Lucide.createIcons() failed:", e);
      replaceLucideWithFallback();
    }
  } else {
    replaceLucideWithFallback();
  }
}

function replaceLucideWithFallback() {
  document.querySelectorAll("i[data-lucide]").forEach((el) => {
    if (!el.dataset.replaced) {
      const span = document.createElement("span");
      span.className = "icon-fallback";
      span.title = `Icon: ${el.dataset.lucide}`;
      el.replaceWith(span);
      span.dataset.replaced = "true";
    }
  });
}

// ─── STATE ────────────────────────────────────────────────────────
let computersData = {};

// wrapper autour de fetch qui redirige vers la page de login si la
// session n'est plus valide (retourne 401). Cela évite au client de rester
// bloqué lorsque l'auth est activée.
async function vigilFetch(url, opts = {}) {
  let res;
  try {
    res = await fetch(url, opts);
  } catch (e) {
    // TypeError "Failed to fetch" = serveur injoignable (arrêté, redémarrage
    // ou panne réseau) — message explicite au lieu d'un générique.
    if (e instanceof TypeError) {
      throw new Error(
        "Serveur VIGIL injoignable — vérifiez que le serveur est démarré (python server.py) puis rechargez la page",
      );
    }
    throw e;
  }
  if (res.status === 401) {
    window.location = "/login";
    throw new Error("not authenticated");
  }
  return res;
}
let currentHostname = null;
let ws = null;
let liveChart = null;

// historique des alertes (pour l'onglet Notifications)
const alertsHistory = [];
// timestamp de la dernière consultation des notifications
let lastSeenNotifTime = 0;

// badge de notification dans la sidebar
function updateNotifBadge() {
  const span = document.getElementById("notif-count");
  if (!span) return;
  // ne compter que les alertes postérieures à la dernière consultation
  const n = alertsHistory.filter((a) => {
    const t = a.timestamp ? new Date(a.timestamp).getTime() : 0;
    return t > lastSeenNotifTime;
  }).length;
  span.textContent = n > 0 ? n : "";
  span.style.display = n > 0 ? "inline-block" : "none";

  // badge de la cloche (topbar)
  const bellBadge = document.getElementById("topbar-bell-badge");
  if (bellBadge) {
    bellBadge.textContent = n > 0 ? String(n) : "";
    bellBadge.style.display = n > 0 ? "flex" : "none";
  }
}

// échappement HTML pour toutes les valeurs dynamiques injectées en innerHTML
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ─── NOTIFICATIONS TEMPS RÉEL ─────────────────────────────────────
// Les alertes n'apparaissent JAMAIS par-dessus l'interface : elles
// alimentent le badge de la cloche, le panneau latéral s'il est
// ouvert, et le journal.
function showAlert(msg) {
  // historique de session + badges
  alertsHistory.push({
    timestamp: msg.timestamp,
    hostname: msg.hostname,
    message: msg.message,
    severity: msg.severity || "info",
  });
  updateNotifBadge();

  // insertion live en tête du panneau s'il est ouvert
  if (typeof notifPanelOpen !== "undefined" && notifPanelOpen) {
    const list = document.getElementById("notif-panel-list");
    if (list) {
      list.querySelector(".np-empty")?.remove();
      list.insertAdjacentHTML("afterbegin", notifPanelItemHTML(msg, true));
      if (typeof refreshIcons === "function") refreshIcons();
    }
  }

  // pulse de la cloche (seul signal visuel hors panneau)
  const bell = document.getElementById("topbar-bell");
  if (bell) {
    bell.classList.remove("pulse");
    void bell.offsetWidth; // relance l'animation
    bell.classList.add("pulse");
  }

  // si la vue journal est ouverte, la rafraîchir sans marquer comme lu
  if (document.querySelector(".notifications-container")) {
    renderNotificationsView();
  }
}

// ─── PANNEAU DE NOTIFICATIONS ─────────────────────────────────────
let notifPanelOpen = false;
let notifPanelLoaded = false;

function toggleNotifPanel(force) {
  const panel = document.getElementById("notif-panel");
  if (!panel) return;
  const open = force !== undefined ? force : !panel.classList.contains("open");
  panel.classList.toggle("open", open);
  notifPanelOpen = open;
  if (open) {
    markAllNotifsRead();
    renderNotifPanel();
  }
}

async function renderNotifPanel() {
  const list = document.getElementById("notif-panel-list");
  if (!list) return;

  // fusion : alertes live de la session + historique persisté (24h)
  const persisted = notifPanelLoaded ? [] : await fetchPersistedNotifs();
  notifPanelLoaded = true;
  const seen = new Set();
  const items = [];
  const key = (a) => `${a.timestamp}|${a.message}`;
  persisted.forEach((a) => {
    const k = key(a);
    if (!seen.has(k)) { seen.add(k); items.push(a); }
  });
  alertsHistory.forEach((a) => {
    const k = key(a);
    if (!seen.has(k)) { seen.add(k); items.push(a); }
  });
  items.sort((a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0));

  const recent = items.slice(0, 50);
  if (!recent.length) {
    list.innerHTML = `
      <div class="np-empty">
        <i data-lucide="bell-off"></i>
        <div>Aucune notification sur les dernières 24 h.</div>
      </div>`;
    refreshIcons();
    return;
  }
  list.innerHTML = recent.map((a) => notifPanelItemHTML(a)).join("");
  refreshIcons();
}

function notifPanelItemHTML(a, flash = false) {
  const sev = a.severity || "info";
  const icon = sev === "error" || sev === "warning" ? "alert-triangle" : "info";
  const t = a.timestamp ? new Date(a.timestamp).getTime() : 0;
  const unread = t > lastSeenNotifTime;
  return `
    <div class="np-item sev-${sev} ${unread ? "unread" : ""} ${flash ? "flash" : ""}">
      <div class="np-icon"><i data-lucide="${icon}"></i></div>
      <div class="np-body">
        <div class="np-msg">${escapeHtml(a.message || "")}</div>
        <div class="np-meta">
          ${a.hostname ? `<span class="np-host">${escapeHtml(a.hostname)}</span>` : ""}
          <span>${timeAgo(a.timestamp)}</span>
        </div>
      </div>
    </div>`;
}

async function fetchPersistedNotifs() {
  try {
    const res = await vigilFetch("/api/notifications?hours=24");
    const json = await res.json();
    return (json?.notifications || []).slice(0, 50);
  } catch {
    return [];
  }
}

function markAllNotifsRead() {
  lastSeenNotifTime = Date.now();
  updateNotifBadge();
}

// depuis le panneau : bascule vers la vue journal complète
function openNotifsJournal() {
  toggleNotifPanel(false);
  document
    .querySelectorAll(".nav-item")
    .forEach((i) => i.classList.remove("active"));
  const nav = [...document.querySelectorAll(".nav-item")].find(
    (n) =>
      (n.querySelector(".nav-text")?.textContent || n.textContent || "")
        .trim().toLowerCase() === "notifications",
  );
  if (nav) nav.classList.add("active");
  if (typeof window.setPageTitle === "function") {
    window.setPageTitle("Notifications", "JOURNAL DES ALERTES SYSTÈME");
  }
  renderNotificationsView(12, true);
}

// affichage relatif « il y a … »
function timeAgo(ts) {
  if (!ts) return "";
  const s = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (isNaN(s)) return "";
  if (s < 60) return "à l'instant";
  if (s < 3600) return `il y a ${Math.floor(s / 60)} min`;
  if (s < 86400) return `il y a ${Math.floor(s / 3600)} h`;
  const d = new Date(ts);
  return (
    d.toLocaleDateString("fr", { day: "numeric", month: "short" }) +
    " " +
    d.toLocaleTimeString("fr", { hour: "2-digit", minute: "2-digit" })
  );
}

const MAX_POINTS = 40;
const chartHistory = {}; // { hostname: { cpu[], ram[], disk[], labels[] } }
// cache dédié pour les historiques récupérés (séparé du flux live `chartHistory`)
const historyCache = {};

// abort controller pour annuler les requetes en attente lors de changements de vue
let currentAbortController = null;

// ─── INIT ─────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  refreshIcons();
  initWebSocket();

  // global error hooks so that loader overlay doesn't stay forever
  window.addEventListener("error", () => hideLoader());
  window.addEventListener("unhandledrejection", () => hideLoader());

  document.getElementById("btn-close").onclick = closeModal;
  document.getElementById("modal").addEventListener("click", (e) => {
    if (e.target === document.getElementById("modal")) closeModal();
  });
  // fermeture clavier (Échap) pour plus d'intuitivité
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (document.getElementById("modal").classList.contains("open")) {
      closeModal();
    }
    if (
      typeof notifPanelOpen !== "undefined" &&
      notifPanelOpen &&
      document.getElementById("notif-panel")?.classList.contains("open")
    ) {
      toggleNotifPanel(false);
    }
  });

  // Titres contextuels affichés dans la topbar selon la vue active
  window.setPageTitle = (title, subtitle) => {
    const t = document.getElementById("page-title");
    const s = document.getElementById("page-subtitle");
    if (t && title) t.textContent = title;
    if (s && subtitle) s.textContent = subtitle;
  };

  // structure initiale de contenu (dashboard)
  const initialContentHTML = document.querySelector(".content").innerHTML;

  function resetDashboardView() {
    document.querySelector(".content").innerHTML = initialContentHTML;
    // réattacher le listener de fermeture de modal si nécessaire
    document.getElementById("btn-close").onclick = closeModal;
    document.getElementById("modal").addEventListener("click", (e) => {
      if (e.target === document.getElementById("modal")) closeModal();
    });
  }

  // hookup sidebar navigation
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.onclick = () => {
      const prevActive = document.querySelector(".nav-item.active");
      document
        .querySelectorAll(".nav-item")
        .forEach((i) => i.classList.remove("active"));
      item.classList.add("active");
      const textEl = item.querySelector(".nav-text");
      const text = textEl
        ? textEl.textContent.trim().toLowerCase()
        : item.textContent.trim().toLowerCase();
      switch (text) {
        case "dashboard":
        case "agents":
          resetDashboardView();
          setPageTitle(
            text === "agents" ? "Agents" : "Dashboard",
            "SUPERVISION · PARC MACHINES",
          );
          if (typeof renderDashboardView === "function") {
            renderDashboardView();
          } else {
            renderComputers();
          }
          break;
        case "activité":
        case "activite":
          resetDashboardView();
          setPageTitle("Activité", "HISTORIQUE CPU · RAM · DISQUE");
          renderActivityView();
          break;
        case "notifications":
          // déroule le panneau temps réel sans quitter la vue courante
          if (typeof toggleNotifPanel === "function") toggleNotifPanel();
          if (prevActive) prevActive.classList.add("active");
          item.classList.remove("active");
          break;
        case "paramètres":
        case "parametres":
          resetDashboardView();
          setPageTitle("Paramètres", "CONFIGURATION DU SERVEUR VIGIL");
          renderSettingsView();
          break;
        case "ia copilote":
        case "copilote":
        case "ia":
          resetDashboardView();
          setPageTitle("IA Copilote", "VILI · DIAGNOSTICS INTELLIGENTS");
          if (typeof renderAiView === "function") {
            renderAiView();
          } else {
            document.querySelector(".content").innerHTML = '<p>Chargement de Vili...</p>';
          }
          break;
        case "sécurité":
        case "securite":
          resetDashboardView();
          setPageTitle("Sécurité", "POSTURE DE SÉCURITÉ DU PARC");
          if (typeof renderSecurityView === "function") {
            renderSecurityView();
          } else {
            document.querySelector(".content").innerHTML =
              '<p class="security-placeholder">Fonctionnalité de sécurité en cours de développement.</p>';
          }
          break;
        case "parc & sites":
        case "parc et sites":
        case "parc":
          resetDashboardView();
          setPageTitle("Parc & Sites", "GROUPES · INVENTAIRE · FÉDÉRATION");
          if (typeof renderFleetView === "function") {
            renderFleetView();
          } else {
            document.querySelector(".content").innerHTML = '<p>Chargement du parc…</p>';
          }
          break;
        default:
          resetDashboardView();
          setPageTitle("Dashboard", "SUPERVISION · PARC MACHINES");
          renderComputers();
      }
    };
  });

  // Données de démo : retire ce bloc quand les vrais agents sont connectés
  if (DEMO_MODE) injectDemoData();
  updateNotifBadge();
});

// ─── DÉMO (désactivé en mode réel) ─────────────────────────────────
// Cette section injecte des données factices et simule des changements.
// Lorsqu'on se connecte à un vrai serveur WebSocket, elle n'est pas exécutée
// pour éviter les erreurs `d is undefined` lorsque le tableau `hosts`
// ne correspond plus à la collection `computersData`.

const DEMO_MODE = false;

function injectDemoData() {
  if (!DEMO_MODE) return;

  const hosts = ["WORKSTATION-01", "SERVER-PROD", "DEV-MACHINE", "LAPTOP-RH"];
  const oses = [
    "Windows 11 Pro",
    "Ubuntu 22.04 LTS",
    "Windows 10",
    "macOS Ventura",
  ];

  hosts.forEach((h, i) => {
    computersData[h] = makeFakeAgent(h, oses[i]);
    // créer historique factice pour démonstration
    const now = Date.now();
    const hist = { cpu: [], ram: [], disk: [], labels: [] };
    for (let k = 0; k < 20; k++) {
      const ts = new Date(now - (20 - k) * 3600 * 1000); // points sur les 20 dernières heures
      hist.labels.push(ts.toLocaleTimeString());
      hist.cpu.push(rand(10, 90));
      hist.ram.push(rand(20, 80));
      hist.disk.push(rand(10, 70));
    }
    chartHistory[h] = hist;
    // also populate history cache for the demo so history views show data
    historyCache[h] = hist;
  });

  updateStats();
  renderComputers();

  // simulate an offline agent after a few seconds
  setTimeout(() => {
    const h = hosts[1];
    if (computersData[h]) {
      computersData[h].offline = true;
      computersData[h].offline_since = new Date().toISOString();
      showAlert({
        hostname: h,
        message: "Agent hors ligne (simulation)",
        timestamp: new Date().toISOString(),
      });
      updateStats();
      renderComputers();
    }
  }, 5000);

  setInterval(() => {
    hosts.forEach((h) => {
      const d = computersData[h];
      if (!d) return; // defensive
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

// ─── DÉTAIL À LA DEMANDE ──────────────────────────────────────────
// Le flux WS est allégé : les sections détaillées (processus, interfaces,
// connexions) sont récupérées via l'API quand un onglet en a besoin.
let detailTimer = null;

async function fetchHostDetail(hostname) {
  if (!hostname || !computersData[hostname]) return;
  try {
    const res = await vigilFetch(
      `/api/computers/${encodeURIComponent(hostname)}`,
    );
    if (!res.ok) return;
    const data = await res.json();
    if (!data || !computersData[hostname]) return;
    computersData[hostname] = Object.assign(computersData[hostname], data);

    if (
      currentHostname === hostname &&
      document.getElementById("modal").classList.contains("open")
    ) {
      const active = document.querySelector(".tab-content.active");
      const d = computersData[hostname];
      if (active?.id === "tab-processes") renderProcesses(d);
      if (active?.id === "tab-network") renderNetwork(d);
      if (active?.id === "tab-protocols") renderProtocols(d);
    }
  } catch {
    /* détail indisponible (agent déconnecté) */
  }
}

function startDetailPolling(hostname) {
  stopDetailPolling();
  fetchHostDetail(hostname);
  detailTimer = setInterval(() => {
    if (
      currentHostname === hostname &&
      document.getElementById("modal")?.classList.contains("open")
    ) {
      fetchHostDetail(hostname);
    } else {
      stopDetailPolling();
    }
  }, 5000);
}

function stopDetailPolling() {
  if (detailTimer) {
    clearInterval(detailTimer);
    detailTimer = null;
  }
}

function initWebSocket() {
  // reconnect loop
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  let reconnectTimer = null;

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(connect, 3000);
  }

  function connect() {
    // indicate we are trying to open a socket
    setWsStatus(null);
    try {
      ws = new WebSocket(`${proto}//${location.host}/ws`);

      ws.onopen = () => {
        setWsStatus(true);
        if (reconnectTimer) {
          clearTimeout(reconnectTimer);
          reconnectTimer = null;
        }
      };
      ws.onclose = () => {
        setWsStatus(false, "Déconnecté");
        scheduleReconnect();
      };
      ws.onerror = () => {
        setWsStatus(false, "Erreur, reconnexion");
        // attempt reconnect after error
        scheduleReconnect();
      };

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);

          if (msg.type === "update" && msg.data) {
            // Fusion : le flux seconde/seconde est volontairement allégé
            // (sans processus/interfaces/connexions détaillées). On conserve
            // donc les clés déjà connues et on complète avec le flux.
            Object.keys(msg.data).forEach((h) => {
              computersData[h] = Object.assign(
                computersData[h] || {},
                msg.data[h] || {},
              );
              if (!chartHistory[h])
                chartHistory[h] = { cpu: [], ram: [], disk: [], labels: [] };
              pushHistory(h, computersData[h]);
            });
            updateStats();
            renderComputers();
          }

          if (msg.type === "agent_update" && msg.hostname && msg.data) {
            console.log(
              `[SMART] onmessage agent_update for ${msg.hostname}`,
              msg.data.smart,
            );
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
              if (active?.id === "tab-smart") {
                console.log(
                  `[SMART] agent_update received for ${msg.hostname}:`,
                  msg.data.smart,
                );
                try {
                  if (typeof updateSmartHealthTab === "function")
                    updateSmartHealthTab(msg.hostname);
                } catch (e) {
                  console.warn(
                    "[SMART] failed to update smart tab on agent_update",
                    e,
                  );
                }
              }
              updateLiveChart(msg.hostname);
              updateHistoryChart(msg.hostname);
            }
          }
          if (msg.type === "approval_request" && msg.id) {
            showApprovalCard(msg);
          }

          if (msg.type === "approval_done" && msg.id) {
            removeApprovalCard(msg.id);
          }

          if (msg.type === "alert") {
            // message d'alerte générique
            showAlert(msg);
            // si l'alerte concerne un agent et qu'il y a des données,
            // on met à jour l'état local pour forcer re-render (ex: offline)
            if (msg.hostname && computersData[msg.hostname]) {
              // l'alerte provenant du serveur devrait également inclure
              // les données actualisées si nécessaire (cf. cleanup)
              // on se contente de redessiner
              updateStats();
              renderComputers();
              if (
                currentHostname === msg.hostname &&
                document.getElementById("modal").classList.contains("open")
              ) {
                renderOverview(msg.hostname);
              }
            }
          }
          // always refresh badge counter in case alertsHistory changed through other paths
          updateNotifBadge();
        } catch {
          /* message malformé, on ignore */
        }
      };
    } catch {
      /* WebSocket non disponible */
      scheduleReconnect();
    }
  }

  // start initially
  connect();
}

function setWsStatus(ok, text) {
  // ok === true  => connected
  // ok === false => disconnected/error
  // ok === null  => connecting/reconnecting
  const dot = document.getElementById("ws-dot");
  const label = document.getElementById("ws-label");
  if (ok === true) {
    dot.className = "ws-dot";
    label.textContent = "WebSocket actif";
  } else if (ok === false) {
    dot.className = "ws-dot disconnected";
    label.textContent = text || "Déconnecté";
  } else {
    // connecting or trying to reconnect
    dot.className = "ws-dot connecting";
    label.textContent = text || "Connexion…";
  }
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

// Récupère l'historique depuis le serveur et initialise chartHistory
// store last requested hours when using activity view
let currentActivityHours = 24;

function showLoader() {
  let l = document.getElementById("loader");
  if (!l) {
    l = document.createElement("div");
    l.id = "loader";
    l.className = "loader";
    document.body.appendChild(l);
  }
  // use flex so spinner is centered horizontally/vertically
  l.style.display = "flex";
}
function hideLoader() {
  const l = document.getElementById("loader");
  if (l) l.style.display = "none";
}

const HISTORY_TTL_MS = 60000; // revalidation après 1 minute
const historyCacheMeta = {}; // clé "host|heures" → timestamp de récupération

async function fetchHistory(hostname, hours = 24, { force = false } = {}) {
  currentActivityHours = hours;
  const key = `${hostname}|${hours}`;
  const cached = historyCache[key];
  const fetchedAt = historyCacheMeta[key] || 0;
  // cache par (hôte, plage) : basculer 24h ↔ 7j est instantané
  if (!force && cached && Date.now() - fetchedAt < HISTORY_TTL_MS) {
    historyCache[hostname] = cached;
    return cached;
  }
  try {
    const res = await vigilFetch(
      `/api/history/${encodeURIComponent(hostname)}?hours=${hours}`,
      { signal: currentAbortController.signal },
    );
    const json = await res.json().catch(() => null);
    if (json && json.history) {
      const h = { cpu: [], ram: [], disk: [], labels: [] };
      json.history.forEach((row) => {
        const ts = new Date(row.timestamp);
        h.labels.push(ts.toLocaleTimeString());
        const data = row.data || {};
        h.cpu.push(+(data.cpu_percent || 0).toFixed(1));
        h.ram.push(+(data.memory?.percent || 0).toFixed(1));
        h.disk.push(+(data.disk?.percent || 0).toFixed(1));
      });
      // store fetched history separately from live stream data
      historyCache[key] = h;
      historyCacheMeta[key] = Date.now();
      historyCache[hostname] = h;
    }
    return historyCache[hostname] || null;
  } catch (e) {
    if (e.name === "AbortError") return null; // request was cancelled
    console.warn("fetchHistory failed", e);
    return null;
  }
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
  // pas de contrôle d'historique ici : le graphique montre déjà le flux temps réel
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
        ${
          data.offline && data.offline_since
            ? `<div class="sysinfo-row"><span class="sysinfo-key">DEPUIS</span><span class="sysinfo-val">${new Date(data.offline_since).toLocaleString()}</span></div>`
            : ""
        }
        <div style="margin-top:0.75rem; text-align:center;">
          <button class="btn-ai-diagnose" onclick="triggerAgentAiDiagnosis('${hostname}')">
            <i data-lucide="bot"></i> Lancer le Diagnostic IA
          </button>
        </div>
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
  if (typeof window.renderProcesses === "function" && window.renderProcesses !== renderProcesses) {
    return window.renderProcesses(data);
  }
}

// ─── RÉSEAU ───────────────────────────────────────────────────────
function renderNetwork(data) {
  if (typeof window.renderNetwork === "function" && window.renderNetwork !== renderNetwork) {
    return window.renderNetwork(data);
  }
}

// ─── PROTOCOLES ───────────────────────────────────────────────────
function renderProtocols(data) {
  if (typeof window.renderProtocols === "function" && window.renderProtocols !== renderProtocols) {
    return window.renderProtocols(data);
  }
}

// ─── DEMANDES D'AUTORISATION VILI (Oui / Non) ─────────────────────
// Vili demande l'autorisation d'exécuter une commande : carte flottante
// interactive en bas à droite, persistée tant que l'admin n'a pas tranché.

const _approvalDeciding = new Set();

function ensureApprovalContainer() {
  let c = document.getElementById("approval-container");
  if (!c) {
    c = document.createElement("div");
    c.id = "approval-container";
    c.className = "approval-container";
    document.body.appendChild(c);
  }
  return c;
}

function showApprovalCard(req) {
  if (!req || req.id == null) return;
  const container = ensureApprovalContainer();
  if (document.getElementById(`approval-card-${req.id}`)) return;

  const card = document.createElement("div");
  card.className = "approval-card";
  card.id = `approval-card-${req.id}`;
  card.innerHTML = `
    <div class="approval-head">
      <span class="approval-avatar"><i data-lucide="bot"></i></span>
      <div>
        <div class="approval-title">Vili demande votre autorisation</div>
        <div class="approval-sub">Exécuter sur <strong>${escapeHtml(req.hostname || "?")}</strong></div>
      </div>
    </div>
    ${req.reason ? `<div class="approval-reason">${escapeHtml(req.reason)}</div>` : ""}
    <code class="approval-command">${escapeHtml(req.command || "")}</code>
    <div class="approval-actions">
      <button class="approval-btn approve" onclick="decideApproval(${req.id}, true)">
        <i data-lucide="check"></i> Effectuer l'action
      </button>
      <button class="approval-btn reject" onclick="decideApproval(${req.id}, false)">
        <i data-lucide="x"></i> Refuser
      </button>
    </div>
  `;
  container.appendChild(card);
  refreshIcons();
  // animation d'entrée
  requestAnimationFrame(() => card.classList.add("visible"));
}

function removeApprovalCard(id) {
  const card = document.getElementById(`approval-card-${id}`);
  if (!card) return;
  card.classList.remove("visible");
  setTimeout(() => card.remove(), 350);
}

async function decideApproval(id, approved) {
  if (_approvalDeciding.has(id)) return;
  _approvalDeciding.add(id);
  const card = document.getElementById(`approval-card-${id}`);
  card?.querySelectorAll(".approval-btn").forEach((b) => (b.disabled = true));
  try {
    const res = await vigilFetch(`/api/ai/approvals/${id}/decide`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved }),
    });
    const data = await res.json().catch(() => ({}));
    if (approved && data.status === "executed") {
      const out = data.approval?.result;
      showAlert({
        hostname: data.approval?.hostname,
        message: `✅ Commande Vili exécutée (${out?.exit_code ?? "?"}) : ${(out?.stdout || out?.stderr || out?.error || "").slice(0, 160)}`,
        severity: out?.ok ? "info" : "error",
        timestamp: new Date().toISOString(),
      });
    } else if (data.status === "refused") {
      showAlert({
        message: "🚫 Commande de Vili refusée.",
        severity: "info",
        timestamp: new Date().toISOString(),
      });
    } else if (data.status === "approved_but_offline") {
      showAlert({
        message: "⚠️ Commande approuvée mais l'agent est hors ligne.",
        severity: "error",
        timestamp: new Date().toISOString(),
      });
    }
  } catch (e) {
    showAlert({
      message: `Erreur décision : ${e.message}`,
      severity: "error",
      timestamp: new Date().toISOString(),
    });
  } finally {
    _approvalDeciding.delete(id);
    removeApprovalCard(id);
  }
}

// Au chargement : reprendre les demandes en attente (survivent au refresh)
document.addEventListener("DOMContentLoaded", async () => {
  try {
    const res = await vigilFetch("/api/ai/approvals?status=pending&limit=5");
    const pending = await res.json();
    (Array.isArray(pending) ? pending : []).forEach((p) =>
      showApprovalCard({
        id: p.id,
        hostname: p.hostname,
        command: p.command,
        reason: p.reason,
        timestamp: p.ts,
      }),
    );
  } catch {
    /* endpoint indisponible (auth non passée encore) */
  }
});
