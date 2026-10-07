/* ─────────────────────────────────────────────────────────────
   VIGIL — ai.js (Copilote IA : cockpit de conversation + diagnostics)
   Layout chat-first : rail gauche (Vili, conversations, santé,
   surveillance) + zone de discussion pleine hauteur.
   ───────────────────────────────────────────────────────────── */

async function renderAiView() {
  const content = document.querySelector(".content");
  if (!content) return;

  content.innerHTML = `
    <div class="ai-app">

      <!-- ── RAIL GAUCHE ── -->
      <aside class="ai-rail">
        <div class="ai-rail-brand">
          <div class="ai-brand-avatar"><i data-lucide="bot"></i></div>
          <div class="ai-brand-text">
            <div class="ai-brand-name">Vili</div>
            <div class="ai-brand-sub" id="ai-provider-label">Moteur IA…</div>
          </div>
          <span class="ai-live-dot" id="ai-provider-pill" title="État du moteur IA"></span>
        </div>

        <button class="ai-new-chat" onclick="onChatSessionNew()">
          <i data-lucide="plus"></i> Nouvelle conversation
        </button>

        <div class="ai-rail-section ai-rail-grow">
          <div class="ai-rail-label">Conversations</div>
          <div class="ai-conversations" id="ai-conversations"></div>
        </div>

        <div class="ai-rail-section">
          <div class="ai-rail-label"><i data-lucide="activity"></i> Santé du cluster</div>
          <div class="ai-health-mini">
            <svg viewBox="0 0 60 60" class="ai-health-ring">
              <circle class="ai-health-ring-bg" cx="30" cy="30" r="25"/>
              <circle class="ai-health-ring-fill" id="ai-cluster-ring" cx="30" cy="30" r="25"/>
            </svg>
            <div class="ai-health-mini-text">
              <div class="ai-health-score health-healthy" id="ai-cluster-score">--/100</div>
              <div id="ai-cluster-status-tag" class="ai-health-tag">Chargement…</div>
            </div>
          </div>
        </div>

        <div class="ai-rail-section ai-rail-intel">
          <div class="ai-rail-label"><i data-lucide="brain-circuit"></i> Surveillance Vili</div>
          <div id="vili-intel-panel" class="vili-intel-panel">
            <div class="ai-intel-loading">Analyse en cours…</div>
          </div>
        </div>
      </aside>

      <!-- ── ZONE DE CONVERSATION ── -->
      <main class="ai-main">
        <header class="ai-chat-header">
          <div class="ai-chat-header-id">
            <div class="ai-chat-header-avatar"><i data-lucide="bot"></i></div>
            <div>
              <div class="ai-chat-title" id="ai-active-title">Conversation</div>
              <div class="ai-chat-sub">Copilote d'administration — métriques temps réel</div>
            </div>
          </div>
          <button class="ai-icon-btn" title="Supprimer cette conversation" onclick="onChatSessionDelete()">
            <i data-lucide="trash-2"></i>
          </button>
        </header>

        <div class="ai-chat-messages" id="ai-chat-messages"></div>

        <div class="ai-suggestions" id="ai-suggestions">
          <button class="ai-chip" onclick="sendAiPrompt('Génère un rapport de santé complet de l\'infrastructure')">
            <i data-lucide="file-text"></i> Rapport de santé global
          </button>
          <button class="ai-chip" onclick="sendAiPrompt('Analyse les anomalies et prévisions de saturation détectées par l\'analyse avancée')">
            <i data-lucide="trending-up"></i> Analyse prédictive
          </button>
          <button class="ai-chip" onclick="sendAiPrompt('Quels processus consomment le plus de CPU ou RAM ?')">
            <i data-lucide="cpu"></i> Processus gourmands
          </button>
          <button class="ai-chip" onclick="sendAiPrompt('Exemple : surveille la RAM et préviens-moi si ça dépasse 85%')">
            <i data-lucide="eye"></i> Créer une surveillance
          </button>
          <button class="ai-chip" onclick="triggerDailyReport()">
            <i data-lucide="sunrise"></i> Rapport quotidien
          </button>
        </div>

        <div class="ai-composer">
          <input type="text" class="ai-composer-input" id="ai-chat-input"
                 placeholder="Posez une question sur votre infrastructure (ex : « Diagnostique le serveur SRV-PROD »)…"
                 autocomplete="off" />
          <button class="ai-send-btn" id="ai-send-btn" onclick="handleAiSend()" title="Envoyer (Entrée)">
            <i data-lucide="send"></i>
          </button>
        </div>
      </main>
    </div>
  `;

  refreshIcons();

  // Restaurer la conversation active (persistante) + liste des conversations
  if (typeof ChatStore !== "undefined") {
    ChatStore.getActive();
    renderActiveChatInto(document.getElementById("ai-chat-messages"));
    renderAiConversations();
  }

  // Attach Enter key event listener to chat input
  const inputEl = document.getElementById("ai-chat-input");
  if (inputEl) {
    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAiSend();
      }
    });
  }

  // Load status and initial cluster diagnostic
  fetchAiStatus();
  fetchClusterHealthSummary();
  fetchViliIntelligence();
}

/* ─── LISTE DES CONVERSATIONS (rail gauche) ─────────────────────── */
function renderAiConversations() {
  const list = document.getElementById("ai-conversations");
  if (!list || typeof ChatStore === "undefined") return;

  const sessions = ChatStore.list();
  const active = ChatStore.getActive();
  const titleEl = document.getElementById("ai-active-title");
  if (titleEl) titleEl.textContent = active.title || "Nouvelle conversation";

  if (!sessions.length) {
    list.innerHTML = `<div class="ai-conv-empty">Aucune conversation pour le moment.</div>`;
    return;
  }

  list.innerHTML = sessions
    .map(
      (s) => `
      <div class="ai-conv-item ${s.id === active.id ? "active" : ""}"
           onclick="onChatSessionSwitch('${s.id}')"
           title="${escapeHtmlEntities(s.title || "Sans titre")}">
        <i data-lucide="${s.id === active.id ? "message-square" : "message-circle"}"></i>
        <div class="ai-conv-text">
          <div class="ai-conv-title">${escapeHtmlEntities(s.title || "Sans titre")}</div>
          <div class="ai-conv-meta">${s.messages.length} message${s.messages.length > 1 ? "s" : ""} · ${_aiConvTime(s.updatedAt)}</div>
        </div>
        <button class="ai-conv-del" title="Supprimer"
                onclick="event.stopPropagation(); _aiDeleteSession('${s.id}')">
          <i data-lucide="trash-2"></i>
        </button>
      </div>`,
    )
    .join("");
  refreshIcons();
}

function _aiConvTime(ts) {
  if (!ts) return "";
  const d = Date.now() - ts;
  if (d < 60e3) return "à l'instant";
  if (d < 3600e3) return `il y a ${Math.floor(d / 60e3)} min`;
  if (d < 86400e3) return `il y a ${Math.floor(d / 3600e3)} h`;
  return new Date(ts).toLocaleDateString("fr", { day: "numeric", month: "short" });
}

function _aiDeleteSession(id) {
  if (typeof ChatStore === "undefined") return;
  ChatStore.remove(id);
  refreshChatUI();
}

/* ─────────────────────────────────────────────────────────────
   INTELLIGENCE VILI : anomalies, prévisions, corrélations, règles
   ───────────────────────────────────────────────────────────── */

let intelRefreshTimer = null;

async function fetchViliIntelligence() {
  try {
    const res = await vigilFetch("/api/ai/analytics");
    const data = await res.json();
    renderViliIntelPanel(data);
  } catch (e) {
    const panel = document.getElementById("vili-intel-panel");
    if (panel) panel.innerHTML = `<div class="ai-intel-loading">Analyse indisponible : ${e.message}</div>`;
  }

  if (intelRefreshTimer) clearInterval(intelRefreshTimer);
  intelRefreshTimer = setInterval(() => {
    if (!document.getElementById("vili-intel-panel")) {
      clearInterval(intelRefreshTimer);
      intelRefreshTimer = null;
      return;
    }
    fetchViliIntelligence();
  }, 60000);
}

function _aiEsc(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderViliIntelPanel(data) {
  const panel = document.getElementById("vili-intel-panel");
  if (!panel) return;
  if (!data) return;

  const anomalies = data.anomalies || [];
  const forecasts = data.forecasts || [];
  const degradations = data.degradations || [];
  const storms = data.storms || [];

  if (!anomalies.length && !forecasts.length && !degradations.length && !storms.length) {
    panel.innerHTML = `
      <div class="vili-intel-card vili-ok">
        <i data-lucide="check-circle-2"></i>
        <div>
          <div class="vili-intel-title">Tout est nominal</div>
          <div class="vili-intel-sub">Aucune anomalie statistique, saturation prévue ou corrélation d'incident. Baselines apprises par machine et par créneau horaire.</div>
        </div>
      </div>`;
    refreshIcons();
    return;
  }

  let html = "";
  forecasts.forEach((f) => {
    const urgent = f.days_left < 2;
    html += `
      <div class="vili-intel-card ${urgent ? "vili-danger" : "vili-warn"}">
        <i data-lucide="hourglass"></i>
        <div>
          <div class="vili-intel-title">Saturation ${_aiEsc(f.hostname)} — ${_aiEsc(f.metric)}</div>
          <div class="vili-intel-sub">${_aiEsc(f.detail)}</div>
          ${urgent ? `<button class="vili-intel-btn" onclick="sendAiPrompt('Prépare un plan d\\'action pour : ${_aiEsc(f.detail)}')">Plan d'action</button>` : ""}
        </div>
      </div>`;
  });
  anomalies.forEach((a) => {
    html += `
      <div class="vili-intel-card vili-warn">
        <i data-lucide="radar"></i>
        <div>
          <div class="vili-intel-title">Anomalie ${_aiEsc(a.hostname)} — ${_aiEsc(a.metric)}</div>
          <div class="vili-intel-sub">${_aiEsc(a.detail)}</div>
        </div>
      </div>`;
  });
  degradations.forEach((d) => {
    html += `
      <div class="vili-intel-card vili-warn">
        <i data-lucide="trending-down"></i>
        <div>
          <div class="vili-intel-title">Tendance ${_aiEsc(d.hostname)}</div>
          <div class="vili-intel-sub">${_aiEsc(d.detail)}</div>
        </div>
      </div>`;
  });
  storms.forEach((s) => {
    html += `
      <div class="vili-intel-card vili-danger">
        <i data-lucide="cloud-lightning"></i>
        <div>
          <div class="vili-intel-title">Tempête d'incidents</div>
          <div class="vili-intel-sub">${_aiEsc(s.detail)}</div>
        </div>
      </div>`;
  });

  panel.innerHTML = html;
  refreshIcons();
}

async function triggerDailyReport() {
  const panel = document.getElementById("vili-intel-panel");
  try {
    if (panel) {
      const note = document.createElement("div");
      note.className = "vili-intel-card vili-ok";
      note.innerHTML = `<i data-lucide="loader-2"></i><div><div class="vili-intel-title">Génération du rapport…</div><div class="vili-intel-sub">Vili analyse 24h de données + prévisions. Patiente quelques secondes.</div></div>`;
      panel.prepend(note);
      refreshIcons();
    }
    const res = await vigilFetch("/api/ai/daily-report", { method: "POST" });
    const data = await res.json();
    if (data.status === "ok") {
      appendChatMessage(
        document.getElementById("ai-chat-messages"),
        "assistant",
        data.report,
      );
      if (typeof ChatStore !== "undefined") {
        const s = ChatStore.getActive();
        ChatStore.append(s.id, "assistant", data.report);
      }
    }
  } catch (e) {
    appendChatMessage(
      document.getElementById("ai-chat-messages"),
      "assistant",
      `⚠️ Rapport quotidien indisponible : ${e.message}`,
    );
  }
}

async function fetchAiStatus() {
  try {
    const res = await vigilFetch("/api/ai/config");
    const data = await res.json();
    const labelEl = document.getElementById("ai-provider-label");
    if (labelEl) {
      const prov = data.AI_PROVIDER || "auto_rule";
      if (prov === "ollama") {
        labelEl.textContent = `Ollama · ${data.AI_MODEL || "local"}`;
      } else if (prov === "openai") {
        labelEl.textContent = `OpenAI · ${data.AI_MODEL || "gpt"}`;
      } else if (prov === "glm") {
        labelEl.textContent = `GLM · ${data.AI_MODEL || "glm-5.3"}`;
      } else {
        labelEl.textContent = "Moteur autonome VIGIL";
      }
    }
  } catch (e) {
    console.warn("fetchAiStatus error:", e);
  }
}

async function fetchClusterHealthSummary() {
  try {
    const res = await vigilFetch("/api/ai/diagnose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hostname: "all" }),
    });
    const data = await res.json();

    const scoreEl = document.getElementById("ai-cluster-score");
    const tagEl = document.getElementById("ai-cluster-status-tag");
    const ring = document.getElementById("ai-cluster-ring");

    if (scoreEl && data.health_score !== undefined) {
      scoreEl.textContent = `${data.health_score}/100`;
      scoreEl.className = `ai-health-score health-${(data.status || "healthy").toLowerCase()}`;
    }
    if (ring && data.health_score !== undefined) {
      const c = 2 * Math.PI * 25;
      const pct = Math.max(0, Math.min(100, data.health_score)) / 100;
      ring.style.strokeDasharray = `${c}`;
      ring.style.strokeDashoffset = `${c * (1 - pct)}`;
      ring.className = `ai-health-ring-fill health-${(data.status || "healthy").toLowerCase()}`;
    }
    if (tagEl) {
      tagEl.textContent = `${data.online_hosts || 0} hôte(s) en ligne sur ${data.total_hosts || 0}`;
    }
  } catch (e) {
    console.warn("fetchClusterHealthSummary error:", e);
  }
}

function handleAiSend() {
  const inputEl = document.getElementById("ai-chat-input");
  if (!inputEl) return;
  const prompt = inputEl.value.trim();
  if (!prompt) return;
  inputEl.value = "";
  sendAiPrompt(prompt);
}

async function sendAiPrompt(promptText) {
  const container = document.getElementById("ai-chat-messages");
  if (!container) return;

  const session = typeof ChatStore !== "undefined" ? ChatStore.getActive() : null;

  // Append user message
  appendChatMessage(container, "user", promptText);
  if (session) ChatStore.append(session.id, "user", promptText);

  // Append typing indicator
  const typingId = "ai-typing-" + Date.now();
  const typingEl = document.createElement("div");
  typingEl.className = "ai-msg assistant";
  typingEl.id = typingId;
  typingEl.innerHTML = `
    <div class="ai-avatar"><i data-lucide="bot"></i></div>
    <div class="ai-bubble">
      <div class="ai-typing">
        <span></span><span></span><span></span>
      </div>
    </div>
  `;
  container.appendChild(typingEl);
  container.scrollTop = container.scrollHeight;
  refreshIcons();

  try {
    const res = await vigilFetch("/api/ai/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: promptText,
        chat_history: session
          ? ChatStore.history(session.id)
          : [],
      }),
    });
    const data = await res.json();

    // Remove typing indicator
    const t = document.getElementById(typingId);
    if (t) t.remove();

    const reply = data.reply || "Aucune réponse générée.";
    appendChatMessage(container, "assistant", reply);

    // Exécutions directes (commandes de lecture) → résultat dans le chat
    if (Array.isArray(data.executions) && data.executions.length) {
      appendChatExecutions(container, data.executions);
    }

    // Demandes de confirmation (commandes sensibles / plan d'action)
    if (Array.isArray(data.approvals) && data.approvals.length) {
      appendChatApprovals(container, data.approvals);
    }

    if (session) ChatStore.append(session.id, "assistant", reply);
    renderAiConversations();
  } catch (e) {
    const t = document.getElementById(typingId);
    if (t) t.remove();
    const errMsg = `⚠️ Erreur lors de la communication avec le service IA : ${e.message}`;
    appendChatMessage(container, "assistant", errMsg);
    if (session) ChatStore.append(session.id, "assistant", errMsg);
  }
}

function appendChatMessage(container, role, text) {
  const msgEl = document.createElement("div");
  msgEl.className = `ai-msg ${role}`;

  const icon = role === "assistant" ? "bot" : "user";
  const formattedText = formatMarkdown(text);

  msgEl.innerHTML = `
    <div class="ai-avatar"><i data-lucide="${icon}"></i></div>
    <div class="ai-bubble">${formattedText}</div>
  `;

  container.appendChild(msgEl);
  container.scrollTop = container.scrollHeight;
  refreshIcons();
}

function escapeHtmlEntities(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatInlineMarkdown(str) {
  if (!str) return "";
  let s = str;
  s = s.replace(/\*\*\*([^*]+)\*\*\*/g, "<strong><em>$1</em></strong>");
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  s = s.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  s = s.replace(/_([^_]+)_/g, "<em>$1</em>");
  return s;
}

function formatMarkdown(str) {
  if (!str) return "";

  // 0. Sécurité : échapper tout le HTML en entrée. Les réponses LLM peuvent
  // relayer du texte contrôlé par une machine supervisée (noms de processus,
  // hostnames...) — aucun HTML brut ne doit passer. Les extraits de code sont
  // extraits ensuite et réinsérés tels quels (déjà échappés ici).
  let text = escapeHtmlEntities(str);

  // 1. Sauvegarder les blocs de code ```...```
  const codeBlocks = [];
  text = text.replace(/```([a-zA-Z0-9_-]*)\r?\n([\s\S]*?)```/g, (match, lang, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push(`<pre><code class="language-${lang}">${code.trim()}</code></pre>`);
    return `@@@CODEBLOCK${idx}@@@`;
  });

  // 2. Sauvegarder le code inline `...`
  const inlineCodes = [];
  text = text.replace(/`([^`]+)`/g, (match, code) => {
    const idx = inlineCodes.length;
    inlineCodes.push(`<code>${code}</code>`);
    return `@@@INLINECODE${idx}@@@`;
  });

  // 3. Traitement des tableaux Markdown (| Col 1 | Col 2 | ...)
  text = text.replace(/((?:^|\n)\|[^\n]+\|\r?\n\|[-:\s|]+\|\r?\n(?:\|[^\n]+\|\r?\n?)+)/g, (match) => {
    const raw = match.trim();
    const lines = raw.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
    if (lines.length < 2) return match;

    const parseRow = (r) => {
      let s = r.trim();
      if (s.startsWith("|")) s = s.slice(1);
      if (s.endsWith("|")) s = s.slice(0, -1);
      return s.split("|").map(c => c.trim());
    };

    const headers = parseRow(lines[0]);
    const bodyRows = lines.slice(2).map(parseRow);

    let html = '<div class="ai-table-wrap"><table><thead><tr>';
    headers.forEach(h => {
      html += `<th>${formatInlineMarkdown(h)}</th>`;
    });
    html += '</tr></thead><tbody>';

    bodyRows.forEach(row => {
      html += '<tr>';
      row.forEach((cell) => {
        html += `<td>${formatInlineMarkdown(cell)}</td>`;
      });
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    return "\n\n" + html + "\n\n";
  });

  // 4. Blockquotes (> ...)
  text = text.replace(/((?:^|\n)>[^\n]+(?:\r?\n>[^\n]+)*)/g, (match) => {
    const lines = match.trim().split(/\r?\n/).map(l => l.replace(/^>\s?/, ""));
    return `\n<blockquote class="ai-quote">${lines.map(l => formatInlineMarkdown(l)).join("<br>")}</blockquote>\n`;
  });

  // 5. Titres (#, ##, ###, ####)
  text = text.replace(/^#### (.*$)/gim, "<h4>$1</h4>");
  text = text.replace(/^### (.*$)/gim, "<h3>$1</h3>");
  text = text.replace(/^## (.*$)/gim, "<h2>$1</h2>");
  text = text.replace(/^# (.*$)/gim, "<h1>$1</h1>");

  // 6. Lignes horizontales
  text = text.replace(/^(\-\-\-|\*\*\*)$/gim, '<hr class="ai-divider">');

  // 7. Listes à puces (- item ou * item)
  text = text.replace(/((?:^|\n)(?:[-*] [^\n]+(?:\r?\n|$))+)/g, (match) => {
    const items = match.trim().split(/\r?\n/).map(l => l.replace(/^[-*] /, "").trim()).filter(Boolean);
    return "\n<ul>" + items.map(it => `<li>${formatInlineMarkdown(it)}</li>`).join("") + "</ul>\n";
  });

  // 8. Listes numérotées (1. item)
  text = text.replace(/((?:^|\n)(?:\d+\. [^\n]+(?:\r?\n|$))+)/g, (match) => {
    const items = match.trim().split(/\r?\n/).map(l => l.replace(/^\d+\. /, "").trim()).filter(Boolean);
    return "\n<ol>" + items.map(it => `<li>${formatInlineMarkdown(it)}</li>`).join("") + "</ol>\n";
  });

  // 9. Formatage inline
  text = formatInlineMarkdown(text);

  // 10. Nettoyage des paragraphes et retours à la ligne
  const blocks = text.split(/\n{2,}/);
  text = blocks.map(b => {
    b = b.trim();
    if (!b) return "";
    if (b.startsWith("<div class=\"ai-table-wrap\"") || b.startsWith("<table") ||
        b.startsWith("<ul") || b.startsWith("<ol") || b.startsWith("<blockquote") ||
        b.startsWith("<h") || b.startsWith("<hr") || b.startsWith("<pre")) {
      return b;
    }
    return `<p>${b.replace(/\n/g, "<br>")}</p>`;
  }).join("\n");

  // 11. Restauration des blocs de code
  inlineCodes.forEach((code, idx) => {
    text = text.replaceAll(`@@@INLINECODE${idx}@@@`, code);
  });
  codeBlocks.forEach((code, idx) => {
    text = text.replaceAll(`@@@CODEBLOCK${idx}@@@`, code);
  });

  return text;
}

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

    // Show diagnosis results in modal
    let modalBody = document.querySelector("#modal .modal-body");
    if (!modalBody) return;

    let issuesHtml = (data.issues || []).map(i => `<li style="color:var(--red);">${i}</li>`).join("");
    let recsHtml = (data.recommendations || []).map(r => `<li style="color:var(--accent2);">${r}</li>`).join("");

    let contentHtml = `
      <div class="ai-diag-result">
        <div class="ai-diag-section">
          <div class="ai-diag-section-title"><i data-lucide="activity"></i> Synthèse du Diagnostic (${hostname})</div>
          <p><strong>Score de santé :</strong> <span class="health-${(data.status||'healthy').toLowerCase()}" style="font-weight:bold; font-size:1.1rem;">${data.health_score}/100 (${data.status})</span></p>
          <p>${data.summary || ''}</p>
        </div>

        ${issuesHtml ? `
        <div class="ai-diag-section">
          <div class="ai-diag-section-title" style="color:var(--red);"><i data-lucide="alert-triangle"></i> Problèmes Identifiés</div>
          <ul>${issuesHtml}</ul>
        </div>` : ''}

        ${recsHtml ? `
        <div class="ai-diag-section">
          <div class="ai-diag-section-title"><i data-lucide="check-circle"></i> Recommandations Administrateur</div>
          <ul>${recsHtml}</ul>
        </div>` : ''}

        ${data.ai_analysis ? `
        <div class="ai-diag-section">
          <div class="ai-diag-section-title"><i data-lucide="bot"></i> Analyse Approfondie LLM (${data.provider})</div>
          <div>${formatMarkdown(data.ai_analysis)}</div>
        </div>` : ''}
      </div>
    `;

    // Open or inject in modal
    const modalTitle = document.getElementById("modal-title");
    if (modalTitle) modalTitle.textContent = `Diagnostic IA — ${hostname}`;

    // Switch to overview or create custom view inside modal
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

/* ─────────────────────────────────────────────────────────────
   ACTIONS DE VILI DANS LE CHAT
   - exécutions directes (commandes de lecture) → résultat inline
   - demandes sensibles → carte Oui / Non (ou plan multi-étapes)
   ───────────────────────────────────────────────────────────── */

function _aiActionEsc(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function appendChatExecutions(container, executions) {
  if (!container) return;
  executions.forEach((ex) => {
    const msgEl = document.createElement("div");
    msgEl.className = "ai-msg assistant";
    const out = (ex.stdout || ex.stderr || ex.error || "").trim();
    const refusedBlock = ex.refused
      ? `<div class="chat-exec-refused"><i data-lucide="ban"></i> ${_aiActionEsc(ex.reason || "Commande refusée.")}</div>`
      : `
      <div class="chat-exec-meta">
        <span class="badge ${ex.ok ? "online" : "offline"}">${ex.ok ? "terminé" : "échec"} · exit ${ex.exit_code ?? "?"}</span>
      </div>
      ${out ? `<pre class="chat-exec-out">${_aiActionEsc(out)}</pre>` : `<div class="chat-exec-meta" style="color:var(--muted)">Aucune sortie.</div>`}`;
    msgEl.innerHTML = `
      <div class="ai-avatar"><i data-lucide="terminal"></i></div>
      <div class="ai-bubble">
        <div class="chat-exec-cmd"><span class="term-prompt">${_aiActionEsc(ex.hostname)}</span>:${_aiActionEsc(ex.command)}</div>
        ${refusedBlock}
      </div>`;
    container.appendChild(msgEl);
  });
  container.scrollTop = container.scrollHeight;
  refreshIcons();
}

function appendChatApprovals(container, approvals) {
  if (!container) return;
  const isPlan = approvals.length > 1;
  const ids = approvals.map((a) => a.id);

  const stepsHtml = approvals
    .map(
      (a, i) => `
      <div class="chat-appr-step">
        ${isPlan ? `<span class="chat-appr-stepnum">${i + 1}.</span>` : ""}
        <div class="chat-appr-stepbody">
          <div class="chat-appr-cmd"><code>${_aiActionEsc(a.command)}</code></div>
          ${a.reason ? `<div class="chat-appr-reason">${_aiActionEsc(a.reason)}</div>` : ""}
        </div>
      </div>`,
    )
    .join("");

  const msgEl = document.createElement("div");
  msgEl.className = "ai-msg assistant";
  msgEl.innerHTML = `
    <div class="ai-avatar"><i data-lucide="shield-alert"></i></div>
    <div class="ai-bubble chat-appr-card" data-ids="${ids.join(",")}">
      <div class="chat-appr-title">
        ${isPlan
          ? `🛡️ Plan d'action — ${approvals.length} étapes sur <strong>${_aiActionEsc(approvals[0].hostname)}</strong>`
          : `🛡️ Action sensible sur <strong>${_aiActionEsc(approvals[0].hostname)}</strong>`}
      </div>
      ${stepsHtml}
      <div class="chat-appr-hint">Rien ne sera exécuté sans votre confirmation.</div>
      <div class="chat-appr-actions">
        <button class="chat-appr-btn approve" onclick="decideChatApprovals(${JSON.stringify(ids)}, true, this)">
          <i data-lucide="check"></i> ${isPlan ? "Effectuer toutes les actions" : "Effectuer l'action"}
        </button>
        <button class="chat-appr-btn reject" onclick="decideChatApprovals(${JSON.stringify(ids)}, false, this)">
          <i data-lucide="x"></i> Refuser
        </button>
      </div>
      <div class="chat-appr-result" style="display:none;"></div>
    </div>`;
  container.appendChild(msgEl);
  container.scrollTop = container.scrollHeight;
  refreshIcons();
}

async function decideChatApprovals(ids, approved, btnEl) {
  const card = btnEl?.closest(".chat-appr-card");
  if (!card || card.dataset.decided) return;
  card.dataset.decided = "1";
  card.querySelectorAll(".chat-appr-btn").forEach((b) => (b.disabled = true));
  btnEl.innerHTML = `<i data-lucide="loader-2"></i> En cours…`;
  refreshIcons();

  const resultBox = card.querySelector(".chat-appr-result");
  try {
    const single = ids.length === 1;
    const url = single
      ? `/api/ai/approvals/${ids[0]}/decide`
      : "/api/ai/approvals/decide-batch";
    const body = single
      ? { approved }
      : { ids, approved };

    const res = await vigilFetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));

    resultBox.style.display = "block";
    if (!approved) {
      resultBox.innerHTML = `<div class="chat-exec-refused"><i data-lucide="ban"></i> ${single ? "Commande refusée" : "Plan refusé"} — rien n'a été exécuté.</div>`;
      btnEl.innerHTML = `<i data-lucide="x"></i> Refusé`;
    } else {
      const results = single ? [data] : data.results || [];
      const lines = results.map((r) => {
        const ap = r.result || r.approval?.result || {};
        const out = (ap.stdout || ap.stderr || ap.error || "").trim();
        const ok = ap.ok !== false && r.status !== "approved_but_offline";
        return `<div class="chat-plan-step ${ok ? "ok" : "ko"}">
          <strong>${ok ? "✅" : "❌"} étape</strong> — exit ${ap.exit_code ?? "?"}
          ${out ? `<pre class="chat-exec-out">${_aiActionEsc(out.slice(0, 1200))}</pre>` : ""}
        </div>`;
      });
      resultBox.innerHTML = lines.join("") || `<div class="chat-exec-refused">Aucun résultat.</div>`;
      btnEl.innerHTML = `<i data-lucide="check-check"></i> Exécuté`;
    }
  } catch (e) {
    card.dataset.decided = "";
    resultBox.style.display = "block";
    resultBox.innerHTML = `<div class="chat-exec-refused">Erreur : ${_aiActionEsc(e.message)}</div>`;
    card.querySelectorAll(".chat-appr-btn").forEach((b) => (b.disabled = false));
  }
  refreshIcons();
  const chat = document.getElementById("ai-chat-messages");
  if (chat) chat.scrollTop = chat.scrollHeight;
}
