/**
 * CHATGPTxIDFC — Frontend Application Logic
 * Ultra-Premium Real-Life ChatGPT 4o Experience with Two-Layer Banking RAG
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

// Curated Prompts by Category
const PROMPTS_BY_CATEGORY = {
  all: [
    { title: "RBI KYC & OVD Rules", sub: "Officially valid documents and V-CIP requirements", prompt: "What are the latest RBI KYC requirements and Officially Valid Documents (OVD)?" },
    { title: "NEFT 24x7 Settlement", sub: "Operating hours, 48 batches, and limit rules", prompt: "What is NEFT and what are its operating hours and transaction limits?" },
    { title: "Digital Lending 2022", sub: "Cooling-off look-up period & KFS disclosures", prompt: "What are the cooling-off period and KFS rules under RBI Digital Lending Directions 2022?" },
    { title: "Housing Loan LTV Caps", sub: "Max 90% up to ₹30L, 80% up to ₹75L limits", prompt: "What are the Loan-to-Value (LTV) ratio caps for housing loans under RBI regulations?" }
  ],
  rbi: [
    { title: "KYC Master Direction 2016", sub: "Periodic KYC updates & non-face-to-face onboarding", prompt: "Explain the RBI Master Direction on KYC 2016 periodic update requirements." },
    { title: "Digital Lending KFS Policy", sub: "Key Fact Statement APR disclosures & recovery agent rules", prompt: "What are the rules regarding Key Fact Statement (KFS) under Digital Lending Guidelines?" },
    { title: "Customer Protection (Fraud)", sub: "Zero liability for third-party fraud notified in 3 days", prompt: "What is customer liability in unauthorized electronic banking transactions?" },
    { title: "Fair Practices Code (FPC)", sub: "Loan sanction terms & transparent penal charges", prompt: "What are the key directives in RBI Master Direction on Fair Practices Code?" }
  ],
  payments: [
    { title: "NEFT Operating Timings", sub: "Round the clock 24x7x365 batch settlement process", prompt: "What is NEFT and what are its operating hours and transaction limits?" },
    { title: "RTGS vs NEFT Rules", sub: "Gross settlement min ₹2,00,000 threshold comparison", prompt: "What is RTGS and how does its minimum limit compare with NEFT?" },
    { title: "Failed Transaction TAT (T+1)", sub: "Auto-reversal timeline and ₹100/day compensation", prompt: "What is the RBI mandated compensation for failed ATM and electronic transactions?" },
    { title: "Card-on-File Tokenization", sub: "RBI guidelines on replacing actual card numbers with tokens", prompt: "What are the RBI regulations regarding Card-on-File Tokenization (CoFT)?" }
  ],
  lending: [
    { title: "Housing Loan LTV Ratios", sub: "Prudential limits for individual residential housing loans", prompt: "What are the Loan-to-Value (LTV) ratio caps for housing loans under RBI regulations?" },
    { title: "IDFC Savings Account", sub: "Monthly interest credit compounding & zero charges", prompt: "What are the key benefits of IDFC FIRST Bank Savings Account monthly interest credit?" },
    { title: "V-CIP Video KYC Process", sub: "Live video verification, geo-tagging & Aadhaar XML", prompt: "Explain the step-by-step V-CIP process for opening an account digitally." },
    { title: "Penal Charges Directives", sub: "Reasonable penal charges vs penal interest compounding", prompt: "What are the latest RBI guidelines on Fair Lending Practice regarding penal charges?" }
  ]
};

// DOM Elements
const DOM = {
  sidebar: document.getElementById("sidebar"),
  btnSidebarCollapse: document.getElementById("btn-sidebar-collapse"),
  btnSidebarExpand: document.getElementById("btn-sidebar-expand"),
  btnMobileSidebar: document.getElementById("btn-mobile-sidebar"),
  btnNewChat: document.getElementById("btn-new-chat"),
  conversationSearch: document.getElementById("conversation-search"),
  conversationList: document.getElementById("conversation-list"),
  messagesStream: document.getElementById("messages-stream"),
  welcomeHero: document.getElementById("welcome-hero"),
  btnModelSelector: document.getElementById("btn-model-selector"),
  modelDropdownMenu: document.getElementById("model-dropdown-menu"),
  btnExploreKb: document.getElementById("btn-explore-kb"),
  chatForm: document.getElementById("chat-form"),
  chatTextarea: document.getElementById("chat-textarea"),
  btnSend: document.getElementById("btn-send"),
  btnMic: document.getElementById("btn-mic"),
  btnAttachFile: document.getElementById("btn-attach-file"),
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
  userAvatarPlaceholder: document.getElementById("user-avatar-placeholder"),
  adminKbBtnContainer: document.getElementById("admin-kb-btn-container"),
  btnOpenAdminKb: document.getElementById("btn-open-admin-kb"),
  toastContainer: document.getElementById("toast-container"),
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
  btnQuickCustomer: document.getElementById("btn-quick-customer"),
  btnQuickAdmin: document.getElementById("btn-quick-admin"),
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

// ==================== TOAST NOTIFICATIONS ====================
function showToast(msg) {
  if (!DOM.toastContainer) return;
  const toast = document.createElement("div");
  toast.className = "toast-msg";
  toast.textContent = msg;
  DOM.toastContainer.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

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

async function validateOrRefreshToken() {
  const account = getActiveAccount();
  if (account && account.token) {
    try {
      const checkRes = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { "Authorization": `Bearer ${account.token}` }
      });
      if (checkRes.ok) {
        return account.token;
      }
    } catch (e) {
      console.log("Token validation check error:", e);
    }
  }

  // Token is missing, expired, or invalid. Auto-login default customer user.
  try {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "customer@idfcbank.com", password: "Customer@123" })
    });
    if (res.ok) {
      const data = await res.json();
      const newAcc = {
        id: data.user.id,
        name: data.user.name,
        email: data.user.email,
        role: data.user.role,
        token: data.access_token
      };
      addAccount(newAcc);
      return data.access_token;
    }
  } catch (err) {
    console.error("Auto session recover failed:", err);
  }
  return null;
}

async function authenticatedFetch(url, options = {}) {
  let headers = { ...(options.headers || {}), ...getAuthHeader() };
  let res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    const newToken = await validateOrRefreshToken();
    if (newToken) {
      headers = { ...(options.headers || {}), "Authorization": `Bearer ${newToken}` };
      res = await fetch(url, { ...options, headers });
    }
  }
  return res;
}

function updateUIForAuth() {
  const account = getActiveAccount();
  if (account) {
    DOM.userDisplayName.textContent = account.name;
    DOM.authBtnLabel.textContent = account.name.split(" ")[0];
    DOM.userAvatarPlaceholder.innerHTML = `<span>${escapeHtml(account.name.charAt(0).toUpperCase())}</span>`;
    
    // Check admin role
    if (account.role === "admin") {
      DOM.adminKbBtnContainer.classList.remove("hidden");
    } else {
      DOM.adminKbBtnContainer.classList.add("hidden");
    }
  } else {
    DOM.userDisplayName.textContent = "Guest User";
    DOM.authBtnLabel.textContent = "Log in";
    DOM.userAvatarPlaceholder.innerHTML = `<span>G</span>`;
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
    showToast(`Signed in as ${data.user.name}`);
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
    showToast(`Registered successfully!`);
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
    showToast(`Google authenticated as ${data.user.name}`);
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
    closeAllModals();
    showToast(`Switched account to ${state.accounts[index].name}`);
  }
}

function logoutCurrentAccount() {
  if (state.accounts.length > 0) {
    const name = state.accounts[state.activeAccountIndex].name;
    state.accounts.splice(state.activeAccountIndex, 1);
    state.activeAccountIndex = 0;
    state.currentConversationId = null;
    saveAccountsToStorage();
    updateUIForAuth();
    loadConversations();
    DOM.messagesStream.innerHTML = "";
    DOM.messagesStream.appendChild(DOM.welcomeHero);
    DOM.welcomeHero.classList.remove("hidden");
    closeAllModals();
    showToast(`Logged out ${name}`);
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
        <div class="user-avatar" style="width:28px;height:28px;font-size:11px;">
          <span>${escapeHtml(acc.name.charAt(0).toUpperCase())}</span>
        </div>
        <div>
          <strong style="font-size:13px;">${escapeHtml(acc.name)}</strong>
          <span style="display:block;font-size:11px;color:var(--text-muted);">${escapeHtml(acc.email)}</span>
        </div>
      </div>
      <div>
        ${isActive ? '<span class="badge-active">Active</span>' : '<button class="btn btn-chatgpt-ghost btn-sm">Switch</button>'}
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
    DOM.conversationList.innerHTML = `<div class="list-skeleton">Sign in to see conversation history.</div>`;
    return;
  }

  try {
    const url = searchQuery
      ? `${API_BASE}/api/conversations/search?q=${encodeURIComponent(searchQuery)}`
      : `${API_BASE}/api/conversations`;

    const res = await authenticatedFetch(url);
    if (!res.ok) throw new Error("Failed to load conversations");
    state.conversations = await res.json();
    renderConversationList(state.conversations);
  } catch (err) {
    console.error(err);
    DOM.conversationList.innerHTML = `<div class="list-skeleton">No conversations yet.</div>`;
  }
}

function renderConversationList(convs) {
  DOM.conversationList.innerHTML = "";
  if (convs.length === 0) {
    DOM.conversationList.innerHTML = `<div class="list-skeleton">No conversations yet.</div>`;
    return;
  }

  // Group by Today, Yesterday, Previous 7 Days, Previous 30 Days
  const now = new Date();
  const groups = {
    "Today": [],
    "Yesterday": [],
    "Previous 7 Days": [],
    "Previous 30 Days": []
  };

  convs.forEach(c => {
    const updated = new Date(c.updated_at);
    const diffDays = Math.floor((now - updated) / (1000 * 60 * 60 * 24));
    if (diffDays === 0) groups["Today"].push(c);
    else if (diffDays === 1) groups["Yesterday"].push(c);
    else if (diffDays <= 7) groups["Previous 7 Days"].push(c);
    else groups["Previous 30 Days"].push(c);
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
    const res = await authenticatedFetch(`${API_BASE}/api/conversations/${id}`);
    if (!res.ok) throw new Error("Failed to load conversation messages");
    const detail = await res.json();
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
  const newTitle = prompt("Rename chat title:", oldTitle);
  if (newTitle && newTitle.trim() && newTitle !== oldTitle) {
    try {
      const res = await authenticatedFetch(`${API_BASE}/api/conversations/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle.trim() })
      });
      if (res.ok) {
        showToast("Chat renamed");
        await loadConversations();
      }
    } catch (err) {
      console.error(err);
    }
  }
}

async function deleteConversationPrompt(id) {
  if (confirm("Delete this conversation?")) {
    try {
      const res = await authenticatedFetch(`${API_BASE}/api/conversations/${id}`, {
        method: "DELETE"
      });
      if (res.ok) {
        showToast("Chat deleted");
        if (state.currentConversationId === id) {
          state.currentConversationId = null;
          DOM.messagesStream.innerHTML = "";
          DOM.messagesStream.appendChild(DOM.welcomeHero);
          DOM.welcomeHero.classList.remove("hidden");
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
    ? ""
    : `<div class="message-avatar">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1683a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4947zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1683a.0757.0757 0 0 1-.071 0l-4.8303-2.7866A4.4992 4.4992 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.6667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1635a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z"/>
        </svg>
      </div>`;

  let innerContentHtml = "";

  if (isUser) {
    innerContentHtml = `<div class="message-content">${escapeHtml(content)}</div>`;
  } else {
    // Assistant message
    const rawAnswer = meta.answer || content;
    const renderedText = marked.parse(rawAnswer);

    // Source Badge
    let badgeClass = "badge-kb";
    let badgeText = "Knowledge Base";
    let badgeIcon = "fa-book-bookmark";

    if (meta.source_type === "DATABASE") {
      badgeClass = "badge-db";
      badgeText = "Conversation DB";
      badgeIcon = "fa-database";
    } else if (meta.source_type === "DATABASE_AND_KNOWLEDGE_BASE") {
      badgeClass = "badge-hybrid";
      badgeText = "DB + Knowledge Base";
      badgeIcon = "fa-network-wired";
    } else if (meta.source_type === "CONVERSATIONAL") {
      badgeClass = "badge-chat";
      badgeText = "Conversational";
      badgeIcon = "fa-comments";
    } else if (meta.source_type === "NO_SUPPORTED_SOURCE") {
      badgeClass = "badge-nosource";
      badgeText = "No Verified Source";
      badgeIcon = "fa-circle-exclamation";
    }

    // Do not show distracting badges for pure conversational greetings
    const badgeHtml = meta.source_type === "CONVERSATIONAL" 
      ? "" 
      : `<div class="source-badge ${badgeClass}"><i class="fa-solid ${badgeIcon}"></i> ${badgeText}</div>`;

    // Normalized Query Tag
    let normTagHtml = "";
    if (meta.normalized_query && meta.normalized_query !== content) {
      normTagHtml = `<div class="normalized-query-tag"><i class="fa-solid fa-wand-magic-sparkles"></i> Interpreted: "${escapeHtml(meta.normalized_query)}"</div>`;
    }

    // Citations Accordion
    let citationsHtml = "";
    if (meta.citations && meta.citations.length > 0) {
      const citeCards = meta.citations.map(c => `
        <div class="citation-card">
          <div class="citation-header">
            <span class="citation-title">${escapeHtml(c.document_title)} ${c.notification_number ? `(${escapeHtml(c.notification_number)})` : ''}</span>
            <span class="citation-page">Page ${c.page_number || 1} • ${(c.score * 100).toFixed(0)}% match</span>
          </div>
          <div class="citation-snippet">"${escapeHtml(c.snippet)}"</div>
        </div>
      `).join("");

      citationsHtml = `
        <div class="citations-wrapper">
          <button class="citations-toggle-btn" type="button">
            <i class="fa-solid fa-chevron-down"></i> ${meta.citations.length} verified source citation(s)
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

    // Actions Toolbar (TTS, Copy, Thumbs)
    const actionsHtml = `
      <div class="message-actions">
        <button class="action-icon-btn btn-read-aloud" title="Read aloud">
          <i class="fa-solid fa-volume-high"></i>
        </button>
        <button class="action-icon-btn btn-copy-msg" title="Copy response">
          <i class="fa-solid fa-copy"></i>
        </button>
        <button class="action-icon-btn btn-thumb-up" title="Good response">
          <i class="fa-regular fa-thumbs-up"></i>
        </button>
        <button class="action-icon-btn btn-thumb-down" title="Bad response">
          <i class="fa-regular fa-thumbs-down"></i>
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

  if (!isUser) {
    const citeToggleBtn = row.querySelector(".citations-toggle-btn");
    if (citeToggleBtn) {
      citeToggleBtn.addEventListener("click", () => {
        const list = citeToggleBtn.nextElementSibling;
        if (list) list.classList.toggle("hidden");
      });
    }

    const copyBtn = row.querySelector(".btn-copy-msg");
    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(meta.answer || content);
        copyBtn.innerHTML = `<i class="fa-solid fa-check"></i>`;
        showToast("Copied to clipboard");
        setTimeout(() => { copyBtn.innerHTML = `<i class="fa-solid fa-copy"></i>`; }, 2000);
      });
    }

    const ttsBtn = row.querySelector(".btn-read-aloud");
    if (ttsBtn) {
      ttsBtn.addEventListener("click", () => {
        speakText(meta.answer || content);
      });
    }

    const thumbUp = row.querySelector(".btn-thumb-up");
    if (thumbUp) {
      thumbUp.addEventListener("click", async () => {
        thumbUp.classList.toggle("active");
        showToast("Feedback recorded");
        if (meta && meta.assistant_message_id) {
          try {
            await fetch(`${API_BASE}/api/chat/feedback`, {
              method: "POST",
              headers: { ...getAuthHeader(), "Content-Type": "application/json" },
              body: JSON.stringify({
                message_id: meta.assistant_message_id,
                rating: 5,
                category: "ACCURACY",
                feedback_text: "Helpful and accurate answer"
              })
            });
          } catch (e) {
            console.log("Feedback submit err:", e);
          }
        }
      });
    }

    const thumbDown = row.querySelector(".btn-thumb-down");
    if (thumbDown) {
      thumbDown.addEventListener("click", async () => {
        thumbDown.classList.toggle("active");
        showToast("Feedback recorded");
        if (meta && meta.assistant_message_id) {
          try {
            await fetch(`${API_BASE}/api/chat/feedback`, {
              method: "POST",
              headers: { ...getAuthHeader(), "Content-Type": "application/json" },
              body: JSON.stringify({
                message_id: meta.assistant_message_id,
                rating: 1,
                category: "ACCURACY",
                feedback_text: "User indicated issue with answer"
              })
            });
          } catch (e) {
            console.log("Feedback submit err:", e);
          }
        }
      });
    }
  }

  DOM.messagesStream.appendChild(row);
  scrollChatToBottom();
}

let activeChatAbortController = null;

async function sendChatMessage(queryText) {
  const query = (queryText || DOM.chatTextarea.value).trim();
  if (!query) return;

  // Cleanly abort any prior in-flight request without error
  if (activeChatAbortController) {
    activeChatAbortController.abort();
  }
  activeChatAbortController = new AbortController();

  // Render User Message in stream
  renderMessage("user", query);
  DOM.chatTextarea.value = "";
  DOM.chatTextarea.style.height = "24px";

  // Toggle Send button to Stop Generation button
  DOM.btnSend.disabled = false;
  DOM.btnSend.innerHTML = `<i class="fa-solid fa-square" style="font-size:12px;"></i>`;
  DOM.btnSend.setAttribute("title", "Stop generation");

  // Render Loading Placeholder
  const loadingRow = document.createElement("div");
  loadingRow.className = "message-row assistant-row";
  loadingRow.id = "assistant-loading-indicator";
  loadingRow.innerHTML = `
    <div class="message-avatar">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
        <path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1683a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4947zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1683a.0757.0757 0 0 1-.071 0l-4.8303-2.7866A4.4992 4.4992 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.6667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1635a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z"/>
      </svg>
    </div>
    <div class="message-body-wrapper">
      <div class="message-content" style="color:var(--text-muted);font-style:italic;">
        <i class="fa-solid fa-circle-notch fa-spin"></i> Searching approved banking directives & grounding answer...
      </div>
    </div>
  `;
  DOM.messagesStream.appendChild(loadingRow);
  scrollChatToBottom();

  try {
    const res = await authenticatedFetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: state.currentConversationId,
        query: query
      }),
      signal: activeChatAbortController.signal
    });

    // Remove loading placeholder
    const loader = document.getElementById("assistant-loading-indicator");
    if (loader) loader.remove();

    if (!res.ok) {
      let errMsg = "Error querying knowledge base";
      try {
        const errJson = await res.json();
        errMsg = errJson.detail || errMsg;
      } catch (_) {}
      throw new Error(errMsg);
    }

    const data = await res.json();
    state.currentConversationId = data.conversation_id;

    renderMessage("assistant", data.answer, {
      normalized_query: data.normalized_query,
      answer: data.answer,
      source_type: data.source_type,
      confidence: data.confidence,
      citations: data.citations,
      ambiguity_flags: data.ambiguity_flags,
      assistant_message_id: data.assistant_message_id
    });

    if (state.autoTts) {
      speakText(data.answer);
    }

    await loadConversations();
  } catch (err) {
    const loader = document.getElementById("assistant-loading-indicator");
    if (loader) loader.remove();

    if (err.name === "AbortError") {
      // User cancelled execution cleanly — do not render error bubble
      return;
    }

    renderMessage("assistant", err.message || "Something went wrong while processing your request. Please try again.", {
      source_type: "NO_SUPPORTED_SOURCE"
    });
  } finally {
    activeChatAbortController = null;
    DOM.btnSend.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 4L12 20M12 4L6 10M12 4L18 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    DOM.btnSend.setAttribute("title", "Send message");
    DOM.btnSend.disabled = !DOM.chatTextarea.value.trim();
  }
}

function scrollChatToBottom() {
  DOM.messagesStream.scrollTop = DOM.messagesStream.scrollHeight;
}

// ==================== PROMPT CATEGORY FILTERING ====================

function renderPromptCards(categoryKey = "all") {
  const grid = document.querySelector(".prompt-grid");
  if (!grid) return;
  const items = PROMPTS_BY_CATEGORY[categoryKey] || PROMPTS_BY_CATEGORY.all;

  grid.innerHTML = items.map(p => `
    <div class="prompt-card" data-prompt="${escapeHtml(p.prompt)}">
      <div class="card-text">
        <div class="card-title">${escapeHtml(p.title)}</div>
        <div class="card-sub">${escapeHtml(p.sub)}</div>
      </div>
      <div class="card-arrow-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M5 12h14M12 5l7 7-7 7"/>
        </svg>
      </div>
    </div>
  `).join("");

  grid.querySelectorAll(".prompt-card").forEach(card => {
    card.addEventListener("click", () => {
      const text = card.dataset.prompt;
      DOM.chatTextarea.value = text;
      DOM.btnSend.disabled = false;
      sendChatMessage(text);
    });
  });
}

// ==================== SPEECH-TO-TEXT & TEXT-TO-SPEECH ====================

function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return;

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

  state.speechRecognition.onerror = () => {
    state.isRecordingSpeech = false;
    DOM.btnMic.classList.remove("recording");
  };
}

function toggleSpeechRecognition() {
  if (!state.speechRecognition) {
    initSpeechRecognition();
  }
  if (!state.speechRecognition) {
    alert("Speech recognition is not supported in this browser.");
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
  window.speechSynthesis.cancel();

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
    const res = await authenticatedFetch(`${API_BASE}/api/admin/documents`);
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
      ? `<span class="badge-active" style="background:rgba(227,160,24,0.15);color:var(--badge-amber);"><i class="fa-solid fa-eye"></i> OCR (${(d.ocr_confidence*100).toFixed(0)}%)</span>`
      : `<span class="badge-active"><i class="fa-solid fa-file-lines"></i> Native</span>`;

    const ambInfo = d.ocr_ambiguity_notes
      ? `<span style="color:var(--badge-amber);font-size:11px;" title="${escapeHtml(d.ocr_ambiguity_notes)}"><i class="fa-solid fa-triangle-exclamation"></i> Flagged</span>`
      : `<span style="color:var(--text-muted);font-size:11px;">Clean</span>`;

    tr.innerHTML = `
      <td><strong>${escapeHtml(d.title)}</strong><br><span style="font-size:10px;color:var(--text-muted);">${escapeHtml(d.source)}</span></td>
      <td><code>${escapeHtml(d.notification_number || 'N/A')}</code></td>
      <td>${escapeHtml(d.document_type.toUpperCase())}</td>
      <td>${d.page_count}</td>
      <td>${d.chunk_count}</td>
      <td>${ocrBadge}<br>${ambInfo}</td>
      <td>
        <button class="btn btn-danger-chatgpt btn-sm btn-delete-doc" data-id="${d.id}" title="Delete"><i class="fa-solid fa-trash"></i></button>
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
    const res = await authenticatedFetch(`${API_BASE}/api/admin/documents/upload`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload failed");
    }
    showToast("Document ingested & OCR processed successfully!");
    DOM.kbUploadForm.reset();
    DOM.kbUploadForm.classList.add("hidden");
    state.selectedUploadFile = null;
    await loadAdminDocuments();
  } catch (err) {
    alert(err.message);
  } finally {
    DOM.btnSubmitUpload.disabled = false;
    DOM.btnSubmitUpload.innerHTML = `Ingest Document`;
  }
}

async function deleteDocument(docId) {
  if (confirm("Delete this document and rebuild vector indexes?")) {
    try {
      const res = await authenticatedFetch(`${API_BASE}/api/admin/documents/${docId}`, {
        method: "DELETE"
      });
      if (res.ok) {
        showToast("Document deleted");
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
    const res = await authenticatedFetch(`${API_BASE}/api/admin/reindex`, {
      method: "POST"
    });
    if (res.ok) {
      const data = await res.json();
      showToast(data.message);
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
  if (DOM.modelDropdownMenu) DOM.modelDropdownMenu.classList.add("hidden");
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// ==================== INITIALIZATION & EVENT LISTENERS ====================

function initEventListeners() {
  // Sidebar Collapse & Expand
  if (DOM.btnSidebarCollapse) {
    DOM.btnSidebarCollapse.addEventListener("click", () => {
      if (DOM.sidebar) DOM.sidebar.classList.add("collapsed");
      if (DOM.btnSidebarExpand) DOM.btnSidebarExpand.classList.remove("hidden");
    });
  }

  if (DOM.btnSidebarExpand) {
    DOM.btnSidebarExpand.addEventListener("click", () => {
      if (DOM.sidebar) DOM.sidebar.classList.remove("collapsed");
      if (DOM.btnSidebarExpand) DOM.btnSidebarExpand.classList.add("hidden");
    });
  }

  if (DOM.btnMobileSidebar) {
    DOM.btnMobileSidebar.addEventListener("click", () => {
      if (DOM.sidebar) DOM.sidebar.classList.toggle("collapsed");
    });
  }

  // Model Selector Dropdown
  if (DOM.btnModelSelector) {
    DOM.btnModelSelector.addEventListener("click", (e) => {
      e.stopPropagation();
      if (DOM.modelDropdownMenu) DOM.modelDropdownMenu.classList.toggle("hidden");
    });
  }

  document.addEventListener("click", (e) => {
    if (DOM.modelDropdownMenu && !DOM.modelDropdownMenu.contains(e.target) && e.target !== DOM.btnModelSelector) {
      DOM.modelDropdownMenu.classList.add("hidden");
    }
  });

  // New Chat
  if (DOM.btnNewChat) {
    DOM.btnNewChat.addEventListener("click", () => {
      if (activeChatAbortController) {
        activeChatAbortController.abort();
        activeChatAbortController = null;
      }
      state.currentConversationId = null;
      if (DOM.messagesStream && DOM.welcomeHero) {
        DOM.messagesStream.innerHTML = "";
        DOM.messagesStream.appendChild(DOM.welcomeHero);
        DOM.welcomeHero.classList.remove("hidden");
      }
      renderConversationList(state.conversations);
    });
  }

  // Explore KB / Directives shortcut
  if (DOM.btnExploreKb) {
    DOM.btnExploreKb.addEventListener("click", () => {
      sendChatMessage("List all approved RBI Master Directions and IDFC FIRST Bank policy circulars in the knowledge base");
    });
  }

  // Suggestion Category Filter Tabs
  document.querySelectorAll(".cat-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".cat-tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      renderPromptCards(tab.dataset.cat);
    });
  });

  // Initial render of prompt cards
  renderPromptCards("all");

  // Conversation Search
  if (DOM.conversationSearch) {
    let searchTimer;
    DOM.conversationSearch.addEventListener("input", (e) => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        const q = e.target.value.trim();
        loadConversations(q.length > 0 ? q : null);
      }, 250);
    });
  }

  // Chat Form Submit & Keydown
  if (DOM.chatForm) {
    DOM.chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      if (activeChatAbortController) {
        activeChatAbortController.abort();
        activeChatAbortController = null;
        return;
      }
      sendChatMessage();
    });
  }

  if (DOM.chatTextarea) {
    DOM.chatTextarea.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
      }
    });

    // Auto-resize textarea & enable send button
    DOM.chatTextarea.addEventListener("input", () => {
      DOM.chatTextarea.style.height = "auto";
      DOM.chatTextarea.style.height = Math.min(DOM.chatTextarea.scrollHeight, 180) + "px";
      if (DOM.btnSend) DOM.btnSend.disabled = !DOM.chatTextarea.value.trim();
    });
  }

  // Attach File Button (opens KB modal for Admin)
  if (DOM.btnAttachFile) {
    DOM.btnAttachFile.addEventListener("click", () => {
      const account = getActiveAccount();
      if (account && account.role === "admin") {
        if (DOM.adminKbModal) DOM.adminKbModal.classList.remove("hidden");
        loadAdminDocuments();
      } else {
        alert("Document ingestion is enabled for Admin accounts. Please sign in with an Admin account or use the Quick Admin Login.");
      }
    });
  }

  // Mic Button
  if (DOM.btnMic) {
    DOM.btnMic.addEventListener("click", toggleSpeechRecognition);
  }

  // Speech Review Bar Actions
  if (DOM.btnConfirmSpeech) {
    DOM.btnConfirmSpeech.addEventListener("click", () => {
      const text = DOM.speechTranscriptInput ? DOM.speechTranscriptInput.value.trim() : "";
      if (text) {
        if (DOM.chatTextarea) DOM.chatTextarea.value = text;
        if (DOM.btnSend) DOM.btnSend.disabled = false;
        if (DOM.speechReviewBar) DOM.speechReviewBar.classList.add("hidden");
        sendChatMessage(text);
      }
    });
  }

  if (DOM.btnCancelSpeech) {
    DOM.btnCancelSpeech.addEventListener("click", () => {
      if (DOM.speechReviewBar) DOM.speechReviewBar.classList.add("hidden");
    });
  }

  // Theme Toggle
  if (DOM.btnThemeToggle) {
    DOM.btnThemeToggle.addEventListener("click", () => {
      document.body.classList.toggle("light-theme");
      const isLight = document.body.classList.contains("light-theme");
      DOM.btnThemeToggle.innerHTML = isLight 
        ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>`
        : `<svg class="sun-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>`;
      showToast(isLight ? "Light theme enabled" : "Dark theme enabled");
    });
  }

  // Auth Modal & Trigger
  if (DOM.btnAuthTrigger) {
    DOM.btnAuthTrigger.addEventListener("click", () => {
      const active = getActiveAccount();
      if (active) {
        if (DOM.accountDrawer) DOM.accountDrawer.classList.remove("hidden");
      } else {
        if (DOM.authModal) DOM.authModal.classList.remove("hidden");
      }
    });
  }

  if (DOM.userProfileWidget) {
    DOM.userProfileWidget.addEventListener("click", () => {
      if (DOM.accountDrawer) DOM.accountDrawer.classList.remove("hidden");
    });
  }

  if (DOM.btnAuthToggleMode) {
    DOM.btnAuthToggleMode.addEventListener("click", () => {
      state.isAuthModeRegister = !state.isAuthModeRegister;
      if (DOM.authNameGroup) DOM.authNameGroup.classList.toggle("hidden", !state.isAuthModeRegister);
      if (DOM.authModalTitle) DOM.authModalTitle.textContent = state.isAuthModeRegister ? "Create your account" : "Welcome back";
      if (DOM.btnAuthSubmit) DOM.btnAuthSubmit.textContent = state.isAuthModeRegister ? "Sign up" : "Continue";
      if (DOM.authTogglePrompt) DOM.authTogglePrompt.textContent = state.isAuthModeRegister ? "Already have an account?" : "Don't have an account?";
      DOM.btnAuthToggleMode.textContent = state.isAuthModeRegister ? "Log in" : "Sign up";
    });
  }

  // Demo Login Buttons
  if (DOM.btnQuickCustomer) {
    DOM.btnQuickCustomer.addEventListener("click", () => {
      loginUser("customer@idfcbank.com", "Customer@123");
    });
  }

  if (DOM.btnQuickAdmin) {
    DOM.btnQuickAdmin.addEventListener("click", () => {
      loginUser("admin@idfcbank.com", "Admin@12345");
    });
  }

  if (DOM.authForm) {
    DOM.authForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const email = DOM.authEmailInput ? DOM.authEmailInput.value.trim() : "";
      const password = DOM.authPasswordInput ? DOM.authPasswordInput.value : "";
      if (state.isAuthModeRegister) {
        const name = (DOM.authNameInput ? DOM.authNameInput.value.trim() : "") || email.split("@")[0];
        registerUser(name, email, password);
      } else {
        loginUser(email, password);
      }
    });
  }

  if (DOM.btnGoogleLogin) {
    DOM.btnGoogleLogin.addEventListener("click", () => googleLogin());
  }

  // Account Drawer Actions
  if (DOM.btnAddAccount) {
    DOM.btnAddAccount.addEventListener("click", () => {
      if (DOM.accountDrawer) DOM.accountDrawer.classList.add("hidden");
      state.isAuthModeRegister = false;
      if (DOM.authNameGroup) DOM.authNameGroup.classList.add("hidden");
      if (DOM.authModal) DOM.authModal.classList.remove("hidden");
    });
  }

  if (DOM.btnLogoutCurrent) {
    DOM.btnLogoutCurrent.addEventListener("click", logoutCurrentAccount);
  }

  // Admin KB Actions
  if (DOM.btnOpenAdminKb) {
    DOM.btnOpenAdminKb.addEventListener("click", () => {
      if (DOM.adminKbModal) DOM.adminKbModal.classList.remove("hidden");
      loadAdminDocuments();
    });
  }

  if (DOM.btnReindexAll) {
    DOM.btnReindexAll.addEventListener("click", triggerReindex);
  }

  // File Upload Handlers
  if (DOM.btnBrowseFile && DOM.kbFileInput) {
    DOM.btnBrowseFile.addEventListener("click", () => DOM.kbFileInput.click());
  }
  if (DOM.uploadDropzone && DOM.kbFileInput) {
    DOM.uploadDropzone.addEventListener("click", () => DOM.kbFileInput.click());
  }

  if (DOM.kbFileInput) {
    DOM.kbFileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) {
        state.selectedUploadFile = file;
        if (DOM.docTitleInput) DOM.docTitleInput.value = file.name.replace(/\.[^/.]+$/, "").replace(/_/g, " ");
        if (DOM.kbUploadForm) DOM.kbUploadForm.classList.remove("hidden");
      }
    });
  }

  if (DOM.kbUploadForm) {
    DOM.kbUploadForm.addEventListener("submit", (e) => {
      e.preventDefault();
      uploadDocument();
    });
  }

  if (DOM.btnCancelUpload) {
    DOM.btnCancelUpload.addEventListener("click", () => {
      if (DOM.kbUploadForm) {
        DOM.kbUploadForm.reset();
        DOM.kbUploadForm.classList.add("hidden");
      }
      state.selectedUploadFile = null;
    });
  }

  // Settings Modal
  if (DOM.btnOpenSettings && DOM.settingsModal) {
    DOM.btnOpenSettings.addEventListener("click", () => DOM.settingsModal.classList.remove("hidden"));
  }
  if (DOM.settingSttReview) {
    DOM.settingSttReview.addEventListener("change", (e) => {
      state.sttReview = e.target.checked;
      showToast("Voice settings updated");
    });
  }
  if (DOM.settingAutoTts) {
    DOM.settingAutoTts.addEventListener("change", (e) => {
      state.autoTts = e.target.checked;
      showToast("Auto Read-Aloud updated");
    });
  }
  if (DOM.settingTtsRate) {
    DOM.settingTtsRate.addEventListener("input", (e) => state.ttsRate = parseFloat(e.target.value));
  }

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

// Initial Boot Orchestrator
async function bootApp() {
  loadAccountsFromStorage();
  await validateOrRefreshToken();
  updateUIForAuth();
  initEventListeners();
  initSpeechRecognition();
  await loadConversations();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootApp);
} else {
  bootApp();
}
