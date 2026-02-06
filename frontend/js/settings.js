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
                <div class="users-loading">
                  <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
                  <span>載入中...</span>
                </div>
              </div>
            </div>
          </section>

          <section class="settings-section" id="section-bot-settings">
            <h2 class="settings-section-title">Bot 設定</h2>
            <div class="bot-settings-container">
              <div class="users-loading">
                <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
                <span>載入中...</span>
              </div>
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
      loadUsersList(windowEl);
    }
    // 如果切換到 Bot 設定，載入設定
    if (sectionId === 'bot-settings') {
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
      container.innerHTML = `
        <div class="users-error">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入使用者列表失敗：${escapeHtml(error.message)}</span>
        </div>
      `;
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
   * 渲染使用者列表
   * @param {HTMLElement} container
   * @param {Array} users
   */
  function renderUsersList(container, users) {
    container.innerHTML = `
      <table class="users-table">
        <thead>
          <tr>
            <th>使用者</th>
            <th>顯示名稱</th>
            <th>角色</th>
            <th>最後登入</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          ${users.map(user => {
            const userRole = user.role || 'user';
            const canManage_ = canManageUser(userRole);
            const roleIcon = userRole === 'admin' ? 'shield-crown' : '';
            const roleClass = userRole === 'admin' ? 'user-admin-badge' : '';

            const safeUsername = escapeHtml(user.username);
            const safeDisplayName = escapeHtml(user.display_name || '-');

            return `
              <tr data-user-id="${user.id}">
                <td>
                  ${roleIcon ? `<span class="${roleClass} icon" title="${getRoleDisplay(userRole)}">${getIcon(roleIcon)}</span>` : ''}
                  ${safeUsername}
                </td>
                <td>${safeDisplayName}</td>
                <td><span class="role-badge role-${userRole}">${getRoleDisplay(userRole)}</span></td>
                <td>${user.last_login_at ? new Date(user.last_login_at).toLocaleString('zh-TW') : '-'}</td>
                <td>
                  ${canManage_
                    ? `<button class="btn btn-ghost btn-sm user-permissions-btn" data-user-id="${user.id}" data-username="${safeUsername}">
                        <span class="icon">${getIcon('shield-edit')}</span> 設定權限
                       </button>`
                    : `<span class="user-admin-label">${getRoleDisplay(userRole)}</span>`
                  }
                </td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    `;

    // 綁定權限設定按鈕事件
    container.querySelectorAll('.user-permissions-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const userId = parseInt(btn.dataset.userId, 10);
        const username = btn.dataset.username;
        const user = users.find(u => u.id === userId);
        if (user) {
          openPermissionsDialog(container, user);
        }
      });
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
        html += `
          <div class="settings-group">
            <h3 class="settings-group-title">
              <span class="icon">${getIcon(config.icon)}</span> ${config.name}
            </h3>
            <div class="users-error">
              <span class="icon">${getIcon('alert-circle')}</span>
              <span>載入失敗：${error.message}</span>
            </div>
          </div>
        `;
      }
    }

    container.innerHTML = html;
    bindBotSettingsEvents(container, windowEl);
  }

  /**
   * 渲染單一平台設定卡片
   */
  function renderBotPlatformCard(platform, config, data) {
    const fields = data.fields || {};

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
  }

  /**
   * 顯示 Bot 設定狀態訊息
   */
  function showBotStatus(container, platform, message, isError = false) {
    const el = container.querySelector(`.bot-status-msg[data-platform="${platform}"]`);
    if (el) {
      el.textContent = message;
      el.className = `bot-status-msg ${isError ? 'bot-status-error' : 'bot-status-success'}`;
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
