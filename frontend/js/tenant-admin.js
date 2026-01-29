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
            <li class="tenant-admin-nav-item" data-section="users">
              <span class="icon">${getIcon('account-multiple')}</span>
              <span>使用者</span>
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

          <!-- 使用者管理區段 -->
          <section class="tenant-admin-section" id="section-users">
            <div class="tenant-admin-section-header">
              <h2 class="tenant-admin-section-title">使用者管理</h2>
              <button class="btn btn-primary btn-sm" id="createUserBtn">
                <span class="icon">${getIcon('plus')}</span>
                <span>新增使用者</span>
              </button>
            </div>
            <div class="tenant-admin-filters">
              <select id="userRoleFilter" class="tenant-admin-filter-select">
                <option value="">全部角色</option>
                <option value="tenant_admin">管理員</option>
                <option value="user">一般使用者</option>
              </select>
              <select id="userStatusFilter" class="tenant-admin-filter-select">
                <option value="">全部狀態</option>
                <option value="active">啟用</option>
                <option value="inactive">停用</option>
              </select>
            </div>
            <div class="tenant-admin-loading" id="users-loading">
              <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
              <span>載入中...</span>
            </div>
            <div id="users-content" style="display: none;"></div>
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
          <button class="mobile-tab-item" data-section="users">
            <span class="icon">${getIcon('account-multiple')}</span>
            <span class="mobile-tab-label">使用者</span>
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

    // 綁定新增使用者按鈕
    const createUserBtn = windowEl.querySelector('#createUserBtn');
    createUserBtn?.addEventListener('click', () => openCreateUserDialog(windowEl));

    // 綁定使用者篩選器
    const roleFilter = windowEl.querySelector('#userRoleFilter');
    const statusFilter = windowEl.querySelector('#userStatusFilter');
    roleFilter?.addEventListener('change', () => loadUsers(windowEl));
    statusFilter?.addEventListener('change', () => loadUsers(windowEl));

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
      case 'users':
        loadUsers(windowEl);
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

  // ============================================================
  // 使用者管理
  // ============================================================

  let usersCache = [];

  /**
   * 載入使用者列表
   * @param {HTMLElement} windowEl
   */
  async function loadUsers(windowEl) {
    const loading = windowEl.querySelector('#users-loading');
    const content = windowEl.querySelector('#users-content');

    loading.style.display = '';
    content.style.display = 'none';

    try {
      const roleFilter = windowEl.querySelector('#userRoleFilter')?.value || '';
      const statusFilter = windowEl.querySelector('#userStatusFilter')?.value || '';

      // 後端只支援 include_inactive 參數，篩選在前端進行
      const data = await APIClient.get('/tenant/users?include_inactive=true');
      usersCache = data.users || [];

      // 在本地進行角色和狀態篩選
      let filteredUsers = usersCache;
      if (roleFilter) {
        filteredUsers = filteredUsers.filter(u => u.role === roleFilter);
      }
      if (statusFilter) {
        const isActive = statusFilter === 'active';
        filteredUsers = filteredUsers.filter(u => u.is_active === isActive);
      }

      renderUsers(windowEl, content, filteredUsers);
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
   * 渲染使用者列表
   * @param {HTMLElement} windowEl
   * @param {HTMLElement} container
   * @param {Array} users
   */
  function renderUsers(windowEl, container, users) {
    const roleLabels = {
      'platform_admin': '平台管理員',
      'tenant_admin': '租戶管理員',
      'user': '一般使用者'
    };

    const roleClass = {
      'platform_admin': 'admin',
      'tenant_admin': 'admin',
      'user': 'user'
    };

    if (users.length === 0) {
      container.innerHTML = `
        <div class="tenant-admin-empty">
          <span class="icon">${getIcon('account-off')}</span>
          <span>沒有符合條件的使用者</span>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="tenant-admin-table-container">
        <table class="tenant-admin-table">
          <thead>
            <tr>
              <th>帳號</th>
              <th>顯示名稱</th>
              <th>角色</th>
              <th>狀態</th>
              <th>最後登入</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            ${users.map(user => `
              <tr data-user-id="${user.id}">
                <td><code class="tenant-admin-code">${escapeHtml(user.username)}</code></td>
                <td>${escapeHtml(user.display_name || '-')}</td>
                <td>
                  <span class="tenant-admin-role-badge ${roleClass[user.role] || ''}">${roleLabels[user.role] || user.role}</span>
                </td>
                <td>
                  <span class="tenant-admin-status-badge ${user.is_active ? 'active' : 'inactive'}">
                    ${user.is_active ? '啟用' : '停用'}
                  </span>
                </td>
                <td>${user.last_login_at ? formatDateTime(user.last_login_at) : '-'}</td>
                <td class="tenant-admin-actions">
                  <button class="btn btn-ghost btn-sm user-detail-btn" data-user-id="${user.id}" title="編輯">
                    <span class="icon">${getIcon('pencil')}</span>
                  </button>
                  <button class="btn btn-ghost btn-sm user-permissions-btn" data-user-id="${user.id}" data-username="${escapeHtml(user.display_name || user.username)}" data-role="${user.role}" title="設定權限">
                    <span class="icon">${getIcon('shield-edit')}</span>
                  </button>
                  <button class="btn btn-ghost btn-sm user-password-btn" data-user-id="${user.id}" data-username="${escapeHtml(user.display_name || user.username)}" title="重設密碼">
                    <span class="icon">${getIcon('lock-reset')}</span>
                  </button>
                  ${user.is_active ? `
                    <button class="btn btn-ghost btn-sm user-deactivate-btn" data-user-id="${user.id}" data-username="${escapeHtml(user.display_name || user.username)}" title="停用">
                      <span class="icon">${getIcon('account-cancel')}</span>
                    </button>
                  ` : `
                    <button class="btn btn-ghost btn-sm user-activate-btn" data-user-id="${user.id}" data-username="${escapeHtml(user.display_name || user.username)}" title="啟用">
                      <span class="icon">${getIcon('account-check')}</span>
                    </button>
                  `}
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;

    // 綁定操作按鈕
    container.querySelectorAll('.user-detail-btn').forEach(btn => {
      btn.addEventListener('click', () => openUserDetailDialog(windowEl, btn.dataset.userId));
    });

    container.querySelectorAll('.user-permissions-btn').forEach(btn => {
      btn.addEventListener('click', () => openUserPermissionsDialog(windowEl, btn.dataset.userId, btn.dataset.username, btn.dataset.role));
    });

    container.querySelectorAll('.user-password-btn').forEach(btn => {
      btn.addEventListener('click', () => openResetPasswordDialog(windowEl, btn.dataset.userId, btn.dataset.username));
    });

    container.querySelectorAll('.user-deactivate-btn').forEach(btn => {
      btn.addEventListener('click', () => deactivateUser(windowEl, btn.dataset.userId, btn.dataset.username));
    });

    container.querySelectorAll('.user-activate-btn').forEach(btn => {
      btn.addEventListener('click', () => activateUser(windowEl, btn.dataset.userId, btn.dataset.username));
    });
  }

  /**
   * 開啟使用者權限設定對話框
   * @param {HTMLElement} windowEl
   * @param {string} userId
   * @param {string} username
   * @param {string} userRole - 目標使用者的角色
   */
  async function openUserPermissionsDialog(windowEl, userId, username, userRole) {
    // 取得目前登入者資訊
    const session = LoginModule.getSession();
    const currentUserId = session?.user_id;
    const currentRole = session?.role;

    // 檢查是否嘗試修改自己的權限
    if (String(currentUserId) === String(userId)) {
      showToast('無法修改自己的權限', 'alert');
      return;
    }

    // 檢查權限階層：租戶管理員只能管理一般使用者
    if (currentRole === 'tenant_admin' && userRole !== 'user') {
      showToast('無法修改管理員的權限', 'alert');
      return;
    }

    const permDialog = document.createElement('div');
    permDialog.className = 'tenant-admin-dialog-overlay';
    permDialog.innerHTML = `
      <div class="tenant-admin-dialog" style="max-width: 500px;">
        <div class="tenant-admin-dialog-header">
          <h3>
            <span class="icon">${getIcon('shield-edit')}</span>
            設定 App 權限
          </h3>
          <button class="btn btn-ghost btn-sm dialog-close-btn">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="tenant-admin-dialog-body">
          <p class="user-perm-target">使用者：<strong>${escapeHtml(username)}</strong></p>
          <div class="tenant-admin-loading" id="perm-loading">
            <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
            <span>載入中...</span>
          </div>
          <div id="perm-content" style="display: none;"></div>
        </div>
      </div>
    `;

    document.body.appendChild(permDialog);

    // 關閉對話框
    const closeDialog = () => permDialog.remove();
    permDialog.querySelector('.dialog-close-btn').addEventListener('click', closeDialog);
    permDialog.addEventListener('click', (e) => {
      if (e.target === permDialog) closeDialog();
    });

    // 載入使用者權限和預設權限
    const loading = permDialog.querySelector('#perm-loading');
    const content = permDialog.querySelector('#perm-content');

    try {
      const [defaultPerms, userInfo] = await Promise.all([
        APIClient.get('/admin/default-permissions'),
        APIClient.get('/tenant/users?include_inactive=true')
      ]);

      // 找到目標使用者
      const targetUser = (userInfo.users || []).find(u => String(u.id) === String(userId));
      if (!targetUser) {
        throw new Error('找不到使用者');
      }

      const currentPerms = targetUser.permissions?.apps || {};
      const appNames = defaultPerms.app_names || {};

      // 渲染權限設定表單
      content.innerHTML = `
        <p class="perm-hint">
          <span class="icon">${getIcon('information-outline')}</span>
          控制此使用者可以使用的應用程式功能（Web 介面和 Line Bot）
        </p>
        <div class="perm-app-list">
          ${Object.keys(defaultPerms.apps).filter(appId => appId !== 'platform-admin' && appId !== 'tenant-admin').map(appId => {
            // 一般使用者的預設值是 false（除非明確開啟）
            const isEnabled = currentPerms[appId] === true;
            const appName = appNames[appId] || appId;
            return `
              <label class="perm-app-item">
                <input type="checkbox" name="app_${appId}" ${isEnabled ? 'checked' : ''} />
                <span class="perm-app-name">${escapeHtml(appName)}</span>
              </label>
            `;
          }).join('')}
        </div>
      `;

      // 添加操作按鈕
      const footer = document.createElement('div');
      footer.className = 'tenant-admin-dialog-footer';
      footer.innerHTML = `
        <button class="btn btn-ghost dialog-cancel-btn">取消</button>
        <button class="btn btn-primary dialog-save-btn">
          <span class="icon">${getIcon('content-save')}</span>
          <span>儲存權限</span>
        </button>
      `;
      permDialog.querySelector('.tenant-admin-dialog').appendChild(footer);

      footer.querySelector('.dialog-cancel-btn').addEventListener('click', closeDialog);

      // 儲存權限
      footer.querySelector('.dialog-save-btn').addEventListener('click', async () => {
        const saveBtn = footer.querySelector('.dialog-save-btn');
        saveBtn.disabled = true;
        saveBtn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span><span>儲存中...</span>`;

        try {
          const apps = {};
          Object.keys(defaultPerms.apps).filter(appId => appId !== 'platform-admin' && appId !== 'tenant-admin').forEach(appId => {
            const checkbox = content.querySelector(`input[name="app_${appId}"]`);
            if (checkbox) {
              apps[appId] = checkbox.checked;
            }
          });

          await APIClient.request(`/admin/users/${userId}/permissions`, {
            method: 'PATCH',
            body: JSON.stringify({ apps })
          });

          closeDialog();
          showToast('權限設定已儲存', 'check');
          // 重新載入使用者列表
          loadUsers(windowEl);
        } catch (error) {
          saveBtn.disabled = false;
          saveBtn.innerHTML = `<span class="icon">${getIcon('content-save')}</span><span>儲存權限</span>`;
          alert(`儲存失敗：${error.message}`);
        }
      });

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
   * 開啟新增使用者對話框
   * @param {HTMLElement} windowEl
   */
  function openCreateUserDialog(windowEl) {
    const dialog = document.createElement('div');
    dialog.className = 'tenant-admin-dialog-overlay';
    dialog.innerHTML = `
      <div class="tenant-admin-dialog">
        <div class="tenant-admin-dialog-header">
          <h3>新增使用者</h3>
          <button class="btn btn-ghost btn-sm dialog-close-btn">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="tenant-admin-dialog-body">
          <div class="form-group">
            <label for="newUsername">使用者名稱 *</label>
            <input type="text" id="newUsername" class="input" placeholder="登入用的帳號名稱" pattern="[a-zA-Z0-9_\\-]+" />
            <span class="form-hint">只能使用英文字母、數字、底線和連字號</span>
          </div>
          <div class="form-group">
            <label for="newDisplayName">顯示名稱</label>
            <input type="text" id="newDisplayName" class="input" placeholder="顯示在介面上的名稱" />
          </div>
          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" id="autoGeneratePassword" checked />
              <span>自動產生臨時密碼</span>
            </label>
          </div>
          <div class="form-group" id="passwordGroup" style="display: none;">
            <label for="newPassword">初始密碼</label>
            <input type="password" id="newPassword" class="input" placeholder="至少 8 個字元" minlength="8" />
          </div>
          <div class="form-group">
            <label for="newRole">角色</label>
            <select id="newRole" class="input">
              <option value="user">一般使用者</option>
              <option value="tenant_admin">租戶管理員</option>
            </select>
          </div>
          <div class="form-group" id="mustChangeGroup" style="display: none;">
            <label class="checkbox-label">
              <input type="checkbox" id="newMustChangePassword" checked />
              <span>首次登入需變更密碼</span>
            </label>
          </div>
        </div>
        <div class="tenant-admin-dialog-footer">
          <button class="btn btn-ghost dialog-cancel-btn">取消</button>
          <button class="btn btn-primary dialog-confirm-btn">建立帳號</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    // 切換自動產生密碼
    const autoGenCheckbox = dialog.querySelector('#autoGeneratePassword');
    const passwordGroup = dialog.querySelector('#passwordGroup');
    const mustChangeGroup = dialog.querySelector('#mustChangeGroup');
    autoGenCheckbox.addEventListener('change', () => {
      const isAuto = autoGenCheckbox.checked;
      passwordGroup.style.display = isAuto ? 'none' : 'block';
      mustChangeGroup.style.display = isAuto ? 'none' : 'block';
    });

    // 關閉對話框
    const closeDialog = () => dialog.remove();
    dialog.querySelector('.dialog-close-btn').addEventListener('click', closeDialog);
    dialog.querySelector('.dialog-cancel-btn').addEventListener('click', closeDialog);
    dialog.addEventListener('click', (e) => {
      if (e.target === dialog) closeDialog();
    });

    // 確認建立
    dialog.querySelector('.dialog-confirm-btn').addEventListener('click', async () => {
      const username = dialog.querySelector('#newUsername').value.trim();
      const displayName = dialog.querySelector('#newDisplayName').value.trim();
      const autoGenerate = dialog.querySelector('#autoGeneratePassword').checked;
      const password = autoGenerate ? null : dialog.querySelector('#newPassword').value;
      const role = dialog.querySelector('#newRole').value;
      const mustChangePassword = autoGenerate ? true : dialog.querySelector('#newMustChangePassword').checked;

      // 驗證
      if (!username) {
        alert('請輸入使用者名稱');
        return;
      }
      if (!/^[a-zA-Z0-9_-]+$/.test(username)) {
        alert('使用者名稱只能包含英文字母、數字、底線和連字號');
        return;
      }
      if (!autoGenerate && (!password || password.length < 8)) {
        alert('密碼至少需要 8 個字元');
        return;
      }

      const confirmBtn = dialog.querySelector('.dialog-confirm-btn');
      confirmBtn.disabled = true;
      confirmBtn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span> 建立中...`;

      try {
        const requestBody = {
          username,
          display_name: displayName || username,
          role,
          must_change_password: mustChangePassword
        };
        if (password) {
          requestBody.password = password;
        }

        const result = await APIClient.post('/tenant/users', requestBody);

        // 檢查建立是否成功
        if (!result.success) {
          alert(`建立失敗：${result.error || '未知錯誤'}`);
          confirmBtn.disabled = false;
          confirmBtn.innerHTML = '建立帳號';
          return;
        }

        closeDialog();
        loadUsers(windowEl);

        // 如果有自動產生的密碼，顯示給管理員
        if (result.temporary_password) {
          showTemporaryPasswordDialog(username, result.temporary_password);
        } else {
          showToast('使用者已建立', 'check');
        }
      } catch (error) {
        alert(`建立失敗：${error.message}`);
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = '建立帳號';
      }
    });

    // 聚焦第一個輸入欄
    setTimeout(() => dialog.querySelector('#newUsername')?.focus(), 100);
  }

  /**
   * 顯示自動產生密碼的對話框
   * @param {string} username
   * @param {string} password
   */
  function showTemporaryPasswordDialog(username, password) {
    const dialog = document.createElement('div');
    dialog.className = 'tenant-admin-dialog-overlay';
    dialog.innerHTML = `
      <div class="tenant-admin-dialog" style="max-width: 400px;">
        <div class="tenant-admin-dialog-header">
          <h3><span class="icon">${getIcon('check-circle')}</span> 使用者已建立</h3>
        </div>
        <div class="tenant-admin-dialog-body">
          <p style="margin-bottom: var(--spacing-md);">使用者 <strong>${username}</strong> 的臨時密碼如下：</p>
          <div class="temp-password-box">
            <code id="tempPassword">${password}</code>
            <button class="btn btn-ghost btn-sm copy-password-btn" title="複製密碼">
              <span class="icon">${getIcon('content-copy')}</span>
            </button>
          </div>
          <p class="form-hint" style="margin-top: var(--spacing-sm);">
            <span class="icon">${getIcon('alert-circle')}</span>
            請將此密碼告知使用者，此密碼僅顯示一次，關閉後無法再查看。
          </p>
        </div>
        <div class="tenant-admin-dialog-footer">
          <button class="btn btn-primary dialog-close-btn">我已記下密碼</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    // 複製密碼
    dialog.querySelector('.copy-password-btn').addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(password);
        showToast('密碼已複製', 'check');
      } catch (error) {
        // fallback
        const tempInput = document.createElement('input');
        tempInput.value = password;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);
        showToast('密碼已複製', 'check');
      }
    });

    // 關閉對話框
    dialog.querySelector('.dialog-close-btn').addEventListener('click', () => dialog.remove());
  }

  /**
   * 開啟使用者詳情/編輯對話框
   * @param {HTMLElement} windowEl
   * @param {string} userId
   */
  async function openUserDetailDialog(windowEl, userId) {
    const dialog = document.createElement('div');
    dialog.className = 'tenant-admin-dialog-overlay';
    dialog.innerHTML = `
      <div class="tenant-admin-dialog">
        <div class="tenant-admin-dialog-header">
          <h3>使用者詳情</h3>
          <button class="btn btn-ghost btn-sm dialog-close-btn">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="tenant-admin-dialog-body">
          <div class="tenant-admin-loading">
            <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
            <span>載入中...</span>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    // 關閉對話框
    const closeDialog = () => dialog.remove();
    dialog.querySelector('.dialog-close-btn').addEventListener('click', closeDialog);
    dialog.addEventListener('click', (e) => {
      if (e.target === dialog) closeDialog();
    });

    try {
      const user = await APIClient.get(`/tenant/users/${userId}`);
      renderUserDetailDialog(dialog, windowEl, user, closeDialog);
    } catch (error) {
      dialog.querySelector('.tenant-admin-dialog-body').innerHTML = `
        <div class="tenant-admin-error">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入失敗：${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * 渲染使用者詳情對話框內容
   * @param {HTMLElement} dialog
   * @param {HTMLElement} windowEl
   * @param {Object} user
   * @param {Function} closeDialog
   */
  function renderUserDetailDialog(dialog, windowEl, user, closeDialog) {
    const roleLabels = {
      'platform_admin': '平台管理員',
      'tenant_admin': '租戶管理員',
      'user': '一般使用者'
    };

    dialog.querySelector('.tenant-admin-dialog-body').innerHTML = `
      <div class="form-group">
        <label>使用者名稱</label>
        <div class="form-static"><code class="tenant-admin-code">${escapeHtml(user.username)}</code> (不可修改)</div>
      </div>
      <div class="form-group">
        <label for="editDisplayName">顯示名稱</label>
        <input type="text" id="editDisplayName" class="input" value="${escapeHtml(user.display_name || '')}" />
      </div>
      <div class="form-group">
        <label for="editRole">角色</label>
        <select id="editRole" class="input">
          <option value="user" ${user.role === 'user' ? 'selected' : ''}>一般使用者</option>
          <option value="tenant_admin" ${user.role === 'tenant_admin' ? 'selected' : ''}>租戶管理員</option>
        </select>
      </div>
      <div class="user-detail-info">
        <div class="user-detail-row">
          <span class="label">狀態</span>
          <span class="tenant-admin-status-badge ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? '啟用' : '停用'}</span>
        </div>
        <div class="user-detail-row">
          <span class="label">建立時間</span>
          <span>${formatDateTime(user.created_at)}</span>
        </div>
        <div class="user-detail-row">
          <span class="label">最後登入</span>
          <span>${user.last_login_at ? formatDateTime(user.last_login_at) : '-'}</span>
        </div>
      </div>
    `;

    // 添加操作按鈕
    const footer = document.createElement('div');
    footer.className = 'tenant-admin-dialog-footer';
    footer.innerHTML = `
      <button class="btn btn-ghost dialog-cancel-btn">取消</button>
      <button class="btn btn-primary dialog-save-btn">儲存變更</button>
    `;
    dialog.querySelector('.tenant-admin-dialog').appendChild(footer);

    footer.querySelector('.dialog-cancel-btn').addEventListener('click', closeDialog);

    // 儲存變更
    footer.querySelector('.dialog-save-btn').addEventListener('click', async () => {
      const displayName = dialog.querySelector('#editDisplayName').value.trim();
      const role = dialog.querySelector('#editRole').value;

      const saveBtn = footer.querySelector('.dialog-save-btn');
      saveBtn.disabled = true;
      saveBtn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span> 儲存中...`;

      try {
        await APIClient.request(`/tenant/users/${user.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            display_name: displayName,
            role
          })
        });

        closeDialog();
        loadUsers(windowEl);
        showToast('使用者資料已更新', 'check');
      } catch (error) {
        alert(`更新失敗：${error.message}`);
        saveBtn.disabled = false;
        saveBtn.innerHTML = '儲存變更';
      }
    });
  }

  /**
   * 開啟重設密碼對話框
   * @param {HTMLElement} windowEl
   * @param {string} userId
   * @param {string} username
   */
  function openResetPasswordDialog(windowEl, userId, username) {
    const dialog = document.createElement('div');
    dialog.className = 'tenant-admin-dialog-overlay';
    dialog.innerHTML = `
      <div class="tenant-admin-dialog">
        <div class="tenant-admin-dialog-header">
          <h3>重設密碼</h3>
          <button class="btn btn-ghost btn-sm dialog-close-btn">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="tenant-admin-dialog-body">
          <p class="form-hint" style="margin-bottom: 16px;">
            為使用者 <strong>${escapeHtml(username)}</strong> 設定新密碼
          </p>
          <div class="form-group">
            <label for="resetNewPassword">新密碼 *</label>
            <input type="password" id="resetNewPassword" class="input" placeholder="至少 8 個字元" minlength="8" />
          </div>
          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" id="resetMustChange" checked />
              <span>下次登入需變更密碼</span>
            </label>
          </div>
        </div>
        <div class="tenant-admin-dialog-footer">
          <button class="btn btn-ghost dialog-cancel-btn">取消</button>
          <button class="btn btn-primary dialog-confirm-btn">重設密碼</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    // 關閉對話框
    const closeDialog = () => dialog.remove();
    dialog.querySelector('.dialog-close-btn').addEventListener('click', closeDialog);
    dialog.querySelector('.dialog-cancel-btn').addEventListener('click', closeDialog);
    dialog.addEventListener('click', (e) => {
      if (e.target === dialog) closeDialog();
    });

    // 確認重設
    dialog.querySelector('.dialog-confirm-btn').addEventListener('click', async () => {
      const newPassword = dialog.querySelector('#resetNewPassword').value;
      const mustChange = dialog.querySelector('#resetMustChange').checked;

      if (!newPassword || newPassword.length < 8) {
        alert('密碼至少需要 8 個字元');
        return;
      }

      const confirmBtn = dialog.querySelector('.dialog-confirm-btn');
      confirmBtn.disabled = true;
      confirmBtn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span> 重設中...`;

      try {
        const result = await APIClient.post(`/tenant/users/${userId}/reset-password`, {
          new_password: newPassword,
          must_change_password: mustChange
        });

        // 檢查重設是否成功
        if (!result.success) {
          alert(`重設失敗：${result.error || '未知錯誤'}`);
          confirmBtn.disabled = false;
          confirmBtn.innerHTML = '重設密碼';
          return;
        }

        closeDialog();
        showToast('密碼已重設', 'check');
      } catch (error) {
        alert(`重設失敗：${error.message}`);
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = '重設密碼';
      }
    });

    // 聚焦密碼輸入欄
    setTimeout(() => dialog.querySelector('#resetNewPassword')?.focus(), 100);
  }

  /**
   * 停用使用者
   * @param {HTMLElement} windowEl
   * @param {string} userId
   * @param {string} username
   */
  async function deactivateUser(windowEl, userId, username) {
    if (!confirm(`確定要停用使用者「${username}」嗎？\n停用後該使用者將無法登入。`)) {
      return;
    }

    try {
      const result = await APIClient.post(`/tenant/users/${userId}/deactivate`);
      if (!result.success) {
        alert(`停用失敗：${result.message || '未知錯誤'}`);
        return;
      }
      loadUsers(windowEl);
      showToast('使用者已停用', 'check');
    } catch (error) {
      alert(`停用失敗：${error.message}`);
    }
  }

  /**
   * 啟用使用者
   * @param {HTMLElement} windowEl
   * @param {string} userId
   * @param {string} username
   */
  async function activateUser(windowEl, userId, username) {
    if (!confirm(`確定要啟用使用者「${username}」嗎？`)) {
      return;
    }

    try {
      const result = await APIClient.post(`/tenant/users/${userId}/activate`);
      if (!result.success) {
        alert(`啟用失敗：${result.message || '未知錯誤'}`);
        return;
      }
      loadUsers(windowEl);
      showToast('使用者已啟用', 'check');
    } catch (error) {
      alert(`啟用失敗：${error.message}`);
    }
  }

  /**
   * 格式化日期時間
   * @param {string} dateStr
   * @returns {string}
   */
  function formatDateTime(dateStr) {
    if (!dateStr) return '-';
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
   * HTML 跳脫
   * @param {string} str
   * @returns {string}
   */
  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  /**
   * 顯示 Toast 訊息
   * @param {string} message
   * @param {string} icon
   */
  function showToast(message, icon = 'information') {
    if (typeof DesktopModule !== 'undefined') {
      DesktopModule.showToast(message, icon);
    }
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
            <label class="feature-toggle">
              <input type="checkbox" id="enableVendorManagement" ${settings.enable_vendor_management !== false ? 'checked' : ''} />
              <span class="icon">${getIcon('store')}</span>
              <span>廠商管理</span>
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

      <!-- NAS 登入驗證設定區塊（僅平台管理員可見） -->
      <div class="tenant-settings-form nas-auth-settings-section" id="nasAuthSettingsSection" style="display: none;">
        <div class="settings-group">
          <h3 class="settings-group-title">
            <span class="icon">${getIcon('server-network')}</span>
            NAS 登入驗證
          </h3>
          <p class="settings-description">
            啟用後，此租戶的使用者可以使用 NAS 帳號密碼登入系統。<br>
            適用於尚未設定系統密碼的使用者。
          </p>

          <div class="form-group">
            <label class="feature-toggle nas-auth-toggle">
              <input type="checkbox" id="enableNasAuth" ${settings.enable_nas_auth ? 'checked' : ''} />
              <span class="icon">${getIcon('shield-key')}</span>
              <span>啟用 NAS 帳號登入</span>
            </label>
          </div>

          <div class="nas-auth-config" id="nasAuthConfig" style="display: ${settings.enable_nas_auth ? 'block' : 'none'};">
            <div class="form-group">
              <label for="nasAuthHost">NAS 主機位址</label>
              <input type="text" id="nasAuthHost" class="input" placeholder="例如：192.168.1.100" value="${settings.nas_auth_host || ''}" />
              <span class="form-hint">留空則使用系統預設的 NAS 主機</span>
            </div>
            <div class="form-group">
              <label for="nasAuthPort">NAS 連接埠</label>
              <input type="number" id="nasAuthPort" class="input" placeholder="預設：445" value="${settings.nas_auth_port || ''}" min="1" max="65535" />
              <span class="form-hint">SMB 預設為 445，通常不需要修改</span>
            </div>
            <div class="form-group">
              <label for="nasAuthShare">驗證用共享名稱</label>
              <input type="text" id="nasAuthShare" class="input" placeholder="例如：home" value="${settings.nas_auth_share || ''}" />
              <span class="form-hint">用於驗證使用者是否有權存取，建議使用 home（每個 NAS 用戶都有）</span>
            </div>

            <div class="nas-auth-actions">
              <button class="btn btn-secondary" id="testNasAuthBtn">
                <span class="icon">${getIcon('connection')}</span>
                <span>測試連線</span>
              </button>
            </div>
            <div class="nas-auth-test-result" id="nasAuthTestResult" style="display: none;"></div>
          </div>

          <div class="settings-actions">
            <button class="btn btn-primary" id="saveNasAuthBtn">
              <span class="icon">${getIcon('content-save')}</span>
              <span>儲存 NAS 設定</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Line Bot 設定區塊（僅平台管理員可見） -->
      <div class="tenant-settings-form linebot-settings-section" id="linebotSettingsSection" style="display: none;">
        <div class="settings-group">
          <h3 class="settings-group-title">
            <span class="icon">${getIcon('message-text')}</span>
            Line Bot 設定
          </h3>
          <p class="settings-description">
            設定獨立的 Line Bot 憑證，讓此租戶擁有專屬的 Line Bot。<br>
            如果不設定，將使用平台預設的共用 Bot。
          </p>

          <div class="linebot-status" id="linebotStatus">
            <div class="linebot-status-loading">
              <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
              <span>載入中...</span>
            </div>
          </div>

          <div class="linebot-form" id="linebotForm" style="display: none;">
            <div class="form-group">
              <label for="lineChannelId">Channel ID</label>
              <input type="text" id="lineChannelId" class="input" placeholder="Line Channel ID" />
              <span class="form-hint">從 Line Developers Console 取得</span>
            </div>
            <div class="form-group">
              <label for="lineChannelSecret">Channel Secret</label>
              <input type="password" id="lineChannelSecret" class="input" placeholder="留空表示不更新" />
              <span class="form-hint">用於驗證 Webhook 請求</span>
            </div>
            <div class="form-group">
              <label for="lineAccessToken">Access Token</label>
              <input type="password" id="lineAccessToken" class="input" placeholder="留空表示不更新" />
              <span class="form-hint">用於發送訊息給用戶</span>
            </div>

            <div class="linebot-actions">
              <button class="btn btn-secondary" id="testLinebotBtn">
                <span class="icon">${getIcon('connection')}</span>
                <span>測試連線</span>
              </button>
              <button class="btn btn-primary" id="saveLinebotBtn">
                <span class="icon">${getIcon('content-save')}</span>
                <span>儲存設定</span>
              </button>
              <button class="btn btn-text-danger" id="clearLinebotBtn">
                <span class="icon">${getIcon('delete')}</span>
                <span>清除設定</span>
              </button>
            </div>
          </div>

          <div class="linebot-test-result" id="linebotTestResult" style="display: none;"></div>
        </div>
      </div>
    `;

    // 綁定儲存按鈕
    const saveBtn = container.querySelector('#saveSettingsBtn');
    saveBtn.addEventListener('click', () => saveSettings(windowEl, container));

    // 檢查是否為平台管理員或租戶管理員，若是則顯示進階設定
    const isPlatformAdmin = PermissionsModule.isPlatformAdmin?.();
    const isTenantAdmin = PermissionsModule.isTenantAdmin?.();

    // NAS 登入驗證設定：平台管理員和租戶管理員都可以設定
    if (isPlatformAdmin || isTenantAdmin) {
      const nasAuthSection = container.querySelector('#nasAuthSettingsSection');
      nasAuthSection.style.display = '';
      initNasAuthSettings(container, isPlatformAdmin);
    }

    // Line Bot 設定：平台管理員和租戶管理員都可以設定
    if (isPlatformAdmin || isTenantAdmin) {
      const linebotSection = container.querySelector('#linebotSettingsSection');
      linebotSection.style.display = '';
      loadLinebotSettings(container, isPlatformAdmin, true);  // 首次載入，綁定事件
    }
  }

  /**
   * 初始化 NAS 登入驗證設定
   * @param {HTMLElement} container
   * @param {boolean} isPlatformAdmin - 是否為平台管理員
   */
  function initNasAuthSettings(container, isPlatformAdmin = false) {
    const enableCheckbox = container.querySelector('#enableNasAuth');
    const configDiv = container.querySelector('#nasAuthConfig');
    const testBtn = container.querySelector('#testNasAuthBtn');
    const saveBtn = container.querySelector('#saveNasAuthBtn');

    // 切換啟用狀態時顯示/隱藏設定區塊
    enableCheckbox.addEventListener('change', () => {
      configDiv.style.display = enableCheckbox.checked ? 'block' : 'none';
    });

    // 測試連線按鈕
    testBtn.addEventListener('click', () => testNasAuthConnection(container, isPlatformAdmin));

    // 儲存按鈕
    saveBtn.addEventListener('click', () => saveNasAuthSettings(container));
  }

  /**
   * 測試 NAS 登入驗證連線
   * @param {HTMLElement} container
   * @param {boolean} isPlatformAdmin - 是否為平台管理員
   */
  async function testNasAuthConnection(container, isPlatformAdmin = false) {
    const testBtn = container.querySelector('#testNasAuthBtn');
    const resultEl = container.querySelector('#nasAuthTestResult');

    const host = container.querySelector('#nasAuthHost').value.trim();
    const port = container.querySelector('#nasAuthPort').value.trim();
    const share = container.querySelector('#nasAuthShare').value.trim();

    testBtn.disabled = true;
    testBtn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span><span>測試中...</span>`;
    resultEl.style.display = 'none';

    try {
      // 根據角色使用不同的 API 端點
      const apiPath = isPlatformAdmin
        ? `/admin/tenants/${tenantInfo.id}/nas-auth/test`
        : '/tenant/nas-auth/test';

      const response = await APIClient.post(apiPath, {
        host: host || null,
        port: port ? parseInt(port, 10) : null,
        share: share || null
      });

      if (response.success) {
        resultEl.className = 'nas-auth-test-result success';
        resultEl.innerHTML = `
          <span class="icon">${getIcon('check-circle')}</span>
          <span>連線成功：可以連線至 NAS 並存取指定的共享</span>
        `;
      } else {
        resultEl.className = 'nas-auth-test-result error';
        resultEl.innerHTML = `
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>連線失敗：${response.error || '無法連線至 NAS'}</span>
        `;
      }
      resultEl.style.display = '';

    } catch (error) {
      resultEl.className = 'nas-auth-test-result error';
      resultEl.innerHTML = `
        <span class="icon">${getIcon('alert-circle')}</span>
        <span>測試失敗：${error.message}</span>
      `;
      resultEl.style.display = '';
    } finally {
      testBtn.disabled = false;
      testBtn.innerHTML = `<span class="icon">${getIcon('connection')}</span><span>測試連線</span>`;
    }
  }

  /**
   * 儲存 NAS 登入驗證設定
   * @param {HTMLElement} container
   */
  async function saveNasAuthSettings(container) {
    const saveBtn = container.querySelector('#saveNasAuthBtn');
    const enableNasAuth = container.querySelector('#enableNasAuth').checked;
    const nasAuthHost = container.querySelector('#nasAuthHost').value.trim();
    const nasAuthPort = container.querySelector('#nasAuthPort').value.trim();
    const nasAuthShare = container.querySelector('#nasAuthShare').value.trim();

    saveBtn.disabled = true;
    saveBtn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span><span>儲存中...</span>`;

    try {
      // 合併現有設定
      const newSettings = {
        ...tenantInfo.settings,
        enable_nas_auth: enableNasAuth,
        nas_auth_host: nasAuthHost || null,
        nas_auth_port: nasAuthPort ? parseInt(nasAuthPort, 10) : null,
        nas_auth_share: nasAuthShare || null
      };

      await APIClient.updateTenantSettings({ settings: newSettings });

      // 更新快取
      tenantInfo.settings = newSettings;

      showToast('NAS 登入設定已儲存', 'check');
    } catch (error) {
      alert(`儲存失敗：${error.message}`);
    } finally {
      saveBtn.disabled = false;
      saveBtn.innerHTML = `<span class="icon">${getIcon('content-save')}</span><span>儲存 NAS 設定</span>`;
    }
  }

  /**
   * 載入 Line Bot 設定
   * @param {HTMLElement} container
   * @param {boolean} isPlatformAdmin - 是否為平台管理員（未使用，保留向後相容）
   * @param {boolean} bindEvents - 是否綁定事件（首次載入時為 true）
   */
  async function loadLinebotSettings(container, isPlatformAdmin = false, bindEvents = false) {
    const statusEl = container.querySelector('#linebotStatus');
    const formEl = container.querySelector('#linebotForm');

    try {
      // 使用租戶 API（平台管理員和租戶管理員都可以用）
      const response = await APIClient.get('/tenant/bot');

      // 更新狀態顯示
      if (response.configured) {
        statusEl.innerHTML = `
          <div class="linebot-status-configured">
            <span class="icon">${getIcon('check-circle')}</span>
            <span>已設定獨立 Line Bot</span>
            <span class="linebot-channel-id">Channel ID: ${response.channel_id}</span>
          </div>
        `;
        container.querySelector('#lineChannelId').value = response.channel_id || '';
      } else {
        statusEl.innerHTML = `
          <div class="linebot-status-unconfigured">
            <span class="icon">${getIcon('information-outline')}</span>
            <span>使用平台共用 Bot</span>
          </div>
        `;
      }

      // 顯示表單
      formEl.style.display = '';

      // 只在首次載入時綁定按鈕事件
      if (bindEvents) {
        container.querySelector('#testLinebotBtn').addEventListener('click', () => testLinebotConnection(container));
        container.querySelector('#saveLinebotBtn').addEventListener('click', () => saveLinebotSettings(container));
        container.querySelector('#clearLinebotBtn').addEventListener('click', () => clearLinebotSettings(container));
      }

    } catch (error) {
      statusEl.innerHTML = `
        <div class="linebot-status-error">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入失敗：${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * 測試 Line Bot 連線
   * @param {HTMLElement} container
   */
  async function testLinebotConnection(container) {
    const testBtn = container.querySelector('#testLinebotBtn');
    const resultEl = container.querySelector('#linebotTestResult');

    testBtn.disabled = true;
    testBtn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span><span>測試中...</span>`;
    resultEl.style.display = 'none';

    try {
      // 使用租戶 API
      const response = await APIClient.post('/tenant/bot/test');

      if (response.success) {
        resultEl.className = 'linebot-test-result success';
        resultEl.innerHTML = `
          <span class="icon">${getIcon('check-circle')}</span>
          <div class="linebot-test-info">
            <strong>連線成功</strong>
            <span>Bot 名稱：${response.bot_info?.display_name || 'N/A'}</span>
            <span>Basic ID：${response.bot_info?.basic_id || 'N/A'}</span>
          </div>
        `;
      } else {
        resultEl.className = 'linebot-test-result error';
        resultEl.innerHTML = `
          <span class="icon">${getIcon('alert-circle')}</span>
          <div class="linebot-test-info">
            <strong>連線失敗</strong>
            <span>${response.error || '未知錯誤'}</span>
          </div>
        `;
      }
      resultEl.style.display = '';

    } catch (error) {
      resultEl.className = 'linebot-test-result error';
      resultEl.innerHTML = `
        <span class="icon">${getIcon('alert-circle')}</span>
        <div class="linebot-test-info">
          <strong>測試失敗</strong>
          <span>${error.message}</span>
        </div>
      `;
      resultEl.style.display = '';
    } finally {
      testBtn.disabled = false;
      testBtn.innerHTML = `<span class="icon">${getIcon('connection')}</span><span>測試連線</span>`;
    }
  }

  /**
   * 儲存 Line Bot 設定
   * @param {HTMLElement} container
   */
  async function saveLinebotSettings(container) {
    const saveBtn = container.querySelector('#saveLinebotBtn');
    const channelId = container.querySelector('#lineChannelId').value.trim();
    const channelSecret = container.querySelector('#lineChannelSecret').value;
    const accessToken = container.querySelector('#lineAccessToken').value;

    // 如果都沒填，提示用戶
    if (!channelId && !channelSecret && !accessToken) {
      alert('請至少填寫 Channel ID');
      return;
    }

    saveBtn.disabled = true;
    saveBtn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span><span>儲存中...</span>`;

    try {
      const data = {};
      if (channelId) data.channel_id = channelId;
      if (channelSecret) data.channel_secret = channelSecret;
      if (accessToken) data.access_token = accessToken;

      // 使用租戶 API
      await APIClient.put('/tenant/bot', data);

      // 清空密碼欄位
      container.querySelector('#lineChannelSecret').value = '';
      container.querySelector('#lineAccessToken').value = '';

      // 重新載入設定
      await loadLinebotSettings(container);

      if (typeof DesktopModule !== 'undefined') {
        DesktopModule.showToast('Line Bot 設定已儲存', 'check');
      }
    } catch (error) {
      alert(`儲存失敗：${error.message}`);
    } finally {
      saveBtn.disabled = false;
      saveBtn.innerHTML = `<span class="icon">${getIcon('content-save')}</span><span>儲存設定</span>`;
    }
  }

  /**
   * 清除 Line Bot 設定
   * @param {HTMLElement} container
   */
  async function clearLinebotSettings(container) {
    if (!confirm('確定要清除 Line Bot 設定嗎？\n清除後將使用平台共用 Bot。')) {
      return;
    }

    const clearBtn = container.querySelector('#clearLinebotBtn');
    clearBtn.disabled = true;
    clearBtn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span><span>清除中...</span>`;

    try {
      // 使用租戶 API
      await APIClient.delete('/tenant/bot');

      // 清空表單
      container.querySelector('#lineChannelId').value = '';
      container.querySelector('#lineChannelSecret').value = '';
      container.querySelector('#lineAccessToken').value = '';

      // 重新載入設定
      await loadLinebotSettings(container);

      if (typeof DesktopModule !== 'undefined') {
        DesktopModule.showToast('Line Bot 設定已清除', 'check');
      }
    } catch (error) {
      alert(`清除失敗：${error.message}`);
    } finally {
      clearBtn.disabled = false;
      clearBtn.innerHTML = `<span class="icon">${getIcon('delete')}</span><span>清除設定</span>`;
    }
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
        enable_inventory: container.querySelector('#enableInventory').checked,
        enable_vendor_management: container.querySelector('#enableVendorManagement').checked
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
