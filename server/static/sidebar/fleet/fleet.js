/* ─────────────────────────────────────────────────────────────
   VIGIL — fleet.js · Vue Parc & Sites
   Onglets : Groupes · Inventaire · Fédération (multi-sites)
   ───────────────────────────────────────────────────────────── */

let fleetTab = "groups";

async function renderFleetView() {
  const content = document.querySelector(".content");
  if (!content) return;

  content.innerHTML = `
    <div class="fleet-container">
      <div class="fleet-header">
        <div>
          <div class="fleet-title"><i data-lucide="network"></i> Parc &amp; Sites</div>
          <div class="fleet-subtitle">GROUPES · INVENTAIRE · FÉDÉRATION MULTI-SITES</div>
        </div>
        <div class="fleet-tabs">
          <button class="fleet-tab ${fleetTab === "groups" ? "active" : ""}" onclick="fleetSwitchTab('groups')">Groupes</button>
          <button class="fleet-tab ${fleetTab === "inventory" ? "active" : ""}" onclick="fleetSwitchTab('inventory')">Inventaire</button>
          <button class="fleet-tab ${fleetTab === "federation" ? "active" : ""}" onclick="fleetSwitchTab('federation')">Fédération</button>
        </div>
      </div>
      <div class="fleet-body" id="fleet-body">
        <div class="fleet-loading">Chargement…</div>
      </div>
    </div>
  `;
  refreshIcons();
  await fleetRenderTab();
}

function fleetSwitchTab(tab) {
  fleetTab = tab;
  document.querySelectorAll(".fleet-tab").forEach((t) => t.classList.remove("active"));
  document
    .querySelector(`.fleet-tab[onclick="fleetSwitchTab('${tab}')"]`)
    ?.classList.add("active");
  fleetRenderTab();
}

async function fleetRenderTab() {
  const body = document.getElementById("fleet-body");
  if (!body) return;
  body.innerHTML = `<div class="fleet-loading">Chargement…</div>`;
  try {
    if (fleetTab === "groups") await renderFleetGroups(body);
    else if (fleetTab === "inventory") await renderFleetInventory(body);
    else await renderFleetFederation(body);
  } catch (e) {
    body.innerHTML = `<div class="fleet-loading">Erreur : ${_fleetEsc(e.message)}</div>`;
  }
  refreshIcons();
}

function _fleetEsc(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/* ═══════════════════════════════════════════════════════════
   GROUPES
   ═══════════════════════════════════════════════════════════ */
async function renderFleetGroups(body) {
  const [groupsData, computers] = await Promise.all([
    vigilFetch("/api/groups").then((r) => r.json()),
    vigilFetch("/api/computers").then((r) => r.json()),
  ]);
  const hostsMeta = groupsData.hosts || {};
  const groups = {};

  Object.keys(computers).forEach((h) => {
    const g = (hostsMeta[h] || {}).group || "Sans groupe";
    (groups[g] = groups[g] || []).push(h);
  });

  const groupRows = Object.keys(groups)
    .sort()
    .map((g) => {
      const hosts = groups[g];
      const online = hosts.filter((h) => !computers[h]?.offline).length;
      return `
      <div class="fleet-group-row">
        <div>
          <div class="fleet-group-name">${_fleetEsc(g)}</div>
          <div class="fleet-group-count">${online}/${hosts.length} en ligne</div>
        </div>
        <div class="fleet-group-hosts">
          ${hosts
            .map(
              (h) =>
                `<span class="fleet-host-chip">${_fleetEsc(h)}</span>`,
            )
            .join("")}
        </div>
      </div>`;
    })
    .join("");

  const assignRows = Object.keys(computers)
    .sort()
    .map((h) => {
      const current = (hostsMeta[h] || {}).group || "";
      const options = ['<option value="">— Sans groupe —</option>']
        .concat(
          Object.keys(groups)
            .filter((g) => g !== "Sans groupe")
            .map(
              (g) =>
                `<option value="${_fleetEsc(g)}" ${current === g ? "selected" : ""}>${_fleetEsc(g)}</option>`,
            ),
        )
        .join("");
      return `
      <div class="fleet-assign-row">
        <span class="fleet-assign-name">${_fleetEsc(h)}</span>
        <select class="fleet-select" onchange="fleetAssignGroup('${_fleetEsc(h)}', this.value)">
          ${options}
          <option value="__new__">➕ Nouveau groupe…</option>
        </select>
      </div>`;
    })
    .join("");

  body.innerHTML = `
    <div class="fleet-section-card">
      <div class="fleet-card-title"><i data-lucide="folder-tree"></i> Machines par groupe / site</div>
      ${groupRows || '<div class="fleet-loading">Aucune machine connectée.</div>'}
    </div>
    <div class="fleet-section-card">
      <div class="fleet-card-title"><i data-lucide="tags"></i> Affecter une machine à un groupe</div>
      ${assignRows || '<div class="fleet-loading">Aucune machine.</div>'}
    </div>
  `;
}

async function fleetAssignGroup(hostname, group) {
  if (group === "__new__") {
    group = prompt("Nom du nouveau groupe / site (ex : Production, DMZ, Agence Lyon) :");
    if (!group) {
      renderFleetView();
      return;
    }
  }
  try {
    await vigilFetch(
      `/api/computers/${encodeURIComponent(hostname)}/group`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ group }),
      },
    );
    fleetRenderTab();
  } catch (e) {
    alert(`Erreur : ${e.message}`);
  }
}

/* ═══════════════════════════════════════════════════════════
   INVENTAIRE
   ═══════════════════════════════════════════════════════════ */
async function renderFleetInventory(body) {
  const items = await vigilFetch("/api/inventory").then((r) => r.json());
  const computers = await vigilFetch("/api/computers").then((r) => r.json());

  const rows = items
    .map((it) => {
      const d = it.data || {};
      const cpu = d.cpu || {};
      const disks = d.disks || [];
      const mainDisk = disks[0] || {};
      const online = computers[it.hostname] && !computers[it.hostname].offline;
      const ramGo = ((d.memory_total || 0) / 1e9).toFixed(0);
      return `
      <tr>
        <td><strong>${_fleetEsc(it.hostname)}</strong> ${online ? '<span class="fed-host-dot on" style="display:inline-block"></span>' : '<span class="fed-host-dot off" style="display:inline-block"></span>'}</td>
        <td>${_fleetEsc(it.group || "—")}</td>
        <td>${_fleetEsc(d.os || "—")}</td>
        <td>${_fleetEsc(d.kernel || "—")}</td>
        <td>${_fleetEsc((cpu.model || "—").slice(0, 34))}</td>
        <td>${cpu.cores_logical ?? "—"}</td>
        <td>${ramGo} Go</td>
        <td>${_fleetEsc(mainDisk.device || "—")} (${mainDisk.percent ?? "—"}%)</td>
        <td>${d.uptime_hours ?? "—"} h</td>
        <td>${new Date(it.ts).toLocaleString()}</td>
      </tr>`;
    })
    .join("");

  body.innerHTML = `
    <div class="fleet-section-card">
      <div class="fleet-card-title">
        <i data-lucide="clipboard-list"></i> Inventaire du parc (${items.length} machine(s))
        <a href="/api/inventory/export/csv" style="margin-left:auto; text-decoration:none;">
          <button class="fleet-btn"><i data-lucide="download"></i> Export CSV</button>
        </a>
      </div>
      ${
        items.length
          ? `<div class="fleet-table-wrap"><table class="fleet-table">
              <thead><tr>
                <th>Machine</th><th>Groupe</th><th>OS</th><th>Noyau</th>
                <th>CPU</th><th>Cœurs</th><th>RAM</th><th>Disque sys.</th>
                <th>Uptime</th><th>Relevé du</th>
              </tr></thead>
              <tbody>${rows}</tbody>
            </table></div>`
          : '<div class="fleet-loading">Aucun inventaire reçu pour le moment — les agents l\'envoient au démarrage puis toutes les 6 h.</div>'
      }
    </div>
  `;
}

/* ═══════════════════════════════════════════════════════════
   FÉDÉRATION MULTI-SITES
   ═══════════════════════════════════════════════════════════ */
async function renderFleetFederation(body) {
  const data = await vigilFetch("/api/federation/overview").then((r) => r.json());

  const siteCard = (site, isLocal) => {
    const hosts = site.hosts || [];
    const ok = isLocal || site.peer_status === "ok";
    return `
    <div class="fed-site-card">
      <div class="fed-site-head">
        <i data-lucide="${isLocal ? "home" : "building-2"}"></i>
        <span class="fed-site-name">${_fleetEsc(site.site || site.peer_name || "Site")}</span>
        <span class="fed-site-status ${ok ? "ok" : "ko"}">${isLocal ? "local" : _fleetEsc(site.peer_status || "?")}</span>
      </div>
      ${
        hosts.length
          ? hosts
              .map(
                (h) => `
          <div class="fed-host-line">
            <span class="fed-host-dot ${h.online ? "on" : "off"}"></span>
            <span class="fed-host-name">${_fleetEsc(h.hostname)}</span>
            ${h.group ? `<span class="fleet-badge group">${_fleetEsc(h.group)}</span>` : ""}
            ${h.in_maintenance ? '<span class="fleet-badge maint">maintenance</span>' : ""}
            <span class="fed-host-metric" style="margin-left:auto;">
              CPU ${h.cpu?.toFixed?.(0) ?? "—"}% · RAM ${h.ram?.toFixed?.(0) ?? "—"}% · Disque ${h.disk?.toFixed?.(0) ?? "—"}% · ${h.alerts_24h ?? 0} alertes/24h
            </span>
          </div>`,
              )
              .join("")
          : '<div class="fleet-loading">Aucune machine signalée sur ce site.</div>'
      }
    </div>`;
  };

  body.innerHTML = `
    <div class="fed-totals">
      <div class="fed-total-card">
        <div class="fed-total-value">${data.totals?.online ?? 0}/${data.totals?.hosts ?? 0}</div>
        <div class="fed-total-label">Machines en ligne (tous sites)</div>
      </div>
      <div class="fed-total-card">
        <div class="fed-total-value">${(data.peers || []).length + 1}</div>
        <div class="fed-total-label">Sites fédérés</div>
      </div>
    </div>
    ${siteCard(data.local || {}, true)}
    ${(data.peers || []).map((p) => siteCard(p, false)).join("")}
    <div class="fleet-section-card" style="margin-top:8px;">
      <div class="fleet-card-title"><i data-lucide="info"></i> Connecter un site</div>
      <div style="font-size:0.8rem; color:var(--muted); line-height:1.6;">
        Sur chaque serveur distant : définissez <code>FEDERATION_TOKEN</code> (secret partagé) et
        <code>FEDERATION_SITE_NAME</code> dans les Paramètres. Sur ce serveur central, ajoutez le peer
        dans <code>config.yaml</code> :<br>
        <code style="color:#7dd3fc;">FEDERATION_PEERS: [{name: "Agence Lyon", url: "http://IP_SITE:5000", token: "le-meme-secret"}]</code>
      </div>
    </div>
  `;
}

/* ─── Cache des métadonnées (groupes/maintenance) pour les cartes ─── */
window.fleetMeta = { hosts: {}, groups: [] };

async function refreshFleetMeta() {
  try {
    const res = await vigilFetch("/api/groups");
    window.fleetMeta = await res.json();
  } catch {
    /* serveur indisponible */
  }
}

document.addEventListener("DOMContentLoaded", () => {
  refreshFleetMeta();
  setInterval(refreshFleetMeta, 30000);
});
