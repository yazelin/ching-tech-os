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
    `;

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
      const url = `/admin/tenants/line-groups${queryString ? '?' + queryString : ''}`;

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
        await APIClient.request(`/admin/tenants/line-groups/${groupId}/tenant`, {
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
