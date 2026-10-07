/* ─────────────────────────────────────────────────────────────
   VIGIL — ai_autonomous.js (Rapports autonomes de Vili + exécution
   des commandes proposées en un clic)
   ───────────────────────────────────────────────────────────── */

async function fetchAutonomousAiReports() {
  try {
    const res = await vigilFetch("/api/ai/autonomous/reports?unresolved=false");
    const reports = await res.json();
    renderAutonomousReportsWidget(reports);
  } catch (e) {
    console.warn("fetchAutonomousAiReports error:", e);
  }
}

function _escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// registre des propositions affichées (évite l'injection de payload dans
// les attributs onclick, fragile avec les quotes des commandes shell)
window._viliProposals = [];

function _proposedCommandsHtml(report) {
  const proposals = report.details && Array.isArray(report.details.proposed_commands)
    ? report.details.proposed_commands
    : [];
  if (!proposals.length) return "";
  return proposals
    .map(
      (p) => {
        const idx = window._viliProposals.push({
          hostname: p.hostname,
          command: p.command,
        }) - 1;
        return `
      <div class="vili-proposal" style="margin-top:0.5rem; padding:0.5rem 0.6rem; background:rgba(139,147,248,0.1); border:1px dashed rgba(139,147,248,0.45); border-radius:6px;">
        <div style="font-size:0.75rem; color:var(--accent2); margin-bottom:0.25rem;">
          Commande suggérée par Vili — <code>${_escapeHtml(p.hostname)}</code>
        </div>
        <code style="display:block; font-size:0.78rem; color:#e2e8f0; word-break:break-all;">${_escapeHtml(p.command)}</code>
        ${p.reason ? `<div style="font-size:0.72rem; color:var(--muted); margin-top:0.2rem;">${_escapeHtml(p.reason)}</div>` : ""}
        <button class="settings-btn settings-btn-primary" style="padding:0.25rem 0.7rem; font-size:0.75rem; margin-top:0.4rem;"
                onclick="executeViliProposal(${idx})">
          <i data-lucide="play"></i> Exécuter sur l'agent
        </button>
      </div>`;
      },
    )
    .join("");
}

function renderAutonomousReportsWidget(reports) {
  const container = document.getElementById("ai-autonomous-reports-list");
  if (!container) return;

  if (!reports || reports.length === 0) {
    container.innerHTML = `<p style="color:var(--muted); font-size:0.85rem; font-style:italic;">Aucune anomalie détectée automatiquement par Vili en tâche de fond.</p>`;
    return;
  }

  container.innerHTML = reports.map(r => `
    <div class="pro-card" style="margin-bottom:0.75rem; border-left:3px solid ${r.severity==='critical'?'var(--red)':'var(--yellow)'};">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-weight:600; color:var(--text); font-size:0.9rem;">${_escapeHtml(r.title)}</span>
        <span style="font-size:0.75rem; color:var(--muted);">${new Date(r.timestamp).toLocaleTimeString()}</span>
      </div>
      <p style="font-size:0.82rem; color:var(--text); margin:0.4rem 0;">${_escapeHtml(r.summary)}</p>
      ${_proposedCommandsHtml(r)}
      ${!r.resolved ? `
        <button class="settings-btn settings-btn-secondary" style="padding:0.25rem 0.6rem; font-size:0.75rem;" onclick="resolveAutonomousReport(${r.id})">
          <i data-lucide="check"></i> Acquitter
        </button>
      ` : `<span style="font-size:0.75rem; color:var(--green);">✓ Acquitté</span>`}
    </div>
  `).join("");

  refreshIcons();
}

async function executeViliProposal(idx) {
  const p = (window._viliProposals || [])[idx];
  if (!p) return;
  if (!confirm(`Exécuter sur ${p.hostname} ?\n\n${p.command}`)) return;
  try {
    const res = await vigilFetch(
      `/api/computers/${encodeURIComponent(p.hostname)}/command`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: p.command }),
      },
    );
    const data = await res.json().catch(() => ({}));
    if (data.ok) {
      alert(`✅ Exécuté sur ${p.hostname} (exit ${data.exit_code})\n\n${(data.stdout || data.stderr || "").slice(0, 1500)}`);
    } else {
      alert(`❌ Échec : ${data.error || "erreur inconnue"}`);
    }
  } catch (e) {
    alert(`Erreur: ${e.message}`);
  }
}

async function resolveAutonomousReport(reportId) {
  try {
    await vigilFetch(`/api/ai/autonomous/resolve/${reportId}`, { method: "POST" });
    fetchAutonomousAiReports();
  } catch (e) {
    alert(`Erreur acquittement: ${e.message}`);
  }
}
