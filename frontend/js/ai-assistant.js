/**
 * ChingTech OS - AI Assistant Application
 * ChatGPT-style AI chat interface
 */

const AIAssistantApp = (function() {
  'use strict';

  // Application state
  const APP_ID = 'ai-assistant';
  const STORAGE_KEY = 'chingtech_ai_chats';
  let windowId = null;
  let chats = [];
  let currentChatId = null;
  let sidebarCollapsed = false;

  // Available models
  const availableModels = [
    { id: 'claude-opus', name: 'Claude Opus' },
    { id: 'claude-sonnet', name: 'Claude Sonnet' },
    { id: 'claude-haiku', name: 'Claude Haiku' }
  ];

  /**
   * Generate unique ID
   * @returns {string}
   */
  function generateId() {
    return 'chat-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
  }

  /**
   * Generate UUID v4 for Claude CLI session
   * @returns {string}
   */
  function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  /**
   * Load chats from localStorage
   */
  function loadChats() {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      if (data) {
        chats = JSON.parse(data);
      }
    } catch (e) {
      console.error('Failed to load chats:', e);
      chats = [];
    }
  }

  /**
   * Save chats to localStorage
   */
  function saveChats() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(chats));
    } catch (e) {
      console.error('Failed to save chats:', e);
    }
  }

  /**
   * Create a new chat
   * @returns {Object} New chat object
   */
  function createChat() {
    const chat = {
      id: generateId(),
      sessionId: generateUUID(),  // UUID for Claude CLI session
      title: '新對話',
      model: availableModels[0].id,
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now()
    };
    chats.unshift(chat);
    saveChats();
    return chat;
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
   * Delete a chat
   * @param {string} chatId
   */
  function deleteChat(chatId) {
    const index = chats.findIndex(c => c.id === chatId);
    if (index > -1) {
      chats.splice(index, 1);
      saveChats();
      if (currentChatId === chatId) {
        currentChatId = chats.length > 0 ? chats[0].id : null;
        if (!currentChatId) {
          const newChat = createChat();
          currentChatId = newChat.id;
        }
      }
      renderChatList();
      renderMessages();
    }
  }

  /**
   * Generate chat title from first message
   * @param {string} content
   * @returns {string}
   */
  function generateTitle(content) {
    const maxLength = 20;
    const cleaned = content.replace(/\n/g, ' ').trim();
    if (cleaned.length <= maxLength) {
      return cleaned;
    }
    return cleaned.substring(0, maxLength) + '...';
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
          </header>
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
    if (!chat || chat.messages.length === 0) {
      container.innerHTML = `
        <div class="ai-welcome">
          <span class="ai-welcome-icon icon">${getIcon('robot')}</span>
          <h2>AI 助手</h2>
          <p>有什麼我可以幫助你的嗎？</p>
        </div>
      `;
      return;
    }

    container.innerHTML = chat.messages.map(msg => `
      <div class="ai-message ai-message-${msg.role}">
        <div class="ai-message-avatar">
          <span class="icon">${getIcon(msg.role === 'user' ? 'account' : 'robot')}</span>
        </div>
        <div class="ai-message-content">
          <div class="ai-message-role">${msg.role === 'user' ? '你' : 'AI 助手'}</div>
          <div class="ai-message-text">${escapeHtml(msg.content)}</div>
        </div>
      </div>
    `).join('');

    // Scroll to bottom
    const messagesArea = document.querySelector(`#${windowId} .ai-messages`);
    if (messagesArea) {
      messagesArea.scrollTop = messagesArea.scrollHeight;
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
  function switchChat(chatId) {
    currentChatId = chatId;

    // Update model selector
    const chat = getChatById(chatId);
    if (chat) {
      const modelSelect = document.querySelector(`#${windowId} .ai-model-select`);
      if (modelSelect) {
        modelSelect.value = chat.model;
      }
    }

    renderChatList();
    renderMessages();
  }

  /**
   * Send a message
   * @param {string} content
   */
  function sendMessage(content) {
    if (!content.trim()) return;

    let chat = getChatById(currentChatId);
    if (!chat) {
      chat = createChat();
      currentChatId = chat.id;
    }

    // Ensure chat has sessionId (for older chats)
    if (!chat.sessionId) {
      chat.sessionId = generateUUID();
    }

    // Add user message
    const userMessage = {
      role: 'user',
      content: content.trim(),
      timestamp: Date.now()
    };
    chat.messages.push(userMessage);

    // Update title if this is the first message
    if (chat.messages.length === 1) {
      chat.title = generateTitle(content);
    }

    chat.updatedAt = Date.now();
    saveChats();
    renderChatList();
    renderMessages();

    // Send to backend via Socket.IO
    if (typeof SocketClient !== 'undefined' && SocketClient.isConnected()) {
      SocketClient.sendAIChat({
        chatId: chat.id,
        sessionId: chat.sessionId,
        message: content.trim(),
        model: chat.model
      });
    } else {
      // Fallback: show error if not connected
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
    const assistantMessage = {
      role: 'assistant',
      content: message,
      timestamp: Date.now()
    };
    chat.messages.push(assistantMessage);
    chat.updatedAt = Date.now();
    saveChats();

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
    const errorMessage = {
      role: 'assistant',
      content: `[錯誤] ${error}`,
      timestamp: Date.now()
    };
    chat.messages.push(errorMessage);
    chat.updatedAt = Date.now();
    saveChats();

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
  function initApp(windowEl, wId) {
    windowId = wId;

    // Load data
    loadChats();

    // Create initial chat if none exists
    if (chats.length === 0) {
      const chat = createChat();
      currentChatId = chat.id;
    } else {
      currentChatId = chats[0].id;
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
      newChatBtn.addEventListener('click', () => {
        const chat = createChat();
        currentChatId = chat.id;
        renderChatList();
        renderMessages();
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
      modelSelect.addEventListener('change', (e) => {
        const chat = getChatById(currentChatId);
        if (chat) {
          chat.model = e.target.value;
          saveChats();
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
    handleError,
    switchToChat
  };
})();
