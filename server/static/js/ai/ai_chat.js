/* ─────────────────────────────────────────────────────────────
   VIGIL — ai_chat.js (Copilot Conversation & Drawer Logic)
   ───────────────────────────────────────────────────────────── */

function toggleAiDrawer() {
  const drawer = document.getElementById("ai-drawer");
  const overlay = document.getElementById("ai-drawer-overlay");
  if (!drawer || !overlay) return;

  const isOpen = drawer.classList.contains("open");
  if (isOpen) {
    drawer.classList.remove("open");
    overlay.classList.remove("open");
  } else {
    drawer.classList.add("open");
    overlay.classList.add("open");
    refreshIcons();
  }
}

async function sendDrawerAiPrompt(promptText) {
  const container = document.getElementById("ai-drawer-chat-messages");
  if (!container || !promptText) return;

  appendChatMessageTo(container, "user", promptText);

  const typingId = "drawer-typing-" + Date.now();
  const typingEl = document.createElement("div");
  typingEl.className = "ai-msg assistant";
  typingEl.id = typingId;
  typingEl.innerHTML = `
    <div class="ai-avatar"><i data-lucide="bot"></i></div>
    <div class="ai-bubble"><div class="ai-typing"><span></span><span></span><span></span></div></div>
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
    document.getElementById(typingId)?.remove();

    appendChatMessageTo(container, "assistant", data.reply || "Aucune réponse.");
  } catch (e) {
    document.getElementById(typingId)?.remove();
    appendChatMessageTo(container, "assistant", `⚠️ Erreur : ${e.message}`);
  }
}

function appendChatMessageTo(container, role, text) {
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

function handleDrawerAiSend() {
  const inputEl = document.getElementById("ai-drawer-input");
  if (!inputEl) return;
  const prompt = inputEl.value.trim();
  if (!prompt) return;
  inputEl.value = "";
  sendDrawerAiPrompt(prompt);
}
