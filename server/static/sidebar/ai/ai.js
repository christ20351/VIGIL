/* ─────────────────────────────────────────────────────────────
   VIGIL — ai.js (AI Copilot & Monitoring Diagnostics)
   ───────────────────────────────────────────────────────────── */

let aiChatHistory = [];

async function renderAiView() {
  const content = document.querySelector(".content");
  if (!content) return;

  content.innerHTML = `
    <div class="ai-container">
      <div class="ai-header-card">
        <div>
          <div class="ai-header-title">
            <i data-lucide="bot"></i> Copilote & Diagnostics IA VIGIL
          </div>
          <div class="ai-header-subtitle">
            Analyse d'infrastructure intelligente en temps réel et assistance administrateur système
          </div>
        </div>
        <div class="ai-status-pill" id="ai-provider-pill">
          <div class="ai-status-dot"></div>
          <span id="ai-provider-label">Moteur IA VIGIL...</span>
        </div>
      </div>

      <div class="ai-main-grid">
        <!-- Sidebar Panel -->
        <div class="ai-panel">
          <div class="ai-panel-title">
            <i data-lucide="activity"></i> Santé du Cluster
          </div>

          <div class="ai-health-card">
            <div class="ai-health-label">Score Global Infrastructure</div>
            <div class="ai-health-score health-healthy" id="ai-cluster-score">--/100</div>
            <div id="ai-cluster-status-tag" style="font-size:0.85rem; font-weight:600; color:#94a3b8;">Chargement...</div>
          </div>

          <div class="ai-panel-title" style="margin-top:0.5rem;">
            <i data-lucide="zap"></i> Actions & Diagnostic Rapide
          </div>

          <div class="ai-prompts-list">
            <button class="ai-prompt-btn" onclick="sendAiPrompt('Génère un rapport de santé complet de l\'infrastructure')">
              <i data-lucide="file-text"></i> Rapport de Santé Global
            </button>
            <button class="ai-prompt-btn" onclick="sendAiPrompt('Quels processus consomment le plus de CPU ou RAM ?')">
              <i data-lucide="cpu"></i> Analyse des Processus Gourmands
            </button>
            <button class="ai-prompt-btn" onclick="sendAiPrompt('Vérifie la santé des disques S.M.A.R.T. et les risques de panne')">
              <i data-lucide="hard-drive"></i> Audit Santé Disques SMART
            </button>
            <button class="ai-prompt-btn" onclick="sendAiPrompt('Quelles machines sont actuellement hors ligne ?')">
              <i data-lucide="wifi-off"></i> Vérifier la Connectivité
            </button>
          </div>
        </div>

        <!-- Chat Main Area -->
        <div class="ai-chat-card">
          <div class="ai-chat-messages" id="ai-chat-messages">
            <div class="ai-msg assistant">
              <div class="ai-avatar"><i data-lucide="bot"></i></div>
              <div class="ai-bubble">
                Bonjour ! Je suis **VIGIL AI**, votre copilote d'administration système. 
                J'analyse les métriques en direct de vos hôtes.
                Comment puis-je vous aider aujourd'hui ?
              </div>
            </div>
          </div>

          <div class="ai-chat-input-row">
            <input type="text" class="ai-chat-input" id="ai-chat-input" placeholder="Posez une question sur votre infrastructure (ex: 'Diagnostique le serveur SRV-PROD')..." />
            <button class="ai-send-btn" id="ai-send-btn" onclick="handleAiSend()">
              <i data-lucide="send"></i> Envoyer
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  refreshIcons();

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
}

async function fetchAiStatus() {
  try {
    const res = await vigilFetch("/api/ai/config");
    const data = await res.json();
    const labelEl = document.getElementById("ai-provider-label");
    if (labelEl) {
      const prov = data.AI_PROVIDER || "auto_rule";
      if (prov === "ollama") {
        labelEl.textContent = `Ollama (${data.AI_MODEL || "local"})`;
      } else if (prov === "openai") {
        labelEl.textContent = `OpenAI (${data.AI_MODEL || "gpt"})`;
      } else {
        labelEl.textContent = "Moteur Autonome VIGIL";
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

    if (scoreEl && data.health_score !== undefined) {
      scoreEl.textContent = `${data.health_score}/100`;
      scoreEl.className = `ai-health-score health-${(data.status || "healthy").toLowerCase()}`;
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

  // Append user message
  appendChatMessage(container, "user", promptText);

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
      body: JSON.stringify({ prompt: promptText }),
    });
    const data = await res.json();

    // Remove typing indicator
    const t = document.getElementById(typingId);
    if (t) t.remove();

    const reply = data.reply || "Aucune réponse générée.";
    appendChatMessage(container, "assistant", reply);
  } catch (e) {
    const t = document.getElementById(typingId);
    if (t) t.remove();
    appendChatMessage(container, "assistant", `⚠️ Erreur lors de la communication avec le service IA : ${e.message}`);
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

function formatMarkdown(str) {
  if (!str) return "";
  let html = str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Code blocks ```...```
  html = html.replace(/```([\s\S]*?)```/g, (match, code) => {
    return `<pre><code>${code.trim()}</code></pre>`;
  });

  // Inline code `...`
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Headers ###
  html = html.replace(/^### (.*$)/gim, "<h3>$1</h3>");
  html = html.replace(/^## (.*$)/gim, "<h3>$1</h3>");

  // Bold **...**
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  // Lists - ...
  html = html.replace(/^\- (.*$)/gim, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>)/g, "<ul>$1</ul>");

  // Newlines
  html = html.replace(/\n\n/g, "</p><p>");

  return `<p>${html}</p>`;
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

    let issuesHtml = (data.issues || []).map(i => `<li style="color:#f87171;">⚠️ ${i}</li>`).join("");
    let recsHtml = (data.recommendations || []).map(r => `<li style="color:#38bdf8;">💡 ${r}</li>`).join("");

    let contentHtml = `
      <div class="ai-diag-result">
        <div class="ai-diag-section">
          <div class="ai-diag-section-title"><i data-lucide="activity"></i> Synthèse du Diagnostic (${hostname})</div>
          <p><strong>Score de santé :</strong> <span class="health-${(data.status||'healthy').toLowerCase()}" style="font-weight:bold; font-size:1.1rem;">${data.health_score}/100 (${data.status})</span></p>
          <p>${data.summary || ''}</p>
        </div>

        ${issuesHtml ? `
        <div class="ai-diag-section">
          <div class="ai-diag-section-title" style="color:#f87171;"><i data-lucide="alert-triangle"></i> Problèmes Identifiés</div>
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
