/**
 * ChingTech OS - Platform Admin Application
 * 平台管理應用程式：租戶管理、Line 群組管理
 * 僅平台管理員（platform_admin）可存取
 */

const PlatformAdminApp = (function () {
  'use strict';

  const APP_ID = 'platform-admin';
  let currentWindowId = null;
  let tenantsCache = [];
  let lineGroupsCache = [];

  /**
   * 檢查是否為平台管理員
   * @returns {boolean}
   */
  function isPlatformAdmin() {
    const session = LoginModule.getSession();
    return session?.role === 'platform_admin';
  }

  /**
   * 取得視窗內容 HTML
   * @returns {string}
   */
  function getWindowContent() {
    return `
      <div class="platform-admin-container">
        <nav class="platform-admin-sidebar">
          <ul class="platform-admin-nav">
            <li class="platform-admin-nav-item active" data-section="tenants">
              <span class="icon">${getIcon('domain')}</span>
              <span>租戶管理</span>
            </li>
            <li class="platform-admin-nav-item" data-section="line-groups">
              <span class="icon">${getIcon('message-text')}</span>
              <span>Line 群組</span>
            </li>
          </ul>
        </nav>

        <main class="platform-admin-content">
          <!-- 租戶管理區段 -->
          <section class="platform-admin-section active" id="section-tenants">
            <div class="platform-admin-section-header">
              <h2 class="platform-admin-section-title">租戶管理</h2>
              <button class="btn btn-primary btn-sm" id="createTenantBtn">
                <span class="icon">${getIcon('plus')}</span>
                <span>建立租戶</span>
              </button>
            </div>
            <div class="platform-admin-filters">
              <select id="tenantStatusFilter" class="platform-admin-filter-select">
                <option value="">全部狀態</option>
                <option value="active">啟用</option>
                <option value="trial">試用</option>
                <option value="suspended">停用</option>
              </select>
              <select id="tenantPlanFilter" class="platform-admin-filter-select">
                <option value="">全部方案</option>
                <option value="trial">試用版</option>
                <option value="basic">基本版</option>
                <option value="pro">專業版</option>
                <option value="enterprise">企業版</option>
              </select>
            </div>
            <div class="platform-admin-loading" id="tenants-loading">
              <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
              <span>載入中...</span>
            </div>
            <div id="tenants-content" style="display: none;"></div>
          </section>

          <!-- Line 群組區段 -->
          <section class="platform-admin-section" id="section-line-groups">
            <div class="platform-admin-section-header">
              <h2 class="platform-admin-section-title">Line 群組管理</h2>
            </div>
            <div class="platform-admin-filters">
              <select id="lineGroupTenantFilter" class="platform-admin-filter-select">
                <option value="">全部租戶</option>
              </select>
            </div>
            <div class="platform-admin-loading" id="line-groups-loading">
              <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
              <span>載入中...</span>
            </div>
            <div id="line-groups-content" style="display: none;"></div>
          </section>
        </main>

        <!-- 手機版底部 Tab Bar -->
        <nav class="mobile-tab-bar platform-admin-mobile-tabs">
          <button class="mobile-tab-item active" data-section="tenants">
            <span class="icon">${getIcon('domain')}</span>
            <span class="mobile-tab-label">租戶</span>
          </button>
          <button class="mobile-tab-item" data-section="line-groups">
            <span class="icon">${getIcon('message-text')}</span>
            <span class="mobile-tab-label">群組</span>
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
    const navItems = windowEl.querySelectorAll('.platform-admin-nav-item');
    navItems.forEach(item => {
      item.addEventListener('click', () => {
        const section = item.dataset.section;
        switchSection(windowEl, section);
      });
    });

    // 綁定手機版底部 Tab Bar
    const mobileTabs = windowEl.querySelectorAll('.platform-admin-mobile-tabs .mobile-tab-item');
    mobileTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const section = tab.dataset.section;
        switchSection(windowEl, section);
      });
    });

    // 綁定建立租戶按鈕
    const createTenantBtn = windowEl.querySelector('#createTenantBtn');
    createTenantBtn?.addEventListener('click', () => openCreateTenantDialog(windowEl));

    // 綁定篩選器
    const statusFilter = windowEl.querySelector('#tenantStatusFilter');
    const planFilter = windowEl.querySelector('#tenantPlanFilter');
    statusFilter?.addEventListener('change', () => loadTenants(windowEl));
    planFilter?.addEventListener('change', () => loadTenants(windowEl));

    const lineGroupTenantFilter = windowEl.querySelector('#lineGroupTenantFilter');
    lineGroupTenantFilter?.addEventListener('change', () => loadLineGroups(windowEl));

    // 載入租戶資料
    loadTenants(windowEl);
  }

  /**
   * 切換區段
   * @param {HTMLElement} windowEl
   * @param {string} sectionId
   */
  function switchSection(windowEl, sectionId) {
    // 更新側邊欄導航狀態
    const navItems = windowEl.querySelectorAll('.platform-admin-nav-item');
    navItems.forEach(item => {
      item.classList.toggle('active', item.dataset.section === sectionId);
    });

    // 更新手機版 Tab 狀態
    const mobileTabs = windowEl.querySelectorAll('.platform-admin-mobile-tabs .mobile-tab-item');
    mobileTabs.forEach(tab => {
      tab.classList.toggle('active', tab.dataset.section === sectionId);
    });

    // 切換顯示區段
    const sections = windowEl.querySelectorAll('.platform-admin-section');
    sections.forEach(section => {
      section.classList.toggle('active', section.id === `section-${sectionId}`);
    });

    // 根據區段載入資料
    switch (sectionId) {
      case 'tenants':
        loadTenants(windowEl);
        break;
      case 'line-groups':
        loadLineGroups(windowEl);
        break;
    }
  }

  // ============================================================
  // 租戶管理
  // ============================================================

  /**
   * 載入租戶列表
   * @param {HTMLElement} windowEl
   */
  async function loadTenants(windowEl) {
    const loading = windowEl.querySelector('#tenants-loading');
    const content = windowEl.querySelector('#tenants-content');

    loading.style.display = '';
    content.style.display = 'none';

    try {
      const statusFilter = windowEl.querySelector('#tenantStatusFilter')?.value || '';
      const planFilter = windowEl.querySelector('#tenantPlanFilter')?.value || '';

      const params = new URLSearchParams();
      if (statusFilter) params.append('status', statusFilter);
      if (planFilter) params.append('plan', planFilter);

      const queryString = params.toString();
      const url = `/admin/tenants${queryString ? '?' + queryString : ''}`;

      const data = await APIClient.get(url);
      tenantsCache = data.tenants || [];

      renderTenants(windowEl, content, tenantsCache);
      loading.style.display = 'none';
      content.style.display = '';

      // 更新 Line 群組篩選器的租戶選項
      updateTenantFilterOptions(windowEl);
    } catch (error) {
      loading.innerHTML = `
        <div class="platform-admin-error">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入失敗：${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * 渲染租戶列表
   * @param {HTMLElement} windowEl
   * @param {HTMLElement} container
   * @param {Array} tenants
   */
  function renderTenants(windowEl, container, tenants) {
    const statusLabels = {
      'active': '啟用',
      'trial': '試用',
      'suspended': '停用'
    };

    const statusClass = {
      'active': 'success',
      'trial': 'info',
      'suspended': 'error'
    };

    const planLabels = {
      'trial': '試用版',
      'basic': '基本版',
      'pro': '專業版',
      'enterprise': '企業版'
    };

    if (tenants.length === 0) {
      container.innerHTML = `
        <div class="platform-admin-empty">
          <span class="icon">${getIcon('office-building-remove')}</span>
          <span>沒有符合條件的租戶</span>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="platform-admin-table-container">
        <table class="platform-admin-table">
          <thead>
            <tr>
              <th>代碼</th>
              <th>名稱</th>
              <th>狀態</th>
              <th>方案</th>
              <th>儲存使用</th>
              <th>建立時間</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            ${tenants.map(tenant => `
              <tr data-tenant-id="${tenant.id}">
                <td><code class="platform-admin-code">${escapeHtml(tenant.code)}</code></td>
                <td>${escapeHtml(tenant.name)}</td>
                <td>
                  <span class="platform-admin-badge ${statusClass[tenant.status] || ''}">${statusLabels[tenant.status] || tenant.status}</span>
                </td>
                <td>${planLabels[tenant.plan] || tenant.plan}</td>
                <td>${formatStorageSize(tenant.storage_used_mb || 0)} / ${formatStorageSize(tenant.storage_quota_mb)}</td>
                <td>${formatDate(tenant.created_at)}</td>
                <td class="platform-admin-actions">
                  <button class="btn btn-ghost btn-sm tenant-details-btn" data-tenant-id="${tenant.id}" title="詳情">
                    <span class="icon">${getIcon('information-outline')}</span>
                  </button>
                  ${tenant.status === 'suspended' ? `
                    <button class="btn btn-ghost btn-sm tenant-activate-btn" data-tenant-id="${tenant.id}" title="啟用">
                      <span class="icon">${getIcon('check-circle')}</span>
                    </button>
                  ` : `
                    <button class="btn btn-ghost btn-sm tenant-suspend-btn" data-tenant-id="${tenant.id}" title="停用">
                      <span class="icon">${getIcon('cancel')}</span>
                    </button>
                  `}
                  <button class="btn btn-ghost btn-sm btn-danger-text tenant-delete-btn" data-tenant-id="${tenant.id}" data-tenant-name="${escapeHtml(tenant.name)}" data-tenant-code="${escapeHtml(tenant.code)}" title="刪除">
                    <span class="icon">${getIcon('delete')}</span>
                  </button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;

    // 綁定操作按鈕
    container.querySelectorAll('.tenant-details-btn').forEach(btn => {
      btn.addEventListener('click', () => openTenantDetails(windowEl, btn.dataset.tenantId));
    });

    container.querySelectorAll('.tenant-suspend-btn').forEach(btn => {
      btn.addEventListener('click', () => suspendTenant(windowEl, btn.dataset.tenantId));
    });

    container.querySelectorAll('.tenant-activate-btn').forEach(btn => {
      btn.addEventListener('click', () => activateTenant(windowEl, btn.dataset.tenantId));
    });

    container.querySelectorAll('.tenant-delete-btn').forEach(btn => {
      btn.addEventListener('click', () => deleteTenant(windowEl, btn.dataset.tenantId, btn.dataset.tenantName, btn.dataset.tenantCode));
    });
  }

  /**
   * 開啟建立租戶對話框
   * @param {HTMLElement} windowEl
   */
  function openCreateTenantDialog(windowEl) {
    const dialog = document.createElement('div');
    dialog.className = 'platform-admin-dialog-overlay';
    dialog.innerHTML = `
      <div class="platform-admin-dialog">
        <div class="platform-admin-dialog-header">
          <h3>建立新租戶</h3>
          <button class="btn btn-ghost btn-sm dialog-close-btn">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="platform-admin-dialog-body">
          <div class="form-group">
            <label for="newTenantCode">租戶代碼 *</label>
            <input type="text" id="newTenantCode" class="input" placeholder="如 acme、demo（小寫英數字）" pattern="[a-z0-9_-]+" />
            <span class="form-hint">用於登入識別，建立後無法修改</span>
          </div>
          <div class="form-group">
            <label for="newTenantName">租戶名稱 *</label>
            <input type="text" id="newTenantName" class="input" placeholder="公司/組織名稱" />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label for="newTenantPlan">方案</label>
              <select id="newTenantPlan" class="input">
                <option value="trial">試用版</option>
                <option value="basic">基本版</option>
                <option value="pro">專業版</option>
                <option value="enterprise">企業版</option>
              </select>
            </div>
            <div class="form-group">
              <label for="newTenantTrialDays">試用天數</label>
              <input type="number" id="newTenantTrialDays" class="input" value="30" min="0" max="365" />
            </div>
          </div>
          <div class="form-group">
            <label for="newTenantStorageQuota">儲存配額 (MB)</label>
            <input type="number" id="newTenantStorageQuota" class="input" value="5120" min="100" />
          </div>
        </div>
        <div class="platform-admin-dialog-footer">
          <button class="btn btn-ghost dialog-cancel-btn">取消</button>
          <button class="btn btn-primary dialog-confirm-btn">建立</button>
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

    // 確認建立
    dialog.querySelector('.dialog-confirm-btn').addEventListener('click', async () => {
      const code = dialog.querySelector('#newTenantCode').value.trim();
      const name = dialog.querySelector('#newTenantName').value.trim();
      const plan = dialog.querySelector('#newTenantPlan').value;
      const trialDays = parseInt(dialog.querySelector('#newTenantTrialDays').value, 10);
      const storageQuota = parseInt(dialog.querySelector('#newTenantStorageQuota').value, 10);

      if (!code || !name) {
        alert('請填寫租戶代碼和名稱');
        return;
      }

      // 檢查代碼格式
      if (!/^[a-z0-9_-]+$/.test(code)) {
        alert('租戶代碼只能包含小寫英文字母、數字、底線和連字號');
        return;
      }

      const confirmBtn = dialog.querySelector('.dialog-confirm-btn');
      confirmBtn.disabled = true;
      confirmBtn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span> 建立中...`;

      try {
        await APIClient.post('/admin/tenants', {
          code,
          name,
          plan,
          trial_days: trialDays,
          storage_quota_mb: storageQuota,
        });

        closeDialog();
        loadTenants(windowEl);
        showToast('租戶已建立', 'check');
      } catch (error) {
        alert(`建立失敗：${error.message}`);
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = '建立';
      }
    });

    // 聚焦第一個輸入欄
    setTimeout(() => dialog.querySelector('#newTenantCode')?.focus(), 100);
  }

  /**
   * 開啟租戶詳情對話框
   * @param {HTMLElement} windowEl
   * @param {string} tenantId
   */
  async function openTenantDetails(windowEl, tenantId) {
    const dialog = document.createElement('div');
    dialog.className = 'platform-admin-dialog-overlay';
    dialog.innerHTML = `
      <div class="platform-admin-dialog platform-admin-dialog-wide">
        <div class="platform-admin-dialog-header">
          <h3>租戶詳情</h3>
          <button class="btn btn-ghost btn-sm dialog-close-btn">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="platform-admin-dialog-body">
          <div class="platform-admin-loading">
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
      // 同時載入租戶資訊和使用量
      const [tenant, usage] = await Promise.all([
        APIClient.get(`/admin/tenants/${tenantId}`),
        APIClient.get(`/admin/tenants/${tenantId}/usage`),
      ]);

      renderTenantDetailsDialog(dialog, windowEl, tenant, usage);
    } catch (error) {
      dialog.querySelector('.platform-admin-dialog-body').innerHTML = `
        <div class="platform-admin-error">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入失敗：${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * 渲染租戶詳情對話框內容
   * @param {HTMLElement} dialog
   * @param {HTMLElement} windowEl
   * @param {Object} tenant
   * @param {Object} usage
   */
  function renderTenantDetailsDialog(dialog, windowEl, tenant, usage) {
    const statusLabels = { 'active': '啟用', 'trial': '試用', 'suspended': '停用' };
    const planLabels = { 'trial': '試用版', 'basic': '基本版', 'pro': '專業版', 'enterprise': '企業版' };

    const storagePercentage = tenant.storage_quota_mb > 0
      ? Math.round((usage.storage_used_mb / tenant.storage_quota_mb) * 100)
      : 0;

    dialog.querySelector('.platform-admin-dialog-body').innerHTML = `
      <!-- Tab 導航 -->
      <div class="tenant-detail-tabs">
        <button class="tenant-detail-tab active" data-tab="info">
          <span class="icon">${getIcon('information-outline')}</span>
          <span>基本資訊</span>
        </button>
        <button class="tenant-detail-tab" data-tab="admins">
          <span class="icon">${getIcon('account-group')}</span>
          <span>管理員</span>
        </button>
        <button class="tenant-detail-tab" data-tab="linebot">
          <span class="icon">${getIcon('message-text')}</span>
          <span>Line Bot</span>
        </button>
        <button class="tenant-detail-tab" data-tab="telegrambot">
          <span class="icon">${getIcon('send')}</span>
          <span>Telegram Bot</span>
        </button>
      </div>

      <!-- Tab 內容：基本資訊 -->
      <div class="tenant-detail-tab-content active" id="tab-info">
        <div class="tenant-details-grid">
          <!-- 基本資訊 -->
          <div class="tenant-details-card">
            <h4>基本資訊</h4>
            <div class="tenant-details-row">
              <span class="label">代碼</span>
              <code class="platform-admin-code">${escapeHtml(tenant.code)}</code>
            </div>
            <div class="tenant-details-row">
              <span class="label">名稱</span>
              <span>${escapeHtml(tenant.name)}</span>
            </div>
            <div class="tenant-details-row">
              <span class="label">狀態</span>
              <span>${statusLabels[tenant.status] || tenant.status}</span>
            </div>
            <div class="tenant-details-row">
              <span class="label">方案</span>
              <span>${planLabels[tenant.plan] || tenant.plan}</span>
            </div>
            ${tenant.trial_ends_at ? `
            <div class="tenant-details-row">
              <span class="label">試用到期</span>
              <span>${formatDate(tenant.trial_ends_at)}</span>
            </div>
            ` : ''}
            <div class="tenant-details-row">
              <span class="label">建立時間</span>
              <span>${formatDate(tenant.created_at)}</span>
            </div>
          </div>

          <!-- 使用量統計 -->
          <div class="tenant-details-card">
            <h4>使用量統計</h4>
            <div class="tenant-details-stats">
              <div class="tenant-stat">
                <span class="tenant-stat-value">${usage.user_count || 0}</span>
                <span class="tenant-stat-label">使用者</span>
              </div>
              <div class="tenant-stat">
                <span class="tenant-stat-value">${usage.project_count || 0}</span>
                <span class="tenant-stat-label">專案</span>
              </div>
              <div class="tenant-stat">
                <span class="tenant-stat-value">${usage.knowledge_count || 0}</span>
                <span class="tenant-stat-label">知識庫</span>
              </div>
            </div>
            <div class="tenant-storage-bar-container">
              <div class="tenant-storage-label">儲存空間 (${storagePercentage}%)</div>
              <div class="tenant-storage-bar">
                <div class="tenant-storage-bar-fill" style="width: ${Math.min(storagePercentage, 100)}%"></div>
              </div>
              <div class="tenant-storage-text">${formatStorageSize(usage.storage_used_mb)} / ${formatStorageSize(tenant.storage_quota_mb)}</div>
            </div>
          </div>

          <!-- AI 使用量 -->
          <div class="tenant-details-card">
            <h4>AI 使用量</h4>
            <div class="tenant-details-stats">
              <div class="tenant-stat">
                <span class="tenant-stat-value">${usage.ai_calls_today || 0}</span>
                <span class="tenant-stat-label">今日呼叫</span>
              </div>
              <div class="tenant-stat">
                <span class="tenant-stat-value">${usage.ai_calls_this_month || 0}</span>
                <span class="tenant-stat-label">本月呼叫</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab 內容：管理員 -->
      <div class="tenant-detail-tab-content" id="tab-admins">
        <div class="tenant-admins-header">
          <p class="tenant-admins-hint">管理員可以管理此租戶內的使用者和設定</p>
          <button class="btn btn-primary btn-sm" id="addTenantAdminBtn">
            <span class="icon">${getIcon('plus')}</span>
            <span>新增管理員</span>
          </button>
        </div>
        <div class="tenant-admins-loading" id="tenant-admins-loading">
          <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
          <span>載入中...</span>
        </div>
        <div id="tenant-admins-content" style="display: none;"></div>
      </div>

      <!-- Tab 內容：Line Bot -->
      <div class="tenant-detail-tab-content" id="tab-linebot">
        <div class="tenant-linebot-loading" id="tenant-linebot-loading">
          <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
          <span>載入中...</span>
        </div>
        <div id="tenant-linebot-content" style="display: none;"></div>
      </div>

      <!-- Tab 內容：Telegram Bot -->
      <div class="tenant-detail-tab-content" id="tab-telegrambot">
        <div class="tenant-telegrambot-loading" id="tenant-telegrambot-loading">
          <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
          <span>載入中...</span>
        </div>
        <div id="tenant-telegrambot-content" style="display: none;"></div>
      </div>
    `;

    // 綁定 Tab 切換
    const tabs = dialog.querySelectorAll('.tenant-detail-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        // 切換 Tab 狀態
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        // 切換內容
        const tabContents = dialog.querySelectorAll('.tenant-detail-tab-content');
        tabContents.forEach(c => c.classList.remove('active'));
        const targetContent = dialog.querySelector(`#tab-${tab.dataset.tab}`);
        if (targetContent) {
          targetContent.classList.add('active');

          // 載入對應資料
          if (tab.dataset.tab === 'admins') {
            loadTenantAdmins(dialog, tenant.id);
          } else if (tab.dataset.tab === 'linebot') {
            loadTenantLineBotSettings(dialog, tenant.id);
          } else if (tab.dataset.tab === 'telegrambot') {
            loadTenantTelegramBotSettings(dialog, tenant.id);
          }
        }
      });
    });

    // 綁定新增管理員按鈕
    const addAdminBtn = dialog.querySelector('#addTenantAdminBtn');
    addAdminBtn?.addEventListener('click', () => openAddTenantAdminDialog(dialog, windowEl, tenant.id));

    // 添加操作按鈕
    const footer = document.createElement('div');
    footer.className = 'platform-admin-dialog-footer';
    footer.innerHTML = `
      <button class="btn btn-ghost dialog-close-btn">關閉</button>
    `;
    dialog.querySelector('.platform-admin-dialog').appendChild(footer);

    footer.querySelector('.dialog-close-btn').addEventListener('click', () => dialog.remove());
  }

  /**
   * 載入租戶管理員列表
   * @param {HTMLElement} dialog
   * @param {string} tenantId
   */
  async function loadTenantAdmins(dialog, tenantId) {
    const loading = dialog.querySelector('#tenant-admins-loading');
    const content = dialog.querySelector('#tenant-admins-content');

    loading.style.display = '';
    content.style.display = 'none';

    try {
      const admins = await APIClient.get(`/admin/tenants/${tenantId}/admins`);

      renderTenantAdmins(dialog, content, admins || [], tenantId);
      loading.style.display = 'none';
      content.style.display = '';
    } catch (error) {
      loading.innerHTML = `
        <div class="platform-admin-error">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入失敗：${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * 渲染租戶管理員列表
   * @param {HTMLElement} dialog
   * @param {HTMLElement} container
   * @param {Array} admins
   * @param {string} tenantId
   */
  function renderTenantAdmins(dialog, container, admins, tenantId) {
    if (admins.length === 0) {
      container.innerHTML = `
        <div class="tenant-admins-empty">
          <span class="icon">${getIcon('account-question')}</span>
          <span>尚無管理員，請新增一位管理員</span>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="tenant-admins-list">
        ${admins.map(admin => `
          <div class="tenant-admin-item" data-user-id="${admin.user_id}">
            <div class="tenant-admin-info">
              <span class="icon">${getIcon('account')}</span>
              <div class="tenant-admin-details">
                <span class="tenant-admin-name">${escapeHtml(admin.display_name || admin.username)}</span>
                <span class="tenant-admin-username">@${escapeHtml(admin.username)}</span>
              </div>
            </div>
            <div class="tenant-admin-actions">
              <button class="btn btn-ghost btn-sm admin-permissions-btn" data-user-id="${admin.user_id}" data-username="${escapeHtml(admin.display_name || admin.username)}" title="設定 App 權限">
                <span class="icon">${getIcon('shield-edit')}</span>
              </button>
              <button class="btn btn-ghost btn-sm remove-admin-btn" data-user-id="${admin.user_id}" data-username="${escapeHtml(admin.display_name || admin.username)}" title="移除管理員">
                <span class="icon">${getIcon('account-remove')}</span>
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    `;

    // 綁定權限設定按鈕
    container.querySelectorAll('.admin-permissions-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const userId = btn.dataset.userId;
        const username = btn.dataset.username;
        openAdminPermissionsDialog(dialog, tenantId, userId, username);
      });
    });

    // 綁定移除按鈕
    container.querySelectorAll('.remove-admin-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const userId = btn.dataset.userId;
        const username = btn.dataset.username;
        removeTenantAdmin(dialog, tenantId, userId, username);
      });
    });
  }

  /**
   * 開啟租戶管理員權限設定對話框
   * @param {HTMLElement} parentDialog - 父對話框（租戶詳情）
   * @param {string} tenantId
   * @param {string} userId
   * @param {string} username
   */
  async function openAdminPermissionsDialog(parentDialog, tenantId, userId, username) {
    const permDialog = document.createElement('div');
    permDialog.className = 'platform-admin-dialog-overlay';
    permDialog.innerHTML = `
      <div class="platform-admin-dialog" style="max-width: 500px;">
        <div class="platform-admin-dialog-header">
          <h3>
            <span class="icon">${getIcon('shield-edit')}</span>
            設定 App 權限
          </h3>
          <button class="btn btn-ghost btn-sm dialog-close-btn">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="platform-admin-dialog-body">
          <p class="admin-perm-target">管理員：<strong>${escapeHtml(username)}</strong></p>
          <div class="platform-admin-loading" id="perm-loading">
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
        APIClient.get(`/admin/users?tenant_id=${tenantId}`)
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
          控制此租戶管理員可以使用的應用程式功能（Web 介面和 Line Bot）
        </p>
        <div class="perm-app-list">
          ${Object.keys(defaultPerms.apps).filter(appId => appId !== 'platform-admin' && appId !== 'tenant-admin').map(appId => {
            // 租戶管理員的預設值是 true（除非明確禁止）
            const isEnabled = currentPerms[appId] !== false;
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
      footer.className = 'platform-admin-dialog-footer';
      footer.innerHTML = `
        <button class="btn btn-ghost dialog-cancel-btn">取消</button>
        <button class="btn btn-primary dialog-save-btn">
          <span class="icon">${getIcon('content-save')}</span>
          <span>儲存權限</span>
        </button>
      `;
      permDialog.querySelector('.platform-admin-dialog').appendChild(footer);

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
              // 租戶管理員預設是全開，所以只記錄被關閉的
              apps[appId] = checkbox.checked;
            }
          });

          await APIClient.request(`/admin/users/${userId}/permissions`, {
            method: 'PATCH',
            body: JSON.stringify({ apps })
          });

          closeDialog();
          showToast('權限設定已儲存', 'check');
          // 重新載入管理員列表
          loadTenantAdmins(parentDialog, tenantId);
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
        <div class="platform-admin-error">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入失敗：${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * 開啟新增租戶管理員對話框
   * @param {HTMLElement} parentDialog
   * @param {HTMLElement} windowEl
   * @param {string} tenantId
   */
  function openAddTenantAdminDialog(parentDialog, windowEl, tenantId) {
    const dialog = document.createElement('div');
    dialog.className = 'platform-admin-dialog-overlay';
    dialog.innerHTML = `
      <div class="platform-admin-dialog" style="max-width: 480px;">
        <div class="platform-admin-dialog-header">
          <h3>新增租戶管理員</h3>
          <button class="btn btn-ghost btn-sm dialog-close-btn">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="platform-admin-dialog-body">
          <!-- 模式選擇 -->
          <div class="admin-mode-tabs">
            <button class="admin-mode-tab active" data-mode="existing">
              <span class="icon">${getIcon('account-search')}</span>
              從現有使用者選擇
            </button>
            <button class="admin-mode-tab" data-mode="new">
              <span class="icon">${getIcon('account-plus')}</span>
              建立新帳號
            </button>
          </div>

          <!-- 模式一：從現有使用者選擇 -->
          <div class="admin-mode-content active" id="existingUserMode">
            <p class="form-hint" style="margin-bottom: 16px;">
              從此租戶的現有使用者中選擇，指派為管理員。
            </p>
            <div class="form-group">
              <label for="existingUserSelect">選擇使用者 *</label>
              <select id="existingUserSelect" class="input">
                <option value="">載入中...</option>
              </select>
            </div>
          </div>

          <!-- 模式二：建立新帳號 -->
          <div class="admin-mode-content" id="newAccountMode">
            <p class="form-hint" style="margin-bottom: 16px;">
              建立新的管理員帳號，該帳號將擁有管理此租戶使用者的權限。
            </p>
            <div class="form-group">
              <label for="adminUsername">使用者名稱 *</label>
              <input type="text" id="adminUsername" class="input" placeholder="登入用的帳號名稱" pattern="[a-zA-Z0-9_\\-]+" />
              <span class="form-hint">只能使用英文字母、數字、底線和連字號</span>
            </div>
            <div class="form-group">
              <label for="adminDisplayName">顯示名稱</label>
              <input type="text" id="adminDisplayName" class="input" placeholder="顯示在介面上的名稱" />
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" id="adminAutoGenPassword" checked />
                <span>自動產生臨時密碼</span>
              </label>
            </div>
            <div class="form-group" id="adminPasswordGroup" style="display: none;">
              <label for="adminPassword">初始密碼 *</label>
              <input type="password" id="adminPassword" class="input" placeholder="至少 8 個字元" minlength="8" />
            </div>
            <div class="form-group" id="adminMustChangeGroup" style="display: none;">
              <label class="checkbox-label">
                <input type="checkbox" id="adminMustChangePassword" checked />
                <span>首次登入需變更密碼</span>
              </label>
            </div>
          </div>
        </div>
        <div class="platform-admin-dialog-footer">
          <button class="btn btn-ghost dialog-cancel-btn">取消</button>
          <button class="btn btn-primary dialog-confirm-btn">指派為管理員</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    // 載入租戶使用者列表
    loadTenantUsersForSelect(dialog, tenantId);

    // 模式切換
    let currentMode = 'existing';
    const modeTabs = dialog.querySelectorAll('.admin-mode-tab');
    const existingUserMode = dialog.querySelector('#existingUserMode');
    const newAccountMode = dialog.querySelector('#newAccountMode');
    const confirmBtn = dialog.querySelector('.dialog-confirm-btn');

    modeTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const mode = tab.dataset.mode;
        currentMode = mode;

        // 更新 Tab 樣式
        modeTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        // 切換內容（使用 active class）
        if (mode === 'existing') {
          existingUserMode.classList.add('active');
          newAccountMode.classList.remove('active');
          confirmBtn.textContent = '指派為管理員';
        } else {
          existingUserMode.classList.remove('active');
          newAccountMode.classList.add('active');
          confirmBtn.textContent = '建立帳號';
        }
      });
    });

    // 自動產生密碼勾選框切換
    const autoGenCheckbox = dialog.querySelector('#adminAutoGenPassword');
    const passwordGroup = dialog.querySelector('#adminPasswordGroup');
    const mustChangeGroup = dialog.querySelector('#adminMustChangeGroup');

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
    confirmBtn.addEventListener('click', async () => {
      confirmBtn.disabled = true;
      const originalText = confirmBtn.textContent;
      confirmBtn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span> 處理中...`;

      try {
        let result;

        if (currentMode === 'existing') {
          // 模式一：從現有使用者選擇
          const userId = dialog.querySelector('#existingUserSelect').value;
          if (!userId) {
            alert('請選擇一位使用者');
            confirmBtn.disabled = false;
            confirmBtn.textContent = originalText;
            return;
          }

          result = await APIClient.post(`/admin/tenants/${tenantId}/admins`, {
            user_id: parseInt(userId),
            role: 'admin'
          });
        } else {
          // 模式二：建立新帳號
          const username = dialog.querySelector('#adminUsername').value.trim();
          const displayName = dialog.querySelector('#adminDisplayName').value.trim();
          const autoGenPassword = dialog.querySelector('#adminAutoGenPassword').checked;
          const password = autoGenPassword ? null : dialog.querySelector('#adminPassword').value;
          const mustChangePassword = autoGenPassword ? true : dialog.querySelector('#adminMustChangePassword').checked;

          // 驗證
          if (!username) {
            alert('請輸入使用者名稱');
            confirmBtn.disabled = false;
            confirmBtn.textContent = originalText;
            return;
          }
          if (!/^[a-zA-Z0-9_-]+$/.test(username)) {
            alert('使用者名稱只能包含英文字母、數字、底線和連字號');
            confirmBtn.disabled = false;
            confirmBtn.textContent = originalText;
            return;
          }
          if (!autoGenPassword && (!password || password.length < 8)) {
            alert('密碼至少需要 8 個字元');
            confirmBtn.disabled = false;
            confirmBtn.textContent = originalText;
            return;
          }

          const requestData = {
            username,
            display_name: displayName || username,
            must_change_password: mustChangePassword
          };
          if (password) {
            requestData.password = password;
          }

          result = await APIClient.post(`/admin/tenants/${tenantId}/admins`, requestData);
        }

        if (result.success === false) {
          alert(`操作失敗：${result.error}`);
          confirmBtn.disabled = false;
          confirmBtn.textContent = originalText;
          return;
        }

        closeDialog();
        loadTenantAdmins(parentDialog, tenantId);

        // 如果有臨時密碼，顯示給使用者
        if (result.temporary_password) {
          showTemporaryPasswordDialog(result.admin?.username || '', result.temporary_password);
        } else {
          showToast('管理員已新增', 'check');
        }
      } catch (error) {
        alert(`操作失敗：${error.message}`);
        confirmBtn.disabled = false;
        confirmBtn.textContent = originalText;
      }
    });
  }

  /**
   * 載入租戶使用者列表供選擇
   * @param {HTMLElement} dialog
   * @param {string} tenantId
   */
  async function loadTenantUsersForSelect(dialog, tenantId) {
    const select = dialog.querySelector('#existingUserSelect');

    try {
      const response = await APIClient.get(`/admin/tenants/${tenantId}/users`);
      const users = response.users || [];

      // 篩選出尚未是管理員的使用者
      const availableUsers = users.filter(u => !u.is_admin);

      if (availableUsers.length === 0) {
        select.innerHTML = '<option value="">沒有可選擇的使用者（所有使用者都已是管理員）</option>';
        return;
      }

      select.innerHTML = '<option value="">請選擇使用者...</option>' +
        availableUsers.map(u => `
          <option value="${u.id}">${escapeHtml(u.display_name || u.username)} (@${escapeHtml(u.username)})</option>
        `).join('');
    } catch (error) {
      select.innerHTML = `<option value="">載入失敗：${error.message}</option>`;
    }
  }

  /**
   * 顯示臨時密碼對話框
   * @param {string} username
   * @param {string} password
   */
  function showTemporaryPasswordDialog(username, password) {
    const dialog = document.createElement('div');
    dialog.className = 'platform-admin-dialog-overlay';
    dialog.innerHTML = `
      <div class="platform-admin-dialog" style="max-width: 400px;">
        <div class="platform-admin-dialog-header">
          <h3><span class="icon">${getIcon('check-circle')}</span> 管理員已建立</h3>
        </div>
        <div class="platform-admin-dialog-body">
          <p style="margin-bottom: var(--spacing-md);">管理員 <strong>${username}</strong> 的臨時密碼如下：</p>
          <div class="temp-password-box">
            <code id="tempPassword">${password}</code>
            <button class="btn btn-ghost btn-sm copy-password-btn" title="複製密碼">
              <span class="icon">${getIcon('content-copy')}</span>
            </button>
          </div>
          <p class="form-hint" style="margin-top: var(--spacing-sm);">
            <span class="icon">${getIcon('alert-circle')}</span>
            請將此密碼告知管理員，此密碼僅顯示一次，關閉後無法再查看。
          </p>
        </div>
        <div class="platform-admin-dialog-footer">
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
    const closeDialog = () => dialog.remove();
    dialog.querySelector('.dialog-close-btn').addEventListener('click', closeDialog);
  }

  /**
   * 移除租戶管理員
   * @param {HTMLElement} parentDialog - 父對話框（租戶詳情）
   * @param {string} tenantId
   * @param {number} userId
   * @param {string} username
   */
  async function removeTenantAdmin(parentDialog, tenantId, userId, username) {
    // 建立確認對話框
    const confirmDialog = document.createElement('div');
    confirmDialog.className = 'platform-admin-dialog-overlay';
    confirmDialog.innerHTML = `
      <div class="platform-admin-dialog" style="width: 400px;">
        <div class="platform-admin-dialog-header">
          <h3>移除管理員</h3>
          <button class="btn btn-icon btn-ghost close-btn">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="platform-admin-dialog-body">
          <p style="margin-bottom: var(--spacing-md); color: var(--text-primary);">
            確定要移除管理員「<strong>${username}</strong>」嗎？
          </p>

          <div class="platform-admin-warning">
            <span class="icon">${getIcon('alert')}</span>
            <span>移除後該帳號將無法管理此租戶。</span>
          </div>

          <div class="form-group" style="margin-top: var(--spacing-md);">
            <label class="checkbox-label">
              <input type="checkbox" id="deleteUserCheckbox" />
              <span>同時刪除使用者帳號</span>
            </label>
            <span class="form-hint" style="margin-left: 24px;">勾選此選項將完全刪除該使用者帳號，無法復原</span>
          </div>
        </div>
        <div class="platform-admin-dialog-footer">
          <button class="btn btn-ghost cancel-btn">取消</button>
          <button class="btn btn-danger confirm-btn">
            <span class="icon">${getIcon('account-remove')}</span>
            <span>移除</span>
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(confirmDialog);

    // 事件處理
    const closeBtn = confirmDialog.querySelector('.close-btn');
    const cancelBtn = confirmDialog.querySelector('.cancel-btn');
    const confirmBtn = confirmDialog.querySelector('.confirm-btn');
    const deleteUserCheckbox = confirmDialog.querySelector('#deleteUserCheckbox');

    const closeDialog = () => {
      confirmDialog.remove();
    };

    closeBtn.addEventListener('click', closeDialog);
    cancelBtn.addEventListener('click', closeDialog);
    confirmDialog.addEventListener('click', (e) => {
      if (e.target === confirmDialog) closeDialog();
    });

    confirmBtn.addEventListener('click', async () => {
      const deleteUser = deleteUserCheckbox.checked;

      confirmBtn.disabled = true;
      confirmBtn.innerHTML = `
        <span class="icon">${getIcon('loading', 'mdi-spin')}</span>
        <span>處理中...</span>
      `;

      try {
        const url = `/admin/tenants/${tenantId}/admins/${userId}${deleteUser ? '?delete_user=true' : ''}`;
        await APIClient.request(url, { method: 'DELETE' });

        closeDialog();
        loadTenantAdmins(parentDialog, tenantId);

        if (deleteUser) {
          showToast('管理員已移除，帳號已刪除', 'check');
        } else {
          showToast('管理員已移除', 'check');
        }
      } catch (error) {
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = `
          <span class="icon">${getIcon('account-remove')}</span>
          <span>移除</span>
        `;
        alert(`移除失敗：${error.message}`);
      }
    });
  }

  /**
   * 載入租戶 Line Bot 設定
   * @param {HTMLElement} dialog
   * @param {string} tenantId
   */
  async function loadTenantLineBotSettings(dialog, tenantId) {
    const loading = dialog.querySelector('#tenant-linebot-loading');
    const content = dialog.querySelector('#tenant-linebot-content');

    loading.style.display = '';
    content.style.display = 'none';

    try {
      const response = await APIClient.get(`/admin/tenants/${tenantId}/bot`);
      renderTenantLineBotSettings(dialog, content, response, tenantId);
      loading.style.display = 'none';
      content.style.display = '';
    } catch (error) {
      loading.innerHTML = `
        <div class="platform-admin-error">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入失敗：${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * 渲染租戶 Line Bot 設定
   * @param {HTMLElement} dialog
   * @param {HTMLElement} container
   * @param {Object} settings
   * @param {string} tenantId
   */
  function renderTenantLineBotSettings(dialog, container, settings, tenantId) {
    const isConfigured = settings.configured;

    container.innerHTML = `
      <div class="tenant-linebot-status ${isConfigured ? 'configured' : 'unconfigured'}">
        <span class="icon">${getIcon(isConfigured ? 'check-circle' : 'information-outline')}</span>
        <span>${isConfigured ? '已設定獨立 Line Bot' : '使用平台共用 Bot'}</span>
        ${isConfigured ? `<span class="linebot-channel-id">Channel ID: ${settings.channel_id}</span>` : ''}
      </div>

      <div class="tenant-linebot-form">
        <div class="form-group">
          <label for="tenantLineChannelId">Channel ID</label>
          <input type="text" id="tenantLineChannelId" class="input" placeholder="Line Channel ID" value="${settings.channel_id || ''}" />
          <span class="form-hint">從 Line Developers Console 取得</span>
        </div>
        <div class="form-group">
          <label for="tenantLineChannelSecret">Channel Secret</label>
          <input type="password" id="tenantLineChannelSecret" class="input" placeholder="留空表示不更新" />
          <span class="form-hint">用於驗證 Webhook 請求</span>
        </div>
        <div class="form-group">
          <label for="tenantLineAccessToken">Access Token</label>
          <input type="password" id="tenantLineAccessToken" class="input" placeholder="留空表示不更新" />
          <span class="form-hint">用於發送訊息給用戶</span>
        </div>

        <div class="tenant-linebot-actions">
          <button class="btn btn-secondary" id="testTenantLinebotBtn">
            <span class="icon">${getIcon('connection')}</span>
            <span>測試連線</span>
          </button>
          <button class="btn btn-primary" id="saveTenantLinebotBtn">
            <span class="icon">${getIcon('content-save')}</span>
            <span>儲存設定</span>
          </button>
          ${isConfigured ? `
          <button class="btn btn-text-danger" id="clearTenantLinebotBtn">
            <span class="icon">${getIcon('delete')}</span>
            <span>清除設定</span>
          </button>
          ` : ''}
        </div>
      </div>

      <div class="tenant-linebot-test-result" id="tenantLinebotTestResult" style="display: none;"></div>
    `;

    // 綁定測試按鈕
    container.querySelector('#testTenantLinebotBtn')?.addEventListener('click', async () => {
      const btn = container.querySelector('#testTenantLinebotBtn');
      const resultEl = container.querySelector('#tenantLinebotTestResult');

      btn.disabled = true;
      btn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span><span>測試中...</span>`;
      resultEl.style.display = 'none';

      try {
        const response = await APIClient.post(`/admin/tenants/${tenantId}/bot/test`);

        if (response.success) {
          resultEl.className = 'tenant-linebot-test-result success';
          resultEl.innerHTML = `
            <span class="icon">${getIcon('check-circle')}</span>
            <div>
              <strong>連線成功</strong>
              <span>Bot 名稱：${response.bot_info?.display_name || 'N/A'}</span>
            </div>
          `;
        } else {
          resultEl.className = 'tenant-linebot-test-result error';
          resultEl.innerHTML = `
            <span class="icon">${getIcon('alert-circle')}</span>
            <div><strong>連線失敗</strong><span>${response.error || '未知錯誤'}</span></div>
          `;
        }
        resultEl.style.display = '';
      } catch (error) {
        resultEl.className = 'tenant-linebot-test-result error';
        resultEl.innerHTML = `
          <span class="icon">${getIcon('alert-circle')}</span>
          <div><strong>測試失敗</strong><span>${error.message}</span></div>
        `;
        resultEl.style.display = '';
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<span class="icon">${getIcon('connection')}</span><span>測試連線</span>`;
      }
    });

    // 綁定儲存按鈕
    container.querySelector('#saveTenantLinebotBtn')?.addEventListener('click', async () => {
      const btn = container.querySelector('#saveTenantLinebotBtn');
      const channelId = container.querySelector('#tenantLineChannelId').value.trim();
      const channelSecret = container.querySelector('#tenantLineChannelSecret').value;
      const accessToken = container.querySelector('#tenantLineAccessToken').value;

      if (!channelId && !channelSecret && !accessToken) {
        alert('請至少填寫 Channel ID');
        return;
      }

      btn.disabled = true;
      btn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span><span>儲存中...</span>`;

      try {
        const data = {};
        if (channelId) data.channel_id = channelId;
        if (channelSecret) data.channel_secret = channelSecret;
        if (accessToken) data.access_token = accessToken;

        await APIClient.put(`/admin/tenants/${tenantId}/bot`, data);

        // 清空密碼欄位
        container.querySelector('#tenantLineChannelSecret').value = '';
        container.querySelector('#tenantLineAccessToken').value = '';

        // 重新載入
        loadTenantLineBotSettings(dialog, tenantId);
        showToast('Line Bot 設定已儲存', 'check');
      } catch (error) {
        alert(`儲存失敗：${error.message}`);
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<span class="icon">${getIcon('content-save')}</span><span>儲存設定</span>`;
      }
    });

    // 綁定清除按鈕
    container.querySelector('#clearTenantLinebotBtn')?.addEventListener('click', async () => {
      if (!confirm('確定要清除 Line Bot 設定嗎？\n清除後將使用平台共用 Bot。')) {
        return;
      }

      const btn = container.querySelector('#clearTenantLinebotBtn');
      btn.disabled = true;
      btn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span><span>清除中...</span>`;

      try {
        await APIClient.request(`/admin/tenants/${tenantId}/bot`, { method: 'DELETE' });
        loadTenantLineBotSettings(dialog, tenantId);
        showToast('Line Bot 設定已清除', 'check');
      } catch (error) {
        alert(`清除失敗：${error.message}`);
        btn.disabled = false;
        btn.innerHTML = `<span class="icon">${getIcon('delete')}</span><span>清除設定</span>`;
      }
    });
  }

  // ============================================================
  // Telegram Bot 設定（平台管理）
  // ============================================================

  async function loadTenantTelegramBotSettings(dialog, tenantId) {
    const loading = dialog.querySelector('#tenant-telegrambot-loading');
    const content = dialog.querySelector('#tenant-telegrambot-content');

    loading.style.display = '';
    content.style.display = 'none';

    try {
      const response = await APIClient.get(`/admin/tenants/${tenantId}/telegram-bot`);
      renderTenantTelegramBotSettings(dialog, content, response, tenantId);
      loading.style.display = 'none';
      content.style.display = '';
    } catch (error) {
      loading.innerHTML = `
        <div class="platform-admin-error">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入失敗：${error.message}</span>
        </div>
      `;
    }
  }

  function renderTenantTelegramBotSettings(dialog, container, settings, tenantId) {
    const isConfigured = settings.configured;

    container.innerHTML = `
      <div class="tenant-linebot-status ${isConfigured ? 'configured' : 'unconfigured'}">
        <span class="icon">${getIcon(isConfigured ? 'check-circle' : 'information-outline')}</span>
        <span>${isConfigured ? '已設定獨立 Telegram Bot' : '使用平台共用 Bot'}</span>
        ${isConfigured && settings.admin_chat_id ? `<span class="linebot-channel-id">Admin Chat ID: ${settings.admin_chat_id}</span>` : ''}
      </div>

      <div class="tenant-linebot-form">
        <div class="form-group">
          <label for="tenantTelegramBotToken">Bot Token</label>
          <input type="password" id="tenantTelegramBotToken" class="input" placeholder="留空表示不更新" />
          <span class="form-hint">從 @BotFather 取得</span>
        </div>
        <div class="form-group">
          <label for="tenantTelegramAdminChatId">Admin Chat ID</label>
          <input type="text" id="tenantTelegramAdminChatId" class="input" placeholder="${isConfigured ? '管理員 Chat ID' : '需先設定 Bot Token'}" value="${settings.admin_chat_id || ''}" ${isConfigured ? '' : 'disabled'} />
          <span class="form-hint">${isConfigured ? '用於接收系統通知' : '僅自訂 Bot 可設定 Admin Chat ID'}</span>
        </div>

        <div class="tenant-linebot-actions">
          <button class="btn btn-secondary" id="testTenantTelegramBtn">
            <span class="icon">${getIcon('connection')}</span>
            <span>測試連線</span>
          </button>
          <button class="btn btn-primary" id="saveTenantTelegramBtn">
            <span class="icon">${getIcon('content-save')}</span>
            <span>儲存設定</span>
          </button>
          ${isConfigured ? `
          <button class="btn btn-text-danger" id="clearTenantTelegramBtn">
            <span class="icon">${getIcon('delete')}</span>
            <span>清除設定</span>
          </button>
          ` : ''}
        </div>
      </div>

      <div class="tenant-linebot-test-result" id="tenantTelegramTestResult" style="display: none;"></div>
    `;

    // 動態啟用 Admin Chat ID：輸入 Bot Token 時啟用
    if (!isConfigured) {
      container.querySelector('#tenantTelegramBotToken')?.addEventListener('input', (e) => {
        const adminInput = container.querySelector('#tenantTelegramAdminChatId');
        if (e.target.value) {
          adminInput.disabled = false;
          adminInput.placeholder = '管理員 Chat ID';
        } else {
          adminInput.disabled = true;
          adminInput.placeholder = '需先設定 Bot Token';
          adminInput.value = '';
        }
      });
    }

    // 測試連線
    container.querySelector('#testTenantTelegramBtn')?.addEventListener('click', async () => {
      const btn = container.querySelector('#testTenantTelegramBtn');
      const resultEl = container.querySelector('#tenantTelegramTestResult');

      btn.disabled = true;
      btn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span><span>測試中...</span>`;
      resultEl.style.display = 'none';

      try {
        const response = await APIClient.post(`/admin/tenants/${tenantId}/telegram-bot/test`);

        if (response.success) {
          resultEl.className = 'tenant-linebot-test-result success';
          resultEl.innerHTML = `
            <span class="icon">${getIcon('check-circle')}</span>
            <div>
              <strong>連線成功</strong>
              <span>Bot：@${response.bot_info?.username || 'N/A'}（${response.bot_info?.first_name || ''}）</span>
            </div>
          `;
        } else {
          resultEl.className = 'tenant-linebot-test-result error';
          resultEl.innerHTML = `
            <span class="icon">${getIcon('alert-circle')}</span>
            <div><strong>連線失敗</strong><span>${response.error || '未知錯誤'}</span></div>
          `;
        }
        resultEl.style.display = '';
      } catch (error) {
        resultEl.className = 'tenant-linebot-test-result error';
        resultEl.innerHTML = `
          <span class="icon">${getIcon('alert-circle')}</span>
          <div><strong>測試失敗</strong><span>${error.message}</span></div>
        `;
        resultEl.style.display = '';
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<span class="icon">${getIcon('connection')}</span><span>測試連線</span>`;
      }
    });

    // 儲存設定
    container.querySelector('#saveTenantTelegramBtn')?.addEventListener('click', async () => {
      const btn = container.querySelector('#saveTenantTelegramBtn');
      const botToken = container.querySelector('#tenantTelegramBotToken').value;
      const adminChatId = container.querySelector('#tenantTelegramAdminChatId').value.trim();

      const isConfigured = !!container.querySelector('.tenant-linebot-status.configured');
      if (!botToken && !adminChatId) {
        alert('請至少填寫一個欄位');
        return;
      }
      if (!isConfigured && !botToken && adminChatId) {
        alert('需先設定 Bot Token 才能設定 Admin Chat ID');
        return;
      }

      btn.disabled = true;
      btn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span><span>儲存中...</span>`;

      try {
        const data = {};
        if (botToken) data.bot_token = botToken;
        if (adminChatId) data.admin_chat_id = adminChatId;

        await APIClient.put(`/admin/tenants/${tenantId}/telegram-bot`, data);

        container.querySelector('#tenantTelegramBotToken').value = '';
        loadTenantTelegramBotSettings(dialog, tenantId);
        showToast('Telegram Bot 設定已儲存', 'check');
      } catch (error) {
        alert(`儲存失敗：${error.message}`);
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<span class="icon">${getIcon('content-save')}</span><span>儲存設定</span>`;
      }
    });

    // 清除設定
    container.querySelector('#clearTenantTelegramBtn')?.addEventListener('click', async () => {
      if (!confirm('確定要清除 Telegram Bot 設定嗎？\n清除後將使用平台共用 Bot。')) {
        return;
      }

      const btn = container.querySelector('#clearTenantTelegramBtn');
      btn.disabled = true;
      btn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span><span>清除中...</span>`;

      try {
        await APIClient.request(`/admin/tenants/${tenantId}/telegram-bot`, { method: 'DELETE' });
        loadTenantTelegramBotSettings(dialog, tenantId);
        showToast('Telegram Bot 設定已清除', 'check');
      } catch (error) {
        alert(`清除失敗：${error.message}`);
        btn.disabled = false;
        btn.innerHTML = `<span class="icon">${getIcon('delete')}</span><span>清除設定</span>`;
      }
    });
  }

  /**
   * 停用租戶
   * @param {HTMLElement} windowEl
   * @param {string} tenantId
   */
  async function suspendTenant(windowEl, tenantId) {
    const tenant = tenantsCache.find(t => t.id === tenantId);
    if (!confirm(`確定要停用租戶「${tenant?.name || tenantId}」嗎？\n停用後該租戶的所有使用者將無法登入。`)) {
      return;
    }

    try {
      await APIClient.post(`/admin/tenants/${tenantId}/suspend`);
      showToast('租戶已停用', 'check');
      loadTenants(windowEl);
    } catch (error) {
      alert(`停用失敗：${error.message}`);
    }
  }

  /**
   * 啟用租戶
   * @param {HTMLElement} windowEl
   * @param {string} tenantId
   */
  async function activateTenant(windowEl, tenantId) {
    const tenant = tenantsCache.find(t => t.id === tenantId);
    if (!confirm(`確定要啟用租戶「${tenant?.name || tenantId}」嗎？`)) {
      return;
    }

    try {
      await APIClient.post(`/admin/tenants/${tenantId}/activate`);
      showToast('租戶已啟用', 'check');
      loadTenants(windowEl);
    } catch (error) {
      alert(`啟用失敗：${error.message}`);
    }
  }

  /**
   * 刪除租戶
   * @param {HTMLElement} windowEl
   * @param {string} tenantId
   * @param {string} tenantName
   * @param {string} tenantCode
   */
  async function deleteTenant(windowEl, tenantId, tenantName, tenantCode) {
    // 建立確認對話框
    const confirmDialog = document.createElement('div');
    confirmDialog.className = 'platform-admin-dialog-overlay';
    confirmDialog.innerHTML = `
      <div class="platform-admin-dialog" style="max-width: 480px;">
        <div class="platform-admin-dialog-header">
          <h3>
            <span class="icon" style="color: var(--color-error);">${getIcon('alert-circle')}</span>
            刪除租戶
          </h3>
          <button class="btn btn-ghost btn-sm dialog-close-btn">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="platform-admin-dialog-body">
          <div class="platform-admin-warning" style="margin-bottom: var(--spacing-md);">
            <span class="icon">${getIcon('alert')}</span>
            <span>此操作不可逆！將永久刪除租戶及其所有資料。</span>
          </div>
          <p style="margin-bottom: var(--spacing-md); color: var(--text-primary);">
            確定要刪除租戶「<strong>${escapeHtml(tenantName)}</strong>」(<code>${escapeHtml(tenantCode)}</code>) 嗎？
          </p>
          <p style="margin-bottom: var(--spacing-md); color: var(--text-secondary); font-size: 0.9em;">
            以下資料將被永久刪除：
          </p>
          <ul style="margin: 0 0 var(--spacing-md) var(--spacing-lg); color: var(--text-secondary); font-size: 0.9em;">
            <li>所有使用者帳號</li>
            <li>專案及相關資料</li>
            <li>知識庫文件</li>
            <li>AI 設定和對話記錄</li>
            <li>Line 群組和使用者綁定</li>
            <li>庫存和廠商資料</li>
          </ul>
          <div class="form-group">
            <label for="confirmTenantCode">請輸入租戶代碼 <code>${escapeHtml(tenantCode)}</code> 確認刪除：</label>
            <input type="text" id="confirmTenantCode" class="input" placeholder="輸入租戶代碼" autocomplete="off" />
          </div>
        </div>
        <div class="platform-admin-dialog-footer">
          <button class="btn btn-ghost dialog-cancel-btn">取消</button>
          <button class="btn btn-danger dialog-confirm-btn" disabled>
            <span class="icon">${getIcon('delete')}</span>
            <span>永久刪除</span>
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(confirmDialog);

    const confirmInput = confirmDialog.querySelector('#confirmTenantCode');
    const confirmBtn = confirmDialog.querySelector('.dialog-confirm-btn');

    // 只有輸入正確的租戶代碼才能刪除
    confirmInput.addEventListener('input', () => {
      confirmBtn.disabled = confirmInput.value !== tenantCode;
    });

    // 關閉對話框
    const closeDialog = () => confirmDialog.remove();
    confirmDialog.querySelector('.dialog-close-btn').addEventListener('click', closeDialog);
    confirmDialog.querySelector('.dialog-cancel-btn').addEventListener('click', closeDialog);
    confirmDialog.addEventListener('click', (e) => {
      if (e.target === confirmDialog) closeDialog();
    });

    // 確認刪除
    confirmBtn.addEventListener('click', async () => {
      if (confirmInput.value !== tenantCode) {
        return;
      }

      confirmBtn.disabled = true;
      confirmBtn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span><span>刪除中...</span>`;

      try {
        await APIClient.request(`/admin/tenants/${tenantId}`, { method: 'DELETE' });
        closeDialog();
        showToast('租戶已刪除', 'check');
        loadTenants(windowEl);
      } catch (error) {
        alert(`刪除失敗：${error.message}`);
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = `<span class="icon">${getIcon('delete')}</span><span>永久刪除</span>`;
      }
    });

    // 聚焦輸入欄位
    setTimeout(() => confirmInput.focus(), 100);
  }

  // ============================================================
  // Line 群組管理
  // ============================================================

  /**
   * 更新租戶篩選器選項
   * @param {HTMLElement} windowEl
   */
  function updateTenantFilterOptions(windowEl) {
    const filter = windowEl.querySelector('#lineGroupTenantFilter');
    if (!filter) return;

    const currentValue = filter.value;
    filter.innerHTML = '<option value="">全部租戶</option>';

    tenantsCache.forEach(tenant => {
      const option = document.createElement('option');
      option.value = tenant.id;
      option.textContent = `${tenant.name} (${tenant.code})`;
      filter.appendChild(option);
    });

    filter.value = currentValue;
  }

  /**
   * 載入 Line 群組列表
   * @param {HTMLElement} windowEl
   */
  async function loadLineGroups(windowEl) {
    const loading = windowEl.querySelector('#line-groups-loading');
    const content = windowEl.querySelector('#line-groups-content');

    loading.style.display = '';
    content.style.display = 'none';

    try {
      const tenantFilter = windowEl.querySelector('#lineGroupTenantFilter')?.value || '';

      const params = new URLSearchParams();
      if (tenantFilter) params.append('tenant_id', tenantFilter);

      const queryString = params.toString();
      const url = `/admin/tenants/bot-groups${queryString ? '?' + queryString : ''}`;

      const data = await APIClient.get(url);
      lineGroupsCache = data.items || [];

      renderLineGroups(windowEl, content, lineGroupsCache);
      loading.style.display = 'none';
      content.style.display = '';
    } catch (error) {
      loading.innerHTML = `
        <div class="platform-admin-error">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入失敗：${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * 渲染 Line 群組列表
   * @param {HTMLElement} windowEl
   * @param {HTMLElement} container
   * @param {Array} groups
   */
  function renderLineGroups(windowEl, container, groups) {
    if (groups.length === 0) {
      container.innerHTML = `
        <div class="platform-admin-empty">
          <span class="icon">${getIcon('message-off')}</span>
          <span>沒有符合條件的 Line 群組</span>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="platform-admin-table-container">
        <table class="platform-admin-table">
          <thead>
            <tr>
              <th>群組名稱</th>
              <th>目前租戶</th>
              <th>成員數</th>
              <th>最後活動</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            ${groups.map(group => `
              <tr data-group-id="${group.id}">
                <td>${escapeHtml(group.group_name || '未命名群組')}</td>
                <td>
                  <span class="platform-admin-tenant-tag">${escapeHtml(group.tenant_name || '-')}</span>
                </td>
                <td>${group.member_count || '-'}</td>
                <td>${group.updated_at ? formatDate(group.updated_at) : '-'}</td>
                <td class="platform-admin-actions">
                  <button class="btn btn-ghost btn-sm change-tenant-btn" data-group-id="${group.id}" data-current-tenant="${group.tenant_id}" title="變更租戶">
                    <span class="icon">${getIcon('swap-horizontal')}</span>
                  </button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;

    // 綁定變更租戶按鈕
    container.querySelectorAll('.change-tenant-btn').forEach(btn => {
      btn.addEventListener('click', () => openChangeTenantDialog(windowEl, btn.dataset.groupId, btn.dataset.currentTenant));
    });
  }

  /**
   * 開啟變更租戶對話框
   * @param {HTMLElement} windowEl
   * @param {string} groupId
   * @param {string} currentTenantId
   */
  function openChangeTenantDialog(windowEl, groupId, currentTenantId) {
    const group = lineGroupsCache.find(g => g.id === groupId);
    const currentTenant = tenantsCache.find(t => t.id === currentTenantId);

    const dialog = document.createElement('div');
    dialog.className = 'platform-admin-dialog-overlay';
    dialog.innerHTML = `
      <div class="platform-admin-dialog">
        <div class="platform-admin-dialog-header">
          <h3>變更群組租戶</h3>
          <button class="btn btn-ghost btn-sm dialog-close-btn">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="platform-admin-dialog-body">
          <div class="platform-admin-warning">
            <span class="icon">${getIcon('alert')}</span>
            <span>變更租戶會影響該群組的資料隔離。請確認操作正確。</span>
          </div>
          <div class="form-group">
            <label>群組名稱</label>
            <div class="form-static">${escapeHtml(group?.group_name || '未命名群組')}</div>
          </div>
          <div class="form-group">
            <label>目前租戶</label>
            <div class="form-static">${escapeHtml(currentTenant?.name || '-')} (${escapeHtml(currentTenant?.code || '-')})</div>
          </div>
          <div class="form-group">
            <label for="newGroupTenant">目標租戶 *</label>
            <select id="newGroupTenant" class="input">
              <option value="">請選擇租戶</option>
              ${tenantsCache.filter(t => t.id !== currentTenantId && t.status === 'active').map(t => `
                <option value="${t.id}">${escapeHtml(t.name)} (${escapeHtml(t.code)})</option>
              `).join('')}
            </select>
          </div>
        </div>
        <div class="platform-admin-dialog-footer">
          <button class="btn btn-ghost dialog-cancel-btn">取消</button>
          <button class="btn btn-primary dialog-confirm-btn">確認變更</button>
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

    // 確認變更
    dialog.querySelector('.dialog-confirm-btn').addEventListener('click', async () => {
      const newTenantId = dialog.querySelector('#newGroupTenant').value;

      if (!newTenantId) {
        alert('請選擇目標租戶');
        return;
      }

      const newTenant = tenantsCache.find(t => t.id === newTenantId);
      if (!confirm(`確定要將群組移動到「${newTenant?.name}」嗎？`)) {
        return;
      }

      const confirmBtn = dialog.querySelector('.dialog-confirm-btn');
      confirmBtn.disabled = true;
      confirmBtn.innerHTML = `<span class="icon">${getIcon('loading', 'mdi-spin')}</span> 變更中...`;

      try {
        await APIClient.request(`/admin/tenants/bot-groups/${groupId}/tenant`, {
          method: 'PATCH',
          body: JSON.stringify({ new_tenant_id: newTenantId }),
        });

        closeDialog();
        loadLineGroups(windowEl);
        showToast('群組租戶已變更', 'check');
      } catch (error) {
        alert(`變更失敗：${error.message}`);
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = '確認變更';
      }
    });
  }

  // ============================================================
  // 工具函數
  // ============================================================

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
   * 格式化日期
   * @param {string} dateStr
   * @returns {string}
   */
  function formatDate(dateStr) {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('zh-TW');
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
   * 開啟平台管理應用程式
   */
  function open() {
    // 檢查權限
    if (!isPlatformAdmin()) {
      showToast('需要平台管理員權限', 'alert');
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
      title: '平台管理',
      appId: APP_ID,
      icon: 'shield-crown',
      width: 900,
      height: 600,
      content: getWindowContent(),
      onInit: (windowEl, windowId) => {
        init(windowEl);
      },
      onClose: (windowId) => {
        currentWindowId = null;
        tenantsCache = [];
        lineGroupsCache = [];
      }
    });

    return currentWindowId;
  }

  // 公開 API
  return {
    open,
    isPlatformAdmin
  };
})();
