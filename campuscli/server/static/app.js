/**
 * CampusCLI Web UI Client Logic
 */

let activeAbortController = null;

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initSlashPopup();
  initChatForm();
  loadSessionStatus();
  loadGitDiff();

  document.getElementById('btnRefreshDiff')?.addEventListener('click', loadGitDiff);
  document.getElementById('btnQuickDiff')?.addEventListener('click', () => {
    switchTab('tabDiff');
    loadGitDiff();
  });
  document.getElementById('btnQuickReview')?.addEventListener('click', () => {
    sendQuickPrompt('/review');
  });
  document.getElementById('btnQuickUndo')?.addEventListener('click', handleUndo);
  document.getElementById('btnClearChat')?.addEventListener('click', clearChat);
  document.getElementById('btnSettings')?.addEventListener('click', () => {
    switchTab('tabConfig');
  });
  document.getElementById('modelPill')?.addEventListener('click', () => {
    switchTab('tabConfig');
  });
  document.getElementById('configForm')?.addEventListener('submit', handleConfigSave);
});

/* Tab Navigation */
function initTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');
      switchTab(tabId);
    });
  });
}

function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

  const activeBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
  const activePanel = document.getElementById(tabId);

  if (activeBtn) activeBtn.classList.add('active');
  if (activePanel) activePanel.classList.add('active');
}

/* Load Session Metadata */
async function loadSessionStatus() {
  try {
    const res = await fetch('/api/session/status');
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById('headerModelName').textContent = data.model || 'Unknown';
    document.getElementById('headerWorkspace').textContent = data.workspace_root.split('/').pop() || 'Workspace';
    document.getElementById('cfgModel').value = data.model || '';
    document.getElementById('cfgApiBase').value = data.api_base || '';
  } catch (err) {
    console.error('Failed to load session status:', err);
  }
}

/* Load Git Diff */
async function loadGitDiff() {
  const viewer = document.getElementById('diffViewer');
  if (!viewer) return;

  try {
    viewer.textContent = 'Loading git diff...';
    const res = await fetch('/api/diff');
    const data = await res.json();

    viewer.textContent = data.diff || 'No changes detected in working tree.';
    if (window.Prism) {
      Prism.highlightElement(viewer);
    }
  } catch (err) {
    viewer.textContent = `Error loading diff: ${err.message}`;
  }
}

/* Undo Action */
async function handleUndo() {
  try {
    const res = await fetch('/api/undo', { method: 'POST' });
    const data = await res.json();
    showToast(data.result || 'Undo executed.');
    loadGitDiff();
  } catch (err) {
    showToast(`Undo failed: ${err.message}`, 'error');
  }
}

/* Model Switch */
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
      showToast(`Switched model to ${data.active_model}`);
      loadSessionStatus();
    }
  } catch (err) {
    showToast(`Failed to switch model: ${err.message}`, 'error');
  }
}

function applyPreset(model, api_base, api_key) {
  document.getElementById('cfgModel').value = model;
  document.getElementById('cfgApiBase').value = api_base;
  document.getElementById('cfgApiKey').value = api_key;
}

/* Chat & SSE Stream */
function initChatForm() {
  const form = document.getElementById('chatForm');
  const input = document.getElementById('promptInput');
  const btnStop = document.getElementById('btnStop');

  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      form.dispatchEvent(new Event('submit'));
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = input.value.trim();
    if (!query) return;

    input.value = '';
    input.style.height = 'auto';
    hideSlashPopup();

    if (query === '/clear') {
      clearChat();
      return;
    }
    if (query === '/diff') {
      switchTab('tabDiff');
      loadGitDiff();
      return;
    }
    if (query === '/undo') {
      handleUndo();
      return;
    }

    await runQueryStream(query);
  });

  btnStop?.addEventListener('click', () => {
    if (activeAbortController) {
      activeAbortController.abort();
      setGeneratingState(false);
    }
  });
}

function sendQuickPrompt(promptText) {
  const input = document.getElementById('promptInput');
  if (input) {
    input.value = promptText;
    document.getElementById('chatForm').dispatchEvent(new Event('submit'));
  }
}

async function runQueryStream(query) {
  appendUserMessage(query);

  const assistantMsgEl = createAssistantMessageElement();
  const contentEl = assistantMsgEl.querySelector('.message-content');
  let accumulatedMarkdown = '';

  activeAbortController = new AbortController();
  setGeneratingState(true);

  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
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
      const lines = buffer.split('\n\n');
      buffer = lines.pop(); // keep last incomplete line

      for (const block of lines) {
        const line = block.trim();
        if (line.startsWith('data: ')) {
          const jsonStr = line.substring(6);
          try {
            const event = JSON.parse(jsonStr);
            handleAgentEvent(event, contentEl, accumulatedMarkdown, (newMd) => {
              accumulatedMarkdown = newMd;
            });
          } catch (e) {
            console.error('Failed to parse SSE JSON:', jsonStr, e);
          }
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      appendSystemNote(contentEl, 'Generation stopped by user.');
    } else {
      appendSystemNote(contentEl, `Error: ${err.message}`, 'error');
    }
  } finally {
    setGeneratingState(false);
    activeAbortController = null;
    loadGitDiff();
  }
}

function handleAgentEvent(event, contentEl, accumulatedMd, setMdCallback) {
  const messagesContainer = document.getElementById('chatMessages');

  if (event.event_type === 'token_stream') {
    const newMd = accumulatedMd + event.token;
    setMdCallback(newMd);
    contentEl.innerHTML = marked.parse(newMd);
    highlightCodeBlocks(contentEl);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  } else if (event.event_type === 'tool_start') {
    const card = document.createElement('div');
    card.className = 'tool-card';
    card.id = `tool-${event.tool_id}`;
    card.innerHTML = `
      <div class="tool-card-header">
        <span><i class="fa-solid fa-gear fa-spin"></i> Executing: ${event.tool_name}</span>
      </div>
      <div class="tool-card-body">${escapeHtml(JSON.stringify(event.arguments, null, 2))}</div>
    `;
    contentEl.appendChild(card);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  } else if (event.event_type === 'tool_result') {
    const card = contentEl.querySelector(`#tool-${event.tool_id}`);
    if (card) {
      card.classList.add(event.success ? 'tool-result-success' : 'tool-result-error');
      card.querySelector('.tool-card-header').innerHTML = `
        <span><i class="fa-solid fa-check"></i> ${event.tool_name} Finished</span>
      `;
      card.querySelector('.tool-card-body').textContent = String(event.output || event.error);
    }
  } else if (event.event_type === 'error') {
    appendSystemNote(contentEl, event.message, 'error');
  }
}

/* Message DOM helpers */
function appendUserMessage(text) {
  const container = document.getElementById('chatMessages');
  const msg = document.createElement('div');
  msg.className = 'message user-message';
  msg.innerHTML = `
    <div class="message-avatar"><i class="fa-solid fa-user"></i></div>
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
    <div class="message-avatar"><i class="fa-solid fa-robot"></i></div>
    <div class="message-content"><span class="cursor-typing">Thinking...</span></div>
  `;
  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
  return msg;
}

function appendSystemNote(contentEl, text, type = 'info') {
  const note = document.createElement('div');
  note.style.color = type === 'error' ? 'var(--error)' : 'var(--text-muted)';
  note.style.fontSize = '0.8rem';
  note.style.marginTop = '0.5rem';
  note.textContent = text;
  contentEl.appendChild(note);
}

function highlightCodeBlocks(container) {
  if (window.Prism) {
    container.querySelectorAll('pre code').forEach((block) => {
      Prism.highlightElement(block);
    });
  }
}

function clearChat() {
  const container = document.getElementById('chatMessages');
  container.innerHTML = `
    <div class="message assistant-message welcome-card">
      <div class="message-avatar"><i class="fa-solid fa-robot"></i></div>
      <div class="message-content">
        <h3>🧹 Chat Cleared</h3>
        <p>Conversation memory reset. What would you like to work on next?</p>
      </div>
    </div>
  `;
  fetch('/api/clear', { method: 'POST' }).catch(() => {});
}

/* Slash Command Menu */
function initSlashPopup() {
  const input = document.getElementById('promptInput');
  const popup = document.getElementById('slashPopup');

  input.addEventListener('input', () => {
    if (input.value === '/') {
      popup.style.display = 'flex';
    } else {
      popup.style.display = 'none';
    }
  });

  document.querySelectorAll('.slash-item').forEach(item => {
    item.addEventListener('click', () => {
      const cmd = item.getAttribute('data-cmd');
      input.value = cmd;
      popup.style.display = 'none';
      document.getElementById('chatForm').dispatchEvent(new Event('submit'));
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

  if (isGenerating) {
    btnSend?.classList.add('hidden');
    btnStop?.classList.remove('hidden');
  } else {
    btnSend?.classList.remove('hidden');
    btnStop?.classList.add('hidden');
  }
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast';
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
