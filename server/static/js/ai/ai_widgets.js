/* ─────────────────────────────────────────────────────────────
   VIGIL — ai_widgets.js (Cluster Health & DB Widgets)
   ───────────────────────────────────────────────────────────── */

async function updateClusterHealthWidgets() {
  try {
    const res = await vigilFetch("/api/ai/diagnose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hostname: "all" }),
    });
    const data = await res.json();

    const scoreEl = document.getElementById("ai-cluster-score");
    const tagEl = document.getElementById("ai-cluster-status-tag");

    if (scoreEl && data.health_score !== undefined) {
      scoreEl.textContent = `${data.health_score}/100`;
      scoreEl.className = `ai-health-score health-${(data.status || "healthy").toLowerCase()}`;
    }
    if (tagEl) {
      tagEl.textContent = `${data.online_hosts || 0} hôte(s) en ligne | BD 24h: ${data.db_alerts?.total_notifications || 0} alertes`;
    }
  } catch (e) {
    console.warn("updateClusterHealthWidgets error:", e);
  }
}
