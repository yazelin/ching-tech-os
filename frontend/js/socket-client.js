/**
 * Socket.IO 客戶端模組 - 全域連線管理
 *
 * 頁面載入時建立連線，不隨 AI 助手視窗關閉斷線。
 * 處理 AI 回應、typing 狀態等事件。
 */
const SocketClient = (function () {
  let socket = null;
  let isConnected = false;

  // 後端 URL（使用目前頁面的 origin）
  const BACKEND_URL = window.location.origin;

  /**
   * 建立 Socket.IO 連線
   */
  function connect() {
    if (socket && isConnected) {
      console.log('[SocketClient] Already connected');
      return;
    }

    console.log('[SocketClient] Connecting to', BACKEND_URL);

    socket = io(BACKEND_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    // 連線事件
    socket.on('connect', () => {
      isConnected = true;
      console.log('[SocketClient] Connected, id:', socket.id);
    });

    socket.on('disconnect', (reason) => {
      isConnected = false;
      console.log('[SocketClient] Disconnected:', reason);
    });

    socket.on('connect_error', (error) => {
      console.error('[SocketClient] Connection error:', error.message);
    });

    // AI 相關事件
    socket.on('ai_typing', handleAITyping);
    socket.on('ai_response', handleAIResponse);
    socket.on('ai_error', handleAIError);

    // 對話壓縮事件
    socket.on('compress_started', handleCompressStarted);
    socket.on('compress_complete', handleCompressComplete);
    socket.on('compress_error', handleCompressError);

    // 訊息中心事件
    socket.on('message:new', handleNewMessage);
    socket.on('message:unread_count', handleUnreadCount);
  }

  /**
   * 處理新訊息
   * @param {Object} data - { message }
   */
  function handleNewMessage(data) {
    const { message } = data;
    console.log('[SocketClient] New message:', message.id, message.severity);

    // 通知訊息中心
    if (typeof MessageCenterApp !== 'undefined') {
      MessageCenterApp.handleNewMessage(message);
    }

    // 更新 Header badge
    updateMessageBadge();

    // 根據嚴重程度顯示 Toast 通知（warning 以上）
    if (['warning', 'error', 'critical'].includes(message.severity)) {
      if (typeof DesktopModule !== 'undefined') {
        const iconMap = {
          'warning': 'alert',
          'error': 'alert-circle',
          'critical': 'alert-octagon'
        };
        DesktopModule.showToast(
          `[${message.severity.toUpperCase()}] ${message.title}`,
          iconMap[message.severity] || 'information'
        );
      }
    }
  }

  /**
   * 處理未讀數量更新
   * @param {Object} data - { count }
   */
  function handleUnreadCount(data) {
    const { count } = data;
    console.log('[SocketClient] Unread count:', count);
    updateMessageBadgeCount(count);
  }

  /**
   * 更新訊息 badge（從 API 取得）
   */
  async function updateMessageBadge() {
    try {
      const token = LoginModule.getToken();
      if (!token) return;

      const response = await fetch('/api/messages/unread-count', {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        updateMessageBadgeCount(data.count);
      }
    } catch (error) {
      console.error('[SocketClient] Failed to fetch unread count:', error);
    }
  }

  /**
   * 更新訊息 badge 數量
   * @param {number} count
   */
  function updateMessageBadgeCount(count) {
    const badge = document.getElementById('messagesBadge');
    if (!badge) return;

    if (count > 0) {
      badge.textContent = count > 99 ? '99+' : count;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
  }

  /**
   * 處理壓縮開始
   * @param {Object} data - { chatId }
   */
  function handleCompressStarted(data) {
    const { chatId } = data;
    console.log('[SocketClient] Compress started for chat:', chatId);

    if (typeof AIAssistantApp !== 'undefined' && AIAssistantApp.isWindowOpen()) {
      AIAssistantApp.setCompressingState(chatId, true);
    }
  }

  /**
   * 處理壓縮完成
   * @param {Object} data - { chatId, messages, compressed_count }
   */
  function handleCompressComplete(data) {
    const { chatId, messages, compressed_count } = data;
    console.log('[SocketClient] Compress complete for chat:', chatId, 'compressed:', compressed_count);

    if (typeof AIAssistantApp !== 'undefined') {
      AIAssistantApp.handleCompressComplete(chatId, messages);
    }
  }

  /**
   * 處理壓縮錯誤
   * @param {Object} data - { chatId, error }
   */
  function handleCompressError(data) {
    const { chatId, error } = data;
    console.error('[SocketClient] Compress error:', chatId, error);

    if (typeof AIAssistantApp !== 'undefined') {
      AIAssistantApp.handleCompressError(chatId, error);
    }
  }

  /**
   * 處理 AI typing 狀態
   * @param {Object} data - { chatId, typing }
   */
  function handleAITyping(data) {
    const { chatId, typing } = data;
    console.log('[SocketClient] AI typing:', chatId, typing);

    // 通知 AI 助手更新 UI
    if (typeof AIAssistantApp !== 'undefined' && AIAssistantApp.isWindowOpen()) {
      AIAssistantApp.setTypingState(chatId, typing);
    }
  }

  /**
   * 處理 AI 回應
   * @param {Object} data - { chatId, message }
   */
  function handleAIResponse(data) {
    const { chatId, message } = data;
    console.log('[SocketClient] AI response received for chat:', chatId);

    // 更新訊息到 AI 助手
    if (typeof AIAssistantApp !== 'undefined') {
      AIAssistantApp.receiveMessage(chatId, message);

      // 如果 AI 助手視窗未開啟，顯示通知
      if (!AIAssistantApp.isWindowOpen()) {
        if (typeof NotificationModule !== 'undefined') {
          NotificationModule.showAIResponse(chatId);
        }
      }
    }
  }

  /**
   * 處理 AI 錯誤
   * @param {Object} data - { chatId, error }
   */
  function handleAIError(data) {
    const { chatId, error } = data;
    console.error('[SocketClient] AI error:', chatId, error);

    // 通知 AI 助手顯示錯誤
    if (typeof AIAssistantApp !== 'undefined') {
      AIAssistantApp.handleError(chatId, error);
    }
  }

  /**
   * 發送 AI 對話訊息
   * @param {Object} data - { chatId, message, model }
   */
  function sendAIChat(data) {
    if (!socket || !isConnected) {
      console.error('[SocketClient] Not connected, cannot send message');
      return false;
    }

    socket.emit('ai_chat_event', data);
    return true;
  }

  /**
   * 發送對話壓縮請求
   * @param {string} chatId
   */
  function compressChat(chatId) {
    if (!socket || !isConnected) {
      console.error('[SocketClient] Not connected, cannot compress');
      return false;
    }

    socket.emit('compress_chat', { chatId });
    return true;
  }

  /**
   * 檢查連線狀態
   * @returns {boolean}
   */
  function getIsConnected() {
    return isConnected;
  }

  /**
   * 斷開連線
   */
  function disconnect() {
    if (socket) {
      socket.disconnect();
      socket = null;
      isConnected = false;
    }
  }

  /**
   * 發送事件
   * @param {string} event - 事件名稱
   * @param {Object} data - 資料
   */
  function emit(event, data) {
    if (!socket || !isConnected) {
      console.error('[SocketClient] Not connected, cannot emit:', event);
      return false;
    }
    socket.emit(event, data);
    return true;
  }

  /**
   * 發送事件並等待回應 (使用 callback)
   * @param {string} event - 事件名稱
   * @param {Object} data - 資料
   * @returns {Promise}
   */
  function emitWithAck(event, data) {
    return new Promise((resolve, reject) => {
      if (!socket || !isConnected) {
        reject(new Error('Not connected'));
        return;
      }
      socket.emit(event, data, (response) => {
        resolve(response);
      });
    });
  }

  /**
   * 監聽事件
   * @param {string} event - 事件名稱
   * @param {Function} handler - 處理函式
   */
  function on(event, handler) {
    if (!socket) {
      console.error('[SocketClient] Socket not initialized');
      return;
    }
    socket.on(event, handler);
  }

  /**
   * 移除事件監聽
   * @param {string} event - 事件名稱
   * @param {Function} handler - 處理函式
   */
  function off(event, handler) {
    if (!socket) return;
    socket.off(event, handler);
  }

  return {
    connect,
    disconnect,
    sendAIChat,
    compressChat,
    isConnected: getIsConnected,
    emit,
    emitWithAck,
    on,
    off,
    updateMessageBadge,
  };
})();
