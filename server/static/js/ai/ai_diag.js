/* ─────────────────────────────────────────────────────────────
   VIGIL — ai_diag.js (Quick Machine & Alert AI Diagnosis)
   ───────────────────────────────────────────────────────────── */

async function triggerAgentAiDiagnosis(hostname) {
  try {
    showLoader();
    const res = await vigilFetch("/api/ai/diagnose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hostname: hostname }),
    });
    const data = await res.json();
    hideLoader();

    const dbHist = data.db_history || {};
    let issuesHtml = (data.issues || []).map(i => `<li style="color:var(--red);">⚠️ ${i}</li>`).join("");
    let recsHtml = (data.recommendations || []).map(r => `<li style="color:var(--accent2);">💡 ${r}</li>`).join("");

    let contentHtml = `
      <div class="ai-diag-result">
        <div class="ai-diag-section">
          <div class="ai-diag-section-title"><i data-lucide="activity"></i> Synthèse Diagnostic BD (${hostname})</div>
          <p><strong>Score de santé :</strong> <span class="health-${(data.status||'healthy').toLowerCase()}" style="font-weight:bold; font-size:1.1rem;">${data.health_score}/100 (${data.status})</span></p>
          <p>${data.summary || ''}</p>
        </div>

        <div class="ai-diag-section">
          <div class="ai-diag-section-title"><i data-lucide="database"></i> Données SQLite 24h</div>
          <p>Moyenne CPU: <strong>${dbHist.avg_cpu || 0}%</strong> | Pic CPU: <strong>${dbHist.peak_cpu || 0}%</strong></p>
          <p>Moyenne RAM: <strong>${dbHist.avg_ram || 0}%</strong> | Pic RAM: <strong>${dbHist.peak_ram || 0}%</strong></p>
        </div>

        ${issuesHtml ? `
        <div class="ai-diag-section">
          <div class="ai-diag-section-title" style="color:var(--red);"><i data-lucide="alert-triangle"></i> Problèmes Détectés</div>
          <ul>${issuesHtml}</ul>
        </div>` : ''}

        ${recsHtml ? `
        <div class="ai-diag-section">
          <div class="ai-diag-section-title"><i data-lucide="check-circle"></i> Actions Recommandées</div>
          <ul>${recsHtml}</ul>
        </div>` : ''}
      </div>
    `;

    const modalTitle = document.getElementById("modal-title");
    if (modalTitle) modalTitle.textContent = `Diagnostic IA BD — ${hostname}`;

    const activeTabContent = document.querySelector(".tab-content.active");
    if (activeTabContent) {
      activeTabContent.innerHTML = contentHtml;
    }
    refreshIcons();
  } catch (e) {
    hideLoader();
    alert(`Erreur diagnostic IA: ${e.message}`);
  }
}
