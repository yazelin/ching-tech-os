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
  let availablePrompts = [];
  let isCompressing = false;

  // Token estimation constants
  const TOKEN_LIMIT = 200000;
  const WARNING_THRESHOLD = 0.75; // 75%

  // Available models
  const availableModels = [
    { id: 'claude-opus', name: 'Claude Opus' },
    { id: 'claude-sonnet', name: 'Claude Sonnet' },
    { id: 'claude-haiku', name: 'Claude Haiku' }
  ];

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
   * Load available prompts from API
   */
  async function loadPrompts() {
    try {
      if (typeof APIClient !== 'undefined') {
        availablePrompts = await APIClient.getPrompts();
      } else {
        availablePrompts = [{ name: 'default', display_name: '預設助手', description: '' }];
      }
    } catch (e) {
      console.error('[AIAssistant] Failed to load prompts:', e);
      availablePrompts = [{ name: 'default', display_name: '預設助手', description: '' }];
    }
  }

  /**
   * Create a new chat via API
   * @param {string} promptName
   * @returns {Object} New chat object
   */
  async function createChat(promptName = 'default') {
    try {
      if (typeof APIClient !== 'undefined') {
        const chat = await APIClient.createChat({
          title: '新對話',
          model: availableModels[1].id, // Default to Sonnet
          prompt_name: promptName,
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
            <div class="ai-model-selector">
              <label>模型：</label>
              <select class="ai-model-select input">
                ${availableModels.map(m => `<option value="${m.id}">${m.name}</option>`).join('')}
              </select>
            </div>
            <div class="ai-prompt-selector">
              <label>助手：</label>
              <select class="ai-prompt-select input">
                ${availablePrompts.map(p => `<option value="${p.name}">${p.display_name}</option>`).join('')}
              </select>
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
      container.innerHTML = `
        <div class="ai-chat-empty">
          <span class="icon">${getIcon('chat')}</span>
          <p>尚無對話</p>
        </div>
      `;
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
        return `
          <div class="ai-message ai-message-${msg.role}">
            <div class="ai-message-avatar">
              <span class="icon">${getIcon(msg.role === 'user' ? 'account' : 'robot')}</span>
            </div>
            <div class="ai-message-content">
              <div class="ai-message-role">${msg.role === 'user' ? '你' : 'AI 助手'}</div>
              <div class="ai-message-text">${escapeHtml(msg.content)}</div>
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
   * Escape HTML special characters
   * @param {string} text
   * @returns {string}
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, '<br>');
  }

  /**
   * Switch to a different chat
   * @param {string} chatId
   */
  async function switchChat(chatId) {
    currentChatId = chatId;

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

    // Update model selector
    const updatedChat = getChatById(chatId);
    if (updatedChat) {
      const modelSelect = document.querySelector(`#${windowId} .ai-model-select`);
      if (modelSelect) {
        modelSelect.value = updatedChat.model || 'claude-sonnet';
      }

      const promptSelect = document.querySelector(`#${windowId} .ai-prompt-select`);
      if (promptSelect) {
        promptSelect.value = updatedChat.prompt_name || 'default';
      }
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
   * Toggle sidebar collapsed state
   */
  function toggleSidebar() {
    sidebarCollapsed = !sidebarCollapsed;
    const app = document.querySelector(`#${windowId} .ai-assistant`);
    const expandBtn = document.querySelector(`#${windowId} .ai-sidebar-expand`);

    if (app) {
      app.classList.toggle('sidebar-collapsed', sidebarCollapsed);
    }
    if (expandBtn) {
      expandBtn.style.display = sidebarCollapsed ? 'flex' : 'none';
    }
  }

  /**
   * Initialize the application after window is created
   * @param {HTMLElement} windowEl
   * @param {string} wId
   */
  async function initApp(windowEl, wId) {
    windowId = wId;

    // Load data from API
    await loadPrompts();
    await loadChats();

    // Update prompt selector after loading
    const promptSelect = document.querySelector(`#${windowId} .ai-prompt-select`);
    if (promptSelect && availablePrompts.length > 0) {
      promptSelect.innerHTML = availablePrompts.map(p =>
        `<option value="${p.name}">${p.display_name}</option>`
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
        const promptSelect = document.querySelector(`#${windowId} .ai-prompt-select`);
        const promptName = promptSelect ? promptSelect.value : 'default';
        const chat = await createChat(promptName);
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

    // Model selector
    const modelSelect = document.querySelector(`#${windowId} .ai-model-select`);
    if (modelSelect) {
      modelSelect.addEventListener('change', async (e) => {
        const chat = getChatById(currentChatId);
        if (chat) {
          chat.model = e.target.value;
          // Update on server
          try {
            await APIClient.updateChat(chat.id, { model: e.target.value });
          } catch (err) {
            console.error('[AIAssistant] Failed to update model:', err);
          }
        }
      });
    }

    // Prompt selector
    const promptSelect = document.querySelector(`#${windowId} .ai-prompt-select`);
    if (promptSelect) {
      promptSelect.addEventListener('change', async (e) => {
        const chat = getChatById(currentChatId);
        if (chat) {
          chat.prompt_name = e.target.value;
          // Update on server
          try {
            await APIClient.updateChat(chat.id, { prompt_name: e.target.value });
          } catch (err) {
            console.error('[AIAssistant] Failed to update prompt:', err);
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
