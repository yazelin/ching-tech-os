/**
 * ChingTech OS - Tenant Admin Application
 * 租戶管理應用程式：租戶資訊、使用量統計、管理員設定
 */

const TenantAdminApp = (function () {
  'use strict';

  const APP_ID = 'tenant-admin';
  let currentWindowId = null;
  let tenantInfo = null;
  let isTenantAdmin = false;

  /**
   * 檢查是否為租戶管理員
   * @returns {boolean}
   */
  function checkIsTenantAdmin() {
    if (typeof PermissionsModule === 'undefined') return false;
    const session = LoginModule.getSession();
    // 從後端 session 判斷 role
    // 這裡簡化處理：如果是系統管理員或有 tenant_admin 標記
    return PermissionsModule.isAdmin() || PermissionsModule.isTenantAdmin?.() === true;
  }

  /**
   * 取得視窗內容 HTML
   * @returns {string}
   */
  function getWindowContent() {
    isTenantAdmin = checkIsTenantAdmin();

    return `
      <div class="tenant-admin-container">
        <nav class="tenant-admin-sidebar">
          <ul class="tenant-admin-nav">
            <li class="tenant-admin-nav-item active" data-section="overview">
              <span class="icon">${getIcon('domain')}</span>
              <span>總覽</span>
            </li>
            <li class="tenant-admin-nav-item" data-section="settings">
              <span class="icon">${getIcon('cog')}</span>
              <span>設定</span>
            </li>
            <li class="tenant-admin-nav-item" data-section="admins">
              <span class="icon">${getIcon('account-group')}</span>
              <span>管理員</span>
            </li>
          </ul>
        </nav>

        <main class="tenant-admin-content">
          <!-- 總覽區段 -->
          <section class="tenant-admin-section active" id="section-overview">
            <h2 class="tenant-admin-section-title">租戶總覽</h2>
            <div class="tenant-admin-loading" id="overview-loading">
              <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
              <span>載入中...</span>
            </div>
            <div id="overview-content" style="display: none;"></div>
          </section>

          <!-- 設定區段 -->
          <section class="tenant-admin-section" id="section-settings">
            <h2 class="tenant-admin-section-title">租戶設定</h2>
            <div class="tenant-admin-loading" id="settings-loading">
              <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
              <span>載入中...</span>
            </div>
            <div id="settings-content" style="display: none;"></div>
          </section>

          <!-- 管理員區段 -->
          <section class="tenant-admin-section" id="section-admins">
            <h2 class="tenant-admin-section-title">租戶管理員</h2>
            <div class="tenant-admin-loading" id="admins-loading">
              <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
              <span>載入中...</span>
            </div>
            <div id="admins-content" style="display: none;"></div>
          </section>
        </main>

        <!-- 手機版底部 Tab Bar -->
        <nav class="mobile-tab-bar tenant-admin-mobile-tabs">
          <button class="mobile-tab-item active" data-section="overview">
            <span class="icon">${getIcon('domain')}</span>
            <span class="mobile-tab-label">總覽</span>
          </button>
          <button class="mobile-tab-item" data-section="settings">
            <span class="icon">${getIcon('cog')}</span>
            <span class="mobile-tab-label">設定</span>
          </button>
          <button class="mobile-tab-item" data-section="admins">
            <span class="icon">${getIcon('account-group')}</span>
            <span class="mobile-tab-label">管理員</span>
          </button>
        </nav>
      </div>
    `;
  }

  /**
   * 初始化視窗
   * @param {HTMLElement} windowEl - 視窗元素
   */
  function init(windowEl) {
    // 綁定側邊欄導航
    const navItems = windowEl.querySelectorAll('.tenant-admin-nav-item');
    navItems.forEach(item => {
      item.addEventListener('click', () => {
        const section = item.dataset.section;
        switchSection(windowEl, section);
      });
    });

    // 綁定手機版底部 Tab Bar
    const mobileTabs = windowEl.querySelectorAll('.tenant-admin-mobile-tabs .mobile-tab-item');
    mobileTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const section = tab.dataset.section;
        switchSection(windowEl, section);
      });
    });

    // 載入總覽資料
    loadOverview(windowEl);
  }

  /**
   * 切換區段
   * @param {HTMLElement} windowEl
   * @param {string} sectionId
   */
  function switchSection(windowEl, sectionId) {
    // 更新側邊欄導航狀態
    const navItems = windowEl.querySelectorAll('.tenant-admin-nav-item');
    navItems.forEach(item => {
      item.classList.toggle('active', item.dataset.section === sectionId);
    });

    // 更新手機版 Tab 狀態
    const mobileTabs = windowEl.querySelectorAll('.tenant-admin-mobile-tabs .mobile-tab-item');
    mobileTabs.forEach(tab => {
      tab.classList.toggle('active', tab.dataset.section === sectionId);
    });

    // 切換顯示區段
    const sections = windowEl.querySelectorAll('.tenant-admin-section');
    sections.forEach(section => {
      section.classList.toggle('active', section.id === `section-${sectionId}`);
    });

    // 根據區段載入資料
    switch (sectionId) {
      case 'overview':
        loadOverview(windowEl);
        break;
      case 'settings':
        loadSettings(windowEl);
        break;
      case 'admins':
        loadAdmins(windowEl);
        break;
    }
  }

  /**
   * 載入總覽資料
   * @param {HTMLElement} windowEl
   */
  async function loadOverview(windowEl) {
    const loading = windowEl.querySelector('#overview-loading');
    const content = windowEl.querySelector('#overview-content');

    loading.style.display = '';
    content.style.display = 'none';

    try {
      // 同時載入租戶資訊和使用量
      const [info, usage] = await Promise.all([
        APIClient.getTenantInfo(),
        APIClient.getTenantUsage()
      ]);

      tenantInfo = info;
      renderOverview(content, info, usage);
      loading.style.display = 'none';
      content.style.display = '';
    } catch (error) {
      loading.innerHTML = `
        <div class="tenant-admin-error">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入失敗：${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * 渲染總覽內容
   * @param {HTMLElement} container
   * @param {Object} info
   * @param {Object} usage
   */
  function renderOverview(container, info, usage) {
    const statusLabels = {
      'active': '啟用中',
      'trial': '試用期',
      'suspended': '已暫停'
    };

    const planLabels = {
      'trial': '試用版',
      'basic': '基本版',
      'pro': '專業版',
      'enterprise': '企業版'
    };

    const statusClass = {
      'active': 'success',
      'trial': 'info',
      'suspended': 'error'
    };

    container.innerHTML = `
      <div class="tenant-overview-grid">
        <!-- 基本資訊卡片 -->
        <div class="tenant-card tenant-info-card">
          <div class="tenant-card-header">
            <span class="icon">${getIcon('office-building')}</span>
            <h3>租戶資訊</h3>
          </div>
          <div class="tenant-card-body">
            <div class="tenant-info-row">
              <span class="tenant-info-label">名稱</span>
              <span class="tenant-info-value">${info.name}</span>
            </div>
            <div class="tenant-info-row">
              <span class="tenant-info-label">代碼</span>
              <span class="tenant-info-value tenant-code">${info.code}</span>
            </div>
            <div class="tenant-info-row">
              <span class="tenant-info-label">狀態</span>
              <span class="tenant-badge ${statusClass[info.status] || ''}">${statusLabels[info.status] || info.status}</span>
            </div>
            <div class="tenant-info-row">
              <span class="tenant-info-label">方案</span>
              <span class="tenant-info-value">${planLabels[info.plan] || info.plan}</span>
            </div>
            ${info.trial_ends_at ? `
            <div class="tenant-info-row">
              <span class="tenant-info-label">試用期限</span>
              <span class="tenant-info-value">${new Date(info.trial_ends_at).toLocaleDateString('zh-TW')}</span>
            </div>
            ` : ''}
            <div class="tenant-info-row">
              <span class="tenant-info-label">建立時間</span>
              <span class="tenant-info-value">${new Date(info.created_at).toLocaleDateString('zh-TW')}</span>
            </div>
          </div>
        </div>

        <!-- 儲存空間卡片 -->
        <div class="tenant-card tenant-storage-card">
          <div class="tenant-card-header">
            <span class="icon">${getIcon('harddisk')}</span>
            <h3>儲存空間</h3>
          </div>
          <div class="tenant-card-body">
            <div class="storage-usage">
              <div class="storage-bar">
                <div class="storage-bar-fill" style="width: ${Math.min(usage.storage_percentage, 100)}%"></div>
              </div>
              <div class="storage-text">
                <span>${formatStorageSize(usage.storage_used_mb)}</span>
                <span> / </span>
                <span>${formatStorageSize(usage.storage_quota_mb)}</span>
              </div>
              <div class="storage-percentage">${usage.storage_percentage.toFixed(1)}%</div>
            </div>
          </div>
        </div>

        <!-- 使用量統計卡片 -->
        <div class="tenant-card tenant-usage-card">
          <div class="tenant-card-header">
            <span class="icon">${getIcon('chart-bar')}</span>
            <h3>使用統計</h3>
          </div>
          <div class="tenant-card-body">
            <div class="usage-stats-grid">
              <div class="usage-stat">
                <span class="usage-stat-value">${usage.user_count}</span>
                <span class="usage-stat-label">使用者</span>
              </div>
              <div class="usage-stat">
                <span class="usage-stat-value">${usage.project_count}</span>
                <span class="usage-stat-label">專案</span>
              </div>
              <div class="usage-stat">
                <span class="usage-stat-value">${usage.knowledge_count}</span>
                <span class="usage-stat-label">知識庫</span>
              </div>
            </div>
          </div>
        </div>

        <!-- AI 使用量卡片 -->
        <div class="tenant-card tenant-ai-card">
          <div class="tenant-card-header">
            <span class="icon">${getIcon('robot')}</span>
            <h3>AI 使用量</h3>
          </div>
          <div class="tenant-card-body">
            <div class="ai-stats-grid">
              <div class="ai-stat">
                <span class="ai-stat-value">${usage.ai_calls_today}</span>
                <span class="ai-stat-label">今日呼叫</span>
              </div>
              <div class="ai-stat">
                <span class="ai-stat-value">${usage.ai_calls_this_month}</span>
                <span class="ai-stat-label">本月呼叫</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * 格式化儲存空間大小
   * @param {number} mb
   * @returns {string}
   */
  function formatStorageSize(mb) {
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(1)} GB`;
    }
    return `${mb} MB`;
  }

  /**
   * 載入設定
   * @param {HTMLElement} windowEl
   */
  async function loadSettings(windowEl) {
    const loading = windowEl.querySelector('#settings-loading');
    const content = windowEl.querySelector('#settings-content');

    loading.style.display = '';
    content.style.display = 'none';

    try {
      if (!tenantInfo) {
        tenantInfo = await APIClient.getTenantInfo();
      }
      renderSettings(windowEl, content, tenantInfo);
      loading.style.display = 'none';
      content.style.display = '';
    } catch (error) {
      loading.innerHTML = `
        <div class="tenant-admin-error">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入失敗：${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * 渲染設定內容
   * @param {HTMLElement} windowEl
   * @param {HTMLElement} container
   * @param {Object} info
   */
  function renderSettings(windowEl, container, info) {
    const settings = info.settings || {};

    container.innerHTML = `
      <div class="tenant-settings-form">
        <div class="settings-group">
          <h3 class="settings-group-title">基本設定</h3>
          <div class="form-group">
            <label for="tenantName">租戶名稱</label>
            <input type="text" id="tenantName" class="input" value="${info.name}" />
          </div>
        </div>

        <div class="settings-group">
          <h3 class="settings-group-title">功能開關</h3>
          <div class="feature-toggles">
            <label class="feature-toggle">
              <input type="checkbox" id="enableLinebot" ${settings.enable_linebot !== false ? 'checked' : ''} />
              <span class="icon">${getIcon('message-text')}</span>
              <span>Line Bot</span>
            </label>
            <label class="feature-toggle">
              <input type="checkbox" id="enableAiAssistant" ${settings.enable_ai_assistant !== false ? 'checked' : ''} />
              <span class="icon">${getIcon('robot')}</span>
              <span>AI 助手</span>
            </label>
            <label class="feature-toggle">
              <input type="checkbox" id="enableKnowledgeBase" ${settings.enable_knowledge_base !== false ? 'checked' : ''} />
              <span class="icon">${getIcon('book-open-page-variant')}</span>
              <span>知識庫</span>
            </label>
            <label class="feature-toggle">
              <input type="checkbox" id="enableProjectManagement" ${settings.enable_project_management !== false ? 'checked' : ''} />
              <span class="icon">${getIcon('clipboard-text')}</span>
              <span>專案管理</span>
            </label>
            <label class="feature-toggle">
              <input type="checkbox" id="enableInventory" ${settings.enable_inventory !== false ? 'checked' : ''} />
              <span class="icon">${getIcon('package-variant')}</span>
              <span>物料管理</span>
            </label>
          </div>
        </div>

        <div class="settings-actions">
          <button class="btn btn-primary" id="saveSettingsBtn">
            <span class="icon">${getIcon('content-save')}</span>
            <span>儲存設定</span>
          </button>
        </div>
      </div>
    `;

    // 綁定儲存按鈕
    const saveBtn = container.querySelector('#saveSettingsBtn');
    saveBtn.addEventListener('click', () => saveSettings(windowEl, container));
  }

  /**
   * 儲存設定
   * @param {HTMLElement} windowEl
   * @param {HTMLElement} container
   */
  async function saveSettings(windowEl, container) {
    const saveBtn = container.querySelector('#saveSettingsBtn');
    saveBtn.disabled = true;
    saveBtn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span><span>儲存中...</span>`;

    try {
      const name = container.querySelector('#tenantName').value.trim();
      const settings = {
        enable_linebot: container.querySelector('#enableLinebot').checked,
        enable_ai_assistant: container.querySelector('#enableAiAssistant').checked,
        enable_knowledge_base: container.querySelector('#enableKnowledgeBase').checked,
        enable_project_management: container.querySelector('#enableProjectManagement').checked,
        enable_inventory: container.querySelector('#enableInventory').checked
      };

      await APIClient.updateTenantSettings({ name, settings });

      // 更新快取
      tenantInfo.name = name;
      tenantInfo.settings = settings;

      // 更新 Header 顯示
      if (typeof TenantContext !== 'undefined') {
        TenantContext.reload();
      }

      if (typeof DesktopModule !== 'undefined') {
        DesktopModule.showToast('設定已儲存', 'check');
      }
    } catch (error) {
      alert(`儲存失敗：${error.message}`);
    } finally {
      saveBtn.disabled = false;
      saveBtn.innerHTML = `<span class="icon">${getIcon('content-save')}</span><span>儲存設定</span>`;
    }
  }

  /**
   * 載入管理員列表
   * @param {HTMLElement} windowEl
   */
  async function loadAdmins(windowEl) {
    const loading = windowEl.querySelector('#admins-loading');
    const content = windowEl.querySelector('#admins-content');

    loading.style.display = '';
    content.style.display = 'none';

    try {
      const admins = await APIClient.getTenantAdmins();
      renderAdmins(windowEl, content, admins);
      loading.style.display = 'none';
      content.style.display = '';
    } catch (error) {
      // 如果是權限錯誤，顯示提示
      if (error.message.includes('403') || error.message.includes('權限')) {
        loading.innerHTML = `
          <div class="tenant-admin-notice">
            <span class="icon">${getIcon('lock')}</span>
            <span>需要租戶管理員權限才能查看</span>
          </div>
        `;
      } else {
        loading.innerHTML = `
          <div class="tenant-admin-error">
            <span class="icon">${getIcon('alert-circle')}</span>
            <span>載入失敗：${error.message}</span>
          </div>
        `;
      }
    }
  }

  /**
   * 渲染管理員列表
   * @param {HTMLElement} windowEl
   * @param {HTMLElement} container
   * @param {Array} admins
   */
  function renderAdmins(windowEl, container, admins) {
    const roleLabels = {
      'owner': '擁有者',
      'admin': '管理員'
    };

    container.innerHTML = `
      <div class="admins-list-header">
        <button class="btn btn-primary btn-sm" id="addAdminBtn">
          <span class="icon">${getIcon('plus')}</span>
          <span>新增管理員</span>
        </button>
      </div>
      <div class="admins-list">
        ${admins.length === 0 ? `
          <div class="admins-empty">
            <span class="icon">${getIcon('account-question')}</span>
            <span>尚無管理員</span>
          </div>
        ` : `
          <table class="admins-table">
            <thead>
              <tr>
                <th>使用者</th>
                <th>角色</th>
                <th>加入時間</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              ${admins.map(admin => `
                <tr data-admin-id="${admin.id}" data-user-id="${admin.user_id}">
                  <td>
                    <div class="admin-user">
                      <span class="icon">${getIcon('account')}</span>
                      <span>${admin.display_name || admin.username}</span>
                    </div>
                  </td>
                  <td>
                    <span class="admin-role-badge ${admin.role}">${roleLabels[admin.role] || admin.role}</span>
                  </td>
                  <td>${new Date(admin.created_at).toLocaleDateString('zh-TW')}</td>
                  <td>
                    ${admin.role !== 'owner' ? `
                      <button class="btn btn-ghost btn-sm remove-admin-btn" data-user-id="${admin.user_id}" data-username="${admin.display_name || admin.username}">
                        <span class="icon">${getIcon('account-remove')}</span>
                      </button>
                    ` : ''}
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `}
      </div>
    `;

    // 綁定新增按鈕
    const addBtn = container.querySelector('#addAdminBtn');
    addBtn?.addEventListener('click', () => openAddAdminDialog(windowEl, container));

    // 綁定移除按鈕
    container.querySelectorAll('.remove-admin-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const userId = parseInt(btn.dataset.userId, 10);
        const username = btn.dataset.username;
        removeAdmin(windowEl, container, userId, username);
      });
    });
  }

  /**
   * 開啟新增管理員對話框
   * @param {HTMLElement} windowEl
   * @param {HTMLElement} container
   */
  async function openAddAdminDialog(windowEl, container) {
    const dialog = document.createElement('div');
    dialog.className = 'tenant-admin-dialog-overlay';
    dialog.innerHTML = `
      <div class="tenant-admin-dialog">
        <div class="tenant-admin-dialog-header">
          <h3>新增管理員</h3>
          <button class="btn btn-ghost btn-sm dialog-close-btn">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="tenant-admin-dialog-body">
          <div class="form-group">
            <label for="adminUserId">選擇使用者</label>
            <select id="adminUserId" class="input">
              <option value="">載入中...</option>
            </select>
          </div>
          <div class="form-group">
            <label for="adminRole">角色</label>
            <select id="adminRole" class="input">
              <option value="admin">管理員</option>
            </select>
          </div>
        </div>
        <div class="tenant-admin-dialog-footer">
          <button class="btn btn-ghost dialog-cancel-btn">取消</button>
          <button class="btn btn-primary dialog-confirm-btn">新增</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    // 載入使用者列表
    const userSelect = dialog.querySelector('#adminUserId');
    try {
      const response = await APIClient.get('/user/list');
      const users = response.users || [];
      if (users.length === 0) {
        userSelect.innerHTML = '<option value="">沒有可用的使用者</option>';
      } else {
        userSelect.innerHTML = '<option value="">請選擇使用者</option>' +
          users.map(u => `<option value="${u.id}">${u.display_name || u.username} (${u.username})</option>`).join('');
      }
    } catch (error) {
      userSelect.innerHTML = `<option value="">載入失敗：${error.message}</option>`;
    }

    // 關閉對話框
    const closeDialog = () => dialog.remove();
    dialog.querySelector('.dialog-close-btn').addEventListener('click', closeDialog);
    dialog.querySelector('.dialog-cancel-btn').addEventListener('click', closeDialog);
    dialog.addEventListener('click', (e) => {
      if (e.target === dialog) closeDialog();
    });

    // 確認新增
    dialog.querySelector('.dialog-confirm-btn').addEventListener('click', async () => {
      const userId = parseInt(dialog.querySelector('#adminUserId').value, 10);
      const role = dialog.querySelector('#adminRole').value;

      if (!userId) {
        alert('請選擇使用者');
        return;
      }

      try {
        await APIClient.addTenantAdmin({ user_id: userId, role });
        closeDialog();
        loadAdmins(windowEl);
        if (typeof DesktopModule !== 'undefined') {
          DesktopModule.showToast('已新增管理員', 'check');
        }
      } catch (error) {
        alert(`新增失敗：${error.message}`);
      }
    });
  }

  /**
   * 移除管理員
   * @param {HTMLElement} windowEl
   * @param {HTMLElement} container
   * @param {number} userId
   * @param {string} username
   */
  async function removeAdmin(windowEl, container, userId, username) {
    if (!confirm(`確定要移除管理員「${username}」嗎？`)) {
      return;
    }

    try {
      await APIClient.removeTenantAdmin(userId);
      loadAdmins(windowEl);
      if (typeof DesktopModule !== 'undefined') {
        DesktopModule.showToast('已移除管理員', 'check');
      }
    } catch (error) {
      alert(`移除失敗：${error.message}`);
    }
  }

  /**
   * 開啟租戶管理應用程式
   */
  function open() {
    // 檢查是否有租戶
    if (typeof TenantContext !== 'undefined' && !TenantContext.hasTenant()) {
      if (typeof DesktopModule !== 'undefined') {
        DesktopModule.showToast('目前未綁定租戶', 'alert');
      }
      return null;
    }

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
      title: '租戶管理',
      appId: APP_ID,
      icon: 'office-building',
      width: 800,
      height: 550,
      content: getWindowContent(),
      onInit: (windowEl, windowId) => {
        init(windowEl);
      },
      onClose: (windowId) => {
        currentWindowId = null;
        tenantInfo = null;
      }
    });

    return currentWindowId;
  }

  // 公開 API
  return {
    open
  };
})();
