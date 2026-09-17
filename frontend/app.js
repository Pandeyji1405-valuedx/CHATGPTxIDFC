/**
 * CHATGPTxIDFC — Frontend Application Logic
 * Production-Quality Banking Conversational AI
 */

const API_BASE = "";

// App State
const state = {
  accounts: [], // [{ id, name, email, token, role, avatar_url }]
  activeAccountIndex: 0,
  currentConversationId: null,
  conversations: [],
  isRecordingSpeech: false,
  speechRecognition: null,
  isAuthModeRegister: false,
  selectedUploadFile: null,
  ttsRate: 1.0,
  autoTts: false,
  sttReview: true
};

// DOM Elements
const DOM = {
  sidebar: document.getElementById("sidebar"),
  btnSidebarCollapse: document.getElementById("btn-sidebar-collapse"),
  btnMobileSidebar: document.getElementById("btn-mobile-sidebar"),
  btnNewChat: document.getElementById("btn-new-chat"),
  conversationSearch: document.getElementById("conversation-search"),
  conversationList: document.getElementById("conversation-list"),
  messagesStream: document.getElementById("messages-stream"),
  welcomeHero: document.getElementById("welcome-hero"),
  currentChatTitle: document.getElementById("current-chat-title"),
  chatForm: document.getElementById("chat-form"),
  chatTextarea: document.getElementById("chat-textarea"),
  btnSend: document.getElementById("btn-send"),
  btnMic: document.getElementById("btn-mic"),
  speechReviewBar: document.getElementById("speech-review-bar"),
  speechTranscriptInput: document.getElementById("speech-transcript-input"),
  btnConfirmSpeech: document.getElementById("btn-confirm-speech"),
  btnCancelSpeech: document.getElementById("btn-cancel-speech"),
  btnThemeToggle: document.getElementById("btn-theme-toggle"),
  btnOpenSettings: document.getElementById("btn-open-settings"),
  btnAuthTrigger: document.getElementById("btn-auth-trigger"),
  authBtnLabel: document.getElementById("auth-btn-label"),
  userProfileWidget: document.getElementById("btn-open-account-drawer"),
  userDisplayName: document.getElementById("user-display-name"),
  userDisplayEmail: document.getElementById("user-display-email"),
  userAvatarPlaceholder: document.getElementById("user-avatar-placeholder"),
  adminKbBtnContainer: document.getElementById("admin-kb-btn-container"),
  btnOpenAdminKb: document.getElementById("btn-open-admin-kb"),
  // Modals
  authModal: document.getElementById("auth-modal"),
  authModalTitle: document.getElementById("auth-modal-title"),
  authForm: document.getElementById("auth-form"),
  authNameGroup: document.getElementById("auth-name-group"),
  authNameInput: document.getElementById("auth-name-input"),
  authEmailInput: document.getElementById("auth-email-input"),
  authPasswordInput: document.getElementById("auth-password-input"),
  btnAuthSubmit: document.getElementById("btn-auth-submit"),
  btnGoogleLogin: document.getElementById("btn-google-login"),
  btnAuthToggleMode: document.getElementById("btn-auth-toggle-mode"),
  authTogglePrompt: document.getElementById("auth-toggle-prompt"),
  accountDrawer: document.getElementById("account-drawer"),
  savedAccountsList: document.getElementById("saved-accounts-list"),
  btnAddAccount: document.getElementById("btn-add-account"),
  btnLogoutCurrent: document.getElementById("btn-logout-current"),
  adminKbModal: document.getElementById("admin-kb-modal"),
  uploadDropzone: document.getElementById("upload-dropzone"),
  kbFileInput: document.getElementById("kb-file-input"),
  btnBrowseFile: document.getElementById("btn-browse-file"),
  kbUploadForm: document.getElementById("kb-upload-form"),
  docTitleInput: document.getElementById("doc-title-input"),
  docNotifInput: document.getElementById("doc-notif-input"),
  docSourceSelect: document.getElementById("doc-source-select"),
  docPubdateInput: document.getElementById("doc-pubdate-input"),
  btnSubmitUpload: document.getElementById("btn-submit-upload"),
  btnCancelUpload: document.getElementById("btn-cancel-upload"),
  kbDocumentsTbody: document.getElementById("kb-documents-tbody"),
  kbDocCount: document.getElementById("kb-doc-count"),
  btnReindexAll: document.getElementById("btn-reindex-all"),
  settingsModal: document.getElementById("settings-modal"),
  settingSttReview: document.getElementById("setting-stt-review"),
  settingAutoTts: document.getElementById("setting-auto-tts"),
  settingTtsRate: document.getElementById("setting-tts-rate")
};

// ==================== AUTHENTICATION & MULTI-ACCOUNT ====================

function getActiveAccount() {
  if (state.accounts.length > 0 && state.activeAccountIndex < state.accounts.length) {
    return state.accounts[state.activeAccountIndex];
  }
  return null;
}

function getAuthHeader() {
  const account = getActiveAccount();
  return account && account.token ? { "Authorization": `Bearer ${account.token}` } : {};
}

function saveAccountsToStorage() {
  localStorage.setItem("chatgptxidfc_accounts", JSON.stringify(state.accounts));
  localStorage.setItem("chatgptxidfc_active_idx", state.activeAccountIndex);
}

function loadAccountsFromStorage() {
  try {
    const raw = localStorage.getItem("chatgptxidfc_accounts");
    const activeIdx = localStorage.getItem("chatgptxidfc_active_idx");
    if (raw) {
      state.accounts = JSON.parse(raw);
      state.activeAccountIndex = activeIdx ? parseInt(activeIdx, 10) : 0;
    }
  } catch (e) {
    console.error("Failed to load accounts from storage:", e);
  }
}

function updateUIForAuth() {
  const account = getActiveAccount();
  if (account) {
    DOM.userDisplayName.textContent = account.name;
    DOM.userDisplayEmail.textContent = account.email;
    DOM.authBtnLabel.textContent = "Switch";
    DOM.userAvatarPlaceholder.innerHTML = `<i class="fa-solid fa-user-check"></i>`;
    
    // Check admin role
    if (account.role === "admin") {
      DOM.adminKbBtnContainer.classList.remove("hidden");
    } else {
      DOM.adminKbBtnContainer.classList.add("hidden");
    }
  } else {
    DOM.userDisplayName.textContent = "Guest User";
    DOM.userDisplayEmail.textContent = "guest@idfcbank.com";
    DOM.authBtnLabel.textContent = "Login";
    DOM.userAvatarPlaceholder.innerHTML = `<i class="fa-solid fa-user"></i>`;
    DOM.adminKbBtnContainer.classList.add("hidden");
  }
  renderSavedAccountsList();
}

async function loginUser(email, password) {
  try {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    addAccount({
      id: data.user.id,
      name: data.user.name,
      email: data.user.email,
      role: data.user.role,
      token: data.access_token
    });
    closeAllModals();
    await loadConversations();
  } catch (err) {
    alert(err.message);
  }
}

async function registerUser(name, email, password) {
  try {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Registration failed");
    }
    const data = await res.json();
    addAccount({
      id: data.user.id,
      name: data.user.name,
      email: data.user.email,
      role: data.user.role,
      token: data.access_token
    });
    closeAllModals();
    await loadConversations();
  } catch (err) {
    alert(err.message);
  }
}

async function googleLogin(email = null, name = null) {
  try {
    const mockEmail = email || prompt("Enter Google Account Email for OAuth Simulation:", "siddharth.google@idfcbank.com");
    if (!mockEmail) return;
    const mockName = name || mockEmail.split("@")[0].replace(".", " ");

    const res = await fetch(`${API_BASE}/api/auth/google`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        credential: "mock_google_oauth_token_" + Date.now(),
        email: mockEmail,
        name: mockName
      })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Google Login failed");
    }
    const data = await res.json();
    addAccount({
      id: data.user.id,
      name: data.user.name,
      email: data.user.email,
      role: data.user.role,
      token: data.access_token
    });
    closeAllModals();
    await loadConversations();
  } catch (err) {
    alert(err.message);
  }
}

function addAccount(accData) {
  const existingIdx = state.accounts.findIndex(a => a.email.toLowerCase() === accData.email.toLowerCase());
  if (existingIdx >= 0) {
    state.accounts[existingIdx] = accData;
    state.activeAccountIndex = existingIdx;
  } else {
    state.accounts.push(accData);
    state.activeAccountIndex = state.accounts.length - 1;
  }
  saveAccountsToStorage();
  updateUIForAuth();
}

function switchAccount(index) {
  if (index >= 0 && index < state.accounts.length) {
    state.activeAccountIndex = index;
    state.currentConversationId = null;
    saveAccountsToStorage();
    updateUIForAuth();
    loadConversations();
    DOM.messagesStream.innerHTML = "";
    DOM.messagesStream.appendChild(DOM.welcomeHero);
    DOM.welcomeHero.classList.remove("hidden");
    DOM.currentChatTitle.textContent = "New Conversation";
    closeAllModals();
  }
}

function logoutCurrentAccount() {
  if (state.accounts.length > 0) {
    state.accounts.splice(state.activeAccountIndex, 1);
    state.activeAccountIndex = 0;
    state.currentConversationId = null;
    saveAccountsToStorage();
    updateUIForAuth();
    loadConversations();
    DOM.messagesStream.innerHTML = "";
    DOM.messagesStream.appendChild(DOM.welcomeHero);
    DOM.welcomeHero.classList.remove("hidden");
    DOM.currentChatTitle.textContent = "New Conversation";
    closeAllModals();
  }
}

function renderSavedAccountsList() {
  DOM.savedAccountsList.innerHTML = "";
  if (state.accounts.length === 0) {
    DOM.savedAccountsList.innerHTML = `<div class="list-skeleton">No accounts signed in.</div>`;
    return;
  }

  state.accounts.forEach((acc, idx) => {
    const isActive = idx === state.activeAccountIndex;
    const card = document.createElement("div");
    card.className = `account-item-card ${isActive ? "active" : ""}`;
    card.innerHTML = `
      <div class="account-card-left">
        <div class="avatar-container" style="background-color: ${isActive ? '#9e1b32' : '#30363d'}">
          <i class="fa-solid fa-user"></i>
        </div>
        <div>
          <strong style="font-size:13px;">${escapeHtml(acc.name)}</strong>
          <span style="display:block;font-size:11px;color:var(--text-muted);">${escapeHtml(acc.email)}</span>
        </div>
      </div>
      <div>
        ${isActive ? '<span class="badge-active">Active</span>' : '<button class="btn btn-secondary btn-sm">Switch</button>'}
      </div>
    `;
    card.addEventListener("click", () => switchAccount(idx));
    DOM.savedAccountsList.appendChild(card);
  });
}

// ==================== CONVERSATIONS ====================

async function loadConversations(searchQuery = null) {
  const account = getActiveAccount();
  if (!account) {
    DOM.conversationList.innerHTML = `<div class="list-skeleton">Please sign in to view history.</div>`;
    return;
  }

  try {
    const url = searchQuery
      ? `${API_BASE}/api/conversations/search?q=${encodeURIComponent(searchQuery)}`
      : `${API_BASE}/api/conversations`;

    const res = await fetch(url, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load conversations");
    state.conversations = await res.json();
    renderConversationList(state.conversations);
  } catch (err) {
    console.error(err);
    DOM.conversationList.innerHTML = `<div class="list-skeleton">Error loading conversations.</div>`;
  }
}

function renderConversationList(convs) {
  DOM.conversationList.innerHTML = "";
  if (convs.length === 0) {
    DOM.conversationList.innerHTML = `<div class="list-skeleton">No conversations yet.</div>`;
    return;
  }

  // Group by Today, Yesterday, Previous 7 Days, Older
  const now = new Date();
  const groups = {
    "Today": [],
    "Yesterday": [],
    "Previous 7 Days": [],
    "Older": []
  };

  convs.forEach(c => {
    const updated = new Date(c.updated_at);
    const diffDays = Math.floor((now - updated) / (1000 * 60 * 60 * 24));
    if (diffDays === 0) groups["Today"].push(c);
    else if (diffDays === 1) groups["Yesterday"].push(c);
    else if (diffDays <= 7) groups["Previous 7 Days"].push(c);
    else groups["Older"].push(c);
  });

  Object.keys(groups).forEach(grpTitle => {
    const items = groups[grpTitle];
    if (items.length > 0) {
      const header = document.createElement("div");
      header.className = "conversation-group-title";
      header.textContent = grpTitle;
      DOM.conversationList.appendChild(header);

      items.forEach(c => {
        const item = document.createElement("div");
        item.className = `conversation-item ${c.id === state.currentConversationId ? "active" : ""}`;
        item.dataset.id = c.id;
        item.innerHTML = `
          <span class="conv-title-text" title="${escapeHtml(c.title)}">${escapeHtml(c.title)}</span>
          <div class="conv-item-actions">
            <button class="conv-action-btn btn-rename" title="Rename"><i class="fa-solid fa-pen"></i></button>
            <button class="conv-action-btn btn-delete" title="Delete"><i class="fa-solid fa-trash"></i></button>
          </div>
        `;

        item.addEventListener("click", (e) => {
          if (e.target.closest(".btn-rename")) {
            e.stopPropagation();
            renameConversationPrompt(c.id, c.title);
          } else if (e.target.closest(".btn-delete")) {
            e.stopPropagation();
            deleteConversationPrompt(c.id);
          } else {
            selectConversation(c.id);
          }
        });

        DOM.conversationList.appendChild(item);
      });
    }
  });
}

async function selectConversation(id) {
  state.currentConversationId = id;
  renderConversationList(state.conversations);

  try {
    const res = await fetch(`${API_BASE}/api/conversations/${id}`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load conversation messages");
    const detail = await res.json();
    DOM.currentChatTitle.textContent = detail.title;
    DOM.messagesStream.innerHTML = "";
    DOM.welcomeHero.classList.add("hidden");

    detail.messages.forEach(msg => {
      renderMessage(msg.role, msg.original_content, {
        normalized_query: msg.normalized_content,
        answer: msg.answer,
        source_type: msg.source_type,
        confidence: msg.confidence,
        citations: msg.citations,
        ambiguity_flags: msg.ambiguity_flags
      });
    });
    scrollChatToBottom();
  } catch (err) {
    console.error(err);
  }
}

async function renameConversationPrompt(id, oldTitle) {
  const newTitle = prompt("Rename conversation title:", oldTitle);
  if (newTitle && newTitle.trim() && newTitle !== oldTitle) {
    try {
      const res = await fetch(`${API_BASE}/api/conversations/${id}`, {
        method: "PUT",
        headers: { ...getAuthHeader(), "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle.trim() })
      });
      if (res.ok) {
        if (state.currentConversationId === id) DOM.currentChatTitle.textContent = newTitle.trim();
        await loadConversations();
      }
    } catch (err) {
      console.error(err);
    }
  }
}

async function deleteConversationPrompt(id) {
  if (confirm("Are you sure you want to delete this conversation?")) {
    try {
      const res = await fetch(`${API_BASE}/api/conversations/${id}`, {
        method: "DELETE",
        headers: getAuthHeader()
      });
      if (res.ok) {
        if (state.currentConversationId === id) {
          state.currentConversationId = null;
          DOM.messagesStream.innerHTML = "";
          DOM.messagesStream.appendChild(DOM.welcomeHero);
          DOM.welcomeHero.classList.remove("hidden");
          DOM.currentChatTitle.textContent = "New Conversation";
        }
        await loadConversations();
      }
    } catch (err) {
      console.error(err);
    }
  }
}

// ==================== CHAT PIPELINE & MESSAGES ====================

function renderMessage(role, content, meta = {}) {
  DOM.welcomeHero.classList.add("hidden");
  const isUser = role === "user";
  const row = document.createElement("div");
  row.className = `message-row ${isUser ? "user-row" : "assistant-row"}`;

  const avatarHtml = isUser
    ? `<div class="message-avatar"><i class="fa-solid fa-user"></i></div>`
    : `<div class="message-avatar"><i class="fa-solid fa-building-columns"></i></div>`;

  let innerContentHtml = "";

  if (isUser) {
    innerContentHtml = `<div class="message-content">${escapeHtml(content)}</div>`;
  } else {
    // Assistant message with Source Badge, Markdown rendering, Citations, OCR Ambiguities, Actions
    const rawAnswer = meta.answer || content;
    const renderedText = marked.parse(rawAnswer);

    // Source Badge class & icon
    let badgeClass = "badge-kb";
    let badgeText = "Knowledge Base";
    let badgeIcon = "fa-book-bookmark";

    if (meta.source_type === "DATABASE") {
      badgeClass = "badge-db";
      badgeText = "Conversation Database";
      badgeIcon = "fa-database";
    } else if (meta.source_type === "DATABASE_AND_KNOWLEDGE_BASE") {
      badgeClass = "badge-hybrid";
      badgeText = "DB + Knowledge Base";
      badgeIcon = "fa-network-wired";
    } else if (meta.source_type === "NO_SUPPORTED_SOURCE") {
      badgeClass = "badge-nosource";
      badgeText = "No Verified Source";
      badgeIcon = "fa-circle-exclamation";
    }

    const badgeHtml = `<div class="source-badge ${badgeClass}"><i class="fa-solid ${badgeIcon}"></i> ${badgeText}</div>`;

    // Normalized Query Tag if available
    let normTagHtml = "";
    if (meta.normalized_query && meta.normalized_query !== content) {
      normTagHtml = `<div class="normalized-query-tag"><i class="fa-solid fa-wand-magic-sparkles"></i> Interpreted Query: "${escapeHtml(meta.normalized_query)}"</div>`;
    }

    // Citations Accordion
    let citationsHtml = "";
    if (meta.citations && meta.citations.length > 0) {
      const citeCards = meta.citations.map(c => `
        <div class="citation-card">
          <div class="citation-header">
            <span class="citation-title">${escapeHtml(c.document_title)} ${c.notification_number ? `(${escapeHtml(c.notification_number)})` : ''}</span>
            <span class="citation-page">Page ${c.page_number || 1} • Conf: ${(c.score * 100).toFixed(0)}%</span>
          </div>
          <div class="citation-snippet">"${escapeHtml(c.snippet)}"</div>
        </div>
      `).join("");

      citationsHtml = `
        <div class="citations-wrapper">
          <button class="citations-toggle-btn" onclick="this.nextElementSibling.classList.toggle('hidden')">
            <i class="fa-solid fa-chevron-down"></i> View ${meta.citations.length} Verified Source Citation(s)
          </button>
          <div class="citations-list hidden">
            ${citeCards}
          </div>
        </div>
      `;
    }

    // OCR Ambiguity Alert
    let ambiguityHtml = "";
    if (meta.ambiguity_flags && meta.ambiguity_flags.length > 0) {
      const flagsText = meta.ambiguity_flags.map(f => `${f.character_pair} in '${f.context_term}'`).join("; ");
      ambiguityHtml = `
        <div class="ocr-ambiguity-alert">
          <i class="fa-solid fa-triangle-exclamation"></i>
          <div>
            <strong>Banking Character Ambiguity Warning:</strong>
            <div>${escapeHtml(flagsText)}. Please verify with physical original document.</div>
          </div>
        </div>
      `;
    }

    // Actions Bar (Read Aloud, Copy)
    const actionsHtml = `
      <div class="message-actions">
        <button class="action-icon-btn btn-read-aloud" title="Read Aloud (TTS)">
          <i class="fa-solid fa-volume-high"></i> Read
        </button>
        <button class="action-icon-btn btn-copy-msg" title="Copy Response">
          <i class="fa-solid fa-copy"></i> Copy
        </button>
      </div>
    `;

    innerContentHtml = `
      ${normTagHtml}
      ${badgeHtml}
      <div class="message-content">
        ${renderedText}
        ${ambiguityHtml}
        ${citationsHtml}
      </div>
      ${actionsHtml}
    `;
  }

  row.innerHTML = `
    ${avatarHtml}
    <div class="message-body-wrapper">
      ${innerContentHtml}
    </div>
  `;

  // Attach event handlers for message actions
  if (!isUser) {
    const copyBtn = row.querySelector(".btn-copy-msg");
    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(meta.answer || content);
        copyBtn.innerHTML = `<i class="fa-solid fa-check"></i> Copied`;
        setTimeout(() => { copyBtn.innerHTML = `<i class="fa-solid fa-copy"></i> Copy`; }, 2000);
      });
    }

    const ttsBtn = row.querySelector(".btn-read-aloud");
    if (ttsBtn) {
      ttsBtn.addEventListener("click", () => {
        speakText(meta.answer || content);
      });
    }
  }

  DOM.messagesStream.appendChild(row);
  scrollChatToBottom();
}

async function sendChatMessage(queryText) {
  const query = (queryText || DOM.chatTextarea.value).trim();
  if (!query) return;

  // Render User Message in stream
  renderMessage("user", query);
  DOM.chatTextarea.value = "";
  DOM.chatTextarea.style.height = "auto";
  DOM.btnSend.disabled = true;

  // Render Loading Placeholder
  const loadingRow = document.createElement("div");
  loadingRow.className = "message-row assistant-row";
  loadingRow.id = "assistant-loading-indicator";
  loadingRow.innerHTML = `
    <div class="message-avatar"><i class="fa-solid fa-building-columns"></i></div>
    <div class="message-body-wrapper">
      <div class="message-content" style="color:var(--text-muted);font-style:italic;">
        <i class="fa-solid fa-circle-notch fa-spin"></i> Retrieving verified banking sources & validating answer...
      </div>
    </div>
  `;
  DOM.messagesStream.appendChild(loadingRow);
  scrollChatToBottom();

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { ...getAuthHeader(), "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: state.currentConversationId,
        query: query
      })
    });

    // Remove loading placeholder
    const loader = document.getElementById("assistant-loading-indicator");
    if (loader) loader.remove();

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Error querying knowledge base");
    }

    const data = await res.json();
    state.currentConversationId = data.conversation_id;
    DOM.currentChatTitle.textContent = data.conversation_title;

    renderMessage("assistant", data.answer, {
      normalized_query: data.normalized_query,
      answer: data.answer,
      source_type: data.source_type,
      confidence: data.confidence,
      citations: data.citations,
      ambiguity_flags: data.ambiguity_flags
    });

    if (state.autoTts) {
      speakText(data.answer);
    }

    await loadConversations();
  } catch (err) {
    const loader = document.getElementById("assistant-loading-indicator");
    if (loader) loader.remove();

    renderMessage("assistant", "Something went wrong while processing the request. Please try again.", {
      source_type: "NO_SUPPORTED_SOURCE"
    });
  } finally {
    DOM.btnSend.disabled = false;
  }
}

function scrollChatToBottom() {
  DOM.messagesStream.scrollTop = DOM.messagesStream.scrollHeight;
}

// ==================== SPEECH-TO-TEXT & TEXT-TO-SPEECH ====================

function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.warn("Speech Recognition API not supported in this browser.");
    return;
  }

  state.speechRecognition = new SpeechRecognition();
  state.speechRecognition.continuous = false;
  state.speechRecognition.interimResults = true;
  state.speechRecognition.lang = "en-IN";

  state.speechRecognition.onstart = () => {
    state.isRecordingSpeech = true;
    DOM.btnMic.classList.add("recording");
    DOM.speechReviewBar.classList.remove("hidden");
    DOM.speechTranscriptInput.value = "";
  };

  state.speechRecognition.onresult = (event) => {
    let transcript = "";
    for (let i = 0; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    DOM.speechTranscriptInput.value = transcript;
  };

  state.speechRecognition.onend = () => {
    state.isRecordingSpeech = false;
    DOM.btnMic.classList.remove("recording");
    if (!state.sttReview && DOM.speechTranscriptInput.value.trim()) {
      DOM.chatTextarea.value = DOM.speechTranscriptInput.value;
      DOM.speechReviewBar.classList.add("hidden");
      sendChatMessage();
    }
  };

  state.speechRecognition.onerror = (err) => {
    console.error("Speech recognition error:", err);
    state.isRecordingSpeech = false;
    DOM.btnMic.classList.remove("recording");
  };
}

function toggleSpeechRecognition() {
  if (!state.speechRecognition) {
    initSpeechRecognition();
  }
  if (!state.speechRecognition) {
    alert("Speech recognition is not supported in your browser.");
    return;
  }

  if (state.isRecordingSpeech) {
    state.speechRecognition.stop();
  } else {
    state.speechRecognition.start();
  }
}

function speakText(text) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel(); // stop previous speech

  // Strip markdown formatting and citations before speaking
  const clean = text
    .replace(/[#*_`~\[\]\(\)]/g, "")
    .replace(/According to the approved.*?document/i, "")
    .replace(/Notification:.*?\n/i, "")
    .trim();

  const utterance = new SpeechSynthesisUtterance(clean);
  utterance.rate = state.ttsRate;
  utterance.pitch = 1.0;
  window.speechSynthesis.speak(utterance);
}

// ==================== ADMIN KNOWLEDGE BASE ====================

async function loadAdminDocuments() {
  try {
    const res = await fetch(`${API_BASE}/api/admin/documents`, { headers: getAuthHeader() });
    if (!res.ok) throw new Error("Failed to load documents");
    const docs = await res.json();
    DOM.kbDocCount.textContent = docs.length;
    renderAdminDocumentsTable(docs);
  } catch (err) {
    console.error(err);
  }
}

function renderAdminDocumentsTable(docs) {
  DOM.kbDocumentsTbody.innerHTML = "";
  if (docs.length === 0) {
    DOM.kbDocumentsTbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:16px;">No documents in knowledge base.</td></tr>`;
    return;
  }

  docs.forEach(d => {
    const tr = document.createElement("tr");
    const ocrBadge = d.is_ocr
      ? `<span class="badge badge-warning" style="color:var(--accent-amber);"><i class="fa-solid fa-eye"></i> OCR (${(d.ocr_confidence*100).toFixed(0)}%)</span>`
      : `<span class="badge" style="color:var(--accent-green);"><i class="fa-solid fa-file-lines"></i> Native</span>`;

    const ambInfo = d.ocr_ambiguity_notes
      ? `<span style="color:var(--accent-amber);font-size:11px;" title="${escapeHtml(d.ocr_ambiguity_notes)}"><i class="fa-solid fa-triangle-exclamation"></i> Ambiguity Flagged</span>`
      : `<span style="color:var(--text-muted);font-size:11px;">Clean</span>`;

    tr.innerHTML = `
      <td><strong>${escapeHtml(d.title)}</strong><br><span style="font-size:10px;color:var(--text-muted);">${escapeHtml(d.source)}</span></td>
      <td><code>${escapeHtml(d.notification_number || 'N/A')}</code></td>
      <td>${escapeHtml(d.document_type.toUpperCase())}</td>
      <td>${d.page_count}</td>
      <td>${d.chunk_count}</td>
      <td>${ocrBadge}<br>${ambInfo}</td>
      <td>
        <button class="btn btn-danger btn-sm btn-delete-doc" data-id="${d.id}" title="Delete"><i class="fa-solid fa-trash"></i></button>
      </td>
    `;

    tr.querySelector(".btn-delete-doc").addEventListener("click", () => deleteDocument(d.id));
    DOM.kbDocumentsTbody.appendChild(tr);
  });
}

async function uploadDocument() {
  if (!state.selectedUploadFile) return;

  const formData = new FormData();
  formData.append("file", state.selectedUploadFile);
  if (DOM.docTitleInput.value.trim()) formData.append("title", DOM.docTitleInput.value.trim());
  if (DOM.docNotifInput.value.trim()) formData.append("notification_number", DOM.docNotifInput.value.trim());
  formData.append("source", DOM.docSourceSelect.value);
  if (DOM.docPubdateInput.value) formData.append("publication_date", DOM.docPubdateInput.value);

  DOM.btnSubmitUpload.disabled = true;
  DOM.btnSubmitUpload.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Ingesting...`;

  try {
    const res = await fetch(`${API_BASE}/api/admin/documents/upload`, {
      method: "POST",
      headers: getAuthHeader(),
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload failed");
    }
    alert("Document processed, OCR evaluated, and ingested successfully!");
    DOM.kbUploadForm.reset();
    DOM.kbUploadForm.classList.add("hidden");
    state.selectedUploadFile = null;
    await loadAdminDocuments();
  } catch (err) {
    alert(err.message);
  } finally {
    DOM.btnSubmitUpload.disabled = false;
    DOM.btnSubmitUpload.innerHTML = `Process & Ingest Document`;
  }
}

async function deleteDocument(docId) {
  if (confirm("Delete this document and rebuild vector indexes?")) {
    try {
      const res = await fetch(`${API_BASE}/api/admin/documents/${docId}`, {
        method: "DELETE",
        headers: getAuthHeader()
      });
      if (res.ok) {
        await loadAdminDocuments();
      }
    } catch (err) {
      console.error(err);
    }
  }
}

async function triggerReindex() {
  try {
    DOM.btnReindexAll.disabled = true;
    DOM.btnReindexAll.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Re-indexing...`;
    const res = await fetch(`${API_BASE}/api/admin/reindex`, {
      method: "POST",
      headers: getAuthHeader()
    });
    if (res.ok) {
      const data = await res.json();
      alert(data.message);
    }
  } catch (err) {
    alert("Re-indexing failed: " + err);
  } finally {
    DOM.btnReindexAll.disabled = false;
    DOM.btnReindexAll.innerHTML = `<i class="fa-solid fa-arrows-rotate"></i> Re-index All`;
  }
}

// ==================== MODALS & HELPERS ====================

function closeAllModals() {
  document.querySelectorAll(".modal-overlay").forEach(m => m.classList.add("hidden"));
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// ==================== INITIALIZATION & EVENT LISTENERS ====================

function initEventListeners() {
  // Sidebar Collapse
  DOM.btnSidebarCollapse.addEventListener("click", () => DOM.sidebar.classList.toggle("collapsed"));
  DOM.btnMobileSidebar.addEventListener("click", () => DOM.sidebar.classList.toggle("collapsed"));

  // New Chat
  DOM.btnNewChat.addEventListener("click", () => {
    state.currentConversationId = null;
    DOM.messagesStream.innerHTML = "";
    DOM.messagesStream.appendChild(DOM.welcomeHero);
    DOM.welcomeHero.classList.remove("hidden");
    DOM.currentChatTitle.textContent = "New Conversation";
    renderConversationList(state.conversations);
  });

  // Conversation Search
  let searchTimer;
  DOM.conversationSearch.addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      const q = e.target.value.trim();
      loadConversations(q.length > 0 ? q : null);
    }, 250);
  });

  // Prompt Cards click
  document.querySelectorAll(".prompt-card").forEach(card => {
    card.addEventListener("click", () => {
      const text = card.dataset.prompt;
      DOM.chatTextarea.value = text;
      sendChatMessage(text);
    });
  });

  // Chat Form Submit & Keydown
  DOM.chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    sendChatMessage();
  });

  DOM.chatTextarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });

  // Auto-resize textarea
  DOM.chatTextarea.addEventListener("input", () => {
    DOM.chatTextarea.style.height = "auto";
    DOM.chatTextarea.style.height = Math.min(DOM.chatTextarea.scrollHeight, 160) + "px";
  });

  // Mic Button
  DOM.btnMic.addEventListener("click", toggleSpeechRecognition);

  // Speech Review Bar Actions
  DOM.btnConfirmSpeech.addEventListener("click", () => {
    const text = DOM.speechTranscriptInput.value.trim();
    if (text) {
      DOM.chatTextarea.value = text;
      DOM.speechReviewBar.classList.add("hidden");
      sendChatMessage(text);
    }
  });

  DOM.btnCancelSpeech.addEventListener("click", () => {
    DOM.speechReviewBar.classList.add("hidden");
  });

  // Theme Toggle
  DOM.btnThemeToggle.addEventListener("click", () => {
    document.body.classList.toggle("light-theme");
    const isLight = document.body.classList.contains("light-theme");
    DOM.btnThemeToggle.innerHTML = isLight ? `<i class="fa-solid fa-moon"></i>` : `<i class="fa-solid fa-sun"></i>`;
  });

  // Auth Modal & Trigger
  DOM.btnAuthTrigger.addEventListener("click", () => {
    const active = getActiveAccount();
    if (active) {
      DOM.accountDrawer.classList.remove("hidden");
    } else {
      DOM.authModal.classList.remove("hidden");
    }
  });

  DOM.userProfileWidget.addEventListener("click", () => {
    DOM.accountDrawer.classList.remove("hidden");
  });

  DOM.btnAuthToggleMode.addEventListener("click", () => {
    state.isAuthModeRegister = !state.isAuthModeRegister;
    DOM.authNameGroup.classList.toggle("hidden", !state.isAuthModeRegister);
    DOM.authModalTitle.innerHTML = state.isAuthModeRegister
      ? `Create Account on CHATGPT<span class="brand-accent">xIDFC</span>`
      : `Sign in to CHATGPT<span class="brand-accent">xIDFC</span>`;
    DOM.btnAuthSubmit.textContent = state.isAuthModeRegister ? "Register" : "Sign In";
    DOM.authTogglePrompt.textContent = state.isAuthModeRegister ? "Already have an account?" : "Don't have an account?";
    DOM.btnAuthToggleMode.textContent = state.isAuthModeRegister ? "Sign In" : "Register";
  });

  DOM.authForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const email = DOM.authEmailInput.value.trim();
    const password = DOM.authPasswordInput.value;
    if (state.isAuthModeRegister) {
      const name = DOM.authNameInput.value.trim() || email.split("@")[0];
      registerUser(name, email, password);
    } else {
      loginUser(email, password);
    }
  });

  DOM.btnGoogleLogin.addEventListener("click", () => googleLogin());

  // Account Drawer Actions
  DOM.btnAddAccount.addEventListener("click", () => {
    DOM.accountDrawer.classList.add("hidden");
    state.isAuthModeRegister = false;
    DOM.authNameGroup.classList.add("hidden");
    DOM.authModal.classList.remove("hidden");
  });

  DOM.btnLogoutCurrent.addEventListener("click", logoutCurrentAccount);

  // Admin KB Actions
  DOM.btnOpenAdminKb.addEventListener("click", () => {
    DOM.adminKbModal.classList.remove("hidden");
    loadAdminDocuments();
  });

  DOM.btnReindexAll.addEventListener("click", triggerReindex);

  // File Upload Handlers
  DOM.btnBrowseFile.addEventListener("click", () => DOM.kbFileInput.click());
  DOM.uploadDropzone.addEventListener("click", () => DOM.kbFileInput.click());

  DOM.kbFileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
      state.selectedUploadFile = file;
      DOM.docTitleInput.value = file.name.replace("_", " ").rsplit ? file.name : file.name;
      DOM.kbUploadForm.classList.remove("hidden");
    }
  });

  DOM.kbUploadForm.addEventListener("submit", (e) => {
    e.preventDefault();
    uploadDocument();
  });

  DOM.btnCancelUpload.addEventListener("click", () => {
    DOM.kbUploadForm.reset();
    DOM.kbUploadForm.classList.add("hidden");
    state.selectedUploadFile = null;
  });

  // Settings Modal
  DOM.btnOpenSettings.addEventListener("click", () => DOM.settingsModal.classList.remove("hidden"));
  DOM.settingSttReview.addEventListener("change", (e) => state.sttReview = e.target.checked);
  DOM.settingAutoTts.addEventListener("change", (e) => state.autoTts = e.target.checked);
  DOM.settingTtsRate.addEventListener("input", (e) => state.ttsRate = parseFloat(e.target.value));

  // Modal Close Buttons
  document.querySelectorAll(".modal-close-btn").forEach(btn => {
    btn.addEventListener("click", () => closeAllModals());
  });

  document.querySelectorAll(".modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeAllModals();
    });
  });
}

// Initial Boot
window.addEventListener("DOMContentLoaded", async () => {
  loadAccountsFromStorage();
  
  // If no saved accounts, seed a default demo account in client state
  if (state.accounts.length === 0) {
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "customer@idfcbank.com", password: "Customer@123" })
      });
      if (res.ok) {
        const data = await res.json();
        addAccount({
          id: data.user.id,
          name: data.user.name,
          email: data.user.email,
          role: data.user.role,
          token: data.access_token
        });
      }
    } catch (e) {
      console.log("Default client login init:", e);
    }
  }

  updateUIForAuth();
  initEventListeners();
  initSpeechRecognition();
  await loadConversations();
});
