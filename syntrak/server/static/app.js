/**
 * syntrak.nvim — Web UI Client Logic
 * ChatGPT-style Chat History, Google Auth, and Multi-turn ReAct Agent Stream
 */

let activeAbortController = null;
let activeConversationId = null;
let conversationsCache = [];
let currentUser = null;
let currentChatMode = localStorage.getItem('syntrak_chat_mode') || 'chat';
let activeSidebarMode = localStorage.getItem('syntrak_chat_mode') || 'chat';
let isRepoAuthorized = localStorage.getItem('syntrak_repo_authorized') === 'true';

document.addEventListener('DOMContentLoaded', () => {
  initThemeSelector();
  initTabs();
  initSidebar();
  initSlashPopup();
  initChatForm();
  initAuth();
  initModeSwitcher();
  loadSessionStatus();
  loadConversations();

  document.getElementById('btnQuickReview')?.addEventListener('click', () => {
    sendQuickPrompt('/review');
  });
  document.getElementById('btnQuickUndo')?.addEventListener('click', handleUndo);
  document.getElementById('btnClearChat')?.addEventListener('click', clearCurrentChat);
  document.getElementById('configForm')?.addEventListener('submit', handleConfigSave);
  document.getElementById('btnNewChat')?.addEventListener('click', startNewConversation);
  document.getElementById('btnToggleSidebar')?.addEventListener('click', toggleSidebar);
  document.getElementById('btnDeleteActiveThread')?.addEventListener('click', deleteCurrentActiveThread);
  document.getElementById('btnEditTitle')?.addEventListener('click', enableTitleEdit);
  document.getElementById('btnLogout')?.addEventListener('click', handleLogout);
});

/* ==========================================================================
   Authentication & User State (Google Identity Services & JWT)
   ========================================================================== */
function initAuth() {
  const token = localStorage.getItem('syntrak_token');
  if (token) {
    fetchUserProfile();
  }
}

// Global callback for Google GIS button
window.handleGoogleCredential = async function(response) {
  try {
    const res = await fetch('/api/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential: response.credential })
    });

    if (!res.ok) {
      throw new Error(`Google Auth failed (${res.status})`);
    }

    const data = await res.json();
    localStorage.setItem('syntrak_token', data.token);
    renderUserProfile(data.user);
    showToast(`Welcome, ${data.user.name || 'Developer'}!`);
    loadConversations();
  } catch (err) {
    showToast(`Google Sign-In Error: ${err.message}`, 'error');
  }
};

async function fetchUserProfile() {
  const token = localStorage.getItem('syntrak_token');
  try {
    const res = await fetch('/api/auth/me', {
      headers: token ? { 'Authorization': `Bearer ${token}` } : {}
    });
    if (res.ok) {
      const user = await res.json();
      renderUserProfile(user);
    }
  } catch (err) {
    console.error('Failed to fetch user profile:', err);
  }
}

function renderUserProfile(user) {
  const authBox = document.getElementById('authBox');
  const userCard = document.getElementById('userCard');
  const userName = document.getElementById('userName');
  const userEmail = document.getElementById('userEmail');
  const userAvatar = document.getElementById('userAvatar');
  const userAvatarFallback = document.getElementById('userAvatarFallback');

  if (user && user.id && user.id !== 'guest-developer') {
    currentUser = user;
    if (authBox) authBox.style.display = 'none';
    if (userCard) userCard.style.display = 'flex';
    if (userName) userName.textContent = user.name || 'Authenticated User';
    if (userEmail) userEmail.textContent = user.email || '';

    if (user.picture && userAvatar) {
      userAvatar.src = user.picture;
      userAvatar.style.display = 'block';
      if (userAvatarFallback) userAvatarFallback.style.display = 'none';
    } else {
      if (userAvatar) userAvatar.style.display = 'none';
      if (userAvatarFallback) userAvatarFallback.style.display = 'flex';
    }
  } else {
    currentUser = null;
    if (authBox) authBox.style.display = 'flex';
    if (userCard) userCard.style.display = 'none';
  }
}

async function handleLogout() {
  try {
    await fetch('/api/auth/logout', { method: 'POST' });
  } catch (e) {}

  localStorage.removeItem('syntrak_token');
  document.cookie = 'syntrak_token=; Max-Age=0; path=/;';

  if (window.google && window.google.accounts && window.google.accounts.id) {
    try {
      google.accounts.id.disableAutoSelect();
    } catch (e) {}
  }

  renderUserProfile(null);
  startNewConversation();
  showToast('Logged out of session.');
  loadConversations();
}

function getAuthHeaders() {
  const token = localStorage.getItem('syntrak_token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/* ==========================================================================
   ChatGPT-Style Chat History & Sidebar Management
   ========================================================================== */
function initSidebar() {
  const searchInput = document.getElementById('sidebarSearchInput');
  searchInput?.addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase();
    filterConversations(query);
  });

  const sideTabChat = document.getElementById('sideTabChat');
  const sideTabAgent = document.getElementById('sideTabAgent');

  sideTabChat?.addEventListener('click', () => {
    switchSidebarMode('chat', true);
  });

  sideTabAgent?.addEventListener('click', () => {
    switchSidebarMode('agent', true);
  });

  document.getElementById('sidebarBackdrop')?.addEventListener('click', closeMobileSidebar);
}

function shiftToMostRecentConversation(mode) {
  const targetMode = mode || currentChatMode || 'chat';
  const modeConvs = (conversationsCache || []).filter(c => (c.mode || 'chat') === targetMode);
  if (modeConvs.length > 0) {
    if (activeConversationId !== modeConvs[0].id) {
      selectConversation(modeConvs[0].id, false);
    }
  } else {
    startNewConversation(targetMode);
  }
}

function switchSidebarMode(mode, syncMain = true) {
  activeSidebarMode = mode;
  const sideTabChat = document.getElementById('sideTabChat');
  const sideTabAgent = document.getElementById('sideTabAgent');
  const btnNewChatLabel = document.getElementById('btnNewChatLabel');

  if (mode === 'chat') {
    sideTabChat?.classList.add('active');
    sideTabAgent?.classList.remove('active');
    if (btnNewChatLabel) btnNewChatLabel.textContent = 'New Chat';
  } else {
    sideTabAgent?.classList.add('active');
    sideTabChat?.classList.remove('active');
    if (btnNewChatLabel) btnNewChatLabel.textContent = 'New Session';
  }

  if (syncMain && typeof setChatMode === 'function') {
    setChatMode(mode, false);
  }

  renderConversationGroups(conversationsCache);
  startNewConversation(mode);
}

function toggleSidebar() {
  const sidebar = document.getElementById('chatSidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  if (sidebar) {
    if (window.innerWidth <= 768) {
      const isMobileOpen = sidebar.classList.toggle('mobile-open');
      sidebar.classList.remove('collapsed');
      if (backdrop) backdrop.classList.toggle('active', isMobileOpen);
    } else {
      sidebar.classList.remove('mobile-open');
      if (backdrop) backdrop.classList.remove('active');
      sidebar.classList.toggle('collapsed');
    }
  }
}

function closeMobileSidebar() {
  if (window.innerWidth <= 768) {
    const sidebar = document.getElementById('chatSidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    if (sidebar) sidebar.classList.remove('mobile-open');
    if (backdrop) backdrop.classList.remove('active');
  }
}

async function loadConversations() {
  const listContainer = document.getElementById('conversationList');
  try {
    const res = await fetch('/api/conversations', {
      headers: getAuthHeaders()
    });
    if (!res.ok) return;

    conversationsCache = await res.json();
    renderConversationGroups(conversationsCache);
  } catch (err) {
    console.error('Failed to load conversations:', err);
  }
}

function renderConversationGroups(conversations) {
  const listContainer = document.getElementById('conversationList');
  if (!listContainer) return;

  listContainer.innerHTML = '';

  const currentMode = activeSidebarMode || 'chat';
  const modeFiltered = (conversations || []).filter(c => {
    const cMode = c.mode || 'chat';
    return cMode === currentMode;
  });

  if (!modeFiltered || modeFiltered.length === 0) {
    listContainer.innerHTML = `
      <div class="sidebar-empty-state">
        <i class="${currentMode === 'agent' ? 'fa-solid fa-bolt' : 'fa-regular fa-comments'}"></i>
        <span>No ${currentMode === 'agent' ? 'agent sessions' : 'conversations'} yet</span>
      </div>
    `;
    return;
  }

  // Group conversations by Date (Today, Yesterday, Previous 7 Days, Older)
  const groups = {
    'Today': [],
    'Yesterday': [],
    'Previous 7 Days': [],
    'Older': []
  };

  const now = new Date();
  const oneDay = 24 * 60 * 60 * 1000;

  modeFiltered.forEach(conv => {
    const date = new Date(conv.updated_at || conv.created_at);
    const diffDays = Math.floor((now - date) / oneDay);

    if (diffDays === 0 && now.getDate() === date.getDate()) {
      groups['Today'].push(conv);
    } else if (diffDays <= 1) {
      groups['Yesterday'].push(conv);
    } else if (diffDays <= 7) {
      groups['Previous 7 Days'].push(conv);
    } else {
      groups['Older'].push(conv);
    }
  });

  Object.entries(groups).forEach(([groupName, items]) => {
    if (items.length === 0) return;

    const header = document.createElement('div');
    header.className = 'conv-group-header';
    header.textContent = groupName;
    listContainer.appendChild(header);

    items.forEach(conv => {
      const item = document.createElement('div');
      item.className = `conv-item ${conv.id === activeConversationId ? 'active' : ''}`;
      item.id = `conv-${conv.id}`;

      const iconClass = conv.mode === 'agent' ? 'fa-solid fa-bolt agent-icon' : 'fa-regular fa-message';

      item.innerHTML = `
        <div class="conv-item-left">
          <i class="${iconClass}"></i>
          <span class="conv-item-title" title="${escapeHtml(conv.title)}">${escapeHtml(conv.title)}</span>
        </div>
        <div class="conv-item-actions">
          <button class="btn-conv-action btn-conv-edit" title="Rename"><i class="fa-solid fa-pencil"></i></button>
          <button class="btn-conv-action btn-conv-del" title="Delete"><i class="fa-regular fa-trash-can"></i></button>
        </div>
      `;

      item.querySelector('.conv-item-left').addEventListener('click', () => {
        selectConversation(conv.id);
      });

      item.querySelector('.btn-conv-edit').addEventListener('click', (e) => {
        e.stopPropagation();
        promptRenameConversation(conv.id, conv.title);
      });

      item.querySelector('.btn-conv-del').addEventListener('click', (e) => {
        e.stopPropagation();
        deleteConversationById(conv.id);
      });

      listContainer.appendChild(item);
    });
  });
}

function filterConversations(query) {
  if (!query) {
    renderConversationGroups(conversationsCache);
    return;
  }
  const filtered = conversationsCache.filter(c => c.title.toLowerCase().includes(query));
  renderConversationGroups(filtered);
}

async function selectConversation(convId, syncMode = true) {
  activeConversationId = convId;
  closeMobileSidebar();
  switchTab('tabChat');

  const selectedConv = (conversationsCache || []).find(c => c.id === convId);
  if (selectedConv && selectedConv.mode && syncMode && selectedConv.mode !== currentChatMode) {
    setChatMode(selectedConv.mode, true, false);
  }

  // Update active styling in sidebar
  document.querySelectorAll('.conv-item').forEach(item => {
    item.classList.toggle('active', item.id === `conv-${convId}`);
  });

  const chatContainer = document.getElementById('chatMessages');
  chatContainer.innerHTML = '<div class="splash-meta"><span>Loading thread messages...</span></div>';

  try {
    const res = await fetch(`/api/conversations/${convId}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Conversation not found');

    const data = await res.json();
    document.getElementById('activeThreadTitle').textContent = data.title;
    renderConversationMessages(data.messages);
  } catch (err) {
    showToast(`Failed to load thread: ${err.message}`, 'error');
  }
}

function renderConversationMessages(messages) {
  const container = document.getElementById('chatMessages');
  container.innerHTML = '';

  if (!messages || messages.length === 0) {
    renderEmptySplash();
    return;
  }

  messages.forEach(msg => {
    if (msg.role === 'user') {
      appendUserMessage(msg.content);
    } else if (msg.role === 'assistant') {
      const msgEl = createAssistantMessageElement();
      const contentEl = msgEl.querySelector('.message-content');
      const cursor = contentEl.querySelector('.cursor-typing');
      if (cursor) cursor.remove();
      const thinking = contentEl.querySelector('.thinking-indicator');
      if (thinking) thinking.remove();

      // Render Markdown response cleanly without raw tool dumps
      const mdText = msg.content || '';
      const textDiv = document.createElement('div');
      textDiv.className = 'markdown-rendered';
      if (window.marked && typeof window.marked.parse === 'function') {
        textDiv.innerHTML = marked.parse(mdText);
      } else {
        textDiv.textContent = mdText;
      }
      contentEl.appendChild(textDiv);

      if (window.Prism) {
        textDiv.querySelectorAll('pre code').forEach(block => Prism.highlightElement(block));
      }
    }
  });

  container.scrollTop = container.scrollHeight;
}

function startNewConversation(mode) {
  const targetMode = mode || currentChatMode || 'chat';
  activeConversationId = null;
  closeMobileSidebar();
  const titleEl = document.getElementById('activeThreadTitle');
  if (titleEl) {
    titleEl.textContent = targetMode === 'agent' ? 'New Session' : 'New Chat';
  }
  document.querySelectorAll('.conv-item').forEach(item => item.classList.remove('active'));
  renderEmptySplash();
  document.getElementById('promptInput')?.focus();
}

function renderEmptySplash() {
  const container = document.getElementById('chatMessages');
  container.innerHTML = `
    <div class="nvim-splash" id="nvimSplash">
      <pre class="ascii-banner">
  ███████╗██╗   ██╗███╗   ██╗████████╗██████╗  █████╗ ██╗  ██╗
  ██╔════╝╚██╗ ██╔╝████╗  ██║╚══██╔══╝██╔══██╗██╔══██╗██║ ██╔╝
  ███████╗ ╚████╔╝ ██╔██╗ ██║   ██║   ██████╔╝███████║█████╔╝ 
  ╚════██║  ╚██╔╝  ██║╚██╗██║   ██║   ██╔══██╗██╔══██║██╔═██╗ 
  ███████║   ██║   ██║ ╚████║   ██║   ██║  ██║██║  ██║██║  ██╗
  ╚══════╝   ╚═╝   ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
      </pre>
      <div class="splash-meta">
        <span>-- Autonomous Code Reviewer & Assistant --</span>
        <span>type <kbd>:help</kbd> or <kbd>/</kbd> for command palette &bull; <kbd>:Review</kbd> to audit diff</span>
      </div>
      <div class="quick-commands-grid">
        <div class="cmd-chip" onclick="sendQuickPrompt('/review')">
          <span class="cmd-key">:Review</span>
          <span class="cmd-desc">Run PR & diff quality audit</span>
        </div>
        <div class="cmd-chip" onclick="sendQuickPrompt('Analyze repository architecture and core components')">
          <span class="cmd-key">:Inspect</span>
          <span class="cmd-desc">Map module dependencies</span>
        </div>
        <div class="cmd-chip" onclick="sendQuickPrompt('Write pytest unit tests for key agent modules')">
          <span class="cmd-key">:Test</span>
          <span class="cmd-desc">Generate test suites</span>
        </div>
        <div class="cmd-chip" onclick="sendQuickPrompt('Scan codebase for security gaps and credential exposure')">
          <span class="cmd-key">:Audit</span>
          <span class="cmd-desc">Security & sanitize scan</span>
        </div>
      </div>
    </div>
  `;
}

function promptRenameConversation(convId, currentTitle) {
  const newTitle = prompt('Rename conversation title:', currentTitle);
  if (newTitle && newTitle.trim() && newTitle.trim() !== currentTitle) {
    updateConversationTitle(convId, newTitle.trim());
  }
}

async function updateConversationTitle(convId, title) {
  try {
    const res = await fetch(`/api/conversations/${convId}`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify({ title })
    });
    if (res.ok) {
      if (activeConversationId === convId) {
        document.getElementById('activeThreadTitle').textContent = title;
      }
      loadConversations();
      showToast('Conversation renamed.');
    }
  } catch (err) {
    showToast(`Rename failed: ${err.message}`, 'error');
  }
}

function enableTitleEdit() {
  const titleEl = document.getElementById('activeThreadTitle');
  if (!activeConversationId) return;

  titleEl.contentEditable = 'true';
  titleEl.focus();

  const handleBlur = () => {
    titleEl.contentEditable = 'false';
    const newTitle = titleEl.textContent.trim();
    if (newTitle) {
      updateConversationTitle(activeConversationId, newTitle);
    }
    titleEl.removeEventListener('blur', handleBlur);
  };

  titleEl.addEventListener('blur', handleBlur);
  titleEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      titleEl.blur();
    }
  });
}

async function deleteConversationById(convId) {
  if (!confirm('Are you sure you want to delete this conversation?')) return;

  try {
    const res = await fetch(`/api/conversations/${convId}`, {
      method: 'DELETE',
      headers: getAuthHeaders()
    });
    if (res.ok) {
      showToast('Conversation deleted.');
      if (activeConversationId === convId) {
        startNewConversation();
      }
      loadConversations();
    }
  } catch (err) {
    showToast(`Delete failed: ${err.message}`, 'error');
  }
}

function deleteCurrentActiveThread() {
  if (activeConversationId) {
    deleteConversationById(activeConversationId);
  } else {
    clearCurrentChat();
  }
}

function clearCurrentChat() {
  renderEmptySplash();
  fetch('/api/clear', { method: 'POST' }).catch(() => {});
  showToast(':clear Buffer reset.');
}

/* ==========================================================================
   Theme Selector (:colorscheme)
   ========================================================================== */
function initThemeSelector() {
  const select = document.getElementById('themeSelect');
  const savedTheme = localStorage.getItem('syntrak_theme') || 'gruvbox';

  document.documentElement.setAttribute('data-theme', savedTheme);
  if (select) {
    select.value = savedTheme;
    select.addEventListener('change', (e) => {
      setTheme(e.target.value);
    });
  }
}

function setTheme(themeName) {
  const validThemes = ['gruvbox', 'tokyonight', 'nord', 'monokai', 'solarized'];
  const theme = validThemes.includes(themeName) ? themeName : 'gruvbox';
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('syntrak_theme', theme);
  const select = document.getElementById('themeSelect');
  if (select) select.value = theme;
  showToast(`:colorscheme ${theme}`);
}

/* ==========================================================================
   Tab Navigation (Buffer switching)
   ========================================================================== */
function initTabs() {
  const tabBtns = document.querySelectorAll('.buffer-tab');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');
      switchTab(tabId);
    });
  });
}

function switchTab(tabId) {
  document.querySelectorAll('.buffer-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.window-pane').forEach(p => p.classList.remove('active'));

  const activeBtn = document.querySelector(`.buffer-tab[data-tab="${tabId}"]`);
  const activePanel = document.getElementById(tabId);

  if (activeBtn) activeBtn.classList.add('active');
  if (activePanel) activePanel.classList.add('active');

  const activeBufLabel = document.getElementById('stlActiveBuffer');
  if (activeBufLabel && activeBtn) {
    activeBufLabel.textContent = activeBtn.querySelector('.tab-name')?.textContent || 'buffer';
  }
}

/* ==========================================================================
   Mode Switcher (ChatGPT Chat vs Repo Agent) & Repository Authorization
   ========================================================================== */
function initModeSwitcher() {
  const btnChat = document.getElementById('btnModeChat');
  const btnAgent = document.getElementById('btnModeAgent');
  const repoBadge = document.getElementById('repoBadgeStatus');
  const modal = document.getElementById('repoAuthModal');
  const btnCloseModal = document.getElementById('btnCloseRepoModal');
  const btnCancelAuth = document.getElementById('btnCancelRepoAuth');
  const btnConnectRepo = document.getElementById('btnConnectRepo');

  function updateModeUI() {
    const stlMode = document.getElementById('stlMode');
    const stlArrow1 = document.getElementById('stlArrow1');
    const promptInput = document.getElementById('promptInput');
    const repoBadgeText = document.getElementById('repoBadgeText');

    if (currentChatMode === 'chat') {
      btnChat?.classList.add('active');
      btnAgent?.classList.remove('active', 'agent-active');
      if (stlMode) {
        stlMode.textContent = 'CHAT';
        stlMode.className = 'stl-mode chat';
      }
      if (stlArrow1) {
        stlArrow1.className = 'stl-arrow-1 chat';
      }
      if (promptInput) {
        promptInput.placeholder = 'Ask anything in Chat mode, or switch to Agent mode for repo coding...';
      }
    } else {
      btnAgent?.classList.add('active', 'agent-active');
      btnChat?.classList.remove('active');
      if (stlMode) {
        stlMode.textContent = 'AGENT';
        stlMode.className = 'stl-mode agent';
      }
      if (stlArrow1) {
        stlArrow1.className = 'stl-arrow-1 agent';
      }
      if (promptInput) {
        promptInput.placeholder = 'Ask a question, request code changes, or type / for commands...';
      }
    }

    if (repoBadge && repoBadgeText) {
      const savedRepo = localStorage.getItem('syntrak_connected_repo');
      if (isRepoAuthorized) {
        repoBadge.classList.add('connected');
        repoBadgeText.textContent = savedRepo || 'Repo Connected';
        repoBadge.title = `Connected to ${savedRepo || 'Repository'}. Click to manage.`;
      } else {
        repoBadge.classList.remove('connected');
        repoBadgeText.textContent = 'Repo Locked';
        repoBadge.title = 'No repository connected. Click to connect your GitHub repo.';
      }
    }
  }

  async function openRepoModal() {
    if (!modal) return;
    modal.classList.remove('hidden');
    try {
      const res = await fetch('/api/repo/info', { headers: getAuthHeaders() });
      if (res.ok) {
        const info = await res.json();
        const modalCurrentRepo = document.getElementById('modalCurrentRepo');
        if (modalCurrentRepo) {
          modalCurrentRepo.textContent = info.is_git_repo && info.repo_name ? `${info.repo_name} (${info.branch || 'main'})` : 'None (Chat Mode)';
        }
      }
    } catch (e) {
      console.error('Failed to load repo info:', e);
    }
  }

  function closeRepoModal() {
    if (modal) modal.classList.add('hidden');
  }

  function setChatMode(mode, syncSidebar = true) {
    currentChatMode = mode;
    activeSidebarMode = mode;
    localStorage.setItem('syntrak_chat_mode', mode);
    updateModeUI();
    if (syncSidebar && typeof switchSidebarMode === 'function') {
      switchSidebarMode(mode, false);
    } else {
      renderConversationGroups(conversationsCache);
      startNewConversation(mode);
    }
  }
  window.setChatMode = setChatMode;

  btnChat?.addEventListener('click', () => {
    setChatMode('chat', true);
    showToast('Switched to Chat Mode (ChatGPT-style conversational assistant)');
  });

  btnAgent?.addEventListener('click', () => {
    if (!isRepoAuthorized) {
      openRepoModal();
    } else {
      setChatMode('agent', true);
      showToast('Switched to Agent Mode (Autonomous repo coding & tools enabled)');
    }
  });

  repoBadge?.addEventListener('click', () => {
    openRepoModal();
  });

  btnCloseModal?.addEventListener('click', closeRepoModal);
  btnCancelAuth?.addEventListener('click', closeRepoModal);

  btnConnectRepo?.addEventListener('click', async () => {
    const repoUrl = document.getElementById('modalRepoUrl')?.value.trim();
    const githubToken = document.getElementById('modalGithubToken')?.value.trim();
    const branch = document.getElementById('modalBranch')?.value.trim() || 'main';

    if (!repoUrl) {
      showToast('Please enter your GitHub repository URL or owner/repo name.', 'error');
      return;
    }

    btnConnectRepo.disabled = true;
    btnConnectRepo.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Connecting...';

    try {
      const payload = { repo_url: repoUrl, github_token: githubToken || null, branch };

      const res = await fetch('/api/repo/connect', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned ${res.status}`);
      }

      const data = await res.json();
      isRepoAuthorized = true;
      localStorage.setItem('syntrak_repo_authorized', 'true');
      localStorage.setItem('syntrak_connected_repo', data.repo_name);

      startNewConversation('agent');
      setChatMode('agent', true, false);

      const headerWorkspace = document.getElementById('headerWorkspace');
      if (headerWorkspace) headerWorkspace.textContent = `${data.repo_name} (${data.branch || 'main'})`;

      closeRepoModal();
      updateModeUI();
      showToast(data.message || `Connected to ${data.repo_name}! Switched to Agent Mode.`);
    } catch (err) {
      showToast(`Connection failed: ${err.message}`, 'error');
    } finally {
      btnConnectRepo.disabled = false;
      btnConnectRepo.innerHTML = '<i class="fa-solid fa-plug"></i> Connect & Enable Agent';
    }
  });

  updateModeUI();
}


/* ==========================================================================
   Session & Git Controls
   ========================================================================== */
async function loadSessionStatus() {
  try {
    const res = await fetch('/api/session/status', {
      headers: getAuthHeaders()
    });
    if (!res.ok) return;
    const data = await res.json();

    const shortModel = (data.model || 'Unknown').split('/').pop();
    document.getElementById('headerModelName').textContent = shortModel;

    const headerWs = document.getElementById('headerWorkspace');
    if (headerWs) {
      if (data.has_connected_repo && data.connected_repo_name) {
        headerWs.textContent = data.connected_repo_name;
        headerWs.title = `Connected Workspace: ${data.workspace_root || data.connected_repo_name}`;
      } else {
        headerWs.textContent = 'No Repo';
        headerWs.title = 'No repository connected. Click Agent mode to connect a repo.';
      }
    }

    document.getElementById('cfgModel').value = data.model || '';
    document.getElementById('cfgApiBase').value = data.api_base || '';

    initGoogleSignInButton(data.google_client_id);

    if (data.user) {
      renderUserProfile(data.user);
    }
  } catch (err) {
    console.error('Failed to load session status:', err);
  }
}

function initGoogleSignInButton(clientId) {
  const container = document.getElementById('googleSignInContainer');
  if (!container) return;

  if (!clientId) {
    container.innerHTML = `
      <div class="btn-setup-google" style="cursor: default;" title="Set GOOGLE_CLIENT_ID in .env file">
        <i class="fa-brands fa-google"></i>
        <span>Sign In (Set in .env)</span>
      </div>
    `;
    return;
  }

  const tryRender = () => {
    if (window.google && window.google.accounts && window.google.accounts.id) {
      container.innerHTML = '';
      try {
        google.accounts.id.initialize({
          client_id: clientId,
          callback: window.handleGoogleCredential
        });
        google.accounts.id.renderButton(container, {
          theme: 'outline',
          size: 'medium',
          type: 'standard',
          shape: 'rectangular'
        });
      } catch (gErr) {
        console.warn('Google GIS render error:', gErr);
      }
    } else {
      setTimeout(tryRender, 300);
    }
  };

  tryRender();
}

async function handleUndo() {
  try {
    const res = await fetch('/api/undo', { method: 'POST' });
    const data = await res.json();
    showToast(data.result || 'Undo executed.');
  } catch (err) {
    showToast(`Undo failed: ${err.message}`, 'error');
  }
}

async function handleConfigSave(e) {
  e.preventDefault();
  const model = document.getElementById('cfgModel').value.trim();
  const api_base = document.getElementById('cfgApiBase').value.trim() || null;
  const api_key = document.getElementById('cfgApiKey').value.trim() || null;

  try {
    const res = await fetch('/api/model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, api_base, api_key })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`:w config saved. Active model: ${data.active_model}`);
      loadSessionStatus();
    }
  } catch (err) {
    showToast(`Config error: ${err.message}`, 'error');
  }
}

/* ==========================================================================
   Chat & SSE Stream Execution
   ========================================================================== */
function initChatForm() {
  const form = document.getElementById('chatForm');
  const input = document.getElementById('promptInput');
  const btnSend = document.getElementById('btnSend');
  const btnStop = document.getElementById('btnStop');

  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
  });

  function submitCurrentInput() {
    const query = input.value.trim();
    if (!query) return;

    input.value = '';
    input.style.height = 'auto';
    hideSlashPopup();

    if (query === '/clear' || query === ':clear') {
      clearCurrentChat();
      return;
    }
    if (query === '/undo' || query === ':undo') {
      handleUndo();
      return;
    }
    if (query.startsWith(':colorscheme ') || query.startsWith(':cs ')) {
      const theme = query.split(' ')[1]?.trim();
      setTheme(theme);
      return;
    }
    if (query === ':w' || query === ':config') {
      switchTab('tabConfig');
      return;
    }
    if (query === ':Review' || query === '/review') {
      switchTab('tabChat');
    }

    runQueryStream(query);
  }

  btnSend?.addEventListener('click', (e) => {
    e.preventDefault();
    submitCurrentInput();
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitCurrentInput();
    }
  });

  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      submitCurrentInput();
    });
  }

  btnStop?.addEventListener('click', (e) => {
    e.preventDefault();
    if (activeAbortController) {
      activeAbortController.abort();
      setGeneratingState(false);
    }
  });
}

function sendQuickPrompt(promptText) {
  const input = document.getElementById('promptInput');
  if (input) {
    switchTab('tabChat');
    input.value = promptText;
    const btnSend = document.getElementById('btnSend');
    if (btnSend) btnSend.click();
  }
}

async function runQueryStream(query) {
  // Remove splash screen if visible
  const splash = document.getElementById('nvimSplash');
  if (splash) splash.remove();

  appendUserMessage(query);

  const assistantMsgEl = createAssistantMessageElement();
  const contentEl = assistantMsgEl.querySelector('.message-content');
  let accumulatedMarkdown = '';

  activeAbortController = new AbortController();
  setGeneratingState(true);

  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        query,
        conversation_id: activeConversationId,
        mode: currentChatMode,
        repo_authorized: isRepoAuthorized
      }),
      signal: activeAbortController.signal
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}: ${response.statusText}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop();

      for (const block of blocks) {
        const lines = block.split('\n');
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            const jsonStr = trimmed.substring(6);
            try {
              const event = JSON.parse(jsonStr);

              if (event.event_type === 'conversation_init') {
                activeConversationId = event.conversation_id;
                document.getElementById('activeThreadTitle').textContent = query.substring(0, 35);
                loadConversations();
              } else {
                handleAgentEvent(event, contentEl, accumulatedMarkdown, (newMd) => {
                  accumulatedMarkdown = newMd;
                });
              }
            } catch (e) {
              console.error('Failed to parse SSE JSON:', jsonStr, e);
            }
          }
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      appendSystemNote(contentEl, '-- Interrupted by user --');
    } else {
      appendSystemNote(contentEl, `Error: ${err.message}`, 'error');
    }
  } finally {
    setGeneratingState(false);
    activeAbortController = null;
    loadConversations();
  }
}

function handleAgentEvent(event, contentEl, accumulatedMd, setMdCallback) {
  const messagesContainer = document.getElementById('chatMessages');

  if (event.event_type === 'token_stream') {
    // Remove thinking indicator as soon as text tokens stream
    const thinking = contentEl.querySelector('.thinking-indicator');
    if (thinking) thinking.remove();
    const cursor = contentEl.querySelector('.cursor-typing');
    if (cursor) cursor.remove();

    const newMd = accumulatedMd + event.token;
    setMdCallback(newMd);

    let textDiv = contentEl.querySelector('.markdown-rendered');
    if (!textDiv) {
      textDiv = document.createElement('div');
      textDiv.className = 'markdown-rendered';
      contentEl.appendChild(textDiv);
    }

    if (window.marked && typeof window.marked.parse === 'function') {
      textDiv.innerHTML = marked.parse(newMd);
    } else {
      textDiv.textContent = newMd;
    }

    if (window.Prism) {
      textDiv.querySelectorAll('pre code').forEach((block) => {
        Prism.highlightElement(block);
      });
    }
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  } else if (event.event_type === 'agent_status' || event.event_type === 'tool_start' || event.event_type === 'tool_result' || event.event_type === 'thought_stream') {
    // Keep the clean thinking... indicator active throughout processing
    if (!contentEl.querySelector('.markdown-rendered') && !contentEl.querySelector('.thinking-indicator')) {
      const thinking = document.createElement('div');
      thinking.className = 'thinking-indicator';
      thinking.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> <span>thinking...</span>`;
      contentEl.appendChild(thinking);
    }
  } else if (event.event_type === 'error') {
    const thinking = contentEl.querySelector('.thinking-indicator');
    if (thinking) thinking.remove();
    const cursor = contentEl.querySelector('.cursor-typing');
    if (cursor) cursor.remove();
    appendSystemNote(contentEl, event.message, 'error');
  }
}

/* ==========================================================================
   DOM & UI Helpers
   ========================================================================== */
function appendUserMessage(text) {
  const container = document.getElementById('chatMessages');
  const msg = document.createElement('div');
  msg.className = 'message user-message';
  const nameLabel = currentUser?.name || 'enky';
  msg.innerHTML = `
    <div class="user-prompt-badge">
      <span class="user-host">❯ ${escapeHtml(nameLabel)}@syntrak</span>
      <span class="user-branch">(main )</span>
      <span>$</span>
    </div>
    <div class="message-content"><p>${escapeHtml(text)}</p></div>
  `;
  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
}

function createAssistantMessageElement() {
  const container = document.getElementById('chatMessages');
  const msg = document.createElement('div');
  msg.className = 'message assistant-message';
  msg.innerHTML = `
    <div class="user-prompt-badge">
      <span style="color: var(--color-blue)">󰚩 syntrak[agent]</span>
      <span style="color: var(--text-dim)">&gt;</span>
    </div>
    <div class="message-content">
      <div class="thinking-indicator">
        <i class="fa-solid fa-circle-notch fa-spin"></i>
        <span>thinking...</span>
      </div>
    </div>
  `;
  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
  return msg;
}

function appendSystemNote(contentEl, text, type = 'info') {
  const note = document.createElement('div');
  note.style.color = type === 'error' ? 'var(--color-red)' : 'var(--text-dim)';
  note.style.fontSize = '12px';
  note.style.marginTop = '6px';
  note.textContent = text;
  contentEl.appendChild(note);
}

function initSlashPopup() {
  const input = document.getElementById('promptInput');
  const popup = document.getElementById('slashPopup');

  input.addEventListener('input', () => {
    if (input.value === '/' || input.value === ':') {
      popup.style.display = 'flex';
    } else {
      popup.style.display = 'none';
    }
  });

  document.querySelectorAll('.slash-row').forEach(item => {
    item.addEventListener('click', () => {
      const cmd = item.getAttribute('data-cmd');
      input.value = cmd;
      popup.style.display = 'none';
      const btnSend = document.getElementById('btnSend');
      if (btnSend) btnSend.click();
    });
  });
}

function hideSlashPopup() {
  const popup = document.getElementById('slashPopup');
  if (popup) popup.style.display = 'none';
}

function setGeneratingState(isGenerating) {
  const btnSend = document.getElementById('btnSend');
  const btnStop = document.getElementById('btnStop');
  const stlMode = document.getElementById('stlMode');
  const stlArrow1 = document.querySelector('.stl-arrow-1');

  if (isGenerating) {
    btnSend?.classList.add('hidden');
    btnStop?.classList.remove('hidden');
    if (stlMode) {
      stlMode.textContent = 'EXEC';
      stlMode.className = 'stl-mode exec';
    }
    if (stlArrow1) {
      stlArrow1.className = 'stl-arrow-1 exec';
    }
  } else {
    btnSend?.classList.remove('hidden');
    btnStop?.classList.add('hidden');
    if (stlMode) {
      stlMode.textContent = 'NORMAL';
      stlMode.className = 'stl-mode';
    }
    if (stlArrow1) {
      stlArrow1.className = 'stl-arrow-1';
    }
  }
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast-msg';
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 3500);
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
}
