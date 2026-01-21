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
    // 判斷是否已設定密碼
    const hasPassword = user.has_password || false;
    const passwordBtnText = hasPassword ? '變更密碼' : '設定密碼';
    const passwordBtnIcon = hasPassword ? 'lock-reset' : 'lock-plus';

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

          <div class="form-group">
            <label>密碼</label>
            <div class="password-status">
              <span class="status-text">${hasPassword ? '已設定' : '尚未設定（使用 NAS 認證）'}</span>
              <button class="btn btn-sm btn-ghost" id="changePasswordBtn">
                <span class="icon">${getIcon(passwordBtnIcon)}</span>
                ${passwordBtnText}
              </button>
            </div>
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

    // Bind change password button
    const changePasswordBtn = contentEl.querySelector('#changePasswordBtn');
    changePasswordBtn.addEventListener('click', () => openChangePasswordDialog(hasPassword));
  }

  /**
   * Open change password dialog
   * @param {boolean} hasPassword - 是否已有密碼
   */
  function openChangePasswordDialog(hasPassword) {
    const dialog = document.createElement('div');
    dialog.className = 'modal-overlay';
    dialog.innerHTML = `
      <div class="modal change-password-modal">
        <div class="modal-header">
          <h3>${hasPassword ? '變更密碼' : '設定密碼'}</h3>
          <button class="btn btn-ghost btn-sm modal-close-btn">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="modal-body">
          ${hasPassword ? `
            <div class="form-group">
              <label for="currentPassword">目前密碼</label>
              <input type="password" id="currentPassword" class="input" placeholder="輸入目前密碼">
            </div>
          ` : `
            <p class="form-hint" style="margin-bottom: var(--spacing-md);">
              <span class="icon">${getIcon('information')}</span>
              設定密碼後，您可以使用密碼登入，不再依賴 NAS 認證。
            </p>
          `}
          <div class="form-group">
            <label for="newPassword">新密碼</label>
            <input type="password" id="newPassword" class="input" placeholder="至少 8 個字元">
          </div>
          <div class="form-group">
            <label for="confirmPassword">確認新密碼</label>
            <input type="password" id="confirmPassword" class="input" placeholder="再次輸入新密碼">
          </div>
          <div id="changePasswordMessage"></div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost modal-cancel-btn">取消</button>
          <button class="btn btn-primary modal-confirm-btn">${hasPassword ? '變更密碼' : '設定密碼'}</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    // Close handlers
    const closeDialog = () => dialog.remove();
    dialog.querySelector('.modal-close-btn').addEventListener('click', closeDialog);
    dialog.querySelector('.modal-cancel-btn').addEventListener('click', closeDialog);
    dialog.addEventListener('click', (e) => {
      if (e.target === dialog) closeDialog();
    });

    // Confirm handler
    dialog.querySelector('.modal-confirm-btn').addEventListener('click', async () => {
      const currentPassword = hasPassword ? dialog.querySelector('#currentPassword').value : null;
      const newPassword = dialog.querySelector('#newPassword').value;
      const confirmPassword = dialog.querySelector('#confirmPassword').value;
      const messageEl = dialog.querySelector('#changePasswordMessage');
      const confirmBtn = dialog.querySelector('.modal-confirm-btn');

      // Validation
      if (hasPassword && !currentPassword) {
        messageEl.className = 'user-profile-message error';
        messageEl.textContent = '請輸入目前密碼';
        return;
      }
      if (!newPassword || newPassword.length < 8) {
        messageEl.className = 'user-profile-message error';
        messageEl.textContent = '新密碼至少需要 8 個字元';
        return;
      }
      if (newPassword !== confirmPassword) {
        messageEl.className = 'user-profile-message error';
        messageEl.textContent = '兩次輸入的密碼不一致';
        return;
      }

      confirmBtn.disabled = true;
      confirmBtn.textContent = '處理中...';

      try {
        const result = await changePassword(currentPassword, newPassword);
        if (result.success) {
          closeDialog();
          showToast(hasPassword ? '密碼已變更' : '密碼已設定', 'check');
          // 重新載入使用者資訊以更新狀態
          if (currentWindowId) {
            const windowEl = document.getElementById(currentWindowId);
            if (windowEl) {
              initWindow(windowEl);
            }
          }
        } else {
          messageEl.className = 'user-profile-message error';
          messageEl.textContent = result.error || '操作失敗';
          confirmBtn.disabled = false;
          confirmBtn.textContent = hasPassword ? '變更密碼' : '設定密碼';
        }
      } catch (error) {
        messageEl.className = 'user-profile-message error';
        messageEl.textContent = error.message || '操作失敗';
        confirmBtn.disabled = false;
        confirmBtn.textContent = hasPassword ? '變更密碼' : '設定密碼';
      }
    });

    // Focus first input
    setTimeout(() => {
      const firstInput = dialog.querySelector(hasPassword ? '#currentPassword' : '#newPassword');
      if (firstInput) firstInput.focus();
    }, 100);
  }

  /**
   * Call change password API
   * @param {string|null} currentPassword
   * @param {string} newPassword
   * @returns {Promise<Object>}
   */
  async function changePassword(currentPassword, newPassword) {
    const token = LoginModule.getToken();
    const response = await fetch('/api/auth/change-password', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword
      })
    });

    return response.json();
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
