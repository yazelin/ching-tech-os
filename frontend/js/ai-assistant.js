/**
 * ChingTech OS - AI Assistant Application
 * ChatGPT-style AI chat interface with DB persistence
 */

const AIAssistantApp = (function() {
  'use strict';

  // Application state
  const APP_ID = 'ai-assistant';
  let windowId = null;
  let chats = [];
  let currentChatId = null;
  let sidebarCollapsed = false;
  let availableAgents = [];
  let isCompressing = false;

  // Token estimation constants
  const TOKEN_LIMIT = 200000;
  const WARNING_THRESHOLD = 0.75; // 75%

  // Model display names mapping
  const modelDisplayNames = {
    'claude-opus': 'Claude Opus',
    'claude-sonnet': 'Claude Sonnet',
    'claude-haiku': 'Claude Haiku'
  };

  /**
   * 取得認證 headers
   */
  function getAuthHeaders() {
    const token = LoginModule?.getToken?.() || localStorage.getItem('chingtech_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  }

  /**
   * Estimate tokens from text (simplified: ~2 chars per token)
   * @param {string} text
   * @returns {number}
   */
  function estimateTokens(text) {
    if (!text) return 0;
    return Math.ceil(text.length / 2);
  }

  /**
   * Calculate total tokens for a chat
   * @param {Array} messages
   * @returns {number}
   */
  function getChatTokens(messages) {
    if (!messages || !Array.isArray(messages)) return 0;
    return messages.reduce((sum, msg) => sum + estimateTokens(msg.content || ''), 0);
  }

  /**
   * Load chats from API
   */
  async function loadChats() {
    try {
      if (typeof APIClient !== 'undefined') {
        chats = await APIClient.getChats();
      } else {
        console.warn('[AIAssistant] APIClient not available, using empty chats');
        chats = [];
      }
    } catch (e) {
      console.error('[AIAssistant] Failed to load chats:', e);
      chats = [];
    }
  }

  /**
   * Load available agents from API
   */
  async function loadAgents() {
    try {
      const response = await fetch('/api/ai/agents', {
        headers: getAuthHeaders()
      });
      if (response.ok) {
        const data = await response.json();
        availableAgents = (data.items || []).filter(a => a.is_active);
      } else {
        availableAgents = [];
      }
    } catch (e) {
      console.error('[AIAssistant] Failed to load agents:', e);
      availableAgents = [];
    }

    // 確保有預設選項
    if (availableAgents.length === 0) {
      availableAgents = [{ name: 'web-chat-default', display_name: '預設對話', model: 'claude-sonnet' }];
    }
  }

  /**
   * Create a new chat via API
   * @param {string} agentName - Agent 名稱
   * @returns {Object} New chat object
   */
  async function createChat(agentName = 'web-chat-default') {
    try {
      // 從 agent 取得對應的 model
      const agent = availableAgents.find(a => a.name === agentName);
      const model = agent?.model || 'claude-sonnet';

      if (typeof APIClient !== 'undefined') {
        const chat = await APIClient.createChat({
          title: '新對話',
          model: model,
          prompt_name: agentName, // 保持向後相容，用 prompt_name 儲存 agent name
        });
        chats.unshift(chat);
        return chat;
      }
    } catch (e) {
      console.error('[AIAssistant] Failed to create chat:', e);
    }
    return null;
  }

  /**
   * Get chat by ID
   * @param {string} chatId
   * @returns {Object|null}
   */
  function getChatById(chatId) {
    return chats.find(c => c.id === chatId) || null;
  }

  /**
   * Update model display text
   * @param {string} modelId
   */
  function updateModelDisplay(modelId) {
    const modelNameEl = document.querySelector(`#${windowId} .ai-model-name`);
    if (modelNameEl) {
      modelNameEl.textContent = modelDisplayNames[modelId] || modelId;
    }
  }

  /**
   * Delete a chat via API
   * @param {string} chatId
   */
  async function deleteChat(chatId) {
    try {
      if (typeof APIClient !== 'undefined') {
        await APIClient.deleteChat(chatId);
      }

      const index = chats.findIndex(c => c.id === chatId);
      if (index > -1) {
        chats.splice(index, 1);

        if (currentChatId === chatId) {
          if (chats.length > 0) {
            currentChatId = chats[0].id;
          } else {
            const newChat = await createChat();
            if (newChat) {
              currentChatId = newChat.id;
            }
          }
        }
        renderChatList();
        renderMessages();
      }
    } catch (e) {
      console.error('[AIAssistant] Failed to delete chat:', e);
    }
  }

  /**
   * Build window content HTML
   * @returns {string}
   */
  function buildWindowContent() {
    return `
      <div class="ai-assistant">
        <div class="ai-sidebar-overlay"></div>
        <aside class="ai-sidebar">
          <div class="ai-sidebar-header">
            <button class="ai-sidebar-toggle btn btn-ghost" title="收合側邊欄">
              <span class="icon">${getIcon('chevron-left')}</span>
            </button>
            <button class="ai-new-chat-btn btn btn-primary" title="新對話">
              <span class="icon">${getIcon('plus')}</span>
              <span class="ai-new-chat-text">新對話</span>
            </button>
          </div>
          <div class="ai-chat-list">
            <!-- Chat items will be rendered here -->
          </div>
        </aside>
        <main class="ai-main">
          <header class="ai-toolbar">
            <button class="ai-sidebar-expand btn btn-ghost" title="展開側邊欄" style="display: none;">
              <span class="icon">${getIcon('menu')}</span>
            </button>
            <div class="ai-agent-selector">
              <label>Agent：</label>
              <select class="ai-agent-select input">
                ${availableAgents.map(a => `<option value="${a.name}">${a.display_name || a.name}</option>`).join('')}
              </select>
            </div>
            <div class="ai-model-info">
              <span class="ai-model-label">模型：</span>
              <span class="ai-model-name">${availableAgents[0]?.model || 'claude-sonnet'}</span>
            </div>
            <div class="ai-token-info">
              <span class="ai-token-count">0</span>
              <span class="ai-token-separator">/</span>
              <span class="ai-token-limit">${TOKEN_LIMIT.toLocaleString()}</span>
            </div>
          </header>
          <div class="ai-token-warning" style="display: none;">
            <span class="ai-warning-text"></span>
            <button class="ai-compress-btn btn btn-warning">壓縮對話</button>
          </div>
          <div class="ai-messages">
            <div class="ai-messages-container">
              <!-- Messages will be rendered here -->
            </div>
          </div>
          <div class="ai-input-area">
            <div class="ai-input-wrapper">
              <textarea class="ai-input input" placeholder="輸入訊息..." rows="1"></textarea>
              <button class="ai-send-btn btn btn-accent" title="送出">
                <span class="icon">${getIcon('send')}</span>
              </button>
            </div>
          </div>
        </main>
      </div>
    `;
  }

  /**
   * Render chat list in sidebar
   */
  function renderChatList() {
    const container = document.querySelector(`#${windowId} .ai-chat-list`);
    if (!container) return;

    if (chats.length === 0) {
      UIHelpers.showEmpty(container, {
        icon: 'chat',
        text: '尚無對話',
      });
      return;
    }

    container.innerHTML = chats.map(chat => `
      <div class="ai-chat-item ${chat.id === currentChatId ? 'active' : ''}" data-chat-id="${chat.id}">
        <span class="ai-chat-item-icon icon">${getIcon('chat')}</span>
        <span class="ai-chat-item-title">${chat.title}</span>
        <button class="ai-chat-item-delete btn btn-ghost" title="刪除對話">
          <span class="icon">${getIcon('delete')}</span>
        </button>
      </div>
    `).join('');

    // Bind click events
    container.querySelectorAll('.ai-chat-item').forEach(item => {
      item.addEventListener('click', (e) => {
        if (e.target.closest('.ai-chat-item-delete')) return;
        switchChat(item.dataset.chatId);
      });
    });

    container.querySelectorAll('.ai-chat-item-delete').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const chatId = btn.closest('.ai-chat-item').dataset.chatId;
        deleteChat(chatId);
      });
    });
  }

  /**
   * Render messages for current chat
   */
  function renderMessages() {
    const container = document.querySelector(`#${windowId} .ai-messages-container`);
    if (!container) return;

    const chat = getChatById(currentChatId);
    const messages = chat?.messages || [];

    if (messages.length === 0) {
      container.innerHTML = `
        <div class="ai-welcome">
          <span class="ai-welcome-icon icon">${getIcon('robot')}</span>
          <h2>AI 助手</h2>
          <p>有什麼我可以幫助你的嗎？</p>
        </div>
      `;
    } else {
      container.innerHTML = messages.map(msg => {
        // Skip system summary messages in display (or show differently)
        if (msg.is_summary) {
          return `
            <div class="ai-message ai-message-summary">
              <div class="ai-message-content">
                <div class="ai-message-role">對話摘要</div>
                <div class="ai-message-text">${escapeHtml(msg.content)}</div>
              </div>
            </div>
          `;
        }
        // 使用者訊息使用純文字，AI 回應使用 Markdown 渲染
        const isAssistant = msg.role === 'assistant';
        const messageContent = isAssistant ? renderMarkdown(msg.content) : escapeHtml(msg.content);
        const textClass = isAssistant ? 'ai-message-text markdown-rendered' : 'ai-message-text';
        return `
          <div class="ai-message ai-message-${msg.role}">
            <div class="ai-message-avatar">
              <span class="icon">${getIcon(msg.role === 'user' ? 'account' : 'robot')}</span>
            </div>
            <div class="ai-message-content">
              <div class="ai-message-role">${msg.role === 'user' ? '你' : 'AI 助手'}</div>
              <div class="${textClass}">${messageContent}</div>
            </div>
          </div>
        `;
      }).join('');
    }

    // Scroll to bottom
    const messagesArea = document.querySelector(`#${windowId} .ai-messages`);
    if (messagesArea) {
      messagesArea.scrollTop = messagesArea.scrollHeight;
    }

    // Update token count and warning
    updateTokenDisplay(messages);
  }

  /**
   * Update token display and warning
   * @param {Array} messages
   */
  function updateTokenDisplay(messages) {
    const tokens = getChatTokens(messages);
    const percentage = tokens / TOKEN_LIMIT;

    // Update token count
    const tokenCount = document.querySelector(`#${windowId} .ai-token-count`);
    if (tokenCount) {
      tokenCount.textContent = tokens.toLocaleString();
      tokenCount.className = 'ai-token-count' + (percentage > WARNING_THRESHOLD ? ' warning' : '');
    }

    // Update warning bar
    const warningBar = document.querySelector(`#${windowId} .ai-token-warning`);
    const warningText = document.querySelector(`#${windowId} .ai-warning-text`);
    if (warningBar && warningText) {
      if (percentage > WARNING_THRESHOLD) {
        const pct = Math.round(percentage * 100);
        warningText.textContent = `對話過長 (${pct}%)，建議壓縮以維持 AI 回應品質`;
        warningBar.style.display = 'flex';
      } else {
        warningBar.style.display = 'none';
      }
    }
  }

  /**
   * Escape HTML special characters (用於使用者訊息)
   * @param {string} text
   * @returns {string}
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
  }

  /**
   * Render Markdown content (用於 AI 回應)
   * @param {string} text
   * @returns {string}
   */
  function renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
      try {
        return marked.parse(text);
      } catch (e) {
        console.error('[AIAssistant] Markdown parse error:', e);
        return escapeHtml(text);
      }
    }
    return escapeHtml(text);
  }

  /**
   * Switch to a different chat
   * @param {string} chatId
   */
  async function switchChat(chatId) {
    currentChatId = chatId;

    // 手機版：切換對話後自動關閉 Drawer
    if (isMobileView()) {
      closeMobileSidebar();
    }

    // Load full chat details from API if messages not loaded
    const chat = getChatById(chatId);
    if (chat && (!chat.messages || chat.messages.length === undefined)) {
      try {
        const fullChat = await APIClient.getChat(chatId);
        const index = chats.findIndex(c => c.id === chatId);
        if (index > -1) {
          chats[index] = fullChat;
        }
      } catch (e) {
        console.error('[AIAssistant] Failed to load chat details:', e);
      }
    }

    // Update agent selector and model display
    const updatedChat = getChatById(chatId);
    if (updatedChat) {
      const agentSelect = document.querySelector(`#${windowId} .ai-agent-select`);
      if (agentSelect) {
        agentSelect.value = updatedChat.prompt_name || 'web-chat-default';
      }
      updateModelDisplay(updatedChat.model || 'claude-sonnet');
    }

    renderChatList();
    renderMessages();
  }

  /**
   * Send a message
   * @param {string} content
   */
  async function sendMessage(content) {
    if (!content.trim()) return;

    let chat = getChatById(currentChatId);
    if (!chat) {
      chat = await createChat();
      if (!chat) {
        console.error('[AIAssistant] Failed to create chat');
        return;
      }
      currentChatId = chat.id;
    }

    // Add user message to local state (optimistic update)
    if (!chat.messages) chat.messages = [];
    const userMessage = {
      role: 'user',
      content: content.trim(),
      timestamp: Math.floor(Date.now() / 1000)
    };
    chat.messages.push(userMessage);

    renderChatList();
    renderMessages();

    // Send to backend via Socket.IO
    if (typeof SocketClient !== 'undefined' && SocketClient.isConnected()) {
      SocketClient.sendAIChat({
        chatId: chat.id,
        message: content.trim(),
        model: chat.model || 'claude-sonnet'
      });
    } else {
      handleError(chat.id, '無法連接到伺服器，請稍後再試');
    }
  }

  /**
   * Receive AI response message
   * @param {string} chatId
   * @param {string} message
   */
  function receiveMessage(chatId, message) {
    const chat = getChatById(chatId);
    if (!chat) return;

    // Remove typing indicator
    setTypingState(chatId, false);

    // Add assistant message
    if (!chat.messages) chat.messages = [];
    const assistantMessage = {
      role: 'assistant',
      content: message,
      timestamp: Math.floor(Date.now() / 1000)
    };
    chat.messages.push(assistantMessage);

    // Render if this chat is currently active
    if (chatId === currentChatId && windowId) {
      renderMessages();
    }
  }

  /**
   * Set typing indicator state
   * @param {string} chatId
   * @param {boolean} typing
   */
  function setTypingState(chatId, typing) {
    if (chatId !== currentChatId || !windowId) return;

    const container = document.querySelector(`#${windowId} .ai-messages-container`);
    if (!container) return;

    // Remove existing typing indicator
    const existingTyping = container.querySelector('.ai-typing');
    if (existingTyping) {
      existingTyping.remove();
    }

    if (typing) {
      // Show typing indicator
      const typingDiv = document.createElement('div');
      typingDiv.className = 'ai-message ai-message-assistant ai-typing';
      typingDiv.innerHTML = `
        <div class="ai-message-avatar">
          <span class="icon">${getIcon('robot')}</span>
        </div>
        <div class="ai-message-content">
          <div class="ai-message-role">AI 助手</div>
          <div class="ai-message-text ai-typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      `;
      container.appendChild(typingDiv);

      // Scroll to bottom
      const messagesArea = document.querySelector(`#${windowId} .ai-messages`);
      if (messagesArea) {
        messagesArea.scrollTop = messagesArea.scrollHeight;
      }
    }
  }

  /**
   * Set compressing state
   * @param {string} chatId
   * @param {boolean} compressing
   */
  function setCompressingState(chatId, compressing) {
    isCompressing = compressing;

    const compressBtn = document.querySelector(`#${windowId} .ai-compress-btn`);
    if (compressBtn) {
      compressBtn.textContent = compressing ? '壓縮中...' : '壓縮對話';
      compressBtn.disabled = compressing;
    }
  }

  /**
   * Handle compress complete
   * @param {string} chatId
   * @param {Array} messages
   */
  function handleCompressComplete(chatId, messages) {
    setCompressingState(chatId, false);

    const chat = getChatById(chatId);
    if (chat) {
      chat.messages = messages;
    }

    if (chatId === currentChatId && windowId) {
      renderMessages();
    }
  }

  /**
   * Handle compress error
   * @param {string} chatId
   * @param {string} error
   */
  function handleCompressError(chatId, error) {
    setCompressingState(chatId, false);
    console.error('[AIAssistant] Compress error:', error);

    // Show error notification or message
    if (typeof NotificationModule !== 'undefined') {
      NotificationModule.show({
        title: '壓縮失敗',
        message: error,
        duration: 5000,
      });
    }
  }

  /**
   * Handle error from backend
   * @param {string} chatId
   * @param {string} error
   */
  function handleError(chatId, error) {
    // Remove typing indicator
    setTypingState(chatId, false);

    const chat = getChatById(chatId);
    if (!chat) return;

    // Add error message as system message
    if (!chat.messages) chat.messages = [];
    const errorMessage = {
      role: 'assistant',
      content: `[錯誤] ${error}`,
      timestamp: Math.floor(Date.now() / 1000)
    };
    chat.messages.push(errorMessage);

    // Render if this chat is currently active
    if (chatId === currentChatId && windowId) {
      renderMessages();
    }
  }

  /**
   * Check if AI assistant window is open
   * @returns {boolean}
   */
  function isWindowOpen() {
    return windowId !== null;
  }

  /**
   * Switch to a specific chat (used by notification click)
   * @param {string} chatId
   */
  function switchToChat(chatId) {
    const chat = getChatById(chatId);
    if (chat) {
      switchChat(chatId);
    }
  }

  /**
   * Check if current view is mobile
   * @returns {boolean}
   */
  function isMobileView() {
    return window.innerWidth <= 768;
  }

  /**
   * Toggle sidebar collapsed state
   */
  function toggleSidebar() {
    const app = document.querySelector(`#${windowId} .ai-assistant`);
    if (!app) return;

    if (isMobileView()) {
      // 手機版：切換 Drawer
      app.classList.toggle('mobile-sidebar-open');
    } else {
      // 桌面版：收合側邊欄
      sidebarCollapsed = !sidebarCollapsed;
      app.classList.toggle('sidebar-collapsed', sidebarCollapsed);

      const expandBtn = document.querySelector(`#${windowId} .ai-sidebar-expand`);
      if (expandBtn) {
        expandBtn.style.display = sidebarCollapsed ? 'flex' : 'none';
      }
    }
  }

  /**
   * Close mobile sidebar drawer
   */
  function closeMobileSidebar() {
    const app = document.querySelector(`#${windowId} .ai-assistant`);
    if (app) {
      app.classList.remove('mobile-sidebar-open');
    }
  }

  /**
   * Initialize the application after window is created
   * @param {HTMLElement} windowEl
   * @param {string} wId
   */
  async function initApp(windowEl, wId) {
    windowId = wId;

    // 插入 skeleton 骨架佔位元素
    const chatList = windowEl.querySelector('.ai-chat-list');
    const messagesContainer = windowEl.querySelector('.ai-messages-container');
    const chatSkeletons = [];
    const msgSkeletons = [];

    if (chatList) {
      for (let i = 0; i < 5; i++) {
        const sk = document.createElement('div');
        sk.className = 'skeleton skeleton--chat-item';
        sk.setAttribute('aria-hidden', 'true');
        chatList.appendChild(sk);
        chatSkeletons.push(sk);
      }
    }

    if (messagesContainer) {
      for (let i = 0; i < 3; i++) {
        const sk = document.createElement('div');
        sk.className = 'skeleton skeleton--message';
        sk.setAttribute('aria-hidden', 'true');
        if (i % 2 === 1) sk.style.marginLeft = 'auto';
        messagesContainer.appendChild(sk);
        msgSkeletons.push(sk);
      }
    }

    // Load data from API
    await loadAgents();
    await loadChats();

    // Update agent selector after loading
    const agentSelect = document.querySelector(`#${windowId} .ai-agent-select`);
    if (agentSelect && availableAgents.length > 0) {
      agentSelect.innerHTML = availableAgents.map(a =>
        `<option value="${a.name}">${a.display_name || a.name}</option>`
      ).join('');
    }

    // Create initial chat if none exists
    if (chats.length === 0) {
      const chat = await createChat();
      if (chat) {
        currentChatId = chat.id;
      }
    } else {
      currentChatId = chats[0].id;
      // Load full details for current chat
      await switchChat(currentChatId);
    }

    // 移除所有 skeleton 骨架
    chatSkeletons.forEach(sk => sk.remove());
    msgSkeletons.forEach(sk => sk.remove());

    // Render initial state
    renderChatList();
    renderMessages();

    // Bind events
    bindEvents();
  }

  /**
   * Bind all event handlers
   */
  function bindEvents() {
    // New chat button
    const newChatBtn = document.querySelector(`#${windowId} .ai-new-chat-btn`);
    if (newChatBtn) {
      newChatBtn.addEventListener('click', async () => {
        const agentSelect = document.querySelector(`#${windowId} .ai-agent-select`);
        const agentName = agentSelect ? agentSelect.value : 'web-chat-default';
        const chat = await createChat(agentName);
        if (chat) {
          currentChatId = chat.id;
          renderChatList();
          renderMessages();
        }
      });
    }

    // Sidebar toggle
    const sidebarToggle = document.querySelector(`#${windowId} .ai-sidebar-toggle`);
    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', toggleSidebar);
    }

    // Sidebar expand
    const sidebarExpand = document.querySelector(`#${windowId} .ai-sidebar-expand`);
    if (sidebarExpand) {
      sidebarExpand.addEventListener('click', toggleSidebar);
    }

    // Mobile sidebar overlay (點擊遮罩關閉 Drawer)
    const sidebarOverlay = document.querySelector(`#${windowId} .ai-sidebar-overlay`);
    if (sidebarOverlay) {
      sidebarOverlay.addEventListener('click', closeMobileSidebar);
    }

    // Agent selector
    const agentSelect = document.querySelector(`#${windowId} .ai-agent-select`);
    if (agentSelect) {
      agentSelect.addEventListener('change', async (e) => {
        const chat = getChatById(currentChatId);
        if (chat) {
          const agentName = e.target.value;
          const agent = availableAgents.find(a => a.name === agentName);

          chat.prompt_name = agentName;
          if (agent) {
            chat.model = agent.model;
            // 更新 model 顯示
            updateModelDisplay(agent.model);
          }

          // Update on server
          try {
            await APIClient.updateChat(chat.id, {
              prompt_name: agentName,
              model: chat.model
            });
          } catch (err) {
            console.error('[AIAssistant] Failed to update agent:', err);
          }
        }
      });
    }

    // Compress button
    const compressBtn = document.querySelector(`#${windowId} .ai-compress-btn`);
    if (compressBtn) {
      compressBtn.addEventListener('click', () => {
        if (isCompressing) return;
        if (currentChatId && typeof SocketClient !== 'undefined') {
          SocketClient.compressChat(currentChatId);
        }
      });
    }

    // Send button
    const sendBtn = document.querySelector(`#${windowId} .ai-send-btn`);
    const input = document.querySelector(`#${windowId} .ai-input`);

    if (sendBtn && input) {
      sendBtn.addEventListener('click', () => {
        sendMessage(input.value);
        input.value = '';
        autoResizeInput(input);
      });

      // Enter to send (Shift+Enter for newline)
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendMessage(input.value);
          input.value = '';
          autoResizeInput(input);
        }
      });

      // Auto-resize textarea
      input.addEventListener('input', () => autoResizeInput(input));
    }
  }

  /**
   * Auto-resize textarea based on content
   * @param {HTMLTextAreaElement} textarea
   */
  function autoResizeInput(textarea) {
    textarea.style.height = 'auto';
    const maxHeight = 150;
    textarea.style.height = Math.min(textarea.scrollHeight, maxHeight) + 'px';
  }

  /**
   * Open the AI Assistant application
   */
  function open() {
    // Check if already open
    const existingWindow = WindowModule.getWindowByAppId(APP_ID);
    if (existingWindow) {
      WindowModule.focusWindow(existingWindow.windowId);
      if (existingWindow.minimized) {
        WindowModule.restoreWindow(existingWindow.windowId);
      }
      return;
    }

    // Create window
    WindowModule.createWindow({
      title: 'AI 助手',
      appId: APP_ID,
      icon: 'robot',
      width: 900,
      height: 600,
      content: buildWindowContent(),
      onInit: initApp,
      onClose: () => {
        windowId = null;
      }
    });
  }

  /**
   * Close the AI Assistant application
   */
  function close() {
    if (windowId) {
      WindowModule.closeWindow(windowId);
      windowId = null;
    }
  }

  // Public API
  return {
    open,
    close,
    isWindowOpen,
    receiveMessage,
    setTypingState,
    setCompressingState,
    handleCompressComplete,
    handleCompressError,
    handleError,
    switchToChat
  };
})();
