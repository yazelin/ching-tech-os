/**
 * ChingTech OS - Message Center Module
 *
 * 訊息中心視窗應用程式
 */

const MessageCenterApp = (function () {
  'use strict';

  // API 基礎路徑
  const API_BASE = '';
  const APP_ID = 'message-center';

  // 狀態
  let windowId = null;
  let currentFilter = {
    severity: [],
    source: [],
    search: '',
    page: 1,
    limit: 20,
  };
  let messages = [];
  let totalMessages = 0;
  let totalPages = 1;
  let selectedMessage = null;
  let unreadCount = 0;

  // DOM 元素快取
  let container = null;

  /**
   * 取得認證 Token
   */
  function getToken() {
    return localStorage.getItem('chingtech_token');
  }

  /**
   * API 請求
   */
  async function apiRequest(endpoint, options = {}) {
    const token = getToken();
    const headers = {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    };

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }

    return response.json();
  }

  /**
   * 載入訊息列表
   */
  async function loadMessages() {
    if (!container) return;

    const listEl = container.querySelector('.mc-list');
    /* [Sprint6] 原: <div class="mc-loading">... 載入中... */
    UIHelpers.showLoading(listEl, { text: '載入中...' });

    try {
      const params = new URLSearchParams();
      if (currentFilter.severity.length > 0) {
        currentFilter.severity.forEach((s) => params.append('severity', s));
      }
      if (currentFilter.source.length > 0) {
        currentFilter.source.forEach((s) => params.append('source', s));
      }
      if (currentFilter.search) {
        params.set('search', currentFilter.search);
      }
      params.set('page', currentFilter.page);
      params.set('limit', currentFilter.limit);

      const data = await apiRequest(`/api/messages?${params.toString()}`);
      messages = data.items;
      totalMessages = data.total;
      totalPages = data.total_pages;

      renderMessages();
      renderPagination();
    } catch (error) {
      console.error('Failed to load messages:', error);
      /* [Sprint6] 原: <div class="mc-empty">... 載入訊息失敗 */
      UIHelpers.showError(listEl, { icon: 'alert-circle', message: '載入訊息失敗' });
    }
  }

  /**
   * 渲染訊息列表
   */
  function renderMessages() {
    const listEl = container.querySelector('.mc-list');

    if (messages.length === 0) {
      /* [Sprint6] 原: <div class="mc-empty">... 沒有訊息 */
      UIHelpers.showEmpty(listEl, { icon: 'bell-off', text: '沒有訊息' });
      return;
    }

    // 依日期分組
    const groups = groupMessagesByDate(messages);
    let html = '';

    for (const [label, msgs] of Object.entries(groups)) {
      if (msgs.length === 0) continue;
      html += `
        <div class="mc-date-group">
          <div class="mc-date-header">${label}</div>
          ${msgs.map((msg) => renderMessageItem(msg)).join('')}
        </div>
      `;
    }

    listEl.innerHTML = html;

    // 綁定點擊事件
    listEl.querySelectorAll('.mc-item').forEach((el) => {
      el.addEventListener('click', () => {
        const msgId = parseInt(el.dataset.id, 10);
        selectMessage(msgId);
      });
    });
  }

  /**
   * 依日期分組訊息
   */
  function groupMessagesByDate(msgs) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    const groups = {
      今天: [],
      昨天: [],
      更早: [],
    };

    msgs.forEach((msg) => {
      const msgDate = new Date(msg.created_at);
      msgDate.setHours(0, 0, 0, 0);

      if (msgDate.getTime() === today.getTime()) {
        groups['今天'].push(msg);
      } else if (msgDate.getTime() === yesterday.getTime()) {
        groups['昨天'].push(msg);
      } else {
        groups['更早'].push(msg);
      }
    });

    return groups;
  }

  /**
   * 渲染單一訊息項目
   */
  function renderMessageItem(msg) {
    const severityIcon = getSeverityIcon(msg.severity);
    const time = formatTime(msg.created_at);
    const sourceLabel = getSourceLabel(msg.source);
    const isUnread = !msg.is_read;
    const isSelected = selectedMessage && selectedMessage.id === msg.id;

    return `
      <div class="mc-item ${isUnread ? 'unread' : ''} ${isSelected ? 'selected' : ''}" data-id="${msg.id}">
        <div class="mc-severity-icon mc-severity-${msg.severity}">
          <span class="icon">${severityIcon}</span>
        </div>
        <div class="mc-item-content">
          <div class="mc-item-header">
            <div class="mc-item-title">${escapeHtml(msg.title)}</div>
            <div class="mc-item-meta">
              <span class="mc-tag source">${sourceLabel}</span>
              <span class="mc-item-time">${time}</span>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * 選擇訊息
   */
  async function selectMessage(msgId) {
    try {
      const data = await apiRequest(`/api/messages/${msgId}`);
      selectedMessage = data;

      // 更新列表中的選中狀態
      container.querySelectorAll('.mc-item').forEach((el) => {
        el.classList.toggle('selected', parseInt(el.dataset.id, 10) === msgId);
        if (parseInt(el.dataset.id, 10) === msgId) {
          el.classList.remove('unread');
        }
      });

      // 標記為已讀
      if (!data.is_read) {
        await markAsRead([msgId]);
      }

      // 顯示詳情面板
      showDetail(data);
    } catch (error) {
      console.error('Failed to load message detail:', error);
    }
  }

  /**
   * 顯示訊息詳情
   */
  function showDetail(msg) {
    const detailEl = container.querySelector('.mc-detail');
    detailEl.classList.add('visible');

    const severityIcon = getSeverityIcon(msg.severity);
    const severityLabel = getSeverityLabel(msg.severity);
    const sourceLabel = getSourceLabel(msg.source);
    const time = new Date(msg.created_at).toLocaleString('zh-TW');

    detailEl.innerHTML = `
      <div class="mc-detail-header">
        <div class="mc-detail-title">
          <div class="mc-severity-icon mc-severity-${msg.severity}">
            <span class="icon">${severityIcon}</span>
          </div>
          ${escapeHtml(msg.title)}
        </div>
        <button class="mc-detail-close" onclick="MessageCenterApp.hideDetail()">
          <span class="icon">${getIcon('close')}</span>
        </button>
      </div>
      <div class="mc-detail-body">
        <div class="mc-detail-info">
          <span class="mc-tag severity-${msg.severity}">${severityLabel}</span>
          <span class="mc-tag source">${sourceLabel}</span>
          ${msg.category ? `<span class="mc-tag category">${msg.category}</span>` : ''}
          <span class="mc-tag time">${time}</span>
        </div>
        ${msg.content ? `
        <div class="mc-detail-content">${escapeHtml(msg.content)}</div>
        ` : ''}
        ${msg.metadata ? `
        <div class="mc-detail-metadata">
          <pre>${JSON.stringify(msg.metadata, null, 2)}</pre>
        </div>
        ` : ''}
      </div>
    `;
  }

  /**
   * 隱藏詳情面板
   */
  function hideDetail() {
    const detailEl = container.querySelector('.mc-detail');
    detailEl.classList.remove('visible');
    selectedMessage = null;
  }

  /**
   * 渲染分頁
   */
  function renderPagination() {
    const paginationEl = container.querySelector('.mc-pagination');
    const start = (currentFilter.page - 1) * currentFilter.limit + 1;
    const end = Math.min(currentFilter.page * currentFilter.limit, totalMessages);

    let pageNumbers = '';
    for (let i = 1; i <= Math.min(totalPages, 5); i++) {
      pageNumbers += `
        <button class="mc-page-number ${i === currentFilter.page ? 'active' : ''}"
                onclick="MessageCenterApp.goToPage(${i})">${i}</button>
      `;
    }

    paginationEl.innerHTML = `
      <div class="mc-pagination-info">
        第 ${start}-${end} 筆，共 ${totalMessages} 筆
      </div>
      <div class="mc-pagination-controls">
        <button class="mc-page-btn" onclick="MessageCenterApp.prevPage()" ${currentFilter.page <= 1 ? 'disabled' : ''}>
          <span class="icon">${getIcon('chevron-left')}</span>
        </button>
        <div class="mc-page-numbers">${pageNumbers}</div>
        <button class="mc-page-btn" onclick="MessageCenterApp.nextPage()" ${currentFilter.page >= totalPages ? 'disabled' : ''}>
          <span class="icon">${getIcon('chevron-right')}</span>
        </button>
      </div>
    `;
  }

  /**
   * 標記訊息為已讀
   */
  async function markAsRead(ids) {
    try {
      await apiRequest('/api/messages/mark-read', {
        method: 'POST',
        body: JSON.stringify({ ids }),
      });
      await loadUnreadCount();
    } catch (error) {
      console.error('Failed to mark as read:', error);
    }
  }

  /**
   * 標記全部為已讀
   */
  async function markAllAsRead() {
    try {
      await apiRequest('/api/messages/mark-read', {
        method: 'POST',
        body: JSON.stringify({ all: true }),
      });
      await loadMessages();
      await loadUnreadCount();
    } catch (error) {
      console.error('Failed to mark all as read:', error);
    }
  }

  /**
   * 載入未讀數量
   */
  async function loadUnreadCount() {
    try {
      const data = await apiRequest('/api/messages/unread-count');
      unreadCount = data.count;
      updateBadge(unreadCount);
    } catch (error) {
      console.error('Failed to load unread count:', error);
    }
  }

  /**
   * 更新 Header Bar 徽章
   */
  function updateBadge(count) {
    const badge = document.querySelector('.header-badge');
    if (badge) {
      badge.textContent = count > 99 ? '99+' : count;
      badge.classList.toggle('hidden', count === 0);
    }
    // 同步更新全域 unreadCount
    unreadCount = count;
  }

  /**
   * 分頁操作
   */
  function goToPage(page) {
    currentFilter.page = page;
    loadMessages();
  }

  function prevPage() {
    if (currentFilter.page > 1) {
      currentFilter.page--;
      loadMessages();
    }
  }

  function nextPage() {
    if (currentFilter.page < totalPages) {
      currentFilter.page++;
      loadMessages();
    }
  }

  /**
   * 過濾操作
   */
  function setSeverityFilter(severity) {
    currentFilter.severity = severity ? [severity] : [];
    currentFilter.page = 1;
    loadMessages();
  }

  function setSourceFilter(source) {
    currentFilter.source = source ? [source] : [];
    currentFilter.page = 1;
    loadMessages();
  }

  function setSearch(search) {
    currentFilter.search = search;
    currentFilter.page = 1;
    loadMessages();
  }

  /**
   * 輔助函式
   */
  function getSeverityIcon(severity) {
    const icons = {
      debug: 'bug',
      info: 'information',
      warning: 'alert',
      error: 'alert-circle',
      critical: 'alert-octagon',
    };
    return getIcon(icons[severity] || 'bell');
  }

  function getSeverityLabel(severity) {
    const labels = {
      debug: '除錯',
      info: '資訊',
      warning: '警告',
      error: '錯誤',
      critical: '嚴重',
    };
    return labels[severity] || severity;
  }

  function getSourceLabel(source) {
    const labels = {
      system: '系統',
      security: '安全',
      app: '應用',
      user: '使用者',
    };
    return labels[source] || source;
  }

  function formatTime(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return '剛才';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分鐘前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小時前`;

    return date.toLocaleTimeString('zh-TW', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * 建立視窗內容
   */
  function createContent() {
    return `
      <div class="message-center">
        <!-- Toolbar -->
        <div class="mc-toolbar">
          <div class="mc-search-container">
            <span class="mc-search-icon">
              <span class="icon">${getIcon('magnify')}</span>
            </span>
            <input type="text" class="mc-search-input" placeholder="搜尋訊息..." id="mcSearchInput">
          </div>
          <div class="mc-filter-group">
            <select class="mc-filter-select" id="mcSeverityFilter">
              <option value="">全部程度</option>
              <option value="critical">嚴重</option>
              <option value="error">錯誤</option>
              <option value="warning">警告</option>
              <option value="info">資訊</option>
              <option value="debug">除錯</option>
            </select>
            <select class="mc-filter-select" id="mcSourceFilter">
              <option value="">全部來源</option>
              <option value="security">安全</option>
              <option value="system">系統</option>
              <option value="app">應用</option>
              <option value="user">使用者</option>
            </select>
          </div>
          <div class="mc-toolbar-actions">
            <button class="mc-btn" onclick="MessageCenterApp.markAllAsRead()">
              <span class="icon">${getIcon('check-all')}</span>
              全部已讀
            </button>
            <button class="mc-btn" onclick="MessageCenterApp.refresh()">
              <span class="icon">${getIcon('refresh')}</span>
              重新整理
            </button>
          </div>
        </div>

        <!-- Content -->
        <div class="mc-content">
          <div class="mc-list">
            <div class="mc-loading">
              <span class="icon">${getIcon('loading')}</span>
              載入中...
            </div>
          </div>
          <div class="mc-detail"></div>
        </div>

        <!-- Pagination -->
        <div class="mc-pagination"></div>
      </div>
    `;
  }

  /**
   * 初始化視窗
   */
  function init(windowElement) {
    container = windowElement.querySelector('.message-center');
    if (!container) {
      windowElement.querySelector('.window-content').innerHTML = createContent();
      container = windowElement.querySelector('.message-center');
    }

    // 綁定搜尋事件
    const searchInput = container.querySelector('#mcSearchInput');
    let searchTimeout;
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        setSearch(e.target.value);
      }, 300);
    });

    // 綁定過濾事件
    container.querySelector('#mcSeverityFilter').addEventListener('change', (e) => {
      setSeverityFilter(e.target.value);
    });
    container.querySelector('#mcSourceFilter').addEventListener('change', (e) => {
      setSourceFilter(e.target.value);
    });

    // 載入資料
    loadMessages();
    loadUnreadCount();
  }

  /**
   * 重新整理
   */
  function refresh() {
    loadMessages();
    loadUnreadCount();
  }

  /**
   * 處理新訊息事件（WebSocket）
   */
  function handleNewMessage(msg) {
    // 如果視窗已開啟，重新載入
    if (container) {
      loadMessages();
    }
    loadUnreadCount();

    // 顯示 Toast 通知（warning 以上）
    if (['warning', 'error', 'critical'].includes(msg.severity)) {
      if (window.NotificationModule) {
        NotificationModule.show({
          title: msg.title,
          message: '點擊查看詳情',
          type: msg.severity === 'critical' ? 'error' : msg.severity,
          duration: 5000,
        });
      }
    }
  }

  /**
   * 開啟訊息中心視窗
   */
  function open() {
    // 檢查是否已開啟
    const existing = WindowModule.getWindowByAppId(APP_ID);
    if (existing) {
      WindowModule.focusWindow(existing.windowId);
      if (!existing.minimized) return;
      WindowModule.restoreWindow(existing.windowId);
      return;
    }

    // 建立新視窗
    windowId = WindowModule.createWindow({
      title: '訊息中心',
      appId: APP_ID,
      icon: 'bell',
      width: 800,
      height: 600,
      content: createContent(),
      onClose: handleClose,
      onInit: init,
    });
  }

  /**
   * 處理視窗關閉
   */
  function handleClose() {
    windowId = null;
    container = null;
    selectedMessage = null;
  }

  /**
   * 關閉視窗
   */
  function close() {
    if (windowId) {
      WindowModule.closeWindow(windowId);
    }
  }

  /**
   * 檢查視窗是否開啟
   */
  function isOpen() {
    return windowId !== null;
  }

  // Public API
  return {
    init,
    open,
    close,
    isOpen,
    refresh,
    loadMessages,
    loadUnreadCount,
    updateBadge,
    markAllAsRead,
    goToPage,
    prevPage,
    nextPage,
    hideDetail,
    handleNewMessage,
    getUnreadCount: () => unreadCount,
  };
})();

// 匯出供全域使用
window.MessageCenterApp = MessageCenterApp;
