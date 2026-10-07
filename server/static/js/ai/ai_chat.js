/* ─────────────────────────────────────────────────────────────
   VIGIL — ai_chat.js (Copilot Conversation & Drawer Logic)
   Conversations persistantes multi-sessions (via ChatStore).
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
    openAiDrawerChat();
  }
}

// appelé à chaque ouverture du drawer : restaure la session active
function openAiDrawerChat() {
  if (typeof ChatStore === "undefined") return;
  refreshChatUI();
}

async function sendDrawerAiPrompt(promptText) {
  const container = document.getElementById("ai-drawer-chat-messages");
  if (!container || !promptText) return;
  if (typeof ChatStore === "undefined") return;

  const session = ChatStore.getActive();
  appendChatMessageTo(container, "user", promptText);
  ChatStore.append(session.id, "user", promptText);

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
      body: JSON.stringify({
        prompt: promptText,
        chat_history: ChatStore.history(session.id),
      }),
    });
    const data = await res.json();
    document.getElementById(typingId)?.remove();

    const reply = data.reply || "Aucune réponse.";
    appendChatMessageTo(container, "assistant", reply);

    // Exécutions directes (commandes de lecture) → résultat dans le chat
    if (Array.isArray(data.executions) && data.executions.length) {
      if (typeof appendChatExecutions === "function") {
        appendChatExecutions(container, data.executions);
      }
    }

    // Demandes de confirmation (commandes sensibles / plan d'action)
    if (Array.isArray(data.approvals) && data.approvals.length) {
      if (typeof appendChatApprovals === "function") {
        appendChatApprovals(container, data.approvals);
      }
    }

    ChatStore.append(session.id, "assistant", reply);
    if (typeof buildChatSessionBar === "function") buildChatSessionBar();
  } catch (e) {
    document.getElementById(typingId)?.remove();
    const errMsg = `⚠️ Erreur : ${e.message}`;
    appendChatMessageTo(container, "assistant", errMsg);
    ChatStore.append(session.id, "assistant", errMsg);
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

document.addEventListener("DOMContentLoaded", () => {
  const drawerInput = document.getElementById("ai-drawer-input");
  if (drawerInput) {
    drawerInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleDrawerAiSend();
      }
    });
  }
  // restaure la dernière conversation dès le chargement de la page
  if (typeof ChatStore !== "undefined") {
    ChatStore.getActive();
    renderActiveChatInto(document.getElementById("ai-drawer-chat-messages"));
  }
});
