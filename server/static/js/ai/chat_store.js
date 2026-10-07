/* ─────────────────────────────────────────────────────────────
   VIGIL — chat_store.js
   Magasin multi-sessions pour les conversations avec l'assistant.
   Persistance locale (localStorage) partagée entre le drawer flottant
   et la page "IA Copilote" : plusieurs chats, switch, suppression.
   ───────────────────────────────────────────────────────────── */

const ChatStore = {
  KEY: "vili_chat_sessions_v1",
  ACTIVE_KEY: "vili_chat_active_v1",
  MAX_SESSIONS: 30,

  _load() {
    try {
      const raw = localStorage.getItem(this.KEY);
      const sessions = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(sessions)) return [];
      return sessions.filter(
        (s) => s && typeof s.id === "string" && Array.isArray(s.messages),
      );
    } catch {
      return [];
    }
  },

  _save(sessions) {
    try {
      localStorage.setItem(this.KEY, JSON.stringify(sessions));
    } catch {
      /* quota dépassé ou storage indisponible : on ignore */
    }
  },

  list() {
    // plus récentes d'abord
    return this._load().sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
  },

  get(id) {
    return this._load().find((s) => s.id === id) || null;
  },

  create() {
    const sessions = this._load();
    const session = {
      id: "chat-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7),
      title: "Nouvelle conversation",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: [],
    };
    sessions.push(session);
    // borner le nombre de conversations conservées
    while (sessions.length > this.MAX_SESSIONS) {
      const oldest = sessions
        .slice()
        .sort((a, b) => (a.updatedAt || 0) - (b.updatedAt || 0))[0];
      sessions.splice(sessions.indexOf(oldest), 1);
    }
    this._save(sessions);
    this.setActive(session.id);
    return session;
  },

  remove(id) {
    let sessions = this._load();
    sessions = sessions.filter((s) => s.id !== id);
    this._save(sessions);
    if (this._activeId() === id) {
      try {
        localStorage.removeItem(this.ACTIVE_KEY);
      } catch {}
    }
  },

  rename(id, title) {
    const sessions = this._load();
    const s = sessions.find((x) => x.id === id);
    if (s && title) {
      s.title = title;
      this._save(sessions);
    }
  },

  _activeId() {
    try {
      return localStorage.getItem(this.ACTIVE_KEY);
    } catch {
      return null;
    }
  },

  getActive() {
    const id = this._activeId();
    if (id) {
      const s = this.get(id);
      if (s) return s;
    }
    // aucune session valide → en créer une
    return this.create();
  },

  setActive(id) {
    try {
      localStorage.setItem(this.ACTIVE_KEY, id);
    } catch {}
  },

  append(sessionId, role, content) {
    const sessions = this._load();
    const s = sessions.find((x) => x.id === sessionId);
    if (!s) return;
    s.messages.push({ role, content, ts: Date.now() });
    s.updatedAt = Date.now();
    // titre auto : premier message utilisateur
    const userCount = s.messages.filter((m) => m.role === "user").length;
    if (role === "user" && userCount === 1) {
      const t = content.trim().replace(/\s+/g, " ");
      s.title = t.length > 38 ? t.slice(0, 38) + "…" : t;
    }
    this._save(sessions);
  },

  // historique formaté pour l'API (role/content), borné aux N derniers
  history(sessionId, max = 16) {
    const s = this.get(sessionId);
    if (!s) return [];
    return s.messages
      .slice(-max)
      .map((m) => ({ role: m.role, content: m.content }));
  },
};

/* ─── UI partagée : barres de sessions + rendu de l'historique ─── */

// met à jour TOUTES les barres de sessions présentes (drawer + page IA)
function buildChatSessionBar() {
  const sessions = ChatStore.list();
  const active = ChatStore.getActive();
  const options = sessions
    .map(
      (s) =>
        `<option value="${s.id}" ${s.id === active.id ? "selected" : ""}>${escapeHtml(s.title || "Sans titre")}</option>`,
    )
    .join("");
  document.querySelectorAll(".ai-session-bar").forEach((bar) => {
    bar.innerHTML = `
      <select class="ai-session-select" title="Conversations" onchange="onChatSessionSwitch(this.value)">${options}</select>
      <button class="ai-session-btn" title="Nouvelle conversation" onclick="onChatSessionNew()"><i data-lucide="plus"></i></button>
      <button class="ai-session-btn ai-session-danger" title="Supprimer cette conversation" onclick="onChatSessionDelete()"><i data-lucide="trash-2"></i></button>
    `;
  });
  // liste latérale de la page IA Copilote (si présente)
  if (typeof renderAiConversations === "function") renderAiConversations();
  if (typeof refreshIcons === "function") refreshIcons();
}

// rafraîchit toutes les vues de conversation + les barres
function refreshChatUI() {
  renderActiveChatInto(document.getElementById("ai-drawer-chat-messages"));
  renderActiveChatInto(document.getElementById("ai-chat-messages"));
  buildChatSessionBar();
}

function onChatSessionSwitch(id) {
  ChatStore.setActive(id);
  refreshChatUI();
}

function onChatSessionNew() {
  ChatStore.create();
  refreshChatUI();
}

function onChatSessionDelete() {
  const active = ChatStore.getActive();
  ChatStore.remove(active.id);
  refreshChatUI();
}

const VILI_GREETING =
  "Bonjour ! Je suis **Vili**, connecté à votre base de données en temps réel. Posez-moi vos questions sur vos métriques, l'historique, les pics de charge ou la santé des disques.";

// (re)construit la liste des messages de la session active dans un conteneur
function renderActiveChatInto(container) {
  if (!container) return;
  const session = ChatStore.getActive();
  container.innerHTML = "";
  if (!session.messages.length) {
    appendChatMessageTo(container, "assistant", VILI_GREETING);
    return;
  }
  session.messages.forEach((m) =>
    appendChatMessageTo(container, m.role, m.content),
  );
}
