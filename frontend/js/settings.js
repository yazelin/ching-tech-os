/**
 * ChingTech OS - Settings Application
 * 系統設定應用程式：主題設定、偏好管理、使用者管理、Bot 設定
 */

const SettingsApp = (function () {
  'use strict';

  const APP_ID = 'settings';
  let currentWindowId = null;

  /** HTML 特殊字元跳脫 */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // 應用程式名稱對照
  const APP_NAMES = {
    'file-manager': '檔案管理',
    'terminal': '終端機',
    'code-editor': 'VSCode',
    'project-management': '專案管理',
    'ai-assistant': 'AI 助手',
    'prompt-editor': 'Prompt 編輯器',
    'agent-settings': 'Agent 設定',
    'ai-log': 'AI Log',
    'knowledge-base': '知識庫',
    'linebot': 'Bot 管理',
    'settings': '系統設定',
  };

  /**
   * 取得視窗內容 HTML
   * @returns {string}
   */
  function getWindowContent() {
    const currentTheme = ThemeManager.getTheme();
    const isAdmin = typeof PermissionsModule !== 'undefined' && PermissionsModule.isAdmin();

    return `
      <div class="settings-container">
        <nav class="settings-sidebar">
          <ul class="settings-nav">
            <li class="settings-nav-item active" data-section="appearance">
              <span class="icon">${getIcon('palette')}</span>
              <span>外觀</span>
            </li>
            ${isAdmin ? `
            <li class="settings-nav-item" data-section="users">
              <span class="icon">${getIcon('account-group')}</span>
              <span>使用者管理</span>
            </li>
            <li class="settings-nav-item" data-section="bot-settings">
              <span class="icon">${getIcon('robot')}</span>
              <span>Bot 設定</span>
            </li>
            ` : ''}
          </ul>
        </nav>

        <main class="settings-content">
          <!-- 外觀設定 -->
          <section class="settings-section active" id="section-appearance">
            <h2 class="settings-section-title">外觀設定</h2>

            <div class="settings-group">
              <h3 class="settings-group-title">主題</h3>
              <div class="theme-cards">
                <div class="theme-card ${currentTheme === 'dark' ? 'selected' : ''}" data-theme="dark">
                  <div class="theme-card-preview">
                    <div class="preview-header"></div>
                    <div class="preview-content">
                      <div class="preview-accent"></div>
                    </div>
                  </div>
                  <div class="theme-card-info">
                    <span class="theme-card-name">暗色主題</span>
                    <span class="theme-card-check">
                      <span class="icon">${getIcon('check')}</span>
                    </span>
                  </div>
                </div>

                <div class="theme-card ${currentTheme === 'light' ? 'selected' : ''}" data-theme="light">
                  <div class="theme-card-preview">
                    <div class="preview-header"></div>
                    <div class="preview-content">
                      <div class="preview-accent"></div>
                    </div>
                  </div>
                  <div class="theme-card-info">
                    <span class="theme-card-name">亮色主題</span>
                    <span class="theme-card-check">
                      <span class="icon">${getIcon('check')}</span>
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div class="settings-group">
              <h3 class="settings-group-title">預覽</h3>
              <div class="preview-panel">
                <div class="preview-panel-title">UI 元件預覽</div>
                <div class="preview-elements">
                  <div class="preview-element">
                    <span class="preview-element-label">按鈕</span>
                    <div style="display: flex; gap: 8px;">
                      <button class="btn btn-primary">主要</button>
                      <button class="btn btn-accent">強調</button>
                      <button class="btn btn-ghost">幽靈</button>
                    </div>
                  </div>

                  <div class="preview-element">
                    <span class="preview-element-label">標籤</span>
                    <div class="preview-badges">
                      <span class="preview-badge success">已完成</span>
                      <span class="preview-badge warning">待處理</span>
                      <span class="preview-badge error">緊急</span>
                      <span class="preview-badge info">進行中</span>
                    </div>
                  </div>

                  <div class="preview-element">
                    <span class="preview-element-label">輸入框</span>
                    <input type="text" class="input preview-input" placeholder="輸入文字...">
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- 使用者管理（管理員限定） -->
          ${isAdmin ? `
          <section class="settings-section" id="section-users">
            <h2 class="settings-section-title">使用者管理</h2>

            <div class="settings-group">
              <div class="users-list-container">
                <!-- [Sprint7] 原始: <div class="users-loading"><span class="icon">${getIcon('loading','mdi-spin')}</span><span>載入中...</span></div> -->
              </div>
            </div>
          </section>

          <section class="settings-section" id="section-bot-settings">
            <h2 class="settings-section-title">Bot 設定</h2>
            <div class="bot-settings-container">
              <!-- [Sprint7] 原始: <div class="users-loading"><span class="icon">${getIcon('loading','mdi-spin')}</span><span>載入中...</span></div> -->
            </div>
          </section>
          ` : ''}
        </main>

        <!-- 手機版底部 Tab Bar -->
        <nav class="mobile-tab-bar settings-mobile-tabs">
          <button class="mobile-tab-item active" data-section="appearance">
            <span class="icon">${getIcon('palette')}</span>
            <span class="mobile-tab-label">外觀</span>
          </button>
          ${isAdmin ? `
          <button class="mobile-tab-item" data-section="users">
            <span class="icon">${getIcon('account-group')}</span>
            <span class="mobile-tab-label">使用者</span>
          </button>
          <button class="mobile-tab-item" data-section="bot-settings">
            <span class="icon">${getIcon('robot')}</span>
            <span class="mobile-tab-label">Bot</span>
          </button>
          ` : ''}
        </nav>
      </div>
    `;
  }

  /**
   * 初始化設定視窗
   * @param {HTMLElement} windowEl - 視窗元素
   */
  function init(windowEl) {
    // 綁定主題卡片點擊事件
    const themeCards = windowEl.querySelectorAll('.theme-card');
    themeCards.forEach(card => {
      card.addEventListener('click', () => {
        const theme = card.dataset.theme;
        selectTheme(windowEl, theme);
      });
    });

    // 綁定側邊欄導航
    const navItems = windowEl.querySelectorAll('.settings-nav-item');
    navItems.forEach(item => {
      item.addEventListener('click', () => {
        const section = item.dataset.section;
        switchSection(windowEl, section);
      });
    });

    // 綁定手機版底部 Tab Bar
    const mobileTabs = windowEl.querySelectorAll('.settings-mobile-tabs .mobile-tab-item');
    mobileTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const section = tab.dataset.section;
        switchSection(windowEl, section);
      });
    });
  }

  /**
   * 選擇主題（即時套用並儲存）
   * @param {HTMLElement} windowEl
   * @param {string} theme
   */
  function selectTheme(windowEl, theme) {
    // 更新 UI 選中狀態
    const themeCards = windowEl.querySelectorAll('.theme-card');
    themeCards.forEach(card => {
      card.classList.toggle('selected', card.dataset.theme === theme);
    });

    // 即時套用並儲存主題
    ThemeManager.setTheme(theme);
  }

  /**
   * 切換設定區段
   * @param {HTMLElement} windowEl
   * @param {string} sectionId
   */
  function switchSection(windowEl, sectionId) {
    // 更新側邊欄導航狀態
    const navItems = windowEl.querySelectorAll('.settings-nav-item');
    navItems.forEach(item => {
      item.classList.toggle('active', item.dataset.section === sectionId);
    });

    // 更新手機版 Tab 狀態
    const mobileTabs = windowEl.querySelectorAll('.settings-mobile-tabs .mobile-tab-item');
    mobileTabs.forEach(tab => {
      tab.classList.toggle('active', tab.dataset.section === sectionId);
    });

    // 切換顯示區段
    const sections = windowEl.querySelectorAll('.settings-section');
    sections.forEach(section => {
      section.classList.toggle('active', section.id === `section-${sectionId}`);
    });

    // 如果切換到使用者管理，載入使用者列表
    if (sectionId === 'users') {
      // [Sprint7] 使用 UIHelpers 顯示初始 loading 狀態
      const usersContainer = windowEl.querySelector('.users-list-container');
      if (usersContainer) UIHelpers.showLoading(usersContainer, { text: '載入中…' });
      loadUsersList(windowEl);
    }
    // 如果切換到 Bot 設定，載入設定
    if (sectionId === 'bot-settings') {
      const botContainer = windowEl.querySelector('.bot-settings-container');
      if (botContainer) UIHelpers.showLoading(botContainer, { text: '載入中…' });
      loadBotSettings(windowEl);
    }
  }

  /**
   * 載入使用者列表
   * @param {HTMLElement} windowEl
   */
  async function loadUsersList(windowEl) {
    const container = windowEl.querySelector('.users-list-container');
    if (!container) return;

    try {
      const token = LoginModule.getToken();

      const response = await fetch('/api/admin/users', {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (!response.ok) {
        throw new Error('載入失敗');
      }

      const data = await response.json();
      renderUsersList(container, data.users);
    } catch (error) {
      // [Sprint7] 原始: container.innerHTML = '<div class="users-error">...<span>載入使用者列表失敗</span></div>'
      UIHelpers.showError(container, { message: '載入使用者列表失敗', detail: escapeHtml(error.message), onRetry: () => loadUsersList(windowEl) });
    }
  }

  /**
   * 檢查是否可以管理目標使用者
   * 前端刻意隱藏 admin 對 admin 的操作按鈕，避免管理員互相修改權限。
   * 後端 API 仍允許 admin 管理其他 admin（以備特殊需求）。
   * @param {string} targetRole - 目標使用者角色
   * @returns {boolean}
   */
  function canManageUser(targetRole) {
    return targetRole !== 'admin';
  }

  /**
   * 取得角色顯示文字
   * @param {string} role
   * @returns {string}
   */
  function getRoleDisplay(role) {
    const roleNames = {
      'admin': '管理員',
      'user': '一般使用者',
    };
    return roleNames[role] || '一般使用者';
  }

  /**
   * 取得認證方式顯示文字
   * @param {boolean} hasPassword
   * @returns {string}
   */
  function getAuthBadge(hasPassword) {
    if (hasPassword) {
      return '<span class="auth-badge auth-badge-password">密碼</span>';
    }
    return '<span class="auth-badge auth-badge-nas">NAS</span>';
  }

  /**
   * 渲染使用者列表
   * @param {HTMLElement} container
   * @param {Array} users
   */
  function renderUsersList(container, users) {
    container.innerHTML = `
      <div class="users-toolbar">
        <button class="btn btn-primary btn-sm users-add-btn">
          <span class="icon">${getIcon('account-plus')}</span> 新增使用者
        </button>
      </div>
      <table class="users-table">
        <thead>
          <tr>
            <th>使用者</th>
            <th>顯示名稱</th>
            <th>角色</th>
            <th>認證</th>
            <th>最後登入</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          ${users.map(user => {
            const userRole = user.role || 'user';
            const roleIcon = userRole === 'admin' ? 'shield-crown' : '';
            const roleClass = userRole === 'admin' ? 'user-admin-badge' : '';
            const isInactive = !user.is_active;

            const safeUsername = escapeHtml(user.username);
            const safeDisplayName = escapeHtml(user.display_name || '-');

            return `
              <tr data-user-id="${user.id}" class="${isInactive ? 'user-row-inactive' : ''}">
                <td>
                  ${roleIcon ? `<span class="${roleClass} icon" title="${getRoleDisplay(userRole)}">${getIcon(roleIcon)}</span>` : ''}
                  ${safeUsername}
                  ${isInactive ? '<span class="user-inactive-label">已停用</span>' : ''}
                </td>
                <td>${safeDisplayName}</td>
                <td><span class="role-badge role-${userRole}">${getRoleDisplay(userRole)}</span></td>
                <td>${getAuthBadge(user.has_password)}</td>
                <td>${user.last_login_at ? new Date(user.last_login_at).toLocaleString('zh-TW') : '-'}</td>
                <td>
                  <div class="user-actions-wrapper">
                    <button class="btn btn-ghost btn-sm user-actions-btn" data-user-id="${user.id}">
                      <span class="icon">${getIcon('dots-vertical')}</span>
                    </button>
                  </div>
                </td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    `;

    // 綁定「新增使用者」按鈕
    container.querySelector('.users-add-btn').addEventListener('click', () => {
      openCreateUserDialog(container);
    });

    // 綁定操作下拉選單按鈕
    container.querySelectorAll('.user-actions-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const userId = parseInt(btn.dataset.userId, 10);
        const user = users.find(u => u.id === userId);
        if (user) {
          showUserActionsMenu(btn, container, user);
        }
      });
    });
  }

  /**
   * 顯示使用者操作下拉選單
   */
  function showUserActionsMenu(anchorBtn, container, user) {
    // 關閉其他已開啟的選單
    document.querySelectorAll('.user-actions-menu').forEach(m => m.remove());

    const currentSession = LoginModule.getSession();
    const isSelf = currentSession && currentSession.username === user.username;
    const isInactive = !user.is_active;

    const menuItems = [
      { label: '設定權限', icon: 'shield-edit', action: 'permissions' },
      { label: '編輯資訊', icon: 'account-edit', action: 'edit' },
      { label: '重設密碼', icon: 'lock-reset', action: 'reset-password' },
      {
        label: isInactive ? '啟用帳號' : '停用帳號',
        icon: isInactive ? 'account-check' : 'account-off',
        action: 'toggle-status',
        disabled: isSelf,
      },
      {
        label: '清除密碼（恢復 NAS）',
        icon: 'key-remove',
        action: 'clear-password',
        disabled: isSelf || !user.has_password,
      },
      {
        label: '刪除使用者',
        icon: 'delete',
        action: 'delete',
        disabled: isSelf,
        danger: true,
      },
    ];

    const menu = document.createElement('div');
    menu.className = 'user-actions-menu';
    menu.innerHTML = menuItems.map(item =>
      `<button class="user-actions-menu-item ${item.disabled ? 'disabled' : ''} ${item.danger ? 'danger' : ''}" data-action="${item.action}" ${item.disabled ? 'disabled' : ''}>
        <span class="icon">${getIcon(item.icon)}</span>
        <span>${item.label}</span>
      </button>`
    ).join('');

    // 定位選單
    const wrapper = anchorBtn.closest('.user-actions-wrapper');
    wrapper.appendChild(menu);

    // 綁定選單項目事件
    menu.querySelectorAll('.user-actions-menu-item:not(.disabled)').forEach(item => {
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.remove();
        const action = item.dataset.action;
        handleUserAction(action, container, user);
      });
    });

    // 點擊其他地方關閉選單
    const closeMenu = (e) => {
      if (!menu.contains(e.target)) {
        menu.remove();
        document.removeEventListener('click', closeMenu);
      }
    };
    setTimeout(() => document.addEventListener('click', closeMenu), 0);
  }

  /**
   * 處理使用者操作
   */
  function handleUserAction(action, container, user) {
    switch (action) {
      case 'permissions':
        openPermissionsDialog(container, user);
        break;
      case 'edit':
        openEditUserDialog(container, user);
        break;
      case 'reset-password':
        openResetPasswordDialog(container, user);
        break;
      case 'toggle-status':
        openToggleStatusDialog(container, user);
        break;
      case 'clear-password':
        openClearPasswordDialog(container, user);
        break;
      case 'delete':
        openDeleteUserDialog(container, user);
        break;
    }
  }

  /**
   * 建立通用對話框
   */
  function createDialog(title, bodyHtml, footerHtml) {
    const dialog = document.createElement('div');
    dialog.className = 'permissions-dialog-overlay';
    dialog.innerHTML = `
      <div class="permissions-dialog">
        <div class="permissions-dialog-header">
          <h3>${title}</h3>
          <button class="permissions-dialog-close">${getIcon('close')}</button>
        </div>
        <div class="permissions-dialog-body">
          ${bodyHtml}
        </div>
        <div class="permissions-dialog-footer">
          ${footerHtml}
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    // 關閉按鈕
    dialog.querySelector('.permissions-dialog-close').addEventListener('click', () => dialog.remove());
    dialog.addEventListener('click', (e) => {
      if (e.target === dialog) dialog.remove();
    });

    return dialog;
  }

  /**
   * 重新載入使用者列表的輔助函數
   */
  function reloadUsersList(container) {
    const windowEl = container.closest('.settings-container')?.querySelector('.settings-content')
      || container.closest('[id^="window-"]');
    if (windowEl) loadUsersList(windowEl);
  }

  /**
   * 開啟「新增使用者」對話框
   */
  function openCreateUserDialog(container) {
    const bodyHtml = `
      <div class="dialog-form">
        <div class="form-group">
          <label>使用者名稱 <span class="required">*</span></label>
          <input type="text" class="input" name="username" placeholder="請輸入帳號" required>
        </div>
        <div class="form-group">
          <label>密碼 <span class="required">*</span></label>
          <input type="password" class="input" name="password" placeholder="至少 8 個字元" required minlength="8">
        </div>
        <div class="form-group">
          <label>顯示名稱</label>
          <input type="text" class="input" name="display_name" placeholder="選填">
        </div>
        <div class="form-group">
          <label>角色</label>
          <select class="input" name="role">
            <option value="user">一般使用者</option>
            <option value="admin">管理員</option>
          </select>
        </div>
        <p class="dialog-hint">新帳號首次登入時會要求變更密碼。<br>若 NAS 上已有同名帳號，該使用者將改為密碼認證。</p>
        <div class="dialog-error" id="createUserError"></div>
      </div>
    `;
    const footerHtml = `
      <button class="btn btn-ghost dialog-cancel-btn">取消</button>
      <button class="btn btn-primary dialog-submit-btn">建立</button>
    `;

    const dialog = createDialog('新增使用者', bodyHtml, footerHtml);
    dialog.querySelector('.dialog-cancel-btn').addEventListener('click', () => dialog.remove());

    dialog.querySelector('.dialog-submit-btn').addEventListener('click', async () => {
      const username = dialog.querySelector('[name="username"]').value.trim();
      const password = dialog.querySelector('[name="password"]').value;
      const displayName = dialog.querySelector('[name="display_name"]').value.trim();
      const role = dialog.querySelector('[name="role"]').value;
      const errorDiv = dialog.querySelector('#createUserError');

      if (!username || !password) {
        errorDiv.textContent = '請填入帳號和密碼';
        errorDiv.classList.add('show');
        return;
      }
      if (password.length < 8) {
        errorDiv.textContent = '密碼至少需要 8 個字元';
        errorDiv.classList.add('show');
        return;
      }

      try {
        const token = LoginModule.getToken();
        const resp = await fetch('/api/admin/users', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password, display_name: displayName || null, role }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || '建立失敗');

        dialog.remove();
        reloadUsersList(container);
        if (typeof DesktopModule !== 'undefined') {
          DesktopModule.showToast(`已建立使用者 ${username}`, 'check');
        }
      } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.classList.add('show');
      }
    });
  }

  /**
   * 開啟「編輯使用者」對話框
   */
  function openEditUserDialog(container, user) {
    const bodyHtml = `
      <div class="dialog-form">
        <div class="form-group">
          <label>顯示名稱</label>
          <input type="text" class="input" name="display_name" value="${escapeHtml(user.display_name || '')}">
        </div>
        <div class="form-group">
          <label>Email</label>
          <input type="email" class="input" name="email" value="${escapeHtml(user.email || '')}" placeholder="選填">
        </div>
        <div class="form-group">
          <label>角色</label>
          <select class="input" name="role">
            <option value="user" ${user.role === 'user' ? 'selected' : ''}>一般使用者</option>
            <option value="admin" ${user.role === 'admin' ? 'selected' : ''}>管理員</option>
          </select>
        </div>
        <div class="dialog-error" id="editUserError"></div>
      </div>
    `;
    const footerHtml = `
      <button class="btn btn-ghost dialog-cancel-btn">取消</button>
      <button class="btn btn-primary dialog-submit-btn">儲存</button>
    `;

    const dialog = createDialog(`編輯 ${escapeHtml(user.username)}`, bodyHtml, footerHtml);
    dialog.querySelector('.dialog-cancel-btn').addEventListener('click', () => dialog.remove());

    dialog.querySelector('.dialog-submit-btn').addEventListener('click', async () => {
      const displayName = dialog.querySelector('[name="display_name"]').value.trim();
      const email = dialog.querySelector('[name="email"]').value.trim();
      const role = dialog.querySelector('[name="role"]').value;
      const errorDiv = dialog.querySelector('#editUserError');

      try {
        const token = LoginModule.getToken();
        const resp = await fetch(`/api/admin/users/${user.id}`, {
          method: 'PATCH',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ display_name: displayName || null, email: email || null, role }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || '更新失敗');

        dialog.remove();
        reloadUsersList(container);
        if (typeof DesktopModule !== 'undefined') {
          DesktopModule.showToast(`${user.username} 的資訊已更新`, 'check');
        }
      } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.classList.add('show');
      }
    });
  }

  /**
   * 開啟「重設密碼」對話框
   */
  function openResetPasswordDialog(container, user) {
    const bodyHtml = `
      <div class="dialog-form">
        <p>為 <strong>${escapeHtml(user.username)}</strong> 設定新密碼，使用者下次登入時需要變更密碼。</p>
        <div class="form-group">
          <label>新密碼 <span class="required">*</span></label>
          <input type="password" class="input" name="new_password" placeholder="至少 8 個字元" required minlength="8">
        </div>
        <div class="dialog-error" id="resetPasswordError"></div>
      </div>
    `;
    const footerHtml = `
      <button class="btn btn-ghost dialog-cancel-btn">取消</button>
      <button class="btn btn-primary dialog-submit-btn">重設密碼</button>
    `;

    const dialog = createDialog(`重設密碼 — ${escapeHtml(user.username)}`, bodyHtml, footerHtml);
    dialog.querySelector('.dialog-cancel-btn').addEventListener('click', () => dialog.remove());

    dialog.querySelector('.dialog-submit-btn').addEventListener('click', async () => {
      const newPassword = dialog.querySelector('[name="new_password"]').value;
      const errorDiv = dialog.querySelector('#resetPasswordError');

      if (!newPassword || newPassword.length < 8) {
        errorDiv.textContent = '密碼至少需要 8 個字元';
        errorDiv.classList.add('show');
        return;
      }

      try {
        const token = LoginModule.getToken();
        const resp = await fetch(`/api/admin/users/${user.id}/reset-password`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ new_password: newPassword }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || '重設失敗');

        dialog.remove();
        reloadUsersList(container);
        if (typeof DesktopModule !== 'undefined') {
          DesktopModule.showToast(`${user.username} 的密碼已重設`, 'check');
        }
      } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.classList.add('show');
      }
    });
  }

  /**
   * 開啟「停用/啟用」確認對話框
   */
  function openToggleStatusDialog(container, user) {
    const isInactive = !user.is_active;
    const actionText = isInactive ? '啟用' : '停用';
    const bodyHtml = `
      <p>確定要${actionText}使用者 <strong>${escapeHtml(user.username)}</strong> 嗎？</p>
      ${!isInactive ? '<p class="dialog-warning">停用後該使用者將無法登入系統。</p>' : ''}
      <div class="dialog-error" id="toggleStatusError"></div>
    `;
    const footerHtml = `
      <button class="btn btn-ghost dialog-cancel-btn">取消</button>
      <button class="btn ${isInactive ? 'btn-primary' : 'btn-accent'} dialog-submit-btn">${actionText}</button>
    `;

    const dialog = createDialog(`${actionText}帳號 — ${escapeHtml(user.username)}`, bodyHtml, footerHtml);
    dialog.querySelector('.dialog-cancel-btn').addEventListener('click', () => dialog.remove());

    dialog.querySelector('.dialog-submit-btn').addEventListener('click', async () => {
      const errorDiv = dialog.querySelector('#toggleStatusError');
      try {
        const token = LoginModule.getToken();
        const resp = await fetch(`/api/admin/users/${user.id}/status`, {
          method: 'PATCH',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_active: isInactive }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || '操作失敗');

        dialog.remove();
        reloadUsersList(container);
        if (typeof DesktopModule !== 'undefined') {
          DesktopModule.showToast(`${user.username} 已${actionText}`, 'check');
        }
      } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.classList.add('show');
      }
    });
  }

  /**
   * 開啟「清除密碼」確認對話框
   */
  function openClearPasswordDialog(container, user) {
    const bodyHtml = `
      <p>確定要清除 <strong>${escapeHtml(user.username)}</strong> 的密碼嗎？</p>
      <p class="dialog-warning">清除後該使用者將改為 NAS SMB 認證登入。如果 NAS 上沒有對應帳號，使用者將無法登入。</p>
      <div class="dialog-error" id="clearPasswordError"></div>
    `;
    const footerHtml = `
      <button class="btn btn-ghost dialog-cancel-btn">取消</button>
      <button class="btn btn-accent dialog-submit-btn">清除密碼</button>
    `;

    const dialog = createDialog(`清除密碼 — ${escapeHtml(user.username)}`, bodyHtml, footerHtml);
    dialog.querySelector('.dialog-cancel-btn').addEventListener('click', () => dialog.remove());

    dialog.querySelector('.dialog-submit-btn').addEventListener('click', async () => {
      const errorDiv = dialog.querySelector('#clearPasswordError');
      try {
        const token = LoginModule.getToken();
        const resp = await fetch(`/api/admin/users/${user.id}/clear-password`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || '清除失敗');

        dialog.remove();
        reloadUsersList(container);
        if (typeof DesktopModule !== 'undefined') {
          DesktopModule.showToast(`${user.username} 的密碼已清除，改為 NAS 認證`, 'check');
        }
      } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.classList.add('show');
      }
    });
  }

  /**
   * 開啟「刪除使用者」確認對話框
   */
  function openDeleteUserDialog(container, user) {
    const bodyHtml = `
      <p>確定要永久刪除使用者 <strong>${escapeHtml(user.username)}</strong> 嗎？</p>
      <p class="dialog-warning">此操作無法復原，該使用者的所有資料將被永久移除。</p>
      <div class="dialog-error" id="deleteUserError"></div>
    `;
    const footerHtml = `
      <button class="btn btn-ghost dialog-cancel-btn">取消</button>
      <button class="btn btn-accent dialog-submit-btn">永久刪除</button>
    `;

    const dialog = createDialog(`刪除使用者 — ${escapeHtml(user.username)}`, bodyHtml, footerHtml);
    dialog.querySelector('.dialog-cancel-btn').addEventListener('click', () => dialog.remove());

    dialog.querySelector('.dialog-submit-btn').addEventListener('click', async () => {
      const errorDiv = dialog.querySelector('#deleteUserError');
      try {
        const token = LoginModule.getToken();
        const resp = await fetch(`/api/admin/users/${user.id}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` },
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || '刪除失敗');

        dialog.remove();
        reloadUsersList(container);
        if (typeof DesktopModule !== 'undefined') {
          DesktopModule.showToast(`已刪除使用者 ${user.username}`, 'check');
        }
      } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.classList.add('show');
      }
    });
  }

  /**
   * 開啟權限設定對話框
   * @param {HTMLElement} container
   * @param {Object} user
   */
  async function openPermissionsDialog(container, user) {
    // 取得預設權限設定
    let defaultPerms = null;
    try {
      const token = LoginModule.getToken();
      const response = await fetch('/api/admin/default-permissions', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (response.ok) {
        defaultPerms = await response.json();
      }
    } catch (error) {
      console.error('Failed to load default permissions:', error);
    }

    const appNames = defaultPerms?.app_names || APP_NAMES;
    const userPerms = user.permissions;

    // 建立對話框
    const dialog = document.createElement('div');
    dialog.className = 'permissions-dialog-overlay';
    dialog.innerHTML = `
      <div class="permissions-dialog">
        <div class="permissions-dialog-header">
          <h3>設定 ${user.username} 的權限</h3>
          <button class="permissions-dialog-close">${getIcon('close')}</button>
        </div>
        <div class="permissions-dialog-body">
          <div class="permissions-group">
            <h4>應用程式權限</h4>
            <div class="permissions-list">
              ${Object.entries(appNames).map(([appId, appName]) => `
                <label class="permission-item">
                  <input type="checkbox" name="app_${appId}"
                    ${userPerms.apps[appId] ? 'checked' : ''}>
                  <span>${appName}</span>
                </label>
              `).join('')}
            </div>
          </div>
          <div class="permissions-group">
            <h4>知識庫權限</h4>
            <div class="permissions-list">
              <label class="permission-item">
                <input type="checkbox" name="knowledge_global_write"
                  ${userPerms.knowledge.global_write ? 'checked' : ''}>
                <span>可編輯全域知識</span>
              </label>
              <label class="permission-item">
                <input type="checkbox" name="knowledge_global_delete"
                  ${userPerms.knowledge.global_delete ? 'checked' : ''}>
                <span>可刪除全域知識</span>
              </label>
            </div>
          </div>
        </div>
        <div class="permissions-dialog-footer">
          <button class="btn btn-ghost permissions-cancel">取消</button>
          <button class="btn btn-primary permissions-save">儲存</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    // 綁定事件
    dialog.querySelector('.permissions-dialog-close').addEventListener('click', () => {
      dialog.remove();
    });
    dialog.querySelector('.permissions-cancel').addEventListener('click', () => {
      dialog.remove();
    });
    dialog.addEventListener('click', (e) => {
      if (e.target === dialog) {
        dialog.remove();
      }
    });

    // 儲存權限
    dialog.querySelector('.permissions-save').addEventListener('click', async () => {
      const apps = {};
      const knowledge = {};

      // 收集應用程式權限
      Object.keys(appNames).forEach(appId => {
        const checkbox = dialog.querySelector(`[name="app_${appId}"]`);
        if (checkbox) {
          apps[appId] = checkbox.checked;
        }
      });

      // 收集知識庫權限
      knowledge.global_write = dialog.querySelector('[name="knowledge_global_write"]').checked;
      knowledge.global_delete = dialog.querySelector('[name="knowledge_global_delete"]').checked;

      // 送出更新
      try {
        const token = LoginModule.getToken();
        const response = await fetch(`/api/admin/users/${user.id}/permissions`, {
          method: 'PATCH',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ apps, knowledge }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || '更新失敗');
        }

        dialog.remove();
        // 重新載入使用者列表
        loadUsersList(container.closest('.settings-container').querySelector('.settings-content'));

        // 顯示成功訊息
        if (typeof DesktopModule !== 'undefined') {
          DesktopModule.showToast(`${user.username} 的權限已更新`, 'check');
        }
      } catch (error) {
        alert(`更新權限失敗：${error.message}`);
      }
    });
  }

  // ============================================================
  // Bot 設定
  // ============================================================

  // 平台設定定義
  const BOT_PLATFORMS = {
    line: {
      name: 'Line Bot',
      icon: 'message-text',
      fields: [
        { key: 'channel_secret', label: 'Channel Secret', type: 'password' },
        { key: 'channel_access_token', label: 'Channel Access Token', type: 'password' },
      ],
    },
    telegram: {
      name: 'Telegram Bot',
      icon: 'robot',
      fields: [
        { key: 'bot_token', label: 'Bot Token', type: 'password' },
        { key: 'webhook_secret', label: 'Webhook Secret', type: 'password' },
        { key: 'admin_chat_id', label: 'Admin Chat ID', type: 'text' },
      ],
    },
  };

  /**
   * 載入 Bot 設定
   * @param {HTMLElement} windowEl
   */
  async function loadBotSettings(windowEl) {
    const container = windowEl.querySelector('.bot-settings-container');
    if (!container) return;

    const token = LoginModule.getToken();
    let html = '';

    for (const [platform, config] of Object.entries(BOT_PLATFORMS)) {
      try {
        const resp = await fetch(`/api/admin/bot-settings/${platform}`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        html += renderBotPlatformCard(platform, config, data);
      } catch (error) {
        // [Sprint7] 原始: html += '<div class="settings-group">...<div class="users-error">載入失敗</div></div>'
        html += `
          <div class="settings-group">
            <h3 class="settings-group-title">
              <span class="icon">${getIcon(config.icon)}</span> ${config.name}
            </h3>
            <div class="bot-error-placeholder" data-platform="${platform}"></div>
          </div>
        `;
        // Defer UIHelpers.showError to after innerHTML is set (see below)
      }
    }

    container.innerHTML = html;
    // [Sprint7] 填充延遲的 bot error placeholders
    container.querySelectorAll('.bot-error-placeholder').forEach(el => {
      UIHelpers.showError(el, { message: '載入失敗', onRetry: () => loadBotSettings(windowEl) });
    });
    bindBotSettingsEvents(container, windowEl);
  }

  /**
   * 渲染單一平台設定卡片
   */
  function renderBotPlatformCard(platform, config, data) {
    const fields = data.fields || {};
    const pushEnabled = data.proactive_push_enabled === true;

    return `
      <div class="settings-group bot-platform-card" data-platform="${platform}">
        <h3 class="settings-group-title">
          <span class="icon">${getIcon(config.icon)}</span> ${config.name}
        </h3>
        <div class="bot-fields">
          ${config.fields.map(field => {
            const status = fields[field.key] || {};
            const source = status.source || 'none';
            const sourceLabel = source === 'database' ? '資料庫' : source === 'env' ? '環境變數' : '未設定';
            const sourceClass = source === 'none' ? 'bot-source-none' : 'bot-source-set';

            return `
              <div class="bot-field-row">
                <label class="bot-field-label">${field.label}</label>
                <div class="bot-field-input-group">
                  <input type="${field.type}" class="input bot-field-input"
                    name="${field.key}" placeholder="${status.has_value ? status.masked_value : '未設定'}"
                    data-platform="${platform}" data-key="${field.key}">
                  <span class="bot-field-source ${sourceClass}" title="來源: ${sourceLabel}">${sourceLabel}</span>
                </div>
              </div>
            `;
          }).join('')}
          <div class="bot-field-row bot-push-toggle-row">
            <label class="bot-field-label">主動推送通知</label>
            <div class="bot-push-toggle-group">
              <label class="toggle-switch">
                <input type="checkbox" class="bot-push-toggle" data-platform="${platform}" ${pushEnabled ? 'checked' : ''}>
                <span class="toggle-slider"></span>
              </label>
              <span class="bot-push-toggle-label">${pushEnabled ? '已啟用' : '已停用'}</span>
            </div>
          </div>
        </div>
        <div class="bot-actions">
          <button class="btn btn-primary btn-sm bot-save-btn" data-platform="${platform}">
            <span class="icon">${getIcon('content-save')}</span> 儲存
          </button>
          <button class="btn btn-ghost btn-sm bot-test-btn" data-platform="${platform}">
            <span class="icon">${getIcon('connection')}</span> 測試連線
          </button>
          <button class="btn btn-ghost btn-sm bot-clear-btn" data-platform="${platform}">
            <span class="icon">${getIcon('delete')}</span> 清除
          </button>
        </div>
        <div class="bot-status-msg" data-platform="${platform}"></div>
      </div>
    `;
  }

  /**
   * 綁定 Bot 設定事件
   */
  function bindBotSettingsEvents(container, windowEl) {
    // 儲存按鈕
    container.querySelectorAll('.bot-save-btn').forEach(btn => {
      btn.addEventListener('click', () => saveBotSettings(btn.dataset.platform, container, windowEl));
    });

    // 測試連線按鈕
    container.querySelectorAll('.bot-test-btn').forEach(btn => {
      btn.addEventListener('click', () => testBotConnection(btn.dataset.platform, container));
    });

    // 清除按鈕
    container.querySelectorAll('.bot-clear-btn').forEach(btn => {
      btn.addEventListener('click', () => clearBotSettings(btn.dataset.platform, container, windowEl));
    });

    // 主動推送切換
    container.querySelectorAll('.bot-push-toggle').forEach(toggle => {
      toggle.addEventListener('change', () => savePushToggle(toggle.dataset.platform, toggle.checked, container));
    });
  }

  /**
   * 顯示 Bot 設定狀態訊息
   */
  function showBotStatus(container, platform, message, isError = false) {
    const el = container.querySelector(`.bot-status-msg[data-platform="${platform}"]`);
    if (el) {
      // [Sprint8] 原: el.textContent = message; el.className = `bot-status-msg ${isError ? 'bot-status-error' : 'bot-status-success'}`
      if (isError) {
        UIHelpers.showError(el, { message, variant: 'compact' });
      } else {
        el.textContent = message;
        el.className = 'bot-status-msg bot-status-success';
      }
      setTimeout(() => { el.textContent = ''; el.className = 'bot-status-msg'; }, 5000);
    }
  }

  /**
   * 儲存 Bot 設定
   */
  async function saveBotSettings(platform, container, windowEl) {
    const inputs = container.querySelectorAll(`.bot-field-input[data-platform="${platform}"]`);
    const credentials = {};
    inputs.forEach(input => {
      if (input.value.trim()) {
        credentials[input.dataset.key] = input.value.trim();
      }
    });

    if (Object.keys(credentials).length === 0) {
      showBotStatus(container, platform, '請至少填入一個欄位', true);
      return;
    }

    try {
      const token = LoginModule.getToken();
      const resp = await fetch(`/api/admin/bot-settings/${platform}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials),
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || '儲存失敗');
      }

      showBotStatus(container, platform, '設定已儲存');
      // 清空輸入欄位並重新載入
      inputs.forEach(input => { input.value = ''; });
      loadBotSettings(windowEl);
    } catch (error) {
      showBotStatus(container, platform, `儲存失敗：${error.message}`, true);
    }
  }

  /**
   * 儲存主動推送切換狀態
   */
  async function savePushToggle(platform, enabled, container) {
    const labelEl = container.querySelector(`.bot-push-toggle-row[data-platform="${platform}"] .bot-push-toggle-label`)
      || container.querySelector(`.bot-push-toggle[data-platform="${platform}"]`)?.closest('.bot-push-toggle-row')?.querySelector('.bot-push-toggle-label');
    try {
      const token = LoginModule.getToken();
      const resp = await fetch(`/api/admin/bot-settings/${platform}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ proactive_push_enabled: enabled }),
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || '儲存失敗');
      }

      if (labelEl) labelEl.textContent = enabled ? '已啟用' : '已停用';
      showBotStatus(container, platform, `主動推送已${enabled ? '啟用' : '停用'}`);
    } catch (error) {
      showBotStatus(container, platform, `切換失敗：${error.message}`, true);
      // 還原 toggle 狀態
      const toggle = container.querySelector(`.bot-push-toggle[data-platform="${platform}"]`);
      if (toggle) toggle.checked = !enabled;
    }
  }

  /**
   * 測試 Bot 連線
   */
  async function testBotConnection(platform, container) {
    showBotStatus(container, platform, '測試中...');

    try {
      const token = LoginModule.getToken();
      const resp = await fetch(`/api/admin/bot-settings/${platform}/test`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });

      const data = await resp.json();
      showBotStatus(container, platform, data.message, !data.success);
    } catch (error) {
      showBotStatus(container, platform, `測試失敗：${error.message}`, true);
    }
  }

  /**
   * 清除 Bot 設定
   */
  async function clearBotSettings(platform, container, windowEl) {
    const platformName = BOT_PLATFORMS[platform]?.name || platform;
    if (!confirm(`確定要清除 ${platformName} 的資料庫設定？\n清除後將使用環境變數的設定。`)) {
      return;
    }

    try {
      const token = LoginModule.getToken();
      const resp = await fetch(`/api/admin/bot-settings/${platform}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (!resp.ok) throw new Error('清除失敗');

      const data = await resp.json();
      showBotStatus(container, platform, `已清除 ${data.deleted} 筆設定`);
      loadBotSettings(windowEl);
    } catch (error) {
      showBotStatus(container, platform, `清除失敗：${error.message}`, true);
    }
  }

  /**
   * 開啟設定應用程式
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
      title: '系統設定',
      appId: APP_ID,
      icon: 'settings',
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
// 將模組掛載到 window，供 desktop.js lazy-loader 偵測
window.SettingsApp = SettingsApp;
