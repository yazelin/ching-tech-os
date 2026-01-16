/**
 * ChingTech OS - Vendor Management Module
 * 廠商管理模組 - 支援廠商 CRUD 和 ERP 編號對照
 */

const VendorManagementModule = (function() {
  'use strict';

  const API_BASE = '/api/vendors';

  // State
  let windowId = null;
  let vendorList = [];
  let selectedVendor = null;
  let isEditing = false;
  let editingData = null;
  let listWidth = 320;

  // Filters
  let searchQuery = '';
  let filterActive = true;

  /**
   * Check if current view is mobile
   */
  function isMobileView() {
    return window.innerWidth <= 768;
  }

  /**
   * Show mobile detail view
   */
  function showMobileDetail() {
    const windowEl = document.getElementById(windowId);
    if (windowEl && isMobileView()) {
      windowEl.querySelector('.vnd-container')?.classList.add('showing-detail');
    }
  }

  /**
   * Hide mobile detail view (back to list)
   */
  function hideMobileDetail() {
    const windowEl = document.getElementById(windowId);
    if (windowEl) {
      windowEl.querySelector('.vnd-container')?.classList.remove('showing-detail');
    }
  }

  /**
   * Get authentication token
   */
  function getToken() {
    return LoginModule?.getToken?.() || localStorage.getItem('auth_token') || '';
  }

  /**
   * Make API request
   */
  async function apiRequest(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
    const token = getToken();
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    if (response.status === 204) return null;
    return response.json();
  }

  /**
   * Open vendor management window
   */
  function open() {
    const existing = WindowModule.getWindowByAppId('vendor-management');
    if (existing) {
      WindowModule.focusWindow(existing.windowId);
      if (!existing.minimized) return;
      WindowModule.restoreWindow(existing.windowId);
      return;
    }

    windowId = WindowModule.createWindow({
      title: '廠商管理',
      appId: 'vendor-management',
      icon: 'store',
      width: 1100,
      height: 700,
      content: renderContent(),
      onClose: handleClose,
      onInit: handleInit,
    });
  }

  /**
   * Close window
   */
  function close() {
    if (windowId) {
      WindowModule.closeWindow(windowId);
    }
  }

  /**
   * Handle window close
   */
  function handleClose() {
    windowId = null;
    vendorList = [];
    selectedVendor = null;
    isEditing = false;
    editingData = null;
  }

  /**
   * Handle window init
   */
  function handleInit(windowEl, wId) {
    windowId = wId;
    bindEvents(windowEl);
    loadVendors();
  }

  /**
   * Render main content
   */
  function renderContent() {
    return `
      <div class="vnd-container">
        <div class="vnd-toolbar">
          <div class="vnd-search-container">
            <span class="vnd-search-icon">
              <span class="icon">${getIcon('search')}</span>
            </span>
            <input type="text" class="vnd-search-input" id="vndSearchInput" placeholder="搜尋廠商...">
            <button class="vnd-search-clear" id="vndSearchClear" style="display: none;">
              <span class="icon">${getIcon('close')}</span>
            </button>
          </div>
          <div class="vnd-filters">
            <label class="vnd-filter-checkbox">
              <input type="checkbox" id="vndFilterActive" checked>
              <span>僅顯示啟用</span>
            </label>
          </div>
          <div class="vnd-toolbar-actions">
            <button class="vnd-action-btn" id="vndBtnRefresh" title="重新載入">
              <span class="icon">${getIcon('refresh')}</span>
            </button>
            <button class="vnd-action-btn primary" id="vndBtnNew" title="新增廠商">
              <span class="icon">${getIcon('plus')}</span>
              <span>新增</span>
            </button>
          </div>
        </div>

        <div class="vnd-main">
          <div class="vnd-list-panel" id="vndListPanel">
            <div class="vnd-list-header">
              <span>廠商列表</span>
              <span class="vnd-list-count" id="vndListCount">0 筆</span>
            </div>
            <div class="vnd-list" id="vndList">
              <div class="vnd-loading">
                <span class="icon spinning">${getIcon('refresh')}</span>
                <span>載入中...</span>
              </div>
            </div>
          </div>

          <div class="vnd-resizer" id="vndResizer"></div>

          <div class="vnd-content-panel" id="vndContentPanel">
            <div class="vnd-content-empty" id="vndContentEmpty">
              <span class="icon">${getIcon('store')}</span>
              <p>選擇一個廠商來查看詳情</p>
              <p>或點擊「新增」建立新廠商</p>
            </div>
            <div class="vnd-content-view" id="vndContentView" style="display: none;"></div>
            <div class="vnd-editor" id="vndEditor" style="display: none;"></div>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Bind events
   */
  function bindEvents(windowEl) {
    // Search
    const searchInput = windowEl.querySelector('#vndSearchInput');
    const searchClear = windowEl.querySelector('#vndSearchClear');
    let searchTimeout;

    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value;
      searchClear.style.display = searchQuery ? 'flex' : 'none';
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => loadVendors(), 300);
    });

    searchClear.addEventListener('click', () => {
      searchInput.value = '';
      searchQuery = '';
      searchClear.style.display = 'none';
      loadVendors();
    });

    // Filter
    windowEl.querySelector('#vndFilterActive').addEventListener('change', (e) => {
      filterActive = e.target.checked;
      loadVendors();
    });

    // Toolbar actions
    windowEl.querySelector('#vndBtnRefresh').addEventListener('click', () => {
      loadVendors();
    });
    windowEl.querySelector('#vndBtnNew').addEventListener('click', startNewVendor);

    // Resizer
    setupResizer(windowEl);
  }

  /**
   * Setup resizer for list panel
   */
  function setupResizer(windowEl) {
    const resizer = windowEl.querySelector('#vndResizer');
    const listPanel = windowEl.querySelector('#vndListPanel');
    let isResizing = false;
    let startX = 0;
    let startWidth = 0;

    resizer.addEventListener('mousedown', (e) => {
      isResizing = true;
      startX = e.clientX;
      startWidth = listPanel.offsetWidth;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', (e) => {
      if (!isResizing) return;
      const diff = e.clientX - startX;
      const newWidth = Math.max(220, Math.min(500, startWidth + diff));
      listPanel.style.width = `${newWidth}px`;
      listWidth = newWidth;
    });

    document.addEventListener('mouseup', () => {
      if (isResizing) {
        isResizing = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    });
  }

  // ============================================
  // Data Loading
  // ============================================

  async function loadVendors() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const listEl = windowEl.querySelector('#vndList');
    listEl.innerHTML = `
      <div class="vnd-loading">
        <span class="icon spinning">${getIcon('refresh')}</span>
        <span>載入中...</span>
      </div>
    `;

    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append('q', searchQuery);
      params.append('active', filterActive.toString());

      const response = await apiRequest(`?${params.toString()}`);
      vendorList = response.items || [];

      renderList(windowEl);
    } catch (error) {
      listEl.innerHTML = `
        <div class="vnd-error">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入失敗：${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * Render vendor list
   */
  function renderList(windowEl) {
    const listEl = windowEl.querySelector('#vndList');
    const countEl = windowEl.querySelector('#vndListCount');

    countEl.textContent = `${vendorList.length} 筆`;

    if (vendorList.length === 0) {
      listEl.innerHTML = `
        <div class="vnd-empty">
          <span class="icon">${getIcon('store-off')}</span>
          <span>${searchQuery ? '沒有符合條件的廠商' : '尚無廠商'}</span>
        </div>
      `;
      return;
    }

    listEl.innerHTML = vendorList.map(vendor => `
      <div class="vnd-list-item ${selectedVendor?.id === vendor.id ? 'selected' : ''} ${!vendor.is_active ? 'inactive' : ''}" data-id="${vendor.id}">
        <div class="vnd-list-item-main">
          <div class="vnd-list-item-name">${escapeHtml(vendor.name)}</div>
          ${vendor.short_name ? `<div class="vnd-list-item-short">${escapeHtml(vendor.short_name)}</div>` : ''}
        </div>
        <div class="vnd-list-item-info">
          ${vendor.erp_code ? `<div class="vnd-list-item-erp">${escapeHtml(vendor.erp_code)}</div>` : ''}
          ${!vendor.is_active ? `<div class="vnd-list-item-status">停用</div>` : ''}
        </div>
      </div>
    `).join('');

    // Bind click events
    listEl.querySelectorAll('.vnd-list-item').forEach(el => {
      el.addEventListener('click', () => selectVendor(el.dataset.id));
    });
  }

  /**
   * Select a vendor
   */
  async function selectVendor(vendorId) {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    // Update list selection
    windowEl.querySelectorAll('.vnd-list-item').forEach(el => {
      el.classList.toggle('selected', el.dataset.id === vendorId);
    });

    try {
      selectedVendor = await apiRequest(`/${vendorId}`);
      isEditing = false;
      editingData = null;
      showMobileDetail();
      renderContentView(windowEl);
    } catch (error) {
      NotificationModule.show({ title: '載入失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  /**
   * Render content view (vendor detail)
   */
  function renderContentView(windowEl) {
    const emptyEl = windowEl.querySelector('#vndContentEmpty');
    const viewEl = windowEl.querySelector('#vndContentView');
    const editorEl = windowEl.querySelector('#vndEditor');

    emptyEl.style.display = 'none';
    viewEl.style.display = 'flex';
    editorEl.style.display = 'none';

    const vendor = selectedVendor;
    viewEl.innerHTML = `
      <div class="vnd-detail-header">
        <button class="vnd-back-btn" id="vndBackBtn">
          <span class="icon">${getIcon('arrow-left')}</span>
        </button>
        <div class="vnd-detail-title">
          <h2>${escapeHtml(vendor.name)}</h2>
          ${vendor.short_name ? `<span class="vnd-detail-short">${escapeHtml(vendor.short_name)}</span>` : ''}
        </div>
        <div class="vnd-detail-actions">
          <button class="vnd-action-btn" id="vndBtnEdit" title="編輯">
            <span class="icon">${getIcon('pencil')}</span>
          </button>
          ${vendor.is_active ? `
            <button class="vnd-action-btn danger" id="vndBtnDeactivate" title="停用">
              <span class="icon">${getIcon('store-off')}</span>
            </button>
          ` : `
            <button class="vnd-action-btn success" id="vndBtnActivate" title="啟用">
              <span class="icon">${getIcon('store-check')}</span>
            </button>
          `}
        </div>
      </div>

      <div class="vnd-detail-body">
        <div class="vnd-detail-section">
          <h3>基本資訊</h3>
          <div class="vnd-detail-grid">
            <div class="vnd-detail-item">
              <label>ERP 編號</label>
              <span class="vnd-erp-code">${vendor.erp_code || '-'}</span>
            </div>
            <div class="vnd-detail-item">
              <label>統一編號</label>
              <span>${vendor.tax_id || '-'}</span>
            </div>
            <div class="vnd-detail-item">
              <label>聯絡人</label>
              <span>${vendor.contact_person || '-'}</span>
            </div>
            <div class="vnd-detail-item">
              <label>電話</label>
              <span>${vendor.phone || '-'}</span>
            </div>
            <div class="vnd-detail-item">
              <label>傳真</label>
              <span>${vendor.fax || '-'}</span>
            </div>
            <div class="vnd-detail-item">
              <label>電子郵件</label>
              <span>${vendor.email || '-'}</span>
            </div>
            <div class="vnd-detail-item full-width">
              <label>地址</label>
              <span>${vendor.address || '-'}</span>
            </div>
            <div class="vnd-detail-item full-width">
              <label>付款條件</label>
              <span>${vendor.payment_terms || '-'}</span>
            </div>
          </div>
        </div>

        ${vendor.notes ? `
        <div class="vnd-detail-section">
          <h3>備註</h3>
          <div class="vnd-detail-notes">
            <p>${escapeHtml(vendor.notes)}</p>
          </div>
        </div>
        ` : ''}

        <div class="vnd-detail-section">
          <h3>系統資訊</h3>
          <div class="vnd-detail-grid">
            <div class="vnd-detail-item">
              <label>狀態</label>
              <span class="vnd-status ${vendor.is_active ? 'active' : 'inactive'}">
                ${vendor.is_active ? '啟用中' : '已停用'}
              </span>
            </div>
            <div class="vnd-detail-item">
              <label>建立時間</label>
              <span>${formatDateTime(vendor.created_at)}</span>
            </div>
            <div class="vnd-detail-item">
              <label>更新時間</label>
              <span>${formatDateTime(vendor.updated_at)}</span>
            </div>
          </div>
        </div>
      </div>
    `;

    // Bind events
    viewEl.querySelector('#vndBackBtn').addEventListener('click', () => {
      hideMobileDetail();
    });
    viewEl.querySelector('#vndBtnEdit').addEventListener('click', startEditVendor);

    const deactivateBtn = viewEl.querySelector('#vndBtnDeactivate');
    if (deactivateBtn) {
      deactivateBtn.addEventListener('click', confirmDeactivateVendor);
    }

    const activateBtn = viewEl.querySelector('#vndBtnActivate');
    if (activateBtn) {
      activateBtn.addEventListener('click', confirmActivateVendor);
    }
  }

  // ============================================
  // Vendor CRUD
  // ============================================

  function startNewVendor() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    selectedVendor = null;
    isEditing = true;
    editingData = {
      erp_code: '',
      name: '',
      short_name: '',
      contact_person: '',
      phone: '',
      fax: '',
      email: '',
      address: '',
      tax_id: '',
      payment_terms: '',
      notes: '',
    };

    renderEditor(windowEl);
  }

  function startEditVendor() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl || !selectedVendor) return;

    isEditing = true;
    editingData = {
      erp_code: selectedVendor.erp_code || '',
      name: selectedVendor.name,
      short_name: selectedVendor.short_name || '',
      contact_person: selectedVendor.contact_person || '',
      phone: selectedVendor.phone || '',
      fax: selectedVendor.fax || '',
      email: selectedVendor.email || '',
      address: selectedVendor.address || '',
      tax_id: selectedVendor.tax_id || '',
      payment_terms: selectedVendor.payment_terms || '',
      notes: selectedVendor.notes || '',
    };

    renderEditor(windowEl);
  }

  function renderEditor(windowEl) {
    const emptyEl = windowEl.querySelector('#vndContentEmpty');
    const viewEl = windowEl.querySelector('#vndContentView');
    const editorEl = windowEl.querySelector('#vndEditor');

    emptyEl.style.display = 'none';
    viewEl.style.display = 'none';
    editorEl.style.display = 'flex';

    const isNew = !selectedVendor;
    editorEl.innerHTML = `
      <div class="vnd-editor-header">
        <h2>${isNew ? '新增廠商' : '編輯廠商'}</h2>
      </div>
      <div class="vnd-editor-body">
        <div class="vnd-form-row">
          <div class="vnd-form-group">
            <label>ERP 編號</label>
            <input type="text" id="vndEditErpCode" value="${escapeHtml(editingData.erp_code)}" placeholder="與 ERP 系統對照用">
          </div>
          <div class="vnd-form-group">
            <label>統一編號</label>
            <input type="text" id="vndEditTaxId" value="${escapeHtml(editingData.tax_id)}" placeholder="8 位數字">
          </div>
        </div>
        <div class="vnd-form-row">
          <div class="vnd-form-group">
            <label>廠商名稱 *</label>
            <input type="text" id="vndEditName" value="${escapeHtml(editingData.name)}" required>
          </div>
          <div class="vnd-form-group">
            <label>簡稱</label>
            <input type="text" id="vndEditShortName" value="${escapeHtml(editingData.short_name)}">
          </div>
        </div>
        <div class="vnd-form-row">
          <div class="vnd-form-group">
            <label>聯絡人</label>
            <input type="text" id="vndEditContact" value="${escapeHtml(editingData.contact_person)}">
          </div>
          <div class="vnd-form-group">
            <label>電話</label>
            <input type="text" id="vndEditPhone" value="${escapeHtml(editingData.phone)}">
          </div>
        </div>
        <div class="vnd-form-row">
          <div class="vnd-form-group">
            <label>傳真</label>
            <input type="text" id="vndEditFax" value="${escapeHtml(editingData.fax)}">
          </div>
          <div class="vnd-form-group">
            <label>電子郵件</label>
            <input type="email" id="vndEditEmail" value="${escapeHtml(editingData.email)}">
          </div>
        </div>
        <div class="vnd-form-group">
          <label>地址</label>
          <input type="text" id="vndEditAddress" value="${escapeHtml(editingData.address)}">
        </div>
        <div class="vnd-form-group">
          <label>付款條件</label>
          <input type="text" id="vndEditPaymentTerms" value="${escapeHtml(editingData.payment_terms)}" placeholder="如：月結 30 天">
        </div>
        <div class="vnd-form-group">
          <label>備註</label>
          <textarea id="vndEditNotes" rows="3">${escapeHtml(editingData.notes)}</textarea>
        </div>
      </div>
      <div class="vnd-editor-footer">
        <button class="vnd-btn" id="vndEditCancel">取消</button>
        <button class="vnd-btn primary" id="vndEditSave">${isNew ? '建立' : '儲存'}</button>
      </div>
    `;

    editorEl.querySelector('#vndEditCancel').addEventListener('click', cancelEdit);
    editorEl.querySelector('#vndEditSave').addEventListener('click', saveVendor);
  }

  function cancelEdit() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    isEditing = false;
    editingData = null;

    if (selectedVendor) {
      renderContentView(windowEl);
    } else {
      windowEl.querySelector('#vndContentEmpty').style.display = 'flex';
      windowEl.querySelector('#vndContentView').style.display = 'none';
      windowEl.querySelector('#vndEditor').style.display = 'none';
    }
  }

  async function saveVendor() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const name = windowEl.querySelector('#vndEditName').value.trim();
    if (!name) {
      NotificationModule.show({ title: '提醒', message: '請輸入廠商名稱', icon: 'alert' });
      return;
    }

    const data = {
      erp_code: windowEl.querySelector('#vndEditErpCode').value.trim() || null,
      name,
      short_name: windowEl.querySelector('#vndEditShortName').value.trim() || null,
      contact_person: windowEl.querySelector('#vndEditContact').value.trim() || null,
      phone: windowEl.querySelector('#vndEditPhone').value.trim() || null,
      fax: windowEl.querySelector('#vndEditFax').value.trim() || null,
      email: windowEl.querySelector('#vndEditEmail').value.trim() || null,
      address: windowEl.querySelector('#vndEditAddress').value.trim() || null,
      tax_id: windowEl.querySelector('#vndEditTaxId').value.trim() || null,
      payment_terms: windowEl.querySelector('#vndEditPaymentTerms').value.trim() || null,
      notes: windowEl.querySelector('#vndEditNotes').value.trim() || null,
    };

    try {
      if (selectedVendor) {
        await apiRequest(`/${selectedVendor.id}`, {
          method: 'PUT',
          body: JSON.stringify(data),
        });
        NotificationModule.show({ title: '成功', message: '廠商已更新', icon: 'check-circle' });
      } else {
        const newVendor = await apiRequest('', {
          method: 'POST',
          body: JSON.stringify(data),
        });
        selectedVendor = newVendor;
        NotificationModule.show({ title: '成功', message: '廠商已建立', icon: 'check-circle' });
      }

      isEditing = false;
      editingData = null;
      await loadVendors();
      if (selectedVendor) {
        selectedVendor = await apiRequest(`/${selectedVendor.id}`);
        renderContentView(windowEl);
      }
    } catch (error) {
      NotificationModule.show({ title: '儲存失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  async function confirmDeactivateVendor() {
    if (!selectedVendor) return;
    if (!confirm(`確定要停用廠商「${selectedVendor.name}」嗎？\n停用後可隨時重新啟用。`)) return;

    try {
      await apiRequest(`/${selectedVendor.id}`, { method: 'DELETE' });
      NotificationModule.show({ title: '成功', message: '廠商已停用', icon: 'check-circle' });

      selectedVendor = await apiRequest(`/${selectedVendor.id}`);
      const windowEl = document.getElementById(windowId);
      if (windowEl) {
        renderContentView(windowEl);
      }
      await loadVendors();
    } catch (error) {
      NotificationModule.show({ title: '停用失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  async function confirmActivateVendor() {
    if (!selectedVendor) return;
    if (!confirm(`確定要啟用廠商「${selectedVendor.name}」嗎？`)) return;

    try {
      await apiRequest(`/${selectedVendor.id}/activate`, { method: 'POST' });
      NotificationModule.show({ title: '成功', message: '廠商已啟用', icon: 'check-circle' });

      selectedVendor = await apiRequest(`/${selectedVendor.id}`);
      const windowEl = document.getElementById(windowId);
      if (windowEl) {
        renderContentView(windowEl);
      }
      await loadVendors();
    } catch (error) {
      NotificationModule.show({ title: '啟用失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  // ============================================
  // Utilities
  // ============================================

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    return d.toLocaleString('zh-TW', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  // ============================================
  // Public API
  // ============================================

  return {
    open,
    close,
  };
})();

// Export for global access
window.VendorManagementModule = VendorManagementModule;
