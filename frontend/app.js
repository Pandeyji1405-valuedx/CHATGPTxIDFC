/**
 * CHATGPTxIDFC — Governed Regulatory Knowledge Assistant Logic
 * Ultra-Premium ChatGPT 4o Experience with Multi-Regulator RAG, Visual Passage Viewer & Admin MIS
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
  isLandingAuthModeRegister: false,
  selectedUploadFile: null,
  selectedChatAttachment: null,
  ttsRate: 1.0,
  autoTts: false,
  sttReview: true,
  // Scoped Query Filter State (PRD FR-06)
  activeRegulator: "ALL",
  activeAsOfDate: "",
  activeDepth: "concise"
};

// Curated Prompts by Category
const PROMPTS_BY_CATEGORY = {
  all: [
    { title: "RBI KYC & OVD Rules", sub: "Officially valid documents and V-CIP requirements", prompt: "What are the latest RBI KYC requirements and Officially Valid Documents (OVD)?" },
    { title: "SEBI LODR Disclosures", sub: "30 mins / 12 hrs / 24 hrs material disclosure mandates", prompt: "What are the disclosure timelines for material events under SEBI LODR Regulation 30?" },
    { title: "Digital Lending 2022", sub: "Cooling-off look-up period & KFS disclosures", prompt: "What are the cooling-off period and KFS rules under RBI Digital Lending Directions 2022?" },
    { title: "IRDAI Cyber Security", sub: "6-hour reporting mandate and India data localization", prompt: "What are the IRDAI cyber incident reporting timelines and data localization rules?" }
  ],
  rbi: [
    { title: "KYC Master Direction 2016", sub: "Periodic KYC updates & non-face-to-face onboarding", prompt: "Explain the RBI Master Direction on KYC 2016 periodic update requirements." },
    { title: "Digital Lending KFS Policy", sub: "Key Fact Statement APR disclosures & recovery agent rules", prompt: "What are the rules regarding Key Fact Statement (KFS) under Digital Lending Guidelines?" },
    { title: "Customer Protection (Fraud)", sub: "Zero liability for third-party fraud notified in 3 days", prompt: "What is customer liability in unauthorized electronic banking transactions?" },
    { title: "Fair Practices Code (FPC)", sub: "Loan sanction terms & transparent penal charges", prompt: "What are the key directives in RBI Master Direction on Fair Practices Code?" }
  ],
  sebi: [
    { title: "LODR Material Disclosures", sub: "Timelines for event disclosures under Regulation 30", prompt: "What are the disclosure timelines for material events under SEBI LODR Regulation 30?" },
    { title: "Related Party Transactions", sub: "Thresholds and prior audit committee approval norms", prompt: "What are the approval thresholds for Related Party Transactions under SEBI LODR?" },
    { title: "Intermediaries Cyber Security", sub: "VAPT twice a year and 6-hour CERT-In incident reporting", prompt: "What are the cybersecurity and VAPT mandates for stock brokers under SEBI circular 2023?" },
    { title: "Insider Trading Code", sub: "Pre-clearance and trading window closure requirements", prompt: "What are the key compliance requirements under SEBI Prohibition of Insider Trading regulations?" }
  ],
  irdai: [
    { title: "IRDAI Cyber Guidelines", sub: "CISO appointment and mandatory domestic data localization", prompt: "What are the IRDAI cyber incident reporting timelines and data localization rules?" },
    { title: "Policyholder Protection 2024", sub: "30-day electronic free look period & 30-day complaint resolution", prompt: "What are the grievance resolution timelines and free look period rules under IRDAI 2024 regulations?" },
    { title: "Customer Information Sheet", sub: "Standard CIS disclosure of insurance benefits and exclusions", prompt: "Explain the mandatory Customer Information Sheet (CIS) requirement under IRDAI guidelines." },
    { title: "Outsourcing by Insurers", sub: "Core activities prohibition and confidentiality covenants", prompt: "What are the IRDAI regulations governing outsourcing of activities by insurance companies?" }
  ]
};

// DOM Elements
const DOM = {
  authLandingView: document.getElementById("auth-landing-view"),
  appContainer: document.getElementById("app-container"),
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
  chatAttachmentPreview: document.getElementById("chat-attachment-preview"),
  chatFileInput: document.getElementById("chat-file-input"),
  attachmentIconContainer: document.getElementById("attachment-icon-container"),
  attachmentPillName: document.getElementById("attachment-pill-name"),
  attachmentPillSize: document.getElementById("attachment-pill-size"),
  btnRemoveAttachment: document.getElementById("btn-remove-attachment"),
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
  // Filter Bar
  asOfDateSelect: document.getElementById("as-of-date-select"),
  requestedDepthSelect: document.getElementById("requested-depth-select"),
  regulatorChips: document.getElementById("regulator-chips"),
  // Landing Auth View Elements
  landingAuthForm: document.getElementById("landing-auth-form"),
  landingAuthTitle: document.getElementById("landing-auth-title"),
  landingAuthSubtitle: document.getElementById("landing-auth-subtitle"),
  landingNameGroup: document.getElementById("landing-name-group"),
  landingNameInput: document.getElementById("landing-name-input"),
  landingEmailInput: document.getElementById("landing-email-input"),
  landingPasswordInput: document.getElementById("landing-password-input"),
  landingBtnSubmit: document.getElementById("landing-btn-submit"),
  landingBtnToggleMode: document.getElementById("landing-btn-toggle-mode"),
  landingAuthTogglePrompt: document.getElementById("landing-auth-toggle-prompt"),
  landingBtnGoogle: document.getElementById("landing-btn-google"),
  landingBtnCustomer: document.getElementById("landing-btn-customer"),
  landingBtnAdmin: document.getElementById("landing-btn-admin"),
  landingBtnDevesh: document.getElementById("landing-btn-devesh"),
  // Auth Modal (Secondary / in-app switch)
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
  btnQuickDevesh: document.getElementById("btn-quick-devesh"),
  accountDrawer: document.getElementById("account-drawer"),
  savedAccountsList: document.getElementById("saved-accounts-list"),
  btnAddAccount: document.getElementById("btn-add-account"),
  btnLogoutCurrent: document.getElementById("btn-logout-current"),
  // Admin KB & MIS
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
  adminFilterRegulator: document.getElementById("admin-filter-regulator"),
  misMetricsSummary: document.getElementById("mis-metrics-summary"),
  misRegulatorSummary: document.getElementById("mis-regulator-summary"),
  misConsumptionSummary: document.getElementById("mis-consumption-summary"),
  // Passage Viewer
  passageViewerModal: document.getElementById("passage-viewer-modal"),
  pvDocTitle: document.getElementById("pv-doc-title"),
  pvDocMeta: document.getElementById("pv-doc-meta"),
  pvStatusBadge: document.getElementById("pv-status-badge"),
  pvRegulatorBadge: document.getElementById("pv-regulator-badge"),
  pvPageBadge: document.getElementById("pv-page-badge"),
  pvSectionBadge: document.getElementById("pv-section-badge"),
  pvHighlightContainer: document.getElementById("pv-highlight-container"),
  // Feedback Modal
  feedbackTriageModal: document.getElementById("feedback-triage-modal"),
  feedbackTriageForm: document.getElementById("feedback-triage-form"),
  feedbackTargetMsgId: document.getElementById("feedback-target-msg-id"),
  feedbackCategorySelect: document.getElementById("feedback-category-select"),
  feedbackCommentInput: document.getElementById("feedback-comment-input"),
  // Settings
  settingsModal: document.getElementById("settings-modal"),
  settingSttReview: document.getElementById("setting-stt-review"),
  settingAutoTts: document.getElementById("setting-auto-tts"),
  settingTtsRate: document.getElementById("setting-tts-rate"),
  tabBtnPref: document.getElementById("tab-btn-pref"),
  tabBtnMemories: document.getElementById("tab-btn-memories"),
  settingsTabGeneral: document.getElementById("settings-tab-general"),
  settingsTabMemory: document.getElementById("settings-tab-memory"),
  userMemoryList: document.getElementById("user-memory-list"),
  btnClearAllMemories: document.getElementById("btn-clear-all-memories"),
  // Share Chat (FR-24)
  btnShareChat: document.getElementById("btn-share-chat"),
  shareChatModal: document.getElementById("share-chat-modal"),
  shareLinkInput: document.getElementById("share-link-input"),
  btnCopyShareLink: document.getElementById("btn-copy-share-link"),
  shareExpiresBadge: document.getElementById("share-expires-badge"),
  // Enterprise SSO (FR-01)
  landingBtnSso: document.getElementById("landing-btn-sso"),
  btnSsoLogin: document.getElementById("btn-sso-login")
};

// ==================== TOAST & MODAL HELPERS ====================
function showToast(msg) {
  if (!DOM.toastContainer) return;
  const toast = document.createElement("div");
  toast.className = "toast-msg";
  toast.textContent = msg;
  DOM.toastContainer.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function closeAllModals() {
  document.querySelectorAll(".modal-overlay").forEach(m => m.classList.add("hidden"));
  if (DOM.modelDropdownMenu) DOM.modelDropdownMenu.classList.add("hidden");
}

// ==================== AUTHENTICATION & MULTI-ACCOUNT ====================

function getActiveAccount() {
  if (state.accounts && state.accounts.length > 0 && state.activeAccountIndex < state.accounts.length) {
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
      state.activeAccountIndex = activeIdx ? Math.min(Math.max(0, parseInt(activeIdx, 10)), Math.max(0, state.accounts.length - 1)) : 0;
    }
  } catch (e) {
    console.error("Failed to load accounts from storage:", e);
  }
}

function showLandingAuth() {
  if (DOM.authLandingView) DOM.authLandingView.classList.remove("hidden");
  if (DOM.appContainer) DOM.appContainer.classList.add("hidden");
}

function hideLandingAuth() {
  if (DOM.authLandingView) DOM.authLandingView.classList.add("hidden");
  if (DOM.appContainer) DOM.appContainer.classList.remove("hidden");
}

function setLandingAuthMode(isRegister) {
  state.isLandingAuthModeRegister = isRegister;
  if (DOM.landingNameGroup) DOM.landingNameGroup.classList.toggle("hidden", !isRegister);
  if (DOM.landingAuthTitle) DOM.landingAuthTitle.textContent = isRegister ? "Create your account" : "Welcome to ChatGPT";
  if (DOM.landingAuthSubtitle) DOM.landingAuthSubtitle.textContent = isRegister ? "Sign up to begin conversing with IDFC FIRST Assistant" : "Log in or create your IDFC FIRST Regulatory Assistant account to get started.";
  if (DOM.landingBtnSubmit) DOM.landingBtnSubmit.textContent = isRegister ? "Sign up" : "Continue";
  if (DOM.landingAuthTogglePrompt) DOM.landingAuthTogglePrompt.textContent = isRegister ? "Already have an account?" : "Don't have an account?";
  if (DOM.landingBtnToggleMode) DOM.landingBtnToggleMode.textContent = isRegister ? "Log in" : "Sign up";
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

    // Attempt seamless session refresh on backend for this active account
    try {
      const refreshRes = await fetch(`${API_BASE}/api/auth/switch-account`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: account.id, email: account.email })
      });
      if (refreshRes.ok) {
        const refreshData = await refreshRes.json();
        account.token = refreshData.access_token;
        account.name = refreshData.user.name;
        account.role = refreshData.user.role;
        saveAccountsToStorage();
        updateUIForAuth();
        return refreshData.access_token;
      }
    } catch (e) {
      console.log("Session refresh error:", e);
    }
    return account.token;
  }

  return null;
}

async function authenticatedFetch(url, options = {}) {
  let token = await validateOrRefreshToken();
  const headers = {
    ...options.headers,
    ...(token ? { "Authorization": `Bearer ${token}` } : {})
  };
  try {
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401 && !url.includes("/api/auth/")) {
      console.warn("Session expired or unauthorized for:", url);
      showToast("Your session has expired. Please log in again to continue.");
    }
    return res;
  } catch (e) {
    console.error("Network error during API fetch:", e);
    throw e;
  }
}

function updateUIForAuth() {
  const active = getActiveAccount();
  const isSessionAuth = sessionStorage.getItem("chatgptxidfc_session_authenticated") === "true";

  if (active && isSessionAuth) {
    hideLandingAuth();
    if (DOM.authBtnLabel) DOM.authBtnLabel.textContent = "Switch Account";
    if (DOM.userDisplayName) DOM.userDisplayName.textContent = active.name;
    if (DOM.userAvatarPlaceholder) {
      DOM.userAvatarPlaceholder.innerHTML = `<span>${active.name.charAt(0).toUpperCase()}</span>`;
    }
    if (DOM.adminKbBtnContainer) {
      DOM.adminKbBtnContainer.classList.toggle("hidden", active.role !== "admin");
    }
  } else {
    showLandingAuth();
    if (DOM.authBtnLabel) DOM.authBtnLabel.textContent = "Log in";
    if (DOM.userDisplayName) DOM.userDisplayName.textContent = active ? active.name : "Guest User";
    if (DOM.userAvatarPlaceholder) DOM.userAvatarPlaceholder.innerHTML = `<span>${active ? active.name.charAt(0).toUpperCase() : 'G'}</span>`;
    if (DOM.adminKbBtnContainer) DOM.adminKbBtnContainer.classList.add("hidden");
    if (active && DOM.landingEmailInput && !DOM.landingEmailInput.value) {
      DOM.landingEmailInput.value = active.email;
    }
  }
  renderSavedAccountsList();
}

function renderSavedAccountsList() {
  if (!DOM.savedAccountsList) return;
  DOM.savedAccountsList.innerHTML = "";

  state.accounts.forEach((acc, idx) => {
    const isCurrent = idx === state.activeAccountIndex;
    const item = document.createElement("div");
    item.className = `account-item ${isCurrent ? "active-account" : ""}`;
    item.innerHTML = `
      <div class="account-item-avatar"><span>${acc.name.charAt(0).toUpperCase()}</span></div>
      <div class="account-item-info">
        <div class="account-item-name">${escapeHtml(acc.name)} ${acc.role === 'admin' ? '<span class="role-badge">Admin</span>' : ''}</div>
        <div class="account-item-email">${escapeHtml(acc.email)}</div>
      </div>
      ${isCurrent ? '<i class="fa-solid fa-check check-current"></i>' : ''}
    `;

    item.addEventListener("click", async () => {
      await switchAccount(idx);
      if (DOM.accountDrawer) DOM.accountDrawer.classList.add("hidden");
    });

    DOM.savedAccountsList.appendChild(item);
  });
}

function addAccount(acc) {
  const existingIdx = state.accounts.findIndex(a => a.email.toLowerCase() === acc.email.toLowerCase());
  if (existingIdx !== -1) {
    state.accounts[existingIdx] = { ...state.accounts[existingIdx], ...acc };
    state.activeAccountIndex = existingIdx;
  } else {
    state.accounts.push(acc);
    state.activeAccountIndex = state.accounts.length - 1;
  }
  saveAccountsToStorage();
  updateUIForAuth();
}

async function switchAccount(idx) {
  if (idx >= 0 && idx < state.accounts.length) {
    state.activeAccountIndex = idx;
    saveAccountsToStorage();
    const target = state.accounts[idx];

    // Mark active session authenticated
    sessionStorage.setItem("chatgptxidfc_session_authenticated", "true");

    // Refresh JWT session on backend for target account
    try {
      const res = await fetch(`${API_BASE}/api/auth/switch-account`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: target.id, email: target.email })
      });
      if (res.ok) {
        const data = await res.json();
        target.token = data.access_token;
        target.name = data.user.name;
        target.role = data.user.role;
        saveAccountsToStorage();
      }
    } catch (e) {
      console.log("Account switch backend sync error:", e);
    }

    updateUIForAuth();
    hideLandingAuth();
    showToast(`Switched to ${target.name}`);
    state.currentConversationId = null;
    await loadConversations();
    DOM.messagesStream.innerHTML = "";
    DOM.messagesStream.appendChild(DOM.welcomeHero);
    DOM.welcomeHero.classList.remove("hidden");
  }
}

function logoutCurrentAccount() {
  sessionStorage.removeItem("chatgptxidfc_session_authenticated");
  if (state.accounts.length > 0) {
    const removed = state.accounts.splice(state.activeAccountIndex, 1);
    state.activeAccountIndex = Math.max(0, state.accounts.length - 1);
    saveAccountsToStorage();
    updateUIForAuth();
    showToast(`Logged out ${removed[0]?.name || ''}`);
    state.currentConversationId = null;
    loadConversations();
    DOM.messagesStream.innerHTML = "";
    DOM.messagesStream.appendChild(DOM.welcomeHero);
    DOM.welcomeHero.classList.remove("hidden");
    if (DOM.accountDrawer) DOM.accountDrawer.classList.add("hidden");
  }
  showLandingAuth();
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
      const errMsg = err.detail || "Login failed";
      
      // If user does not exist, ask them to sign up and auto toggle to register
      if (res.status === 404 || errMsg.toLowerCase().includes("does not exist") || errMsg.toLowerCase().includes("not found")) {
        showToast("Account not found. Please sign up below!");
        setLandingAuthMode(true);
        if (DOM.landingEmailInput) DOM.landingEmailInput.value = email;
        if (DOM.landingPasswordInput) DOM.landingPasswordInput.value = password;
        
        state.isAuthModeRegister = true;
        if (DOM.authNameGroup) DOM.authNameGroup.classList.remove("hidden");
        if (DOM.authModalTitle) DOM.authModalTitle.textContent = "Create your account";
        if (DOM.btnAuthSubmit) DOM.btnAuthSubmit.textContent = "Sign up";
        if (DOM.btnAuthToggleMode) DOM.btnAuthToggleMode.textContent = "Log in";
        if (DOM.authEmailInput) DOM.authEmailInput.value = email;
        if (DOM.authPasswordInput) DOM.authPasswordInput.value = password;
        return;
      }
      
      throw new Error(errMsg);
    }
    const data = await res.json();
    sessionStorage.setItem("chatgptxidfc_session_authenticated", "true");
    addAccount({
      id: data.user.id,
      name: data.user.name,
      email: data.user.email,
      role: data.user.role,
      token: data.access_token
    });
    closeAllModals();
    hideLandingAuth();
    showToast(`Welcome back, ${data.user.name}`);
    await loadConversations();
  } catch (err) {
    showToast(err.message);
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
    sessionStorage.setItem("chatgptxidfc_session_authenticated", "true");
    addAccount({
      id: data.user.id,
      name: data.user.name,
      email: data.user.email,
      role: data.user.role,
      token: data.access_token
    });
    closeAllModals();
    hideLandingAuth();
    showToast(`Account created for ${data.user.name}`);
    await loadConversations();
  } catch (err) {
    showToast(err.message);
    alert(err.message);
  }
}

async function googleLogin(email = "devesh.pandey1405@gmail.com", name = "devesh pandey1405") {
  try {
    const res = await fetch(`${API_BASE}/api/auth/google`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        credential: "mock_google_oauth_token_" + Date.now(),
        email: email,
        name: name
      })
    });
    if (!res.ok) throw new Error("Google SSO authentication failed");
    const data = await res.json();
    sessionStorage.setItem("chatgptxidfc_session_authenticated", "true");
    addAccount({
      id: data.user.id,
      name: data.user.name,
      email: data.user.email,
      role: data.user.role,
      token: data.access_token
    });
    closeAllModals();
    hideLandingAuth();
    showToast(`Signed in as ${data.user.name}`);
    await loadConversations();
  } catch (err) {
    showToast(err.message);
    alert(err.message);
  }
}

async function enterpriseSsoLogin(provider = "azure_ad", email = "compliance.officer@idfcbank.com", name = "IDFC Compliance Officer") {
  try {
    const res = await fetch(`${API_BASE}/api/auth/sso`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: provider,
        email: email,
        name: name,
        tenant_domain: "idfcbank.com",
        department: "Compliance & Regulatory Affairs"
      })
    });
    if (!res.ok) throw new Error("Enterprise SSO authentication failed");
    const data = await res.json();
    sessionStorage.setItem("chatgptxidfc_session_authenticated", "true");
    addAccount({
      id: data.user.id,
      name: data.user.name,
      email: data.user.email,
      role: data.user.role,
      token: data.access_token
    });
    closeAllModals();
    hideLandingAuth();
    showToast(`SSO Federated: Signed in as ${data.user.name} (${provider.toUpperCase()})`);
    await loadConversations();
  } catch (err) {
    showToast(err.message);
    alert(err.message);
  }
}


// ==================== CONVERSATIONS (SIDEBAR) ====================

async function loadConversations(searchQuery = null) {
  try {
    const url = searchQuery
      ? `${API_BASE}/api/conversations?search=${encodeURIComponent(searchQuery)}`
      : `${API_BASE}/api/conversations`;

    const res = await authenticatedFetch(url);
    if (!res.ok) return;
    const data = await res.json();
    state.conversations = data;
    renderConversationList(data);
  } catch (err) {
    console.error("Failed to load conversations:", err);
  }
}

function renderConversationList(convs) {
  if (!DOM.conversationList) return;
  DOM.conversationList.innerHTML = "";

  if (convs.length === 0) {
    DOM.conversationList.innerHTML = `<div class="empty-chat-list">No conversations yet</div>`;
    return;
  }

  // Date Grouping (Today, Yesterday, Previous 7 Days, Older)
  const now = new Date();
  const groups = {
    today: [],
    yesterday: [],
    prev7: [],
    older: []
  };

  convs.forEach(c => {
    const cDate = new Date(c.updated_at || c.created_at);
    const diffDays = Math.floor((now - cDate) / (1000 * 60 * 60 * 24));
    if (diffDays === 0) groups.today.push(c);
    else if (diffDays === 1) groups.yesterday.push(c);
    else if (diffDays < 7) groups.prev7.push(c);
    else groups.older.push(c);
  });

  const renderGroup = (label, items) => {
    if (items.length === 0) return;
    const grpDiv = document.createElement("div");
    grpDiv.className = "conv-group";
    grpDiv.innerHTML = `<div class="conv-group-title">${label}</div>`;

    items.forEach(c => {
      const isSelected = c.id === state.currentConversationId;
      const item = document.createElement("div");
      item.className = `conv-item ${isSelected ? "active" : ""}`;
      item.innerHTML = `
        <div class="conv-title-text" title="${escapeHtml(c.title)}">${escapeHtml(c.title)}</div>
        <div class="conv-item-actions">
          <button class="conv-action-btn btn-rename" title="Rename"><i class="fa-solid fa-pen"></i></button>
          <button class="conv-action-btn btn-delete" title="Delete"><i class="fa-solid fa-trash"></i></button>
        </div>
      `;

      item.querySelector(".conv-title-text").addEventListener("click", () => selectConversation(c.id));
      item.querySelector(".btn-rename").addEventListener("click", (e) => {
        e.stopPropagation();
        renameConversationPrompt(c.id, c.title);
      });
      item.querySelector(".btn-delete").addEventListener("click", (e) => {
        e.stopPropagation();
        deleteConversationPrompt(c.id);
      });

      grpDiv.appendChild(item);
    });

    DOM.conversationList.appendChild(grpDiv);
  };

  renderGroup("Today", groups.today);
  renderGroup("Yesterday", groups.yesterday);
  renderGroup("Previous 7 Days", groups.prev7);
  renderGroup("Older", groups.older);
}

async function selectConversation(id) {
  if (state.currentConversationId === id) return;
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

// ==================== VISUAL PASSAGE VIEWER (PRD Section 5.3 & FR-08, FR-09) ====================

function openPassageViewer(citation) {
  if (!DOM.passageViewerModal) return;

  const docTitle = citation.document_title || "Regulatory Circular";
  const notif = citation.notification_number || "Official Notification";
  const reg = citation.regulator || citation.source || "RBI";
  const status = citation.status || "ACTIVE";
  const page = citation.page_number || 1;
  const section = citation.section || "General";
  const snippet = citation.snippet || "";

  if (DOM.pvDocTitle) DOM.pvDocTitle.textContent = docTitle;
  if (DOM.pvDocMeta) DOM.pvDocMeta.textContent = `Authority: ${reg} • Ref: ${notif} • Page ${page}`;
  if (DOM.pvStatusBadge) DOM.pvStatusBadge.textContent = `${status.toUpperCase()} VERSION`;
  if (DOM.pvRegulatorBadge) DOM.pvRegulatorBadge.textContent = reg;
  if (DOM.pvPageBadge) DOM.pvPageBadge.textContent = `Page ${page}`;
  if (DOM.pvSectionBadge) DOM.pvSectionBadge.textContent = section;

  if (DOM.pvHighlightContainer) {
    DOM.pvHighlightContainer.innerHTML = `
      <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">
        <i class="fa-solid fa-highlighter" style="color:#f59e0b;"></i> Supporting Passage (Section: <strong>${escapeHtml(section)}</strong>):
      </div>
      <div class="passage-highlight-text">"${escapeHtml(snippet)}"</div>
      <div style="margin-top:14px;font-size:11px;color:var(--text-muted);border-top:1px solid var(--border-subtle);padding-top:8px;">
        <i class="fa-solid fa-lock"></i> Row-level verified citation bound to Document Version <code>${escapeHtml(notif)}</code>.
      </div>
    `;
  }

  DOM.passageViewerModal.classList.remove("hidden");
}

// ==================== ATTACHMENT PROCESSING (CHATGPT MULTIMODAL) ====================

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function getFileIconClass(fileType) {
  const t = (fileType || "").toLowerCase();
  if (t === "pdf") return "fa-file-pdf";
  if (["png", "jpg", "jpeg", "webp", "gif", "svg"].includes(t)) return "fa-file-image";
  if (["wav", "mp3", "m4a", "ogg", "webm", "audio"].includes(t)) return "fa-file-audio";
  if (["mp4", "mov", "avi", "mkv", "video"].includes(t)) return "fa-file-video";
  if (["docx", "doc"].includes(t)) return "fa-file-word";
  if (["csv", "xlsx", "xls"].includes(t)) return "fa-file-excel";
  if (["json", "js", "py", "html", "css"].includes(t)) return "fa-file-code";
  return "fa-file-lines";
}

async function uploadChatAttachment(file) {
  if (!file) return;

  // Show attachment pill with loading spinner
  if (DOM.chatAttachmentPreview) DOM.chatAttachmentPreview.classList.remove("hidden");
  if (DOM.attachmentIconContainer) DOM.attachmentIconContainer.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i>`;
  if (DOM.attachmentPillName) DOM.attachmentPillName.textContent = file.name;
  if (DOM.attachmentPillSize) DOM.attachmentPillSize.textContent = "Processing & examining...";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await authenticatedFetch(`${API_BASE}/api/chat/upload-attachment`, {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      let errMsg = "Failed to upload file";
      try {
        const errJson = await res.json();
        errMsg = errJson.detail || errMsg;
      } catch (_) {}
      throw new Error(errMsg);
    }

    const data = await res.json();
    state.selectedChatAttachment = data.attachment || data;

    const iconClass = getFileIconClass(state.selectedChatAttachment.file_type);
    if (DOM.attachmentIconContainer) {
      DOM.attachmentIconContainer.innerHTML = `<i class="fa-solid ${iconClass}"></i>`;
    }
    if (DOM.attachmentPillName) {
      DOM.attachmentPillName.textContent = state.selectedChatAttachment.original_name || state.selectedChatAttachment.filename;
    }
    const attSize = state.selectedChatAttachment.size_bytes || state.selectedChatAttachment.file_size || file.size || 0;
    const charCount = state.selectedChatAttachment.extracted_text ? state.selectedChatAttachment.extracted_text.length : 0;
    if (DOM.attachmentPillSize) {
      DOM.attachmentPillSize.textContent = `${formatBytes(attSize)} • ${charCount} chars extracted`;
    }

    showToast(`Attached ${state.selectedChatAttachment.original_name || state.selectedChatAttachment.filename}`);
    if (DOM.btnSend) DOM.btnSend.disabled = false;
  } catch (err) {
    console.error("Chat attachment upload error:", err);
    showToast(`Upload failed: ${err.message}`);
    clearChatAttachment();
  }
}

function clearChatAttachment() {
  state.selectedChatAttachment = null;
  if (DOM.chatAttachmentPreview) DOM.chatAttachmentPreview.classList.add("hidden");
  if (DOM.chatFileInput) DOM.chatFileInput.value = "";
  if (DOM.btnSend) DOM.btnSend.disabled = !DOM.chatTextarea?.value.trim();
}

// ==================== CHAT PIPELINE & MESSAGES ====================

function renderMessage(role, content, meta = {}) {
  DOM.welcomeHero.classList.add("hidden");
  const isUser = role === "user";
  const row = document.createElement("div");
  row.className = `message-row ${isUser ? "user-row" : "assistant-row"}`;

  const avatarHtml = isUser
    ? ""
    : `<div class="message-avatar" title="ChatGPT × IDFC FIRST Bank">
        <div class="chatgpt-avatar-icon">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
            <path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1683a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4947zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1683a.0757.0757 0 0 1-.071 0l-4.8303-2.7866A4.4992 4.4992 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.6667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1635a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z"/>
          </svg>
        </div>
        <img src="/static/idfc_logo.png" alt="IDFC" class="idfc-logo-badge" title="IDFC FIRST Bank">
      </div>`;

  let innerContentHtml = "";

  if (isUser) {
    let attachmentHtml = "";
    if (meta.attachment) {
      const att = meta.attachment;
      const iconClass = getFileIconClass(att.file_type);
      const attSize = att.size_bytes || att.file_size || 0;
      attachmentHtml = `
        <div class="message-attached-file">
          <div class="message-attached-icon"><i class="fa-solid ${iconClass}"></i></div>
          <div>
            <div class="message-attached-name">${escapeHtml(att.original_name || att.filename)}</div>
            <div class="message-attached-type">${escapeHtml(att.file_type || "file")} • ${formatBytes(attSize)}</div>
          </div>
        </div>
      `;
    }
    innerContentHtml = `
      ${attachmentHtml}
      ${content ? `<div class="message-content">${escapeHtml(content)}</div>` : ''}
    `;
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
    } else if (meta.source_type === "ATTACHMENT_ANALYSIS") {
      badgeClass = "badge-attachment";
      badgeText = "Attached Document Examination";
      badgeIcon = "fa-file-lines";
    } else if (meta.source_type === "NO_SUPPORTED_SOURCE") {
      badgeClass = "badge-nosource";
      badgeText = "No Verified Source";
      badgeIcon = "fa-circle-exclamation";
    }

    const badgeHtml = meta.source_type === "CONVERSATIONAL" 
      ? "" 
      : `<div class="source-badge ${badgeClass}"><i class="fa-solid ${badgeIcon}"></i> ${badgeText}</div>`;

    // Normalized Query Tag (Omit for conversational turns)
    let normTagHtml = "";
    if (meta.source_type !== "CONVERSATIONAL" && meta.normalized_query && meta.normalized_query.trim() !== content.trim()) {
      normTagHtml = `<div class="normalized-query-tag"><i class="fa-solid fa-wand-magic-sparkles"></i> Interpreted: "${escapeHtml(meta.normalized_query)}"</div>`;
    }

    // Citations Accordion (Clickable with Visual Passage Highlighter)
    let citationsHtml = "";
    if (meta.citations && meta.citations.length > 0) {
      const citeCards = meta.citations.map((c, cIdx) => `
        <div class="citation-card clickable-citation" data-idx="${cIdx}">
          <div class="citation-header">
            <span class="citation-title">${escapeHtml(c.document_title)} ${c.notification_number ? `(${escapeHtml(c.notification_number)})` : ''}</span>
            <span class="citation-page"><i class="fa-solid fa-arrow-up-right-from-square"></i> Page ${c.page_number || 1} • ${(c.score * 100).toFixed(0)}% match</span>
          </div>
          <div class="citation-snippet">"${escapeHtml(c.snippet)}"</div>
        </div>
      `).join("");

      citationsHtml = `
        <div class="citations-wrapper">
          <button class="citations-toggle-btn" type="button">
            <i class="fa-solid fa-chevron-down"></i> ${meta.citations.length} verified source citation(s) — Click to view passage
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
        <button class="action-icon-btn btn-thumb-down" title="Report issue / Quality triage">
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

    // Clickable Citation Cards -> Open Visual Passage Viewer
    const citeCards = row.querySelectorAll(".clickable-citation");
    citeCards.forEach(card => {
      card.addEventListener("click", () => {
        const idx = parseInt(card.getAttribute("data-idx"), 10);
        if (meta.citations && meta.citations[idx]) {
          openPassageViewer(meta.citations[idx]);
        }
      });
    });

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
            await authenticatedFetch(`${API_BASE}/api/feedback`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                message_id: meta.assistant_message_id,
                rating: "POSITIVE",
                category: null,
                comment: "Helpful and accurate answer"
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
      thumbDown.addEventListener("click", () => {
        if (DOM.feedbackTriageModal) {
          if (DOM.feedbackTargetMsgId) DOM.feedbackTargetMsgId.value = meta.assistant_message_id || "";
          DOM.feedbackTriageModal.classList.remove("hidden");
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
  const attachment = state.selectedChatAttachment;

  if (!query && !attachment) return;

  if (activeChatAbortController) {
    activeChatAbortController.abort();
  }
  activeChatAbortController = new AbortController();

  // Render message in feed
  renderMessage("user", query, { attachment });
  DOM.chatTextarea.value = "";
  DOM.chatTextarea.style.height = "24px";
  clearChatAttachment();

  DOM.btnSend.disabled = false;
  DOM.btnSend.innerHTML = `<i class="fa-solid fa-square" style="font-size:12px;"></i>`;
  DOM.btnSend.setAttribute("title", "Stop generation");

  const loadingRow = document.createElement("div");
  loadingRow.className = "message-row assistant-row";
  loadingRow.id = "assistant-loading-indicator";
  const loadingStatus = attachment
    ? `Examining attached file & synthesizing insights...`
    : `Grounding answer across ${state.activeRegulator === 'ALL' ? 'RBI, SEBI & IRDAI' : state.activeRegulator} directives...`;

  loadingRow.innerHTML = `
    <div class="message-avatar" title="ChatGPT × IDFC FIRST Bank">
      <div class="chatgpt-avatar-icon">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
          <path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1683a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4947zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1683a.0757.0757 0 0 1-.071 0l-4.8303-2.7866A4.4992 4.4992 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.6667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1635a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z"/>
        </svg>
      </div>
      <img src="/static/idfc_logo.png" alt="IDFC" class="idfc-logo-badge" title="IDFC FIRST Bank">
    </div>
    <div class="message-body-wrapper">
      <div class="message-content" style="color:var(--text-muted);font-style:italic;">
        <i class="fa-solid fa-circle-notch fa-spin"></i> ${loadingStatus}
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
        query: query,
        regulator_filter: state.activeRegulator === "ALL" ? null : [state.activeRegulator],
        as_of_date: state.activeAsOfDate || null,
        requested_depth: state.activeDepth || "concise",
        attachment: attachment
      }),
      signal: activeChatAbortController.signal
    });

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
      return;
    }

    const friendlyErr = (err.message === "Failed to fetch" || err.message?.includes("NetworkError"))
      ? "Unable to reach the server. The connection was temporarily interrupted, please try again."
      : (err.message || "Something went wrong while processing your request. Please try again.");

    renderMessage("assistant", friendlyErr, {
      source_type: "NO_SUPPORTED_SOURCE"
    });
  } finally {
    activeChatAbortController = null;
    DOM.btnSend.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 4L12 20M12 4L6 10M12 4L18 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    DOM.btnSend.setAttribute("title", "Send message");
    DOM.btnSend.disabled = !DOM.chatTextarea.value.trim() && !state.selectedChatAttachment;
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
      const p = card.getAttribute("data-prompt");
      if (p) {
        if (DOM.chatTextarea) DOM.chatTextarea.value = p;
        if (DOM.btnSend) DOM.btnSend.disabled = false;
        sendChatMessage(p);
      }
    });
  });
}

// ==================== SPEECH RECOGNITION & TTS ====================

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
    if (DOM.speechReviewBar) DOM.speechReviewBar.classList.remove("hidden");
    if (DOM.speechTranscriptInput) DOM.speechTranscriptInput.value = "";
  };

  state.speechRecognition.onresult = (event) => {
    let transcript = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    if (DOM.speechTranscriptInput) DOM.speechTranscriptInput.value = transcript;
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

// ==================== ADMIN KNOWLEDGE BASE & MIS ====================

async function loadAdminDocuments() {
  try {
    const reg = DOM.adminFilterRegulator ? DOM.adminFilterRegulator.value : "ALL";
    const res = await authenticatedFetch(`${API_BASE}/api/admin/documents?regulator=${reg}`);
    if (!res.ok) throw new Error("Failed to load documents");
    const docs = await res.json();
    if (DOM.kbDocCount) DOM.kbDocCount.textContent = docs.length;
    renderAdminDocumentsTable(docs);
  } catch (err) {
    console.error(err);
  }
}

function renderAdminDocumentsTable(docs) {
  if (!DOM.kbDocumentsTbody) return;
  DOM.kbDocumentsTbody.innerHTML = "";
  if (docs.length === 0) {
    DOM.kbDocumentsTbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:16px;">No documents found for selected regulator.</td></tr>`;
    return;
  }

  docs.forEach(d => {
    const tr = document.createElement("tr");
    const statusBadge = d.status === "superseded"
      ? `<span class="badge-secondary" style="background:rgba(239,68,68,0.15);color:#ef4444;">SUPERSEDED</span>`
      : `<span class="badge-active">ACTIVE</span>`;

    const effDates = `From: ${d.effective_from || 'N/A'}${d.effective_until ? `<br>Until: ${d.effective_until}` : ''}`;

    tr.innerHTML = `
      <td><strong>${escapeHtml(d.title)}</strong><br><span class="badge-secondary" style="font-size:10px;">${escapeHtml(d.regulator || d.source)}</span></td>
      <td><code>${escapeHtml(d.notification_number || 'N/A')}</code></td>
      <td>${statusBadge}</td>
      <td style="font-size:11px;">${effDates}</td>
      <td>${d.chunk_count}</td>
      <td>
        <button class="btn btn-danger-chatgpt btn-sm btn-delete-doc" data-id="${d.id}" title="Delete"><i class="fa-solid fa-trash"></i></button>
      </td>
    `;

    tr.querySelector(".btn-delete-doc").addEventListener("click", () => deleteDocument(d.id));
    DOM.kbDocumentsTbody.appendChild(tr);
  });
}

async function loadIngestionMIS() {
  try {
    const res = await authenticatedFetch(`${API_BASE}/api/admin/mis/ingestion`);
    if (!res.ok) return;
    const mis = await res.json();

    if (DOM.misMetricsSummary) {
      DOM.misMetricsSummary.innerHTML = `
        <div class="mis-card">
          <div class="mis-card-value">${mis.total_documents}</div>
          <div class="mis-card-label">Total Documents</div>
        </div>
        <div class="mis-card">
          <div class="mis-card-value" style="color:#10b981;">${mis.active_documents}</div>
          <div class="mis-card-label">Active Directives</div>
        </div>
        <div class="mis-card">
          <div class="mis-card-value" style="color:#f59e0b;">${mis.superseded_documents}</div>
          <div class="mis-card-label">Superseded</div>
        </div>
        <div class="mis-card">
          <div class="mis-card-value" style="color:#6366f1;">${mis.total_chunks}</div>
          <div class="mis-card-label">Indexed Chunks</div>
        </div>
      `;
    }

    if (DOM.misRegulatorSummary) {
      const regCards = Object.entries(mis.by_regulator).map(([k, v]) => `
        <div class="mis-card">
          <div class="mis-card-value">${v}</div>
          <div class="mis-card-label">${k} Directives</div>
        </div>
      `).join("");

      DOM.misRegulatorSummary.innerHTML = `
        <h4 style="margin-bottom:12px;font-size:13px;color:var(--text-secondary);">Directives by Regulatory Authority:</h4>
        <div class="mis-metrics-grid">${regCards}</div>
      `;
    }
  } catch (err) {
    console.error("Failed to load Ingestion MIS:", err);
  }
}

async function loadConsumptionMIS() {
  try {
    const res = await authenticatedFetch(`${API_BASE}/api/admin/mis/consumption`);
    if (!res.ok) return;
    const cons = await res.json();

    if (DOM.misConsumptionSummary) {
      DOM.misConsumptionSummary.innerHTML = `
        <div class="mis-card">
          <div class="mis-card-value">${cons.total_queries}</div>
          <div class="mis-card-label">Total Queries</div>
        </div>
        <div class="mis-card">
          <div class="mis-card-value" style="color:#10b981;">${cons.cache_hit_rate_pct}%</div>
          <div class="mis-card-label">Cache Avoidance Rate</div>
        </div>
        <div class="mis-card">
          <div class="mis-card-value">${cons.total_tokens_input + cons.total_tokens_output}</div>
          <div class="mis-card-label">Total Tokens Tracked</div>
        </div>
        <div class="mis-card">
          <div class="mis-card-value" style="color:#38bdf8;">${cons.p50_latency_ms}ms</div>
          <div class="mis-card-label">P50 Latency</div>
        </div>
      `;
    }
  } catch (err) {
    console.error("Failed to load Consumption MIS:", err);
  }
}

async function uploadDocument() {
  if (!state.selectedUploadFile) return;

  const formData = new FormData();
  formData.append("file", state.selectedUploadFile);
  if (DOM.docTitleInput.value.trim()) formData.append("title", DOM.docTitleInput.value.trim());
  if (DOM.docNotifInput.value.trim()) formData.append("notification_number", DOM.docNotifInput.value.trim());
  formData.append("regulator", DOM.docSourceSelect.value);
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
    showToast("Document ingested & indexed across vector store!");
    DOM.kbUploadForm.reset();
    DOM.kbUploadForm.classList.add("hidden");
    state.selectedUploadFile = null;
    await loadAdminDocuments();
    await loadIngestionMIS();
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
        await loadIngestionMIS();
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

  // New Chat Button
  if (DOM.btnNewChat) {
    DOM.btnNewChat.addEventListener("click", () => {
      state.currentConversationId = null;
      renderConversationList(state.conversations);
      DOM.messagesStream.innerHTML = "";
      DOM.messagesStream.appendChild(DOM.welcomeHero);
      DOM.welcomeHero.classList.remove("hidden");
      if (DOM.chatTextarea) DOM.chatTextarea.focus();
    });
  }

  // Model Selector Dropdown
  if (DOM.btnModelSelector && DOM.modelDropdownMenu) {
    DOM.btnModelSelector.addEventListener("click", (e) => {
      e.stopPropagation();
      DOM.modelDropdownMenu.classList.toggle("hidden");
    });
  }

  // Prompt Category Filter Tabs
  document.querySelectorAll(".prompt-category-tabs .cat-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".prompt-category-tabs .cat-tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      const cat = tab.getAttribute("data-cat");
      renderPromptCards(cat);
    });
  });

  renderPromptCards("all");

  // Scoped Query Filter Chips (Regulator)
  if (DOM.regulatorChips) {
    DOM.regulatorChips.querySelectorAll(".scope-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        DOM.regulatorChips.querySelectorAll(".scope-chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        state.activeRegulator = chip.getAttribute("data-reg") || "ALL";
        showToast(`Regulator scope: ${state.activeRegulator}`);
      });
    });
  }

  // Timeline Scope
  if (DOM.asOfDateSelect) {
    DOM.asOfDateSelect.addEventListener("change", (e) => {
      state.activeAsOfDate = e.target.value;
      showToast(state.activeAsOfDate ? `Historical rules as of ${state.activeAsOfDate}` : "Current active regulations");
    });
  }

  // Depth Scope
  if (DOM.requestedDepthSelect) {
    DOM.requestedDepthSelect.addEventListener("change", (e) => {
      state.activeDepth = e.target.value;
    });
  }

  // Feedback Triage Form Submission (PRD Section 5.4 8-Category Taxonomy)
  if (DOM.feedbackTriageForm) {
    DOM.feedbackTriageForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msgId = DOM.feedbackTargetMsgId ? DOM.feedbackTargetMsgId.value : null;
      const cat = DOM.feedbackCategorySelect ? DOM.feedbackCategorySelect.value : "INCORRECT_FACT";
      const comment = DOM.feedbackCommentInput ? DOM.feedbackCommentInput.value.trim() : "";

      try {
        const res = await authenticatedFetch(`${API_BASE}/api/feedback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message_id: msgId,
            rating: "NEGATIVE",
            category: cat,
            comment: comment
          })
        });

        if (res.ok) {
          showToast("Feedback submitted for regulatory review");
          if (DOM.feedbackTriageModal) DOM.feedbackTriageModal.classList.add("hidden");
          if (DOM.feedbackCommentInput) DOM.feedbackCommentInput.value = "";
        }
      } catch (err) {
        console.error(err);
      }
    });
  }

  // Admin Tab Switcher
  document.querySelectorAll(".admin-tab-btn").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".admin-tab-btn").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".admin-tab-content").forEach(c => c.classList.add("hidden"));

      tab.classList.add("active");
      const targetId = `tab-content-${tab.getAttribute("data-tab")}`;
      const targetEl = document.getElementById(targetId);
      if (targetEl) targetEl.classList.remove("hidden");

      if (tab.getAttribute("data-tab") === "mis-ingestion") {
        loadIngestionMIS();
      } else if (tab.getAttribute("data-tab") === "mis-consumption") {
        loadConsumptionMIS();
      } else if (tab.getAttribute("data-tab") === "catalogue") {
        loadAdminDocuments();
      }
    });
  });

  if (DOM.adminFilterRegulator) {
    DOM.adminFilterRegulator.addEventListener("change", () => loadAdminDocuments());
  }

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

    // Drag and Drop File Attachments
    DOM.chatForm.addEventListener("dragover", (e) => {
      e.preventDefault();
      DOM.chatForm.classList.add("drag-over");
    });
    DOM.chatForm.addEventListener("dragleave", () => {
      DOM.chatForm.classList.remove("drag-over");
    });
    DOM.chatForm.addEventListener("drop", (e) => {
      e.preventDefault();
      DOM.chatForm.classList.remove("drag-over");
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        uploadChatAttachment(e.dataTransfer.files[0]);
      }
    });
  }

  if (DOM.chatTextarea) {
    DOM.chatTextarea.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
      }
    });

    DOM.chatTextarea.addEventListener("input", () => {
      DOM.chatTextarea.style.height = "auto";
      DOM.chatTextarea.style.height = Math.min(DOM.chatTextarea.scrollHeight, 180) + "px";
      if (DOM.btnSend) DOM.btnSend.disabled = !DOM.chatTextarea.value.trim() && !state.selectedChatAttachment;
    });
  }

  // Attach File to Chat Button (ChatGPT 4o style)
  if (DOM.btnAttachFile && DOM.chatFileInput) {
    DOM.btnAttachFile.addEventListener("click", () => {
      DOM.chatFileInput.click();
    });
  }

  if (DOM.chatFileInput) {
    DOM.chatFileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) {
        uploadChatAttachment(file);
      }
    });
  }

  if (DOM.btnRemoveAttachment) {
    DOM.btnRemoveAttachment.addEventListener("click", clearChatAttachment);
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

  // ==================== LANDING AUTH SCREEN LISTENERS ====================
  if (DOM.landingBtnToggleMode) {
    DOM.landingBtnToggleMode.addEventListener("click", () => {
      setLandingAuthMode(!state.isLandingAuthModeRegister);
    });
  }

  if (DOM.landingAuthForm) {
    DOM.landingAuthForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const email = DOM.landingEmailInput ? DOM.landingEmailInput.value.trim() : "";
      const password = DOM.landingPasswordInput ? DOM.landingPasswordInput.value : "";
      if (state.isLandingAuthModeRegister) {
        const name = (DOM.landingNameInput ? DOM.landingNameInput.value.trim() : "") || email.split("@")[0];
        registerUser(name, email, password);
      } else {
        loginUser(email, password);
      }
    });
  }

  if (DOM.landingBtnCustomer) {
    DOM.landingBtnCustomer.addEventListener("click", () => {
      loginUser("customer@idfcbank.com", "Customer@123");
    });
  }

  if (DOM.landingBtnAdmin) {
    DOM.landingBtnAdmin.addEventListener("click", () => {
      loginUser("admin@idfcbank.com", "Admin@12345");
    });
  }

  if (DOM.landingBtnDevesh) {
    DOM.landingBtnDevesh.addEventListener("click", () => {
      googleLogin("devesh.pandey1405@gmail.com", "devesh pandey1405");
    });
  }

  if (DOM.landingBtnGoogle) {
    DOM.landingBtnGoogle.addEventListener("click", () => googleLogin());
  }

  // ==================== IN-APP AUTH MODAL & TRIGGER ====================
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

  // Demo Login Buttons in Modal
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

  if (DOM.btnQuickDevesh) {
    DOM.btnQuickDevesh.addEventListener("click", () => {
      googleLogin("devesh.pandey1405@gmail.com", "devesh pandey1405");
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

  // ==================== SHARE CONVERSATION (FR-24) ====================
  async function openShareModal() {
    if (!state.currentConversationId) {
      showToast("Please open a conversation to share");
      return;
    }
    try {
      const res = await authenticatedFetch(`${API_BASE}/api/conversations/${state.currentConversationId}/share`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expires_in_hours: 72 })
      });
      if (!res.ok) throw new Error("Failed to generate share link");
      const data = await res.json();
      const fullUrl = `${window.location.origin}${data.share_url}`;
      if (DOM.shareLinkInput) DOM.shareLinkInput.value = fullUrl;
      if (DOM.shareExpiresBadge) DOM.shareExpiresBadge.innerHTML = `<i class="fa-regular fa-clock"></i> Valid until ${new Date(data.expires_at).toLocaleDateString()}`;
      if (DOM.shareChatModal) DOM.shareChatModal.classList.remove("hidden");
    } catch (err) {
      showToast(err.message);
    }
  }

  function copyShareLink() {
    if (!DOM.shareLinkInput || !DOM.shareLinkInput.value) return;
    navigator.clipboard.writeText(DOM.shareLinkInput.value);
    showToast("Shareable link copied to clipboard");
    if (DOM.btnCopyShareLink) {
      DOM.btnCopyShareLink.innerHTML = `<i class="fa-solid fa-check"></i> Copied!`;
      setTimeout(() => {
        if (DOM.btnCopyShareLink) DOM.btnCopyShareLink.innerHTML = `<i class="fa-solid fa-copy"></i> Copy Link`;
      }, 2000);
    }
  }

  // ==================== PERSONAL MEMORY USER CONTROLS (FR-18) ====================
  async function loadUserMemories() {
    if (!DOM.userMemoryList) return;
    DOM.userMemoryList.innerHTML = `<div class="list-skeleton">Loading personal memories...</div>`;
    try {
      const res = await authenticatedFetch(`${API_BASE}/api/user/memories`);
      if (!res.ok) throw new Error("Failed to load user memories");
      const data = await res.json();
      renderUserMemories(data.memories || []);
    } catch (err) {
      DOM.userMemoryList.innerHTML = `<div style="font-size:13px;color:var(--text-muted);padding:8px;">Failed to load memories.</div>`;
    }
  }

  function renderUserMemories(memories) {
    if (!DOM.userMemoryList) return;
    DOM.userMemoryList.innerHTML = "";
    if (memories.length === 0) {
      DOM.userMemoryList.innerHTML = `<div style="font-size:13px;color:var(--text-muted);padding:12px;text-align:center;">No stored personal context or preferences yet. Memory is recorded dynamically as you converse with explicit controls.</div>`;
      return;
    }

    memories.forEach(m => {
      const card = document.createElement("div");
      card.className = "user-memory-card";
      card.innerHTML = `
        <div style="flex: 1; padding-right: 8px;">
          <div>
            <span class="memory-category-tag">${escapeHtml(m.category || 'CONTEXT')}</span>
            <strong style="font-size: 13px;">${escapeHtml(m.key)}</strong>
          </div>
          <p style="font-size: 12.5px; color: var(--text-secondary); margin-top: 3px;">${escapeHtml(m.value)}</p>
        </div>
        <button class="memory-delete-btn" title="Delete this memory" data-key="${escapeHtml(m.key)}">
          <i class="fa-solid fa-trash"></i>
        </button>
      `;

      card.querySelector(".memory-delete-btn").addEventListener("click", async () => {
        await deleteUserMemory(m.key);
      });

      DOM.userMemoryList.appendChild(card);
    });
  }

  async function deleteUserMemory(key) {
    try {
      const res = await authenticatedFetch(`${API_BASE}/api/user/memories/${encodeURIComponent(key)}`, {
        method: "DELETE"
      });
      if (res.ok) {
        showToast(`Memory deleted: ${key}`);
        await loadUserMemories();
      }
    } catch (err) {
      showToast("Failed to delete memory");
    }
  }

  async function clearAllUserMemories() {
    if (!confirm("Are you sure you want to clear all stored personal context and preferences?")) return;
    try {
      const res = await authenticatedFetch(`${API_BASE}/api/user/memories/clear`, {
        method: "POST"
      });
      if (res.ok) {
        showToast("All personal memories cleared");
        await loadUserMemories();
      }
    } catch (err) {
      showToast("Failed to clear memories");
    }
  }

  // Share Chat Triggers
  if (DOM.btnShareChat) {
    DOM.btnShareChat.addEventListener("click", openShareModal);
  }
  if (DOM.btnCopyShareLink) {
    DOM.btnCopyShareLink.addEventListener("click", copyShareLink);
  }

  // Enterprise SSO Triggers
  if (DOM.landingBtnSso) {
    DOM.landingBtnSso.addEventListener("click", () => enterpriseSsoLogin("azure_ad"));
  }
  if (DOM.btnSsoLogin) {
    DOM.btnSsoLogin.addEventListener("click", () => enterpriseSsoLogin("azure_ad"));
  }

  // Settings Modal & Tabs
  if (DOM.btnOpenSettings && DOM.settingsModal) {
    DOM.btnOpenSettings.addEventListener("click", () => {
      DOM.settingsModal.classList.remove("hidden");
      // Default to general tab
      if (DOM.tabBtnPref) DOM.tabBtnPref.click();
    });
  }

  if (DOM.tabBtnPref) {
    DOM.tabBtnPref.addEventListener("click", () => {
      DOM.tabBtnPref.classList.add("active");
      if (DOM.tabBtnMemories) DOM.tabBtnMemories.classList.remove("active");
      if (DOM.settingsTabGeneral) DOM.settingsTabGeneral.classList.remove("hidden");
      if (DOM.settingsTabMemory) DOM.settingsTabMemory.classList.add("hidden");
    });
  }

  if (DOM.tabBtnMemories) {
    DOM.tabBtnMemories.addEventListener("click", () => {
      DOM.tabBtnMemories.classList.add("active");
      if (DOM.tabBtnPref) DOM.tabBtnPref.classList.remove("active");
      if (DOM.settingsTabMemory) DOM.settingsTabMemory.classList.remove("hidden");
      if (DOM.settingsTabGeneral) DOM.settingsTabGeneral.classList.add("hidden");
      loadUserMemories();
    });
  }

  if (DOM.btnClearAllMemories) {
    DOM.btnClearAllMemories.addEventListener("click", clearAllUserMemories);
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
  initEventListeners();
  initSpeechRecognition();

  const isSessionAuth = sessionStorage.getItem("chatgptxidfc_session_authenticated") === "true";
  if (isSessionAuth) {
    const token = await validateOrRefreshToken();
    updateUIForAuth();
    if (token) {
      await loadConversations();
    }
  } else {
    showLandingAuth();
    updateUIForAuth();
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootApp);
} else {
  bootApp();
}
