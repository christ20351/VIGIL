/* ─────────────────────────────────────────────────────────────
   VIGIL — ai_autonomous.js (Autonomous AI Incidents UI Controller)
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

function renderAutonomousReportsWidget(reports) {
  const container = document.getElementById("ai-autonomous-reports-list");
  if (!container) return;

  if (!reports || reports.length === 0) {
    container.innerHTML = `<p style="color:#94a3b8; font-size:0.85rem; font-style:italic;">Aucune anomalie détectée automatiquement par l'IA en tâche de fond.</p>`;
    return;
  }

  container.innerHTML = reports.map(r => `
    <div class="pro-card" style="margin-bottom:0.75rem; border-left:3px solid ${r.severity==='critical'?'#f87171':'#fbbf24'};">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-weight:600; color:#f8fafc; font-size:0.9rem;">${r.title}</span>
        <span style="font-size:0.75rem; color:#94a3b8;">${new Date(r.timestamp).toLocaleTimeString()}</span>
      </div>
      <p style="font-size:0.82rem; color:#cbd5e1; margin:0.4rem 0;">${r.summary}</p>
      ${!r.resolved ? `
        <button class="settings-btn settings-btn-secondary" style="padding:0.25rem 0.6rem; font-size:0.75rem;" onclick="resolveAutonomousReport(${r.id})">
          <i data-lucide="check"></i> Acquitter
        </button>
      ` : `<span style="font-size:0.75rem; color:#4ade80;">✓ Acquitté</span>`}
    </div>
  `).join("");

  refreshIcons();
}

async function resolveAutonomousReport(reportId) {
  try {
    await vigilFetch(`/api/ai/autonomous/resolve/${reportId}`, { method: "POST" });
    fetchAutonomousAiReports();
  } catch (e) {
    alert(`Erreur acquittement: ${e.message}`);
  }
}
