/**
 * ChingTech OS - Inventory Management Module
 * 物料管理模組 - 支援物料 CRUD 和進出貨記錄
 */

const InventoryManagementModule = (function() {
  'use strict';

  const API_BASE = '/api/inventory';

  // State
  let windowId = null;
  let itemList = [];
  let selectedItem = null;
  let isEditing = false;
  let editingData = null;
  let listWidth = 320;

  // Filters
  let searchQuery = '';
  let filterCategory = '';
  let filterLowStock = false;

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
      windowEl.querySelector('.inv-container')?.classList.add('showing-detail');
    }
  }

  /**
   * Hide mobile detail view (back to list)
   */
  function hideMobileDetail() {
    const windowEl = document.getElementById(windowId);
    if (windowEl) {
      windowEl.querySelector('.inv-container')?.classList.remove('showing-detail');
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
   * Open inventory management window
   */
  function open() {
    const existing = WindowModule.getWindowByAppId('inventory-management');
    if (existing) {
      WindowModule.focusWindow(existing.windowId);
      if (!existing.minimized) return;
      WindowModule.restoreWindow(existing.windowId);
      return;
    }

    windowId = WindowModule.createWindow({
      title: '物料管理',
      appId: 'inventory-management',
      icon: 'package-variant',
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
    itemList = [];
    selectedItem = null;
    isEditing = false;
    editingData = null;
  }

  /**
   * Handle window init
   */
  function handleInit(windowEl, wId) {
    windowId = wId;
    bindEvents(windowEl);
    loadItems();
    loadCategories();
  }

  /**
   * Render main content
   */
  function renderContent() {
    return `
      <div class="inv-container">
        <div class="inv-toolbar">
          <div class="inv-search-container">
            <span class="inv-search-icon">
              <span class="icon">${getIcon('search')}</span>
            </span>
            <input type="text" class="inv-search-input" id="invSearchInput" placeholder="搜尋物料...">
            <button class="inv-search-clear" id="invSearchClear" style="display: none;">
              <span class="icon">${getIcon('close')}</span>
            </button>
          </div>
          <div class="inv-filters">
            <select class="inv-filter-select" id="invFilterCategory">
              <option value="">所有類別</option>
            </select>
            <label class="inv-filter-checkbox">
              <input type="checkbox" id="invFilterLowStock">
              <span>僅顯示庫存不足</span>
            </label>
          </div>
          <div class="inv-toolbar-actions">
            <button class="inv-action-btn" id="invBtnRefresh" title="重新載入">
              <span class="icon">${getIcon('refresh')}</span>
            </button>
            <button class="inv-action-btn primary" id="invBtnNew" title="新增物料">
              <span class="icon">${getIcon('plus')}</span>
              <span>新增</span>
            </button>
          </div>
        </div>

        <div class="inv-main">
          <div class="inv-list-panel" id="invListPanel">
            <div class="inv-list-header">
              <span>物料列表</span>
              <span class="inv-list-count" id="invListCount">0 項</span>
            </div>
            <div class="inv-list" id="invList">
              <div class="inv-loading">
                <span class="icon spinning">${getIcon('refresh')}</span>
                <span>載入中...</span>
              </div>
            </div>
          </div>

          <div class="inv-resizer" id="invResizer"></div>

          <div class="inv-content-panel" id="invContentPanel">
            <div class="inv-content-empty" id="invContentEmpty">
              <span class="icon">${getIcon('package-variant')}</span>
              <p>選擇一個物料來查看詳情</p>
              <p>或點擊「新增」建立新物料</p>
            </div>
            <div class="inv-content-view" id="invContentView" style="display: none;"></div>
            <div class="inv-editor" id="invEditor" style="display: none;"></div>
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
    const searchInput = windowEl.querySelector('#invSearchInput');
    const searchClear = windowEl.querySelector('#invSearchClear');
    let searchTimeout;

    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value;
      searchClear.style.display = searchQuery ? 'flex' : 'none';
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => loadItems(), 300);
    });

    searchClear.addEventListener('click', () => {
      searchInput.value = '';
      searchQuery = '';
      searchClear.style.display = 'none';
      loadItems();
    });

    // Filters
    windowEl.querySelector('#invFilterCategory').addEventListener('change', (e) => {
      filterCategory = e.target.value;
      loadItems();
    });

    windowEl.querySelector('#invFilterLowStock').addEventListener('change', (e) => {
      filterLowStock = e.target.checked;
      loadItems();
    });

    // Toolbar actions
    windowEl.querySelector('#invBtnRefresh').addEventListener('click', () => {
      loadItems();
      loadCategories();
    });
    windowEl.querySelector('#invBtnNew').addEventListener('click', startNewItem);

    // Resizer
    setupResizer(windowEl);
  }

  /**
   * Setup resizer for list panel
   */
  function setupResizer(windowEl) {
    const resizer = windowEl.querySelector('#invResizer');
    const listPanel = windowEl.querySelector('#invListPanel');
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

  async function loadItems() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const listEl = windowEl.querySelector('#invList');
    listEl.innerHTML = `
      <div class="inv-loading">
        <span class="icon spinning">${getIcon('refresh')}</span>
        <span>載入中...</span>
      </div>
    `;

    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append('q', searchQuery);
      if (filterCategory) params.append('category', filterCategory);
      if (filterLowStock) params.append('low_stock', 'true');

      const response = await apiRequest(`/items?${params.toString()}`);
      itemList = response.items || [];

      renderList(windowEl);
    } catch (error) {
      listEl.innerHTML = `
        <div class="inv-error">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入失敗：${error.message}</span>
        </div>
      `;
    }
  }

  async function loadCategories() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    try {
      const categories = await apiRequest('/categories');
      const select = windowEl.querySelector('#invFilterCategory');
      const currentValue = select.value;

      select.innerHTML = '<option value="">所有類別</option>';
      categories.forEach(cat => {
        const option = document.createElement('option');
        option.value = cat;
        option.textContent = cat;
        if (cat === currentValue) option.selected = true;
        select.appendChild(option);
      });
    } catch (error) {
      console.error('載入類別失敗:', error);
    }
  }

  /**
   * Render item list
   */
  function renderList(windowEl) {
    const listEl = windowEl.querySelector('#invList');
    const countEl = windowEl.querySelector('#invListCount');

    countEl.textContent = `${itemList.length} 項`;

    if (itemList.length === 0) {
      listEl.innerHTML = `
        <div class="inv-empty">
          <span class="icon">${getIcon('package-variant-closed')}</span>
          <span>${searchQuery || filterCategory || filterLowStock ? '沒有符合條件的物料' : '尚無物料'}</span>
        </div>
      `;
      return;
    }

    listEl.innerHTML = itemList.map(item => `
      <div class="inv-list-item ${selectedItem?.id === item.id ? 'selected' : ''} ${item.is_low_stock ? 'low-stock' : ''}" data-id="${item.id}">
        <div class="inv-list-item-main">
          <div class="inv-list-item-name">${escapeHtml(item.name)}</div>
          ${item.specification ? `<div class="inv-list-item-spec">${escapeHtml(item.specification)}</div>` : ''}
        </div>
        <div class="inv-list-item-info">
          <div class="inv-list-item-stock ${item.is_low_stock ? 'warning' : ''}">
            ${formatNumber(item.current_stock)} ${item.unit || ''}
          </div>
          ${item.category ? `<div class="inv-list-item-category">${escapeHtml(item.category)}</div>` : ''}
        </div>
      </div>
    `).join('');

    // Bind click events
    listEl.querySelectorAll('.inv-list-item').forEach(el => {
      el.addEventListener('click', () => selectItem(el.dataset.id));
    });
  }

  /**
   * Select an item
   */
  async function selectItem(itemId) {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    // Update list selection
    windowEl.querySelectorAll('.inv-list-item').forEach(el => {
      el.classList.toggle('selected', el.dataset.id === itemId);
    });

    try {
      selectedItem = await apiRequest(`/items/${itemId}`);
      isEditing = false;
      editingData = null;
      showMobileDetail();
      renderContentView(windowEl);
    } catch (error) {
      NotificationModule.show({ title: '載入失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  /**
   * Render content view (item detail)
   */
  function renderContentView(windowEl) {
    const emptyEl = windowEl.querySelector('#invContentEmpty');
    const viewEl = windowEl.querySelector('#invContentView');
    const editorEl = windowEl.querySelector('#invEditor');

    emptyEl.style.display = 'none';
    viewEl.style.display = 'flex';
    editorEl.style.display = 'none';

    const item = selectedItem;
    viewEl.innerHTML = `
      <div class="inv-detail-header">
        <button class="inv-back-btn" id="invBackBtn">
          <span class="icon">${getIcon('arrow-left')}</span>
        </button>
        <div class="inv-detail-title">
          <h2>${escapeHtml(item.name)}</h2>
          ${item.specification ? `<span class="inv-detail-spec">${escapeHtml(item.specification)}</span>` : ''}
        </div>
        <div class="inv-detail-actions">
          <button class="inv-action-btn" id="invBtnEdit" title="編輯">
            <span class="icon">${getIcon('pencil')}</span>
          </button>
          <button class="inv-action-btn danger" id="invBtnDelete" title="刪除">
            <span class="icon">${getIcon('delete')}</span>
          </button>
        </div>
      </div>

      <div class="inv-detail-body">
        <div class="inv-detail-section">
          <h3>庫存資訊</h3>
          <div class="inv-stock-display ${item.is_low_stock ? 'warning' : ''}">
            <div class="inv-stock-number">${formatNumber(item.current_stock)}</div>
            <div class="inv-stock-unit">${item.unit || '單位'}</div>
            ${item.is_low_stock ? `<div class="inv-stock-warning"><span class="icon">${getIcon('alert')}</span> 低於安全庫存</div>` : ''}
          </div>
          <div class="inv-detail-grid">
            <div class="inv-detail-item">
              <label>安全庫存</label>
              <span>${item.min_stock !== null ? formatNumber(item.min_stock) : '-'}</span>
            </div>
            <div class="inv-detail-item">
              <label>類別</label>
              <span>${item.category || '-'}</span>
            </div>
            <div class="inv-detail-item">
              <label>預設廠商</label>
              <span>${item.default_vendor || '-'}</span>
            </div>
            <div class="inv-detail-item">
              <label>更新時間</label>
              <span>${formatDate(item.updated_at)}</span>
            </div>
          </div>
          ${item.notes ? `<div class="inv-detail-notes"><label>備註</label><p>${escapeHtml(item.notes)}</p></div>` : ''}
        </div>

        <div class="inv-detail-section">
          <div class="inv-section-header">
            <h3>進出貨記錄</h3>
            <div class="inv-section-actions">
              <button class="inv-action-btn" id="invBtnIn">
                <span class="icon">${getIcon('arrow-down-bold')}</span>
                <span>進貨</span>
              </button>
              <button class="inv-action-btn" id="invBtnOut">
                <span class="icon">${getIcon('arrow-up-bold')}</span>
                <span>出貨</span>
              </button>
            </div>
          </div>
          <div class="inv-transactions" id="invTransactions">
            <div class="inv-loading">
              <span class="icon spinning">${getIcon('refresh')}</span>
              <span>載入中...</span>
            </div>
          </div>
        </div>
      </div>
    `;

    // Bind events
    viewEl.querySelector('#invBackBtn').addEventListener('click', () => {
      hideMobileDetail();
    });
    viewEl.querySelector('#invBtnEdit').addEventListener('click', startEditItem);
    viewEl.querySelector('#invBtnDelete').addEventListener('click', confirmDeleteItem);
    viewEl.querySelector('#invBtnIn').addEventListener('click', () => showTransactionModal('in'));
    viewEl.querySelector('#invBtnOut').addEventListener('click', () => showTransactionModal('out'));

    // Load transactions
    loadTransactions();
  }

  /**
   * Load transactions for selected item
   */
  async function loadTransactions() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl || !selectedItem) return;

    const container = windowEl.querySelector('#invTransactions');

    try {
      const response = await apiRequest(`/items/${selectedItem.id}/transactions`);
      const transactions = response.items || [];

      if (transactions.length === 0) {
        container.innerHTML = `
          <div class="inv-empty-transactions">
            <span>尚無進出貨記錄</span>
          </div>
        `;
        return;
      }

      container.innerHTML = `
        <table class="inv-transactions-table">
          <thead>
            <tr>
              <th>日期</th>
              <th>類型</th>
              <th>數量</th>
              <th>廠商/專案</th>
              <th>備註</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            ${transactions.map(tx => `
              <tr class="inv-tx-row ${tx.type}">
                <td>${formatDate(tx.transaction_date)}</td>
                <td>
                  <span class="inv-tx-type ${tx.type}">
                    ${tx.type === 'in' ? '進貨' : '出貨'}
                  </span>
                </td>
                <td class="inv-tx-qty ${tx.type}">
                  ${tx.type === 'in' ? '+' : '-'}${formatNumber(tx.quantity)}
                </td>
                <td>${escapeHtml(tx.vendor || tx.project_name || '-')}</td>
                <td>${tx.notes ? escapeHtml(tx.notes) : '-'}</td>
                <td>
                  <button class="inv-tx-delete" data-id="${tx.id}" title="刪除">
                    <span class="icon">${getIcon('delete')}</span>
                  </button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;

      // Bind delete events
      container.querySelectorAll('.inv-tx-delete').forEach(btn => {
        btn.addEventListener('click', () => confirmDeleteTransaction(btn.dataset.id));
      });
    } catch (error) {
      container.innerHTML = `
        <div class="inv-error">
          <span>載入失敗：${error.message}</span>
        </div>
      `;
    }
  }

  // ============================================
  // Item CRUD
  // ============================================

  function startNewItem() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    selectedItem = null;
    isEditing = true;
    editingData = {
      name: '',
      specification: '',
      unit: '',
      category: '',
      default_vendor: '',
      default_vendor_id: '',
      min_stock: null,
      notes: '',
    };

    renderEditor(windowEl);
  }

  function startEditItem() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl || !selectedItem) return;

    isEditing = true;
    editingData = {
      name: selectedItem.name,
      specification: selectedItem.specification || '',
      unit: selectedItem.unit || '',
      category: selectedItem.category || '',
      default_vendor: selectedItem.default_vendor || '',
      default_vendor_id: selectedItem.default_vendor_id || '',
      min_stock: selectedItem.min_stock,
      notes: selectedItem.notes || '',
    };

    renderEditor(windowEl);
  }

  async function renderEditor(windowEl) {
    const emptyEl = windowEl.querySelector('#invContentEmpty');
    const viewEl = windowEl.querySelector('#invContentView');
    const editorEl = windowEl.querySelector('#invEditor');

    emptyEl.style.display = 'none';
    viewEl.style.display = 'none';
    editorEl.style.display = 'flex';

    // 載入廠商列表
    let vendors = [];
    try {
      const token = getToken();
      const resp = await fetch('/api/vendors?active=true&limit=500', {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      });
      if (resp.ok) {
        const data = await resp.json();
        vendors = data.items || [];
      }
    } catch (e) {
      console.error('載入廠商列表失敗:', e);
    }

    const isNew = !selectedItem;
    editorEl.innerHTML = `
      <div class="inv-editor-header">
        <h2>${isNew ? '新增物料' : '編輯物料'}</h2>
      </div>
      <div class="inv-editor-body">
        <div class="inv-form-group">
          <label>物料名稱 *</label>
          <input type="text" id="invEditName" value="${escapeHtml(editingData.name)}" required>
        </div>
        <div class="inv-form-row">
          <div class="inv-form-group">
            <label>規格</label>
            <input type="text" id="invEditSpec" value="${escapeHtml(editingData.specification)}">
          </div>
          <div class="inv-form-group">
            <label>單位</label>
            <input type="text" id="invEditUnit" value="${escapeHtml(editingData.unit)}" placeholder="如：個、台、公斤">
          </div>
        </div>
        <div class="inv-form-row">
          <div class="inv-form-group">
            <label>類別</label>
            <input type="text" id="invEditCategory" value="${escapeHtml(editingData.category)}" list="invCategoryList">
            <datalist id="invCategoryList"></datalist>
          </div>
          <div class="inv-form-group">
            <label>安全庫存</label>
            <input type="number" id="invEditMinStock" value="${editingData.min_stock !== null ? editingData.min_stock : ''}" step="0.001" min="0">
          </div>
        </div>
        <div class="inv-form-group">
          <label>預設廠商</label>
          <div class="inv-combo-input">
            <input type="text" id="invEditVendor" value="${escapeHtml(editingData.default_vendor)}" list="invVendorList" placeholder="輸入或選擇廠商">
            <datalist id="invVendorList">
              ${vendors.map(v => `<option value="${escapeHtml(v.name)}" data-id="${v.id}">${v.erp_code ? `[${escapeHtml(v.erp_code)}] ` : ''}${escapeHtml(v.name)}</option>`).join('')}
            </datalist>
            <input type="hidden" id="invEditVendorId" value="${editingData.default_vendor_id || ''}">
          </div>
        </div>
        <div class="inv-form-group">
          <label>備註</label>
          <textarea id="invEditNotes" rows="3">${escapeHtml(editingData.notes)}</textarea>
        </div>
      </div>
      <div class="inv-editor-footer">
        <button class="inv-btn" id="invEditCancel">取消</button>
        <button class="inv-btn primary" id="invEditSave">${isNew ? '建立' : '儲存'}</button>
      </div>
    `;

    // Load categories for datalist
    loadCategoriesForDatalist(windowEl);

    // 當使用者從 datalist 選擇廠商時，自動填入 vendor_id
    const vendorInput = editorEl.querySelector('#invEditVendor');
    const vendorIdInput = editorEl.querySelector('#invEditVendorId');
    vendorInput.addEventListener('change', () => {
      const selectedVendor = vendors.find(v => v.name === vendorInput.value);
      vendorIdInput.value = selectedVendor ? selectedVendor.id : '';
    });
    vendorInput.addEventListener('input', () => {
      const selectedVendor = vendors.find(v => v.name === vendorInput.value);
      vendorIdInput.value = selectedVendor ? selectedVendor.id : '';
    });

    editorEl.querySelector('#invEditCancel').addEventListener('click', cancelEdit);
    editorEl.querySelector('#invEditSave').addEventListener('click', saveItem);
  }

  async function loadCategoriesForDatalist(windowEl) {
    try {
      const categories = await apiRequest('/categories');
      const datalist = windowEl.querySelector('#invCategoryList');
      datalist.innerHTML = categories.map(cat => `<option value="${escapeHtml(cat)}">`).join('');
    } catch (error) {
      console.error('載入類別失敗:', error);
    }
  }

  function cancelEdit() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    isEditing = false;
    editingData = null;

    if (selectedItem) {
      renderContentView(windowEl);
    } else {
      windowEl.querySelector('#invContentEmpty').style.display = 'flex';
      windowEl.querySelector('#invContentView').style.display = 'none';
      windowEl.querySelector('#invEditor').style.display = 'none';
    }
  }

  async function saveItem() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const name = windowEl.querySelector('#invEditName').value.trim();
    if (!name) {
      NotificationModule.show({ title: '提醒', message: '請輸入物料名稱', icon: 'alert' });
      return;
    }

    const minStockValue = windowEl.querySelector('#invEditMinStock').value;
    const vendorIdValue = windowEl.querySelector('#invEditVendorId').value;
    const data = {
      name,
      specification: windowEl.querySelector('#invEditSpec').value.trim() || null,
      unit: windowEl.querySelector('#invEditUnit').value.trim() || null,
      category: windowEl.querySelector('#invEditCategory').value.trim() || null,
      default_vendor: windowEl.querySelector('#invEditVendor').value.trim() || null,
      default_vendor_id: vendorIdValue || null,
      min_stock: minStockValue !== '' ? parseFloat(minStockValue) : null,
      notes: windowEl.querySelector('#invEditNotes').value.trim() || null,
    };

    try {
      if (selectedItem) {
        await apiRequest(`/items/${selectedItem.id}`, {
          method: 'PUT',
          body: JSON.stringify(data),
        });
        NotificationModule.show({ title: '成功', message: '物料已更新', icon: 'check-circle' });
      } else {
        const newItem = await apiRequest('/items', {
          method: 'POST',
          body: JSON.stringify(data),
        });
        selectedItem = newItem;
        NotificationModule.show({ title: '成功', message: '物料已建立', icon: 'check-circle' });
      }

      isEditing = false;
      editingData = null;
      await loadItems();
      await loadCategories();
      if (selectedItem) {
        selectedItem = await apiRequest(`/items/${selectedItem.id}`);
        renderContentView(windowEl);
      }
    } catch (error) {
      NotificationModule.show({ title: '儲存失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  async function confirmDeleteItem() {
    if (!selectedItem) return;
    if (!confirm(`確定要刪除物料「${selectedItem.name}」嗎？\n相關的進出貨記錄也會一併刪除。`)) return;

    try {
      await apiRequest(`/items/${selectedItem.id}`, { method: 'DELETE' });
      NotificationModule.show({ title: '成功', message: '物料已刪除', icon: 'check-circle' });

      selectedItem = null;
      const windowEl = document.getElementById(windowId);
      if (windowEl) {
        windowEl.querySelector('#invContentEmpty').style.display = 'flex';
        windowEl.querySelector('#invContentView').style.display = 'none';
        windowEl.querySelector('#invEditor').style.display = 'none';
      }
      await loadItems();
    } catch (error) {
      NotificationModule.show({ title: '刪除失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  // ============================================
  // Transactions
  // ============================================

  function showTransactionModal(type) {
    if (!selectedItem) return;

    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const isIn = type === 'in';
    const modal = document.createElement('div');
    modal.className = 'inv-modal-overlay';
    modal.innerHTML = `
      <div class="inv-modal">
        <div class="inv-modal-header">
          <h3>${isIn ? '進貨' : '出貨'} - ${escapeHtml(selectedItem.name)}</h3>
          <button class="inv-modal-close">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="inv-modal-body">
          <div class="inv-form-group">
            <label>數量 *</label>
            <div class="inv-input-with-unit">
              <input type="number" id="txQuantity" step="0.001" min="0.001" required>
              <span class="inv-input-unit">${selectedItem.unit || '單位'}</span>
            </div>
          </div>
          <div class="inv-form-group">
            <label>日期</label>
            <input type="date" id="txDate" value="${new Date().toISOString().split('T')[0]}">
          </div>
          ${isIn ? `
          <div class="inv-form-group">
            <label>廠商</label>
            <input type="text" id="txVendor" value="${escapeHtml(selectedItem.default_vendor || '')}">
          </div>
          ` : `
          <div class="inv-form-group">
            <label>用途/專案</label>
            <input type="text" id="txProject" placeholder="可選填">
          </div>
          `}
          <div class="inv-form-group">
            <label>備註</label>
            <textarea id="txNotes" rows="2"></textarea>
          </div>
        </div>
        <div class="inv-modal-footer">
          <button class="inv-btn" id="txCancel">取消</button>
          <button class="inv-btn primary" id="txSave">${isIn ? '確認進貨' : '確認出貨'}</button>
        </div>
      </div>
    `;

    windowEl.appendChild(modal);

    const closeModal = () => modal.remove();
    modal.querySelector('.inv-modal-close').addEventListener('click', closeModal);
    modal.querySelector('#txCancel').addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

    modal.querySelector('#txSave').addEventListener('click', async () => {
      const quantity = parseFloat(modal.querySelector('#txQuantity').value);
      if (!quantity || quantity <= 0) {
        NotificationModule.show({ title: '提醒', message: '請輸入有效數量', icon: 'alert' });
        return;
      }

      const data = {
        type,
        quantity,
        transaction_date: modal.querySelector('#txDate').value || null,
        notes: modal.querySelector('#txNotes').value.trim() || null,
      };

      if (isIn) {
        data.vendor = modal.querySelector('#txVendor').value.trim() || null;
      }

      try {
        await apiRequest(`/items/${selectedItem.id}/transactions`, {
          method: 'POST',
          body: JSON.stringify(data),
        });
        closeModal();

        // Reload item to get updated stock
        selectedItem = await apiRequest(`/items/${selectedItem.id}`);
        await loadItems();
        renderContentView(windowEl);

        NotificationModule.show({
          title: '成功',
          message: `${isIn ? '進貨' : '出貨'}記錄已新增`,
          icon: 'check-circle'
        });
      } catch (error) {
        NotificationModule.show({ title: '失敗', message: error.message, icon: 'alert-circle' });
      }
    });

    // Focus quantity input
    setTimeout(() => modal.querySelector('#txQuantity').focus(), 100);
  }

  async function confirmDeleteTransaction(transactionId) {
    if (!confirm('確定要刪除此進出貨記錄嗎？')) return;

    try {
      await apiRequest(`/transactions/${transactionId}`, { method: 'DELETE' });

      // Reload item and transactions
      selectedItem = await apiRequest(`/items/${selectedItem.id}`);
      await loadItems();
      const windowEl = document.getElementById(windowId);
      if (windowEl) {
        renderContentView(windowEl);
      }

      NotificationModule.show({ title: '成功', message: '記錄已刪除', icon: 'check-circle' });
    } catch (error) {
      NotificationModule.show({ title: '刪除失敗', message: error.message, icon: 'alert-circle' });
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

  function formatNumber(num) {
    if (num === null || num === undefined) return '-';
    const n = parseFloat(num);
    // Remove trailing zeros after decimal point
    return n.toLocaleString('zh-TW', { maximumFractionDigits: 3 });
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    return d.toLocaleDateString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' });
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
window.InventoryManagementModule = InventoryManagementModule;
