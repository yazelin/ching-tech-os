/**
 * ChingTech OS - Knowledge Base Module
 * Provides knowledge management with search, CRUD, and version history
 */

const KnowledgeBaseModule = (function() {
  'use strict';

  const API_BASE = '/api/knowledge';

  // State
  let windowId = null;
  let knowledgeList = [];
  let selectedKnowledge = null;
  let isEditing = false;
  let editingData = null;
  let tags = null;
  let listWidth = 320;
  let historyOpen = false;
  let historyData = null;

  // Filters
  let searchQuery = '';
  let filterProject = '';
  let filterType = '';
  let filterLevel = '';

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
      windowEl.querySelector('.knowledge-base')?.classList.add('showing-detail');
    }
  }

  /**
   * Hide mobile detail view (back to list)
   */
  function hideMobileDetail() {
    const windowEl = document.getElementById(windowId);
    if (windowEl) {
      windowEl.querySelector('.knowledge-base')?.classList.remove('showing-detail');
    }
  }

  /**
   * Get authentication token
   */
  function getToken() {
    return LoginModule?.getToken?.() || localStorage.getItem('chingtech_token') || '';
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
   * Open knowledge base window
   */
  function open() {
    console.log('[KnowledgeBase] open() called');
    const existing = WindowModule.getWindowByAppId('knowledge-base');
    if (existing) {
      console.log('[KnowledgeBase] Window already exists, focusing');
      WindowModule.focusWindow(existing.windowId);
      if (!existing.minimized) return;
      WindowModule.restoreWindow(existing.windowId);
      return;
    }

    console.log('[KnowledgeBase] Creating new window');
    windowId = WindowModule.createWindow({
      title: '知識庫',
      appId: 'knowledge-base',
      icon: 'book-open-page-variant',
      width: 1000,
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
    knowledgeList = [];
    selectedKnowledge = null;
    isEditing = false;
    editingData = null;
    historyOpen = false;
    historyData = null;
  }

  /**
   * Handle window init
   */
  function handleInit(windowEl, wId) {
    console.log('[KnowledgeBase] handleInit called', { windowEl, wId });
    windowId = wId;
    bindEvents(windowEl);
    loadTags();
    loadKnowledge();
  }

  /**
   * Render main content
   */
  function renderContent() {
    return `
      <div class="knowledge-base">
        <div class="kb-toolbar">
          <div class="kb-search-container">
            <span class="kb-search-icon">
              <span class="icon">${getIcon('search')}</span>
            </span>
            <input type="text" class="kb-search-input" id="kbSearchInput" placeholder="搜尋知識...">
            <button class="kb-search-clear" id="kbSearchClear" style="display: none;">
              <span class="icon">${getIcon('close')}</span>
            </button>
          </div>
          <div class="kb-filters">
            <select class="kb-filter-select" id="kbFilterProject">
              <option value="">所有專案</option>
            </select>
            <select class="kb-filter-select" id="kbFilterType">
              <option value="">所有類型</option>
            </select>
            <select class="kb-filter-select" id="kbFilterLevel">
              <option value="">所有層級</option>
            </select>
          </div>
          <div class="kb-toolbar-actions">
            <button class="kb-action-btn" id="kbBtnRefresh" title="重新載入">
              <span class="icon">${getIcon('refresh')}</span>
            </button>
            <button class="kb-action-btn primary" id="kbBtnNew" title="新增知識">
              <span class="icon">${getIcon('plus')}</span>
              <span>新增</span>
            </button>
          </div>
        </div>

        <div class="kb-main">
          <div class="kb-list-panel" id="kbListPanel">
            <div class="kb-list-header">
              <span>知識列表</span>
              <span class="kb-list-count" id="kbListCount">0 筆</span>
            </div>
            <div class="kb-list" id="kbList">
              <div class="kb-loading">
                <span class="icon">${getIcon('refresh')}</span>
                <span>載入中...</span>
              </div>
            </div>
          </div>

          <div class="kb-resizer" id="kbResizer"></div>

          <div class="kb-content-panel" id="kbContentPanel">
            <div class="kb-content-empty" id="kbContentEmpty">
              <span class="icon">${getIcon('book-open-page-variant')}</span>
              <p>選擇一個知識來查看內容</p>
              <p>或點擊「新增」建立新知識</p>
            </div>
            <div class="kb-content-view" id="kbContentView" style="display: none;"></div>
            <div class="kb-editor" id="kbEditor" style="display: none;"></div>
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
    const searchInput = windowEl.querySelector('#kbSearchInput');
    const searchClear = windowEl.querySelector('#kbSearchClear');
    let searchTimer = null;

    searchInput.addEventListener('input', () => {
      searchClear.style.display = searchInput.value ? 'flex' : 'none';
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        searchQuery = searchInput.value;
        loadKnowledge();
      }, 300);
    });

    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        clearTimeout(searchTimer);
        searchQuery = searchInput.value;
        loadKnowledge();
      }
    });

    searchClear.addEventListener('click', () => {
      searchInput.value = '';
      searchClear.style.display = 'none';
      searchQuery = '';
      loadKnowledge();
    });

    // Filters
    windowEl.querySelector('#kbFilterProject').addEventListener('change', (e) => {
      filterProject = e.target.value;
      loadKnowledge();
    });

    windowEl.querySelector('#kbFilterType').addEventListener('change', (e) => {
      filterType = e.target.value;
      loadKnowledge();
    });

    windowEl.querySelector('#kbFilterLevel').addEventListener('change', (e) => {
      filterLevel = e.target.value;
      loadKnowledge();
    });

    // Actions
    windowEl.querySelector('#kbBtnRefresh').addEventListener('click', () => {
      loadKnowledge();
    });

    windowEl.querySelector('#kbBtnNew').addEventListener('click', () => {
      startNewKnowledge();
    });

    // Resizer
    const resizer = windowEl.querySelector('#kbResizer');
    const listPanel = windowEl.querySelector('#kbListPanel');
    let isResizing = false;

    resizer.addEventListener('mousedown', (e) => {
      isResizing = true;
      resizer.classList.add('dragging');
      document.addEventListener('mousemove', handleResize);
      document.addEventListener('mouseup', stopResize);
    });

    function handleResize(e) {
      if (!isResizing) return;
      const rect = windowEl.querySelector('.kb-main').getBoundingClientRect();
      const newWidth = Math.max(250, Math.min(e.clientX - rect.left, rect.width * 0.5));
      listPanel.style.width = newWidth + 'px';
      listWidth = newWidth;
    }

    function stopResize() {
      isResizing = false;
      resizer.classList.remove('dragging');
      document.removeEventListener('mousemove', handleResize);
      document.removeEventListener('mouseup', stopResize);
    }
  }

  /**
   * Load tags from API
   */
  async function loadTags() {
    try {
      tags = await apiRequest('/tags');
      updateFilterOptions();
    } catch (error) {
      console.error('Failed to load tags:', error);
    }
  }

  /**
   * Update filter dropdown options
   */
  function updateFilterOptions() {
    if (!tags) return;
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    // Projects
    const projectSelect = windowEl.querySelector('#kbFilterProject');
    projectSelect.innerHTML = '<option value="">所有專案</option>' +
      tags.projects.map(p => `<option value="${p}">${p}</option>`).join('');

    // Types
    const typeSelect = windowEl.querySelector('#kbFilterType');
    typeSelect.innerHTML = '<option value="">所有類型</option>' +
      tags.types.map(t => `<option value="${t}">${t}</option>`).join('');

    // Levels
    const levelSelect = windowEl.querySelector('#kbFilterLevel');
    levelSelect.innerHTML = '<option value="">所有層級</option>' +
      tags.levels.map(l => `<option value="${l}">${l}</option>`).join('');
  }

  /**
   * Load knowledge list from API
   */
  async function loadKnowledge() {
    console.log('[KnowledgeBase] loadKnowledge called, windowId:', windowId);
    const windowEl = document.getElementById(windowId);
    if (!windowEl) {
      console.log('[KnowledgeBase] windowEl not found!');
      return;
    }

    const listEl = windowEl.querySelector('#kbList');
    listEl.innerHTML = `
      <div class="kb-loading">
        <span class="icon">${getIcon('refresh')}</span>
        <span>載入中...</span>
      </div>
    `;

    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append('q', searchQuery);
      if (filterProject) params.append('project', filterProject);
      if (filterType) params.append('type', filterType);
      if (filterLevel) params.append('level', filterLevel);

      console.log('[KnowledgeBase] Fetching:', `${API_BASE}?${params.toString()}`);
      const result = await apiRequest(`?${params.toString()}`);
      console.log('[KnowledgeBase] API result:', result);
      knowledgeList = result.items;
      renderList(windowEl);
    } catch (error) {
      console.error('Failed to load knowledge:', error);
      listEl.innerHTML = `
        <div class="kb-empty">
          <span class="icon">${getIcon('close')}</span>
          <span>載入失敗: ${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * Render knowledge list
   */
  function renderList(windowEl) {
    const listEl = windowEl.querySelector('#kbList');
    const countEl = windowEl.querySelector('#kbListCount');

    countEl.textContent = `${knowledgeList.length} 筆`;

    if (knowledgeList.length === 0) {
      listEl.innerHTML = `
        <div class="kb-empty">
          <span class="icon">${getIcon('book-open-page-variant')}</span>
          <span>沒有找到符合條件的知識</span>
        </div>
      `;
      return;
    }

    listEl.innerHTML = knowledgeList.map(item => `
      <div class="kb-list-item ${selectedKnowledge?.id === item.id ? 'selected' : ''}"
           data-id="${item.id}">
        <div class="kb-list-item-title">
          ${highlightText(item.title)}
          <span class="kb-scope-badge ${item.scope || 'global'}">${item.scope === 'personal' ? '個人' : '全域'}</span>
        </div>
        <div class="kb-list-item-tags">
          ${item.tags.projects.map(p => `<span class="kb-tag project">${p}</span>`).join('')}
          <span class="kb-tag type">${item.type}</span>
          ${item.tags.level ? `<span class="kb-tag level">${item.tags.level}</span>` : ''}
        </div>
        <div class="kb-list-item-meta">
          <span>${item.author}</span>
          <span>${formatDate(item.updated_at)}</span>
        </div>
        ${item.snippet ? `<div class="kb-list-item-snippet">${item.snippet}</div>` : ''}
      </div>
    `).join('');

    // Bind click events
    listEl.querySelectorAll('.kb-list-item').forEach(el => {
      el.addEventListener('click', () => {
        selectKnowledge(el.dataset.id);
      });
    });
  }

  /**
   * Highlight search text
   */
  function highlightText(text) {
    if (!searchQuery) return text;
    const regex = new RegExp(`(${searchQuery})`, 'gi');
    return text.replace(regex, '<span class="highlight">$1</span>');
  }

  /**
   * Format date
   */
  function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-TW');
  }

  /**
   * Select and load knowledge
   */
  async function selectKnowledge(id) {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    try {
      selectedKnowledge = await apiRequest(`/${id}`);
      isEditing = false;
      renderContentView(windowEl);

      // 手機版：顯示詳情
      showMobileDetail();

      // Update list selection
      windowEl.querySelectorAll('.kb-list-item').forEach(el => {
        el.classList.toggle('selected', el.dataset.id === id);
      });
    } catch (error) {
      console.error('Failed to load knowledge:', error);
      NotificationModule.show({ title: '載入失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  /**
   * 檢查是否有知識的寫入權限
   */
  function canEditKnowledge(kb) {
    if (typeof PermissionsModule === 'undefined') return true;
    const user = PermissionsModule.getCurrentUser();
    if (!user) return false;
    if (user.is_admin) return true;

    // 個人知識：只有擁有者可編輯
    if (kb.scope === 'personal') {
      return kb.owner === user.username;
    }

    // 全域知識：需要 global_write 權限
    return PermissionsModule.canAccessKnowledge('global_write');
  }

  /**
   * 檢查是否有知識的刪除權限
   */
  function canDeleteKnowledge(kb) {
    if (typeof PermissionsModule === 'undefined') return true;
    const user = PermissionsModule.getCurrentUser();
    if (!user) return false;
    if (user.is_admin) return true;

    // 個人知識：只有擁有者可刪除
    if (kb.scope === 'personal') {
      return kb.owner === user.username;
    }

    // 全域知識：需要 global_delete 權限
    return PermissionsModule.canAccessKnowledge('global_delete');
  }

  /**
   * Render content view
   */
  function renderContentView(windowEl) {
    const emptyEl = windowEl.querySelector('#kbContentEmpty');
    const viewEl = windowEl.querySelector('#kbContentView');
    const editorEl = windowEl.querySelector('#kbEditor');

    emptyEl.style.display = 'none';
    editorEl.style.display = 'none';
    viewEl.style.display = 'flex';

    const kb = selectedKnowledge;
    const canEdit = canEditKnowledge(kb);
    const canDelete = canDeleteKnowledge(kb);

    viewEl.innerHTML = `
      <div class="kb-content-header">
        <button class="kb-mobile-back-btn" id="kbMobileBackBtn" style="display: none;">
          <span class="icon">${getIcon('chevron-left')}</span>
          返回
        </button>
        <div class="kb-content-title-section">
          <h2 class="kb-content-title">
            ${kb.title}
            <span class="kb-scope-badge large ${kb.scope || 'global'}">${kb.scope === 'personal' ? '個人' : '全域'}</span>
          </h2>
          <div class="kb-content-meta">
            <span class="kb-content-meta-item">
              <span class="icon">${getIcon('account')}</span>
              ${kb.author}
            </span>
            ${kb.owner ? `
            <span class="kb-content-meta-item">
              <span class="icon">${getIcon('account-circle')}</span>
              擁有者: ${kb.owner}
            </span>
            ` : ''}
            <span class="kb-content-meta-item">
              <span class="icon">${getIcon('clock-outline')}</span>
              ${formatDate(kb.updated_at)}
            </span>
          </div>
        </div>
        <div class="kb-content-actions">
          <button class="kb-action-btn" id="kbBtnShare" title="分享">
            <span class="icon">${getIcon('share-variant')}</span>
          </button>
          <button class="kb-action-btn" id="kbBtnHistory" title="版本歷史">
            <span class="icon">${getIcon('clock-outline')}</span>
          </button>
          ${canEdit ? `
          <button class="kb-action-btn" id="kbBtnEdit" title="編輯">
            <span class="icon">${getIcon('edit')}</span>
          </button>
          ` : ''}
          ${canDelete ? `
          <button class="kb-action-btn" id="kbBtnDelete" title="刪除" style="color: var(--color-error);">
            <span class="icon">${getIcon('delete')}</span>
          </button>
          ` : ''}
        </div>
      </div>
      <div class="kb-tags-section">
        ${kb.tags.projects.map(p => `<span class="kb-tag-large project">${p}</span>`).join('')}
        <span class="kb-tag-large type">${kb.type}</span>
        <span class="kb-tag-large category">${kb.category}</span>
        ${kb.tags.level ? `<span class="kb-tag-large level">${kb.tags.level}</span>` : ''}
        ${kb.tags.roles.map(r => `<span class="kb-tag-large role">${r}</span>`).join('')}
        ${kb.tags.topics.map(t => `<span class="kb-tag-large topic">${t}</span>`).join('')}
      </div>
      <div class="kb-content-body">
        <div class="kb-markdown" id="kbMarkdownContent"></div>
      </div>
      <div class="kb-attachments" id="kbAttachments"></div>
    `;

    // Render markdown
    const markdownEl = viewEl.querySelector('#kbMarkdownContent');
    if (typeof marked !== 'undefined') {
      markdownEl.innerHTML = marked.parse(kb.content);
    } else {
      markdownEl.innerHTML = `<pre>${kb.content}</pre>`;
    }

    // Render attachments
    renderAttachments(viewEl, kb);

    // 手機版返回按鈕
    const mobileBackBtn = viewEl.querySelector('#kbMobileBackBtn');
    if (mobileBackBtn) {
      mobileBackBtn.addEventListener('click', () => {
        hideMobileDetail();
      });
    }

    // Bind action buttons
    const editBtn = viewEl.querySelector('#kbBtnEdit');
    if (editBtn) {
      editBtn.addEventListener('click', () => {
        startEditKnowledge();
      });
    }

    const deleteBtn = viewEl.querySelector('#kbBtnDelete');
    if (deleteBtn) {
      deleteBtn.addEventListener('click', () => {
        confirmDeleteKnowledge();
      });
    }

    viewEl.querySelector('#kbBtnHistory').addEventListener('click', () => {
      loadHistory();
    });

    // 分享按鈕
    const shareBtn = viewEl.querySelector('#kbBtnShare');
    if (shareBtn) {
      shareBtn.addEventListener('click', () => {
        if (typeof ShareDialogModule !== 'undefined') {
          ShareDialogModule.show({
            resourceType: 'knowledge',
            resourceId: kb.id,
            resourceTitle: kb.title
          });
        }
      });
    }
  }

  /**
   * Render attachments section
   */
  function renderAttachments(windowEl, kb) {
    const attachmentsEl = windowEl.querySelector('#kbAttachments');
    if (!attachmentsEl) return;

    const attachments = kb.attachments || [];

    attachmentsEl.innerHTML = `
      <div class="kb-attachments-resizer" title="拖曳調整高度"></div>
      <div class="kb-attachments-body">
        <div class="kb-attachments-header">
          <div class="kb-attachments-title">
            <span class="icon">${getIcon('attachment')}</span>
            附件
            <span class="kb-attachments-count">(${attachments.length})</span>
          </div>
          <button class="kb-attachments-upload-btn" id="kbBtnUploadAttachment">
            <span class="icon">${getIcon('upload')}</span>
            上傳
          </button>
        </div>
        <div class="kb-attachments-list" id="kbAttachmentsList">
          ${attachments.length === 0 ?
            '<div class="kb-attachments-empty">目前沒有附件</div>' :
            attachments.map((att, idx) => renderAttachmentItem(att, idx)).join('')
          }
        </div>
      </div>
    `;

    // 綁定拖曳調整高度事件
    bindAttachmentsResizer(attachmentsEl);

    // Bind attachment events
    bindAttachmentEvents(windowEl, kb);
  }

  /**
   * Render single attachment item
   */
  function escapeHtmlAttr(str) {
    return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function renderAttachmentItem(att, idx) {
    const isNas = att.path.startsWith('nas://');
    const filename = att.path.split('/').pop();
    // 使用 FileUtils 取得圖示和類型 class
    const iconName = FileUtils.getFileIcon(filename, att.type);
    const typeClass = FileUtils.getFileTypeClass(filename, att.type);
    const escapedPath = escapeHtmlAttr(att.path);
    const escapedDesc = escapeHtmlAttr(att.description || '');
    const description = att.description ? `<div class="kb-attachment-desc">${escapeHtmlAttr(att.description)}</div>` : '';

    return `
      <div class="kb-attachment-item" data-idx="${idx}" data-path="${escapedPath}" data-type="${att.type}" data-description="${escapedDesc}">
        <div class="file-icon-wrapper ${typeClass}">
          <span class="icon">${getIcon(iconName)}</span>
        </div>
        <div class="kb-attachment-info">
          <div class="kb-attachment-name">${filename}</div>
          ${description}
          <div class="kb-attachment-meta">
            <span>${att.size}</span>
            <span class="storage-badge ${isNas ? 'nas' : 'local'}">${isNas ? 'NAS' : '本機'}</span>
          </div>
        </div>
        <div class="kb-attachment-actions">
          <button class="file-icon-btn" data-action="preview" title="預覽">
            <span class="icon">${getIcon('eye')}</span>
          </button>
          <button class="file-icon-btn" data-action="download" title="下載">
            <span class="icon">${getIcon('download')}</span>
          </button>
          <button class="file-icon-btn" data-action="edit" title="編輯">
            <span class="icon">${getIcon('edit')}</span>
          </button>
          <button class="file-icon-btn danger" data-action="delete" title="刪除">
            <span class="icon">${getIcon('delete')}</span>
          </button>
        </div>
      </div>
    `;
  }

  /**
   * 綁定附件區塊拖曳調整高度事件
   */
  function bindAttachmentsResizer(attachmentsEl) {
    const resizer = attachmentsEl.querySelector('.kb-attachments-resizer');
    if (!resizer) return;

    let isResizing = false;
    let startY = 0;
    let startHeight = 0;

    resizer.addEventListener('mousedown', (e) => {
      isResizing = true;
      startY = e.clientY;
      startHeight = attachmentsEl.offsetHeight;
      document.body.style.cursor = 'ns-resize';
      document.body.style.userSelect = 'none';
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!isResizing) return;
      // 往上拖 = 增加高度（因為附件區在底部）
      const deltaY = startY - e.clientY;
      const newHeight = Math.max(60, Math.min(startHeight + deltaY, window.innerHeight * 0.5));
      attachmentsEl.style.height = `${newHeight}px`;
    });

    document.addEventListener('mouseup', () => {
      if (isResizing) {
        isResizing = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    });
  }

  /**
   * Bind attachment events
   */
  function bindAttachmentEvents(windowEl, kb) {
    const uploadBtn = windowEl.querySelector('#kbBtnUploadAttachment');
    const attachmentsList = windowEl.querySelector('#kbAttachmentsList');

    // Show upload modal
    uploadBtn?.addEventListener('click', () => {
      showUploadModal(windowEl, kb.id);
    });

    // Attachment item actions
    attachmentsList?.addEventListener('click', (e) => {
      const actionBtn = e.target.closest('.file-icon-btn');
      if (!actionBtn) return;

      const item = actionBtn.closest('.kb-attachment-item');
      const path = item.dataset.path;
      const idx = parseInt(item.dataset.idx, 10);
      const action = actionBtn.dataset.action;

      if (action === 'download') {
        downloadAttachment(kb.id, path);
      } else if (action === 'preview') {
        previewAttachment(kb.id, path);
      } else if (action === 'edit') {
        const currentType = item.dataset.type || 'file';
        const currentDesc = item.dataset.description || '';
        editAttachment(kb.id, idx, currentType, currentDesc);
      } else if (action === 'delete') {
        deleteAttachment(kb.id, idx);
      }
    });

    // 雙擊附件卡片開啟預覽
    attachmentsList?.querySelectorAll('.kb-attachment-item').forEach(item => {
      item.addEventListener('dblclick', (e) => {
        // 排除按鈕區域
        if (e.target.closest('.kb-attachment-actions')) return;
        const path = item.dataset.path;
        previewAttachment(kb.id, path);
      });
    });
  }

  /**
   * Show upload modal
   */
  function showUploadModal(windowEl, kbId) {
    // Create upload modal
    const modal = document.createElement('div');
    modal.className = 'kb-upload-modal';
    modal.innerHTML = `
      <div class="kb-upload-modal-content">
        <div class="kb-upload-modal-header">
          <h3>上傳附件</h3>
          <button class="kb-upload-modal-close" id="kbUploadModalClose">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="kb-upload-modal-body">
          <div class="kb-upload-dropzone" id="kbUploadDropzone">
            <span class="icon">${getIcon('upload')}</span>
            <div class="kb-upload-dropzone-text">拖放檔案至此處</div>
            <div class="kb-upload-dropzone-hint">或點擊選擇檔案</div>
            <div class="kb-upload-dropzone-note">小於 1MB 存本機，大於等於 1MB 存 NAS</div>
            <input type="file" id="kbUploadFileInput" style="display: none;" multiple>
          </div>
          <div class="kb-upload-progress" id="kbUploadProgress">
            <div class="kb-upload-progress-info">
              <span id="kbUploadFileName">準備上傳...</span>
              <span id="kbUploadProgressText">0%</span>
            </div>
            <div class="kb-upload-progress-bar">
              <div class="kb-upload-progress-fill" id="kbUploadProgressFill" style="width: 0%;"></div>
            </div>
          </div>
        </div>
        <div class="kb-upload-modal-footer">
          <button class="btn btn-ghost" id="kbUploadSelectBtn">
            <span class="icon">${getIcon('folder-open')}</span>
            選擇檔案
          </button>
        </div>
      </div>
    `;

    windowEl.appendChild(modal);

    // Elements
    const closeBtn = modal.querySelector('#kbUploadModalClose');
    const selectBtn = modal.querySelector('#kbUploadSelectBtn');
    const dropzone = modal.querySelector('#kbUploadDropzone');
    const fileInput = modal.querySelector('#kbUploadFileInput');

    // Close modal function
    const closeModal = () => modal.remove();

    // Store modal reference for uploadFiles
    modal.dataset.kbId = kbId;
    windowEl._uploadModal = modal;

    // Close events
    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });

    // Select file button
    selectBtn.addEventListener('click', () => fileInput.click());

    // Click dropzone to select file
    dropzone.addEventListener('click', (e) => {
      if (e.target === dropzone || e.target.closest('.kb-upload-dropzone-text') || e.target.closest('.kb-upload-dropzone-hint')) {
        fileInput.click();
      }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        uploadFilesFromModal(modal, Array.from(e.target.files), kbId);
      }
    });

    // Drag and drop
    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files.length > 0) {
        uploadFilesFromModal(modal, Array.from(e.dataTransfer.files), kbId);
      }
    });
  }

  /**
   * Upload files from modal
   */
  async function uploadFilesFromModal(modal, files, kbId) {
    const progressEl = modal.querySelector('#kbUploadProgress');
    const progressFill = modal.querySelector('#kbUploadProgressFill');
    const progressText = modal.querySelector('#kbUploadProgressText');
    const fileNameEl = modal.querySelector('#kbUploadFileName');
    const dropzone = modal.querySelector('#kbUploadDropzone');

    progressEl.classList.add('active');
    dropzone.style.display = 'none';

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const progress = Math.round(((i) / files.length) * 100);
      progressFill.style.width = `${progress}%`;
      progressText.textContent = `${progress}%`;
      fileNameEl.textContent = `上傳中: ${file.name} (${i + 1}/${files.length})`;

      try {
        const formData = new FormData();
        formData.append('file', file);
        const token = getToken();

        const response = await fetch(`${API_BASE}/${kbId}/attachments`, {
          method: 'POST',
          headers: {
            ...(token && { 'Authorization': `Bearer ${token}` }),
          },
          body: formData,
        });

        if (!response.ok) {
          throw new Error(`上傳失敗: ${response.statusText}`);
        }
      } catch (error) {
        console.error('Upload failed:', error);
        NotificationModule.show({ title: '上傳失敗', message: `${file.name}: ${error.message}`, icon: 'alert-circle' });
      }
    }

    progressFill.style.width = '100%';
    progressText.textContent = '100%';
    fileNameEl.textContent = '上傳完成！';

    // Reload knowledge and close modal
    setTimeout(async () => {
      modal.remove();
      await selectKnowledge(kbId);
      NotificationModule.show({ title: '上傳完成', message: `已成功上傳 ${files.length} 個檔案`, icon: 'check-circle' });
    }, 800);
  }

  /**
   * Download attachment
   */
  function downloadAttachment(kbId, path) {
    const url = getAttachmentUrl(path);
    const filename = path.split('/').pop();
    FileUtils.downloadWithAuth(url, filename);
  }

  /**
   * Preview attachment
   */
  function previewAttachment(kbId, path) {
    const url = getAttachmentUrl(path);
    const filename = path.split('/').pop();
    const basePath = window.API_BASE || '';

    // 使用 FileOpener 統一入口開啟檔案
    if (typeof FileOpener !== 'undefined' && FileOpener.canOpen(filename)) {
      FileOpener.open(url, filename);
      return;
    }

    // 不支援的檔案類型 - 直接下載
    window.open(`${basePath}${url}`, '_blank');
  }

  /**
   * Delete attachment
   */
  async function deleteAttachment(kbId, attachmentIdx) {
    if (!confirm('確定要刪除此附件嗎？')) {
      return;
    }

    try {
      await apiRequest(`/${kbId}/attachments/${attachmentIdx}`, {
        method: 'DELETE',
      });

      // Reload knowledge to get updated attachments
      await selectKnowledge(kbId);
      NotificationModule.show({ title: '刪除成功', message: '附件已刪除', icon: 'check-circle' });
    } catch (error) {
      console.error('Delete attachment failed:', error);
      NotificationModule.show({ title: '刪除失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  /**
   * Edit attachment metadata
   */
  async function editAttachment(kbId, attachmentIdx, currentType, currentDesc) {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    // Create edit modal
    const modal = document.createElement('div');
    modal.className = 'kb-attachment-edit-modal';
    modal.innerHTML = `
      <div class="kb-attachment-edit-content">
        <div class="kb-attachment-edit-header">
          <h3>編輯附件</h3>
          <button class="kb-attachment-edit-close" id="kbAttEditClose">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="kb-attachment-edit-body">
          <div class="kb-attachment-edit-field">
            <label>類型</label>
            <select id="kbAttEditType" class="kb-editor-select">
              <option value="file" ${currentType === 'file' ? 'selected' : ''}>一般檔案</option>
              <option value="image" ${currentType === 'image' ? 'selected' : ''}>圖片</option>
              <option value="video" ${currentType === 'video' ? 'selected' : ''}>影片</option>
              <option value="document" ${currentType === 'document' ? 'selected' : ''}>文件</option>
            </select>
          </div>
          <div class="kb-attachment-edit-field">
            <label>說明</label>
            <textarea id="kbAttEditDesc" class="kb-editor-textarea" rows="3" placeholder="輸入附件說明...">${currentDesc}</textarea>
          </div>
        </div>
        <div class="kb-attachment-edit-footer">
          <button class="btn btn-ghost" id="kbAttEditCancel">取消</button>
          <button class="btn btn-primary" id="kbAttEditSave">儲存</button>
        </div>
      </div>
    `;

    windowEl.appendChild(modal);

    // Bind events
    const closeBtn = modal.querySelector('#kbAttEditClose');
    const cancelBtn = modal.querySelector('#kbAttEditCancel');
    const saveBtn = modal.querySelector('#kbAttEditSave');
    const typeSelect = modal.querySelector('#kbAttEditType');
    const descInput = modal.querySelector('#kbAttEditDesc');

    const closeModal = () => modal.remove();

    closeBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });

    saveBtn.addEventListener('click', async () => {
      const newType = typeSelect.value;
      const newDesc = descInput.value.trim();

      try {
        await apiRequest(`/${kbId}/attachments/${attachmentIdx}`, {
          method: 'PATCH',
          body: JSON.stringify({
            type: newType,
            description: newDesc || null,
          }),
        });

        closeModal();
        await selectKnowledge(kbId);
        NotificationModule.show({ title: '儲存成功', message: '附件資訊已更新', icon: 'check-circle' });
      } catch (error) {
        console.error('Update attachment failed:', error);
        NotificationModule.show({ title: '儲存失敗', message: error.message, icon: 'alert-circle' });
      }
    });
  }

  /**
   * Get attachment URL
   */
  function getAttachmentUrl(path) {
    const isNas = path.startsWith('nas://');
    // 不加 base path，由 FileOpener 統一處理

    if (isNas) {
      // NAS path: nas://knowledge/attachments/kb-001/file.bin
      // API endpoint: /api/knowledge/attachments/{path}
      // Need to extract: attachments/kb-001/file.bin
      const nasPath = path.replace('nas://knowledge/', '');
      return `${API_BASE}/${nasPath}`;
    } else {
      // Local path: ../assets/images/kb-001-file.png
      // API endpoint: /api/knowledge/assets/images/{filename}
      const filename = path.split('/').pop();
      return `${API_BASE}/assets/images/${filename}`;
    }
  }

  /**
   * Start new knowledge
   */
  function startNewKnowledge() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    selectedKnowledge = null;
    isEditing = true;
    editingData = {
      title: '',
      content: '',
      type: 'knowledge',
      category: 'technical',
      scope: 'personal',  // 預設為個人知識
      tags: {
        projects: [],
        roles: [],
        topics: [],
        level: 'beginner',
      },
    };

    renderEditor(windowEl);
  }

  /**
   * Start editing knowledge
   */
  function startEditKnowledge() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl || !selectedKnowledge) return;

    isEditing = true;
    editingData = {
      title: selectedKnowledge.title,
      content: selectedKnowledge.content,
      type: selectedKnowledge.type,
      category: selectedKnowledge.category,
      scope: selectedKnowledge.scope || 'global',
      tags: { ...selectedKnowledge.tags },
    };

    renderEditor(windowEl);
  }

  /**
   * 檢查是否有建立全域知識的權限
   */
  function canCreateGlobalKnowledge() {
    if (typeof PermissionsModule === 'undefined') return true;
    const user = PermissionsModule.getCurrentUser();
    if (!user) return false;
    if (user.is_admin) return true;
    return PermissionsModule.canAccessKnowledge('global_write');
  }

  /**
   * Render editor
   */
  function renderEditor(windowEl) {
    const emptyEl = windowEl.querySelector('#kbContentEmpty');
    const viewEl = windowEl.querySelector('#kbContentView');
    const editorEl = windowEl.querySelector('#kbEditor');

    emptyEl.style.display = 'none';
    viewEl.style.display = 'none';
    editorEl.style.display = 'flex';

    const isNew = !selectedKnowledge;
    const canCreateGlobal = canCreateGlobalKnowledge();

    editorEl.innerHTML = `
      <div class="kb-editor-header">
        <input type="text" class="kb-editor-title-input" id="kbEditorTitle"
               placeholder="知識標題" value="${editingData.title}">
        <div class="kb-editor-meta">
          ${isNew ? `
          <div class="kb-editor-field">
            <label class="kb-editor-label">範圍</label>
            <select class="kb-editor-select" id="kbEditorScope">
              <option value="personal" ${editingData.scope === 'personal' ? 'selected' : ''}>個人知識</option>
              ${canCreateGlobal ? `<option value="global" ${editingData.scope === 'global' ? 'selected' : ''}>全域知識</option>` : ''}
            </select>
          </div>
          ` : `
          <div class="kb-editor-field">
            <label class="kb-editor-label">範圍</label>
            <span class="kb-scope-badge large ${editingData.scope || 'global'}">${editingData.scope === 'personal' ? '個人' : '全域'}</span>
          </div>
          `}
          <div class="kb-editor-field">
            <label class="kb-editor-label">類型</label>
            <select class="kb-editor-select" id="kbEditorType">
              ${tags?.types.map(t => `<option value="${t}" ${editingData.type === t ? 'selected' : ''}>${t}</option>`).join('')}
            </select>
          </div>
          <div class="kb-editor-field">
            <label class="kb-editor-label">分類</label>
            <select class="kb-editor-select" id="kbEditorCategory">
              ${tags?.categories.map(c => `<option value="${c}" ${editingData.category === c ? 'selected' : ''}>${c}</option>`).join('')}
            </select>
          </div>
          <div class="kb-editor-field">
            <label class="kb-editor-label">層級</label>
            <select class="kb-editor-select" id="kbEditorLevel">
              ${tags?.levels.map(l => `<option value="${l}" ${editingData.tags.level === l ? 'selected' : ''}>${l}</option>`).join('')}
            </select>
          </div>
          <div class="kb-editor-field">
            <label class="kb-editor-label">專案 (多選)</label>
            <select class="kb-editor-select" id="kbEditorProject" multiple style="height: 60px;">
              ${tags?.projects.map(p => `<option value="${p}" ${editingData.tags.projects.includes(p) ? 'selected' : ''}>${p}</option>`).join('')}
            </select>
          </div>
        </div>
      </div>
      <div class="kb-editor-body">
        <textarea class="kb-editor-textarea" id="kbEditorContent"
                  placeholder="使用 Markdown 格式撰寫知識內容...">${editingData.content}</textarea>
      </div>
      <div class="kb-editor-footer">
        <button class="kb-dialog-btn kb-dialog-btn-cancel" id="kbEditorCancel">取消</button>
        <button class="kb-dialog-btn kb-dialog-btn-primary" id="kbEditorSave">
          ${isNew ? '建立' : '儲存'}
        </button>
      </div>
    `;

    // Bind events
    editorEl.querySelector('#kbEditorCancel').addEventListener('click', () => {
      cancelEdit();
    });

    editorEl.querySelector('#kbEditorSave').addEventListener('click', () => {
      saveKnowledge();
    });
  }

  /**
   * Cancel editing
   */
  function cancelEdit() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    isEditing = false;
    editingData = null;

    if (selectedKnowledge) {
      renderContentView(windowEl);
    } else {
      windowEl.querySelector('#kbContentEmpty').style.display = 'flex';
      windowEl.querySelector('#kbContentView').style.display = 'none';
      windowEl.querySelector('#kbEditor').style.display = 'none';
    }
  }

  /**
   * Save knowledge
   */
  async function saveKnowledge() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const title = windowEl.querySelector('#kbEditorTitle').value.trim();
    const content = windowEl.querySelector('#kbEditorContent').value;
    const type = windowEl.querySelector('#kbEditorType').value;
    const category = windowEl.querySelector('#kbEditorCategory').value;
    const level = windowEl.querySelector('#kbEditorLevel').value;
    const projectSelect = windowEl.querySelector('#kbEditorProject');
    const projects = Array.from(projectSelect.selectedOptions).map(o => o.value);

    // 讀取 scope（只有新增時才有選擇器）
    const scopeSelect = windowEl.querySelector('#kbEditorScope');
    const scope = scopeSelect ? scopeSelect.value : editingData.scope;

    if (!title) {
      NotificationModule.show({ title: '提醒', message: '請輸入標題', icon: 'alert' });
      return;
    }

    try {
      const data = {
        title,
        content,
        type,
        category,
        tags: {
          projects,
          roles: editingData.tags.roles || [],
          topics: editingData.tags.topics || [],
          level,
        },
      };

      if (selectedKnowledge) {
        // Update（不包含 scope，因為建立後不能更改）
        await apiRequest(`/${selectedKnowledge.id}`, {
          method: 'PUT',
          body: JSON.stringify(data),
        });
        NotificationModule.show({ title: '更新成功', message: '知識已更新', icon: 'check-circle' });
      } else {
        // Create（包含 scope）
        data.scope = scope;
        const result = await apiRequest('', {
          method: 'POST',
          body: JSON.stringify(data),
        });
        selectedKnowledge = result;
        NotificationModule.show({ title: '建立成功', message: '知識已建立', icon: 'check-circle' });
      }

      isEditing = false;
      editingData = null;
      loadKnowledge();
      if (selectedKnowledge) {
        selectKnowledge(selectedKnowledge.id);
      }
    } catch (error) {
      console.error('Failed to save knowledge:', error);
      NotificationModule.show({ title: '儲存失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  /**
   * Confirm delete knowledge
   */
  function confirmDeleteKnowledge() {
    if (!selectedKnowledge) return;

    const confirmed = confirm(`確定要刪除「${selectedKnowledge.title}」嗎？`);
    if (confirmed) {
      deleteKnowledge();
    }
  }

  /**
   * Delete knowledge
   */
  async function deleteKnowledge() {
    if (!selectedKnowledge) return;

    try {
      await apiRequest(`/${selectedKnowledge.id}`, {
        method: 'DELETE',
      });

      NotificationModule.show({ title: '刪除成功', message: '知識已刪除', icon: 'check-circle' });
      selectedKnowledge = null;

      const windowEl = document.getElementById(windowId);
      if (windowEl) {
        windowEl.querySelector('#kbContentEmpty').style.display = 'flex';
        windowEl.querySelector('#kbContentView').style.display = 'none';
        windowEl.querySelector('#kbEditor').style.display = 'none';
      }

      loadKnowledge();
    } catch (error) {
      console.error('Failed to delete knowledge:', error);
      NotificationModule.show({ title: '刪除失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  /**
   * Load version history
   */
  async function loadHistory() {
    if (!selectedKnowledge) return;

    try {
      historyData = await apiRequest(`/${selectedKnowledge.id}/history`);
      renderHistoryPanel();
    } catch (error) {
      console.error('Failed to load history:', error);
      NotificationModule.show({ title: '載入失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  /**
   * Render history panel
   */
  function renderHistoryPanel() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl || !historyData) return;

    let historyPanel = windowEl.querySelector('.kb-history-panel');
    if (!historyPanel) {
      historyPanel = document.createElement('div');
      historyPanel.className = 'kb-history-panel';
      windowEl.querySelector('.kb-content-panel').appendChild(historyPanel);
    }

    historyPanel.innerHTML = `
      <div class="kb-history-header">
        <span class="kb-history-title">版本歷史</span>
        <button class="kb-history-close" id="kbHistoryClose">
          <span class="icon">${getIcon('close')}</span>
        </button>
      </div>
      <div class="kb-history-list">
        ${historyData.entries.length === 0 ? `
          <div class="kb-empty" style="height: 100px;">
            <span>尚無版本歷史</span>
          </div>
        ` : historyData.entries.map(entry => `
          <div class="kb-history-item" data-commit="${entry.commit}">
            <div class="kb-history-commit">${entry.commit.substring(0, 7)}</div>
            <div class="kb-history-message">${entry.message}</div>
            <div class="kb-history-meta">${entry.author} - ${formatDate(entry.date)}</div>
          </div>
        `).join('')}
      </div>
    `;

    historyPanel.classList.add('open');
    historyOpen = true;

    // Bind events
    historyPanel.querySelector('#kbHistoryClose').addEventListener('click', () => {
      historyPanel.classList.remove('open');
      historyOpen = false;
    });

    historyPanel.querySelectorAll('.kb-history-item').forEach(el => {
      el.addEventListener('click', () => {
        loadVersion(el.dataset.commit);
      });
    });
  }

  /**
   * Load specific version
   */
  async function loadVersion(commit) {
    if (!selectedKnowledge) return;

    try {
      const version = await apiRequest(`/${selectedKnowledge.id}/version/${commit}`);

      // Show version content in a dialog or replace content temporarily
      const windowEl = document.getElementById(windowId);
      if (windowEl) {
        const markdownEl = windowEl.querySelector('#kbMarkdownContent');
        if (markdownEl) {
          if (typeof marked !== 'undefined') {
            markdownEl.innerHTML = marked.parse(version.content);
          } else {
            markdownEl.innerHTML = `<pre>${version.content}</pre>`;
          }
        }

        // Highlight selected version
        windowEl.querySelectorAll('.kb-history-item').forEach(el => {
          el.classList.toggle('selected', el.dataset.commit === commit);
        });
      }
    } catch (error) {
      console.error('Failed to load version:', error);
      NotificationModule.show({ title: '載入失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  // Public API
  return {
    open,
    close,
  };
})();
