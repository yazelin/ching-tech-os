/**
 * ChingTech OS - User Profile Module
 * Handles user profile window: view and edit user information
 */

const UserProfileModule = (function() {
  'use strict';

  const APP_ID = 'user-profile';
  let currentWindowId = null;

  /**
   * Format datetime for display
   * @param {string} isoString
   * @returns {string}
   */
  function formatDateTime(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString('zh-TW', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  /**
   * Get the window content HTML
   * @returns {string}
   */
  function getWindowContent() {
    return `
      <div class="user-profile-content">
        <div class="user-profile-loading">載入中...</div>
      </div>
    `;
  }

  /**
   * Render user info
   * @param {HTMLElement} contentEl
   * @param {Object} user
   */
  function renderUserInfo(contentEl, user) {
    contentEl.innerHTML = `
      <div class="user-profile-main">
        <div class="user-profile-left">
          <div class="avatar-icon">
            <span class="icon">${getIcon('account-circle')}</span>
          </div>
          <div class="username">${user.username}</div>
        </div>

        <div class="user-profile-right">
          <div class="form-group">
            <label>顯示名稱</label>
            <input type="text" id="userDisplayName" value="${user.display_name || ''}" placeholder="輸入顯示名稱">
          </div>

          <div class="form-group">
            <label>首次登入</label>
            <div class="info-text">${formatDateTime(user.created_at)}</div>
          </div>

          <div class="form-group">
            <label>最後登入</label>
            <div class="info-text">${formatDateTime(user.last_login_at)}</div>
          </div>

          <div id="userProfileMessage"></div>
        </div>
      </div>

      <div class="user-profile-actions">
        <button class="btn btn-primary" id="saveProfileBtn">儲存</button>
      </div>
    `;

    // Bind save button
    const saveBtn = contentEl.querySelector('#saveProfileBtn');
    saveBtn.addEventListener('click', () => handleSave(contentEl));
  }

  /**
   * Show message
   * @param {HTMLElement} contentEl
   * @param {string} message
   * @param {string} type - 'success' or 'error'
   */
  function showMessage(contentEl, message, type) {
    const messageEl = contentEl.querySelector('#userProfileMessage');
    if (messageEl) {
      messageEl.className = `user-profile-message ${type}`;
      messageEl.textContent = message;
      setTimeout(() => {
        messageEl.textContent = '';
        messageEl.className = '';
      }, 3000);
    }
  }

  /**
   * Fetch user info from API
   * @returns {Promise<Object>}
   */
  async function fetchUserInfo() {
    const token = LoginModule.getToken();
    const response = await fetch('/api/user/me', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    if (!response.ok) {
      throw new Error('無法取得使用者資訊');
    }

    return response.json();
  }

  /**
   * Update user info via API
   * @param {string} displayName
   * @returns {Promise<Object>}
   */
  async function updateUserInfo(displayName) {
    const token = LoginModule.getToken();
    const response = await fetch('/api/user/me', {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ display_name: displayName })
    });

    if (!response.ok) {
      throw new Error('更新失敗');
    }

    return response.json();
  }

  /**
   * Handle save button click
   * @param {HTMLElement} contentEl
   */
  async function handleSave(contentEl) {
    const displayNameInput = contentEl.querySelector('#userDisplayName');
    const saveBtn = contentEl.querySelector('#saveProfileBtn');

    if (!displayNameInput || !saveBtn) return;

    const displayName = displayNameInput.value.trim();

    saveBtn.disabled = true;
    saveBtn.textContent = '儲存中...';

    try {
      const user = await updateUserInfo(displayName);
      showMessage(contentEl, '儲存成功', 'success');

      // Update header display name
      updateHeaderDisplayName(user.display_name || user.username);
    } catch (error) {
      showMessage(contentEl, error.message || '儲存失敗', 'error');
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = '儲存';
    }
  }

  /**
   * Update the header display name
   * @param {string} name
   */
  function updateHeaderDisplayName(name) {
    const headerUserName = document.getElementById('headerUserName');
    if (headerUserName) {
      headerUserName.textContent = name;
    }
  }

  /**
   * Initialize window content
   * @param {HTMLElement} windowEl
   */
  async function initWindow(windowEl) {
    const contentEl = windowEl.querySelector('.user-profile-content');
    if (!contentEl) return;

    try {
      const user = await fetchUserInfo();
      renderUserInfo(contentEl, user);
    } catch (error) {
      contentEl.innerHTML = `
        <div class="user-profile-message error" style="margin: var(--spacing-lg);">
          ${error.message || '無法載入使用者資訊'}
        </div>
      `;
    }
  }

  /**
   * Open user profile window
   */
  function open() {
    // Check if already open
    if (typeof WindowModule !== 'undefined') {
      const existingWindow = WindowModule.getWindowByAppId(APP_ID);
      if (existingWindow) {
        WindowModule.focusWindow(existingWindow.windowId);
        return;
      }
    }

    // Create window
    currentWindowId = WindowModule.createWindow({
      title: '使用者資訊',
      appId: APP_ID,
      icon: 'account-circle',
      width: 500,
      height: 320,
      content: getWindowContent(),
      onInit: initWindow,
      onClose: () => {
        currentWindowId = null;
      }
    });

    // Add custom class for styling
    const windowEl = document.getElementById(currentWindowId);
    if (windowEl) {
      windowEl.classList.add('user-profile-window');
    }
  }

  /**
   * Close user profile window
   */
  function close() {
    if (currentWindowId && typeof WindowModule !== 'undefined') {
      WindowModule.closeWindow(currentWindowId);
      currentWindowId = null;
    }
  }

  // Public API
  return {
    open,
    close
  };
})();
