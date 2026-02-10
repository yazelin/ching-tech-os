/**
 * 分享管理應用程式
 * 管理所有公開分享連結
 */

const ShareManagerApp = (function() {
  'use strict';

  const APP_ID = 'share-manager';
  let currentWindowId = null;
  let links = [];
  let filterType = 'all';
  let viewMode = 'mine';  // 'mine' 或 'all'（管理員）
  let isAdmin = false;

  /**
   * 取得圖示 HTML（包含 .icon 包裝）
   */
  function icon(name, extraClass = '') {
    if (typeof window.getIcon === 'function') {
      return `<span class="icon ${extraClass}">${window.getIcon(name)}</span>`;
    }
    return `<span class="icon ${extraClass}"><span class="mdi mdi-${name}"></span></span>`;
  }

  /**
   * 格式化日期時間
   */
  function formatDateTime(dateStr) {
    if (!dateStr) return '永不過期';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-TW', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  /**
   * 檢查連結是否過期
   */
  function isExpired(expiresAt) {
    if (!expiresAt) return false;
    return new Date(expiresAt) < new Date();
  }

  /**
   * 複製文字到剪貼簿
   */
  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      const result = document.execCommand('copy');
      document.body.removeChild(textarea);
      return result;
    }
  }

  /**
   * API 請求
   */
  async function apiRequest(endpoint, options = {}) {
    const token = typeof LoginModule !== 'undefined' ? LoginModule.getToken() : null;
    const response = await fetch(`/api/share${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...options.headers
      }
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || '請求失敗');
    }

    // 204 No Content 沒有 body
    if (response.status === 204) {
      return null;
    }

    return response.json();
  }

  /**
   * 取得視窗內容 HTML
   */
  function getWindowContent() {
    return `
      <div class="share-manager">
        <div class="sm-toolbar">
          <div class="sm-toolbar-title">
            ${icon('share-variant')}
            <span id="smTitle">分享連結</span>
          </div>
          <div class="sm-toolbar-spacer"></div>
          <div class="sm-view-toggle" id="smViewToggle" style="display: none;">
            <button class="sm-view-btn active" data-view="mine">我的</button>
            <button class="sm-view-btn" data-view="all">全部</button>
          </div>
          <select class="sm-filter-select" id="smFilterType">
            <option value="all">全部類型</option>
            <option value="knowledge">知識庫</option>
            <option value="project">專案</option>
          </select>
          <button class="sm-refresh-btn" id="smRefreshBtn">
            ${icon('refresh')}
            <span>重新整理</span>
          </button>
        </div>
        <div class="sm-content" id="smContent">
          <div class="sm-loading">
            ${icon('loading', 'mdi-spin')}
            <span>載入中...</span>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * 載入分享連結列表
   */
  async function loadLinks(windowEl) {
    const contentEl = windowEl.querySelector('#smContent');
    if (!contentEl) return;

    /* [Sprint6] 原: <div class="sm-loading">${icon('loading', 'mdi-spin')}... 載入中... */
    UIHelpers.showLoading(contentEl, { text: '載入中...' });

    try {
      const result = await apiRequest(`?view=${viewMode}`);
      links = result.links || [];
      isAdmin = result.is_admin || false;

      // 顯示/隱藏管理員切換按鈕
      const viewToggle = windowEl.querySelector('#smViewToggle');
      if (viewToggle) {
        viewToggle.style.display = isAdmin ? 'flex' : 'none';
      }

      // 更新標題
      const titleEl = windowEl.querySelector('#smTitle');
      if (titleEl) {
        titleEl.textContent = viewMode === 'all' ? '全部分享連結' : '我的分享連結';
      }

      renderLinks(contentEl);
    } catch (error) {
      console.error('Failed to load share links:', error);
      /* [Sprint6] 原: <div class="sm-error">${icon('alert-circle')}... + retry btn */
      UIHelpers.showError(contentEl, { message: error.message, onRetry: () => loadLinks(windowEl) });
    }
  }

  /**
   * 渲染連結列表
   */
  function renderLinks(contentEl) {
    // 過濾
    let filteredLinks = links;
    if (filterType !== 'all') {
      filteredLinks = links.filter(l => l.resource_type === filterType);
    }

    if (filteredLinks.length === 0) {
      /* [Sprint6] 原: <div class="sm-empty">${icon('link-off')}... 目前沒有分享連結 */
      UIHelpers.showEmpty(contentEl, { icon: 'link-off', text: '目前沒有分享連結' });
      return;
    }

    // 統計
    const activeCount = filteredLinks.filter(l => !isExpired(l.expires_at)).length;
    const expiredCount = filteredLinks.filter(l => isExpired(l.expires_at)).length;

    contentEl.innerHTML = `
      <div class="sm-stats">
        <div class="sm-stat-item">
          <span>有效連結:</span>
          <span class="sm-stat-value">${activeCount}</span>
        </div>
        <div class="sm-stat-item">
          <span>已過期:</span>
          <span class="sm-stat-value">${expiredCount}</span>
        </div>
        <div class="sm-stat-item">
          <span>總數:</span>
          <span class="sm-stat-value">${filteredLinks.length}</span>
        </div>
      </div>
      <div class="sm-links-list">
        ${filteredLinks.map(link => renderLinkCard(link)).join('')}
      </div>
    `;

    // 綁定事件
    bindLinkEvents(contentEl);
  }

  /**
   * 渲染連結卡片
   */
  function renderLinkCard(link) {
    const expired = isExpired(link.expires_at);
    const typeLabel = link.resource_type === 'knowledge' ? '知識庫' : '專案';
    const typeIcon = link.resource_type === 'knowledge' ? 'book-open-variant' : 'folder-account';

    let statusClass, statusText;
    if (expired) {
      statusClass = 'expired';
      statusText = '已過期';
    } else if (!link.expires_at) {
      statusClass = 'permanent';
      statusText = '永久有效';
    } else {
      statusClass = 'active';
      statusText = '有效';
    }

    return `
      <div class="sm-link-card ${expired ? 'expired' : ''}" data-token="${link.token}">
        <div class="sm-link-header">
          <div class="sm-link-info">
            <h4 class="sm-link-title">
              <span class="sm-link-type ${link.resource_type}">
                ${icon(typeIcon)}
                <span>${typeLabel}</span>
              </span>
              <span class="sm-link-name">${escapeHtml(link.resource_title || link.resource_id)}</span>
            </h4>
            <div class="sm-link-meta">
              ${viewMode === 'all' && link.created_by ? `
              <span class="sm-link-meta-item">
                ${icon('account')}
                <span>${escapeHtml(link.created_by)}</span>
              </span>
              ` : ''}
              <span class="sm-link-meta-item">
                ${icon('clock-outline')}
                <span>建立於 ${formatDateTime(link.created_at)}</span>
              </span>
              <span class="sm-link-meta-item">
                ${icon('eye')}
                <span>${link.access_count} 次存取</span>
              </span>
              ${link.expires_at ? `
              <span class="sm-link-meta-item">
                ${icon('timer-sand')}
                <span>${expired ? '過期於' : '有效至'} ${formatDateTime(link.expires_at)}</span>
              </span>
              ` : ''}
            </div>
          </div>
          <span class="sm-link-status ${statusClass}">${statusText}</span>
        </div>
        <div class="sm-link-url-section">
          <span class="sm-link-url">${escapeHtml(link.full_url)}</span>
          <button class="sm-link-copy-btn" data-url="${escapeHtml(link.full_url)}">
            ${icon('content-copy')}
            <span>複製</span>
          </button>
        </div>
        <div class="sm-link-actions">
          <button class="sm-link-action-btn" data-action="open" data-url="${escapeHtml(link.full_url)}">
            ${icon('open-in-new')}
            <span>開啟</span>
          </button>
          <button class="sm-link-action-btn danger" data-action="delete" data-token="${link.token}">
            ${icon('delete')}
            <span>撤銷</span>
          </button>
        </div>
      </div>
    `;
  }

  /**
   * 綁定連結事件
   */
  function bindLinkEvents(contentEl) {
    // 複製按鈕
    contentEl.querySelectorAll('.sm-link-copy-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const url = btn.dataset.url;
        const success = await copyToClipboard(url);
        if (success) {
          btn.classList.add('copied');
          btn.innerHTML = `${icon('check')}<span>已複製</span>`;

          if (typeof DesktopModule !== 'undefined') {
            DesktopModule.showToast('連結已複製到剪貼簿', 'check');
          }

          setTimeout(() => {
            btn.classList.remove('copied');
            btn.innerHTML = `${icon('content-copy')}<span>複製</span>`;
          }, 2000);
        }
      });
    });

    // 開啟按鈕
    contentEl.querySelectorAll('[data-action="open"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const url = btn.dataset.url;
        window.open(url, '_blank');
      });
    });

    // 撤銷按鈕
    contentEl.querySelectorAll('[data-action="delete"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const token = btn.dataset.token;
        if (!confirm('確定要撤銷此分享連結嗎？撤銷後連結將立即失效。')) return;

        try {
          await apiRequest(`/${token}`, { method: 'DELETE' });

          // 從列表中移除
          links = links.filter(l => l.token !== token);
          renderLinks(contentEl);

          if (typeof NotificationModule !== 'undefined') {
            NotificationModule.show({
              title: '成功',
              message: '分享連結已撤銷',
              icon: 'check-circle'
            });
          }
        } catch (error) {
          console.error('Failed to revoke link:', error);
          if (typeof NotificationModule !== 'undefined') {
            NotificationModule.show({
              title: '失敗',
              message: error.message,
              icon: 'alert-circle'
            });
          }
        }
      });
    });
  }

  /**
   * HTML 跳脫
   */
  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  /**
   * 初始化視窗
   */
  function init(windowEl) {
    // 視圖切換（管理員用）
    const viewToggle = windowEl.querySelector('#smViewToggle');
    if (viewToggle) {
      viewToggle.querySelectorAll('.sm-view-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const newView = btn.dataset.view;
          if (newView !== viewMode) {
            viewMode = newView;
            // 更新按鈕狀態
            viewToggle.querySelectorAll('.sm-view-btn').forEach(b => {
              b.classList.toggle('active', b.dataset.view === viewMode);
            });
            // 重新載入
            loadLinks(windowEl);
          }
        });
      });
    }

    // 過濾選擇
    const filterSelect = windowEl.querySelector('#smFilterType');
    if (filterSelect) {
      filterSelect.value = filterType;
      filterSelect.addEventListener('change', () => {
        filterType = filterSelect.value;
        const contentEl = windowEl.querySelector('#smContent');
        if (contentEl) {
          renderLinks(contentEl);
        }
      });
    }

    // 重新整理按鈕
    const refreshBtn = windowEl.querySelector('#smRefreshBtn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => loadLinks(windowEl));
    }

    // 載入資料
    loadLinks(windowEl);
  }

  /**
   * 開啟應用程式
   */
  function open() {
    // 如果已開啟，則聚焦
    if (currentWindowId) {
      const windowEl = document.getElementById(currentWindowId);
      if (windowEl) {
        WindowModule.focusWindow(currentWindowId);
        return currentWindowId;
      }
    }

    // 建立新視窗
    currentWindowId = WindowModule.createWindow({
      title: '分享管理',
      appId: APP_ID,
      icon: 'share-variant',
      width: 700,
      height: 500,
      content: getWindowContent(),
      onInit: (windowEl, windowId) => {
        init(windowEl);
      },
      onClose: (windowId) => {
        currentWindowId = null;
      }
    });

    return currentWindowId;
  }

  // 公開 API
  return {
    open
  };
})();
