/**
 * ChingTech OS - File Manager Module
 * Provides file browsing, preview, and operations for NAS storage
 */

const FileManagerModule = (function() {
  'use strict';

  // State
  let windowId = null;
  let currentPath = '/';
  let history = [];
  let historyIndex = -1;
  let files = [];
  let selectedFiles = new Set();
  let lastSelectedIndex = -1;
  let contextMenu = null;
  let clickTimer = null;
  let isEditingPath = false;
  let previewWidth = 300;
  let isSearching = false;
  let searchQuery = '';
  let searchResults = [];
  let searchTimer = null;
  let mobilePreviewOverlay = null;

  /**
   * Check if current view is mobile
   */
  function isMobileView() {
    return window.innerWidth <= 768;
  }

  // 可分享路徑前綴（對應系統掛載點 /mnt/nas/projects）
  const SHAREABLE_PATH_PREFIX = '/擎添共用區/在案資料分享';

  /**
   * Get auth token
   */
  function getToken() {
    return localStorage.getItem('chingtech_token');
  }

  /**
   * 檢查路徑是否可分享
   * @param {string} path - 檔案管理器路徑
   * @returns {boolean}
   */
  function isShareablePath(path) {
    return path.startsWith(SHAREABLE_PATH_PREFIX);
  }

  /**
   * 將檔案管理器路徑轉換為系統掛載點路徑
   * @param {string} fmPath - 檔案管理器路徑（如 /擎添共用區/在案資料分享/亦達光學/xxx.pdf）
   * @returns {string} - 系統掛載點路徑（如 /mnt/nas/projects/亦達光學/xxx.pdf）
   */
  function toSystemMountPath(fmPath) {
    if (!fmPath.startsWith(SHAREABLE_PATH_PREFIX)) {
      return null;
    }
    // 移除前綴，加上系統掛載點路徑
    const relativePath = fmPath.slice(SHAREABLE_PATH_PREFIX.length);
    return '/mnt/nas/projects' + relativePath;
  }

  /**
   * Get file icon based on type and extension (委派給 FileUtils)
   */
  function getFileIcon(type, name) {
    if (type === 'directory') return 'folder';
    return FileUtils.getFileIcon(name);
  }

  /**
   * Get file type class for styling (委派給 FileUtils)
   */
  function getFileTypeClass(type, name) {
    if (type === 'directory') return 'folder';
    return FileUtils.getFileTypeClass(name);
  }

  /**
   * Format file size (委派給 FileUtils)
   */
  function formatSize(bytes) {
    if (bytes === null || bytes === undefined) return '-';
    return FileUtils.formatFileSize(bytes);
  }

  /**
   * Format date
   */
  function formatDate(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleDateString('zh-TW') + ' ' + date.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' });
  }

  /**
   * Open file manager window
   */
  function open(initialPath = '/') {
    const existing = WindowModule.getWindowByAppId('file-manager');
    if (existing) {
      WindowModule.focusWindow(existing.windowId);
      if (!existing.minimized) return;
      WindowModule.restoreWindow(existing.windowId);
      return;
    }

    currentPath = initialPath;
    history = [initialPath];
    historyIndex = 0;
    selectedFiles.clear();

    windowId = WindowModule.createWindow({
      title: '檔案管理',
      appId: 'file-manager',
      icon: 'folder',
      width: 900,
      height: 600,
      content: renderContent(),
      onClose: handleClose,
      onInit: handleInit
    });
  }

  /**
   * Close file manager
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
    currentPath = '/';
    history = [];
    historyIndex = -1;
    files = [];
    selectedFiles.clear();
    hideContextMenu();
    closeMobilePreview();
  }

  /**
   * Handle window init
   */
  function handleInit(windowEl, wId) {
    windowId = wId;
    bindEvents(windowEl);
    loadDirectory(currentPath);
  }

  /**
   * Render main content
   */
  function renderContent() {
    return `
      <div class="file-manager">
        <div class="fm-toolbar">
          <div class="fm-toolbar-nav">
            <button class="fm-toolbar-btn" id="fmBtnBack" title="上一頁" disabled>
              <span class="icon">${getIcon('chevron-left')}</span>
            </button>
            <button class="fm-toolbar-btn" id="fmBtnForward" title="下一頁" disabled>
              <span class="icon">${getIcon('chevron-right')}</span>
            </button>
            <button class="fm-toolbar-btn" id="fmBtnUp" title="上一層">
              <span class="icon">${getIcon('chevron-up')}</span>
            </button>
            <button class="fm-toolbar-btn" id="fmBtnRefresh" title="重新整理">
              <span class="icon">${getIcon('refresh')}</span>
            </button>
          </div>
          <div class="fm-path-container" id="fmPathContainer">
            <div class="fm-path-input-wrapper" id="fmPathInputWrapper">
              <span class="fm-path-input-icon">
                <span class="icon">${getIcon('folder')}</span>
              </span>
              <input type="text" class="fm-path-input" id="fmPathInput" value="/">
            </div>
            <div class="fm-path-display" id="fmPathDisplay">
              <span class="icon">${getIcon('folder')}</span>
              <span class="fm-path-text" id="fmPathText">/</span>
            </div>
          </div>
          <div class="fm-search-container">
            <span class="fm-search-icon">
              <span class="icon">${getIcon('search')}</span>
            </span>
            <input type="text" class="fm-search-input" id="fmSearchInput" placeholder="搜尋...">
            <button class="fm-search-clear" id="fmSearchClear" title="清除搜尋" style="display: none;">
              <span class="icon">${getIcon('close')}</span>
            </button>
          </div>
          <div class="fm-toolbar-actions">
            <button class="fm-action-btn" id="fmBtnUpload" title="上傳檔案">
              <span class="icon">${getIcon('upload')}</span>
              <span>上傳</span>
            </button>
            <button class="fm-action-btn" id="fmBtnNewFolder" title="新增資料夾">
              <span class="icon">${getIcon('folder-plus')}</span>
              <span>新增</span>
            </button>
          </div>
        </div>
        <div class="fm-main">
          <div class="fm-file-list" id="fmFileList">
            <div class="fm-list-header">
              <span class="fm-list-header-name">名稱</span>
              <span class="fm-list-header-size">大小</span>
              <span class="fm-list-header-date">修改日期</span>
            </div>
            <div class="fm-loading">
              <span class="icon">${getIcon('folder')}</span>
              <span>載入中...</span>
            </div>
          </div>
          <div class="fm-resizer" id="fmResizer"></div>
          <div class="fm-preview" id="fmPreview" style="width: ${previewWidth}px;">
            <div class="fm-preview-header">預覽</div>
            <div class="fm-preview-content">
              <div class="fm-preview-empty">
                <span class="icon">${getIcon('file')}</span>
                <span>選取檔案以預覽</span>
              </div>
            </div>
          </div>
        </div>
        <div class="fm-statusbar">
          <div class="fm-statusbar-info">
            <span id="fmStatusTotal">0 個項目</span>
            <span id="fmStatusSelected"></span>
          </div>
        </div>
        <input type="file" class="fm-upload-input" id="fmUploadInput" multiple>
      </div>
    `;
  }

  /**
   * Bind events
   */
  function bindEvents(windowEl) {
    // Navigation buttons
    windowEl.querySelector('#fmBtnBack').addEventListener('click', navigateBack);
    windowEl.querySelector('#fmBtnForward').addEventListener('click', navigateForward);
    windowEl.querySelector('#fmBtnUp').addEventListener('click', navigateUp);
    windowEl.querySelector('#fmBtnRefresh').addEventListener('click', refresh);

    // Action buttons
    windowEl.querySelector('#fmBtnUpload').addEventListener('click', () => {
      windowEl.querySelector('#fmUploadInput').click();
    });
    windowEl.querySelector('#fmBtnNewFolder').addEventListener('click', showNewFolderDialog);

    // Upload input
    windowEl.querySelector('#fmUploadInput').addEventListener('change', handleUpload);

    // Path display click - enter edit mode
    windowEl.querySelector('#fmPathDisplay').addEventListener('click', enterPathEditMode);

    // Path input events
    const pathInput = windowEl.querySelector('#fmPathInput');
    pathInput.addEventListener('keydown', handlePathInputKeydown);
    pathInput.addEventListener('blur', exitPathEditMode);

    // Search input events
    const searchInput = windowEl.querySelector('#fmSearchInput');
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        if (searchTimer) clearTimeout(searchTimer);
        searchFiles(searchInput.value);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        clearSearch();
      }
    });
    searchInput.addEventListener('input', (e) => {
      // Debounce search for auto-search (optional)
      if (searchTimer) clearTimeout(searchTimer);
      const value = e.target.value;
      if (!value.trim()) {
        clearSearch();
      }
    });

    // Search clear button
    windowEl.querySelector('#fmSearchClear').addEventListener('click', clearSearch);

    // File list events
    const fileList = windowEl.querySelector('#fmFileList');
    fileList.addEventListener('click', (e) => {
      const item = e.target.closest('.fm-file-item');
      if (!item) return;

      if (clickTimer) {
        clearTimeout(clickTimer);
        clickTimer = null;
      }

      clickTimer = setTimeout(() => {
        handleFileListClick(e);
        clickTimer = null;
      }, 200);
    });

    fileList.addEventListener('dblclick', (e) => {
      if (clickTimer) {
        clearTimeout(clickTimer);
        clickTimer = null;
      }
      handleFileListDblClick(e);
    });
    fileList.addEventListener('contextmenu', handleContextMenu);

    // Resizer drag
    const resizer = windowEl.querySelector('#fmResizer');
    resizer.addEventListener('mousedown', startResize);

    // Global click to close context menu
    document.addEventListener('click', hideContextMenu);
  }

  /**
   * Enter path edit mode
   */
  function enterPathEditMode() {
    if (isEditingPath) return;
    isEditingPath = true;

    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const inputWrapper = windowEl.querySelector('#fmPathInputWrapper');
    const pathDisplay = windowEl.querySelector('#fmPathDisplay');
    const pathInput = windowEl.querySelector('#fmPathInput');

    inputWrapper.classList.add('active');
    pathDisplay.style.display = 'none';
    pathInput.value = currentPath;
    pathInput.focus();
    pathInput.select();
  }

  /**
   * Exit path edit mode
   */
  function exitPathEditMode() {
    if (!isEditingPath) return;
    isEditingPath = false;

    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const inputWrapper = windowEl.querySelector('#fmPathInputWrapper');
    const pathDisplay = windowEl.querySelector('#fmPathDisplay');

    inputWrapper.classList.remove('active');
    pathDisplay.style.display = 'flex';
  }

  /**
   * Handle path input keydown
   */
  function handlePathInputKeydown(e) {
    if (e.key === 'Enter') {
      const newPath = e.target.value.trim();
      if (newPath && newPath !== currentPath) {
        navigateTo(newPath);
      }
      exitPathEditMode();
    } else if (e.key === 'Escape') {
      exitPathEditMode();
    }
  }

  /**
   * Start resizer drag
   */
  function startResize(e) {
    e.preventDefault();
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const resizer = windowEl.querySelector('#fmResizer');
    const preview = windowEl.querySelector('#fmPreview');
    const main = windowEl.querySelector('.fm-main');

    resizer.classList.add('dragging');

    const startX = e.clientX;
    const startWidth = preview.offsetWidth;
    const mainRect = main.getBoundingClientRect();

    function onMouseMove(e) {
      const dx = startX - e.clientX;
      let newWidth = startWidth + dx;

      // Constrain width
      const minWidth = 200;
      const maxWidth = mainRect.width * 0.5;
      newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));

      preview.style.width = `${newWidth}px`;
      previewWidth = newWidth;
    }

    function onMouseUp() {
      resizer.classList.remove('dragging');
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }

  /**
   * Load directory contents
   */
  async function loadDirectory(path) {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const fileList = windowEl.querySelector('#fmFileList');
    const pathText = windowEl.querySelector('#fmPathText');

    // Show loading
    fileList.innerHTML = `
      <div class="fm-list-header">
        <span class="fm-list-header-name">名稱</span>
        <span class="fm-list-header-size">大小</span>
        <span class="fm-list-header-date">修改日期</span>
      </div>
      <div class="fm-loading">
        <span class="icon">${getIcon('folder')}</span>
        <span>載入中...</span>
      </div>
    `;

    try {
      if (path === '/') {
        const response = await fetch('/api/nas/shares', {
          headers: { 'Authorization': `Bearer ${getToken()}` }
        });

        if (!response.ok) throw new Error('無法取得共享資料夾');
        const data = await response.json();

        files = data.shares.map(share => ({
          name: share.name,
          type: 'directory',
          size: null,
          modified: null
        }));
      } else {
        const response = await fetch(`/api/nas/browse?path=${encodeURIComponent(path)}`, {
          headers: { 'Authorization': `Bearer ${getToken()}` }
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || '載入失敗');
        }
        const data = await response.json();
        files = data.items;
      }

      currentPath = path;
      pathText.textContent = path;
      selectedFiles.clear();
      lastSelectedIndex = -1;

      renderFileList();
      updateNavButtons();
      updateStatusBar();
      renderPreview();

    } catch (error) {
      fileList.innerHTML = `
        <div class="fm-list-header">
          <span class="fm-list-header-name">名稱</span>
          <span class="fm-list-header-size">大小</span>
          <span class="fm-list-header-date">修改日期</span>
        </div>
        <div class="fm-empty">
          <span class="icon">${getIcon('information')}</span>
          <span>${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * Search files
   */
  async function searchFiles(query) {
    if (!query || !query.trim()) {
      clearSearch();
      return;
    }

    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const fileList = windowEl.querySelector('#fmFileList');
    const clearBtn = windowEl.querySelector('#fmSearchClear');

    isSearching = true;
    searchQuery = query.trim();

    // Show clear button
    if (clearBtn) clearBtn.style.display = 'flex';

    // Show loading
    fileList.innerHTML = `
      <div class="fm-list-header">
        <span class="fm-list-header-name">名稱</span>
        <span class="fm-list-header-size">路徑</span>
        <span class="fm-list-header-date">類型</span>
      </div>
      <div class="fm-loading">
        <span class="icon">${getIcon('search')}</span>
        <span>搜尋中...</span>
      </div>
    `;

    try {
      const response = await fetch(
        `/api/nas/search?path=${encodeURIComponent(currentPath)}&query=${encodeURIComponent(searchQuery)}&max_depth=5&max_results=100`,
        { headers: { 'Authorization': `Bearer ${getToken()}` } }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '搜尋失敗');
      }

      const data = await response.json();
      searchResults = data.results;

      renderSearchResults();
      updateStatusBar();

    } catch (error) {
      fileList.innerHTML = `
        <div class="fm-list-header">
          <span class="fm-list-header-name">名稱</span>
          <span class="fm-list-header-size">路徑</span>
          <span class="fm-list-header-date">類型</span>
        </div>
        <div class="fm-empty">
          <span class="icon">${getIcon('information')}</span>
          <span>${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * Render search results
   */
  function renderSearchResults() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const fileList = windowEl.querySelector('#fmFileList');

    if (searchResults.length === 0) {
      fileList.innerHTML = `
        <div class="fm-list-header">
          <span class="fm-list-header-name">名稱</span>
          <span class="fm-list-header-size">路徑</span>
          <span class="fm-list-header-date">類型</span>
        </div>
        <div class="fm-empty">
          <span class="icon">${getIcon('search')}</span>
          <span>找不到符合「${searchQuery}」的項目</span>
        </div>
      `;
      return;
    }

    let html = `
      <div class="fm-list-header">
        <span class="fm-list-header-name">名稱</span>
        <span class="fm-list-header-size">路徑</span>
        <span class="fm-list-header-date">類型</span>
      </div>
    `;

    searchResults.forEach((item, index) => {
      const iconName = getFileIcon(item.type, item.name);
      const typeClass = getFileTypeClass(item.type, item.name);
      const typeLabel = item.type === 'directory' ? '資料夾' : '檔案';

      html += `
        <div class="fm-file-item fm-search-result ${typeClass}"
             data-index="${index}"
             data-path="${item.path}"
             data-type="${item.type}">
          <span class="fm-file-icon">
            <span class="icon">${getIcon(iconName)}</span>
          </span>
          <span class="fm-file-name">${item.name}</span>
          <span class="fm-file-size">${item.path}</span>
          <span class="fm-file-modified">${typeLabel}</span>
        </div>
      `;
    });

    fileList.innerHTML = html;

    // Add click handlers for search results
    fileList.querySelectorAll('.fm-search-result').forEach(el => {
      el.addEventListener('dblclick', handleSearchResultDoubleClick);
    });
  }

  /**
   * Handle search result double click
   */
  function handleSearchResultDoubleClick(e) {
    const item = e.currentTarget;
    const path = item.dataset.path;
    const type = item.dataset.type;

    clearSearch();

    if (type === 'directory') {
      navigateTo(path);
    } else {
      // Navigate to parent folder
      const parentPath = path.substring(0, path.lastIndexOf('/')) || '/';
      navigateTo(parentPath);
    }
  }

  /**
   * Clear search and return to normal browsing
   */
  function clearSearch() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const searchInput = windowEl.querySelector('#fmSearchInput');
    const clearBtn = windowEl.querySelector('#fmSearchClear');

    isSearching = false;
    searchQuery = '';
    searchResults = [];

    if (searchInput) searchInput.value = '';
    if (clearBtn) clearBtn.style.display = 'none';

    loadDirectory(currentPath);
  }

  /**
   * Render file list
   */
  function renderFileList() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const fileList = windowEl.querySelector('#fmFileList');

    if (files.length === 0) {
      fileList.innerHTML = `
        <div class="fm-list-header">
          <span class="fm-list-header-name">名稱</span>
          <span class="fm-list-header-size">大小</span>
          <span class="fm-list-header-date">修改日期</span>
        </div>
        <div class="fm-empty">
          <span class="icon">${getIcon('folder')}</span>
          <span>資料夾是空的</span>
        </div>
      `;
      return;
    }

    // Sort: folders first, then files, alphabetically
    const sorted = [...files].sort((a, b) => {
      if (a.type === 'directory' && b.type !== 'directory') return -1;
      if (a.type !== 'directory' && b.type === 'directory') return 1;
      return a.name.localeCompare(b.name, 'zh-TW');
    });

    const header = `
      <div class="fm-list-header">
        <span class="fm-list-header-name">名稱</span>
        <span class="fm-list-header-size">大小</span>
        <span class="fm-list-header-date">修改日期</span>
      </div>
    `;

    const items = sorted.map((file, index) => {
      const iconName = getFileIcon(file.type, file.name);
      const typeClass = getFileTypeClass(file.type, file.name);
      const isSelected = selectedFiles.has(file.name);

      return `
        <div class="fm-file-item ${isSelected ? 'selected' : ''}" data-index="${index}" data-name="${file.name}" data-type="${file.type}">
          <div class="fm-file-icon ${typeClass}">
            <span class="icon">${getIcon(iconName)}</span>
          </div>
          <span class="fm-file-name">${file.name}</span>
          <span class="fm-file-size">${formatSize(file.size)}</span>
          <span class="fm-file-modified">${formatDate(file.modified)}</span>
        </div>
      `;
    }).join('');

    fileList.innerHTML = header + items;
    files = sorted;
  }

  /**
   * Handle file list click (selection)
   */
  function handleFileListClick(e) {
    const item = e.target.closest('.fm-file-item');
    if (!item) return;

    const index = parseInt(item.dataset.index);
    const name = item.dataset.name;
    const ctrlKey = e.ctrlKey || e.metaKey;
    const shiftKey = e.shiftKey;

    if (shiftKey && lastSelectedIndex !== -1) {
      const start = Math.min(lastSelectedIndex, index);
      const end = Math.max(lastSelectedIndex, index);
      if (!ctrlKey) selectedFiles.clear();
      for (let i = start; i <= end; i++) {
        selectedFiles.add(files[i].name);
      }
    } else if (ctrlKey) {
      if (selectedFiles.has(name)) {
        selectedFiles.delete(name);
      } else {
        selectedFiles.add(name);
      }
      lastSelectedIndex = index;
    } else {
      selectedFiles.clear();
      selectedFiles.add(name);
      lastSelectedIndex = index;
    }

    renderFileList();
    updateStatusBar();

    // 手機版：單擊即可操作
    if (isMobileView() && selectedFiles.size === 1) {
      const selectedName = [...selectedFiles][0];
      const file = files.find(f => f.name === selectedName);
      if (file) {
        if (file.type === 'directory') {
          // 單擊資料夾 → 進入
          const newPath = currentPath === '/' ? `/${file.name}` : `${currentPath}/${file.name}`;
          navigateTo(newPath);
        } else {
          // 單擊檔案 → 顯示預覽
          showMobilePreview(file);
        }
      }
    } else {
      renderPreview();
    }
  }

  /**
   * Handle file list double click (open)
   */
  function handleFileListDblClick(e) {
    const item = e.target.closest('.fm-file-item');
    if (!item) return;

    const name = item.dataset.name;
    const type = item.dataset.type;

    if (type === 'directory') {
      const newPath = currentPath === '/' ? `/${name}` : `${currentPath}/${name}`;
      navigateTo(newPath);
    } else {
      openFile(name);
    }
  }

  /**
   * Open file in appropriate viewer
   */
  function openFile(name) {
    const filePath = currentPath === '/' ? `/${name}` : `${currentPath}/${name}`;

    // 使用 FileOpener 統一入口開啟檔案
    if (typeof FileOpener !== 'undefined' && FileOpener.canOpen(name)) {
      FileOpener.open(filePath, name);
    }
  }

  /**
   * Handle context menu
   */
  function handleContextMenu(e) {
    e.preventDefault();

    const item = e.target.closest('.fm-file-item');
    if (item) {
      const name = item.dataset.name;
      if (!selectedFiles.has(name)) {
        selectedFiles.clear();
        selectedFiles.add(name);
        renderFileList();
        updateStatusBar();
      }
    }

    showContextMenu(e.clientX, e.clientY, !!item);
  }

  /**
   * Show context menu
   */
  function showContextMenu(x, y, hasSelection) {
    hideContextMenu();

    const selectedFile = selectedFiles.size === 1 ? files.find(f => selectedFiles.has(f.name)) : null;
    const isFile = selectedFile && selectedFile.type !== 'directory';

    let menuItems = '';

    if (hasSelection && selectedFiles.size > 0) {
      if (selectedFiles.size === 1 && selectedFile) {
        if (selectedFile.type === 'directory') {
          menuItems += `<div class="fm-context-menu-item" data-action="open"><span class="icon">${getIcon('folder')}</span>開啟</div>`;
        } else {
          menuItems += `<div class="fm-context-menu-item" data-action="open"><span class="icon">${getIcon('file')}</span>開啟</div>`;
        }
      }
      if (isFile) {
        menuItems += `<div class="fm-context-menu-item" data-action="download"><span class="icon">${getIcon('download')}</span>下載</div>`;
        // 只對可分享路徑下的檔案顯示「產生分享連結」選項
        if (isShareablePath(currentPath)) {
          menuItems += `<div class="fm-context-menu-item" data-action="share"><span class="icon">${getIcon('share-variant')}</span>產生分享連結</div>`;
        }
      }
      menuItems += `<div class="fm-context-menu-divider"></div>`;
      if (selectedFiles.size === 1) {
        menuItems += `<div class="fm-context-menu-item" data-action="rename"><span class="icon">${getIcon('edit')}</span>重命名</div>`;
      }
      menuItems += `<div class="fm-context-menu-item danger" data-action="delete"><span class="icon">${getIcon('delete')}</span>刪除</div>`;
    } else {
      menuItems += `<div class="fm-context-menu-item" data-action="refresh"><span class="icon">${getIcon('refresh')}</span>重新整理</div>`;
      menuItems += `<div class="fm-context-menu-divider"></div>`;
      menuItems += `<div class="fm-context-menu-item" data-action="upload"><span class="icon">${getIcon('upload')}</span>上傳檔案</div>`;
      menuItems += `<div class="fm-context-menu-item" data-action="newfolder"><span class="icon">${getIcon('folder-plus')}</span>新增資料夾</div>`;
    }

    contextMenu = document.createElement('div');
    contextMenu.className = 'fm-context-menu';
    contextMenu.innerHTML = menuItems;
    contextMenu.style.left = `${x}px`;
    contextMenu.style.top = `${y}px`;

    document.body.appendChild(contextMenu);

    const rect = contextMenu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      contextMenu.style.left = `${x - rect.width}px`;
    }
    if (rect.bottom > window.innerHeight) {
      contextMenu.style.top = `${y - rect.height}px`;
    }

    contextMenu.addEventListener('click', handleContextMenuClick);
  }

  /**
   * Hide context menu
   */
  function hideContextMenu() {
    if (contextMenu) {
      contextMenu.remove();
      contextMenu = null;
    }
  }

  /**
   * Handle context menu click
   */
  function handleContextMenuClick(e) {
    const item = e.target.closest('.fm-context-menu-item');
    if (!item) return;

    const action = item.dataset.action;
    hideContextMenu();

    switch (action) {
      case 'open':
        const selectedName = [...selectedFiles][0];
        const selectedFile = files.find(f => f.name === selectedName);
        if (selectedFile.type === 'directory') {
          const newPath = currentPath === '/' ? `/${selectedName}` : `${currentPath}/${selectedName}`;
          navigateTo(newPath);
        } else {
          openFile(selectedName);
        }
        break;
      case 'download':
        downloadSelected();
        break;
      case 'share':
        showShareDialog();
        break;
      case 'rename':
        showRenameDialog();
        break;
      case 'delete':
        showDeleteDialog();
        break;
      case 'refresh':
        refresh();
        break;
      case 'upload':
        document.getElementById(windowId).querySelector('#fmUploadInput').click();
        break;
      case 'newfolder':
        showNewFolderDialog();
        break;
    }
  }

  /**
   * Navigate to path
   */
  function navigateTo(path) {
    history = history.slice(0, historyIndex + 1);
    history.push(path);
    historyIndex = history.length - 1;
    loadDirectory(path);
  }

  /**
   * Navigate back
   */
  function navigateBack() {
    if (historyIndex > 0) {
      historyIndex--;
      loadDirectory(history[historyIndex]);
    }
  }

  /**
   * Navigate forward
   */
  function navigateForward() {
    if (historyIndex < history.length - 1) {
      historyIndex++;
      loadDirectory(history[historyIndex]);
    }
  }

  /**
   * Navigate up
   */
  function navigateUp() {
    if (currentPath === '/') return;
    const parts = currentPath.split('/').filter(Boolean);
    parts.pop();
    const parentPath = parts.length === 0 ? '/' : '/' + parts.join('/');
    navigateTo(parentPath);
  }

  /**
   * Refresh current directory
   */
  function refresh() {
    loadDirectory(currentPath);
  }

  /**
   * Update navigation buttons state
   */
  function updateNavButtons() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    windowEl.querySelector('#fmBtnBack').disabled = historyIndex <= 0;
    windowEl.querySelector('#fmBtnForward').disabled = historyIndex >= history.length - 1;
    windowEl.querySelector('#fmBtnUp').disabled = currentPath === '/';
  }

  /**
   * Update status bar
   */
  function updateStatusBar() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    if (isSearching) {
      windowEl.querySelector('#fmStatusTotal').textContent = `搜尋「${searchQuery}」找到 ${searchResults.length} 個結果`;
      windowEl.querySelector('#fmStatusSelected').textContent = '';
    } else {
      windowEl.querySelector('#fmStatusTotal').textContent = `${files.length} 個項目`;
      const selectedCount = selectedFiles.size;
      windowEl.querySelector('#fmStatusSelected').textContent = selectedCount > 0 ? `選取 ${selectedCount} 個` : '';
    }
  }

  /**
   * Render preview panel - New layout: preview on top, info below
   */
  async function renderPreview() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const previewContent = windowEl.querySelector('#fmPreview .fm-preview-content');

    if (selectedFiles.size !== 1) {
      previewContent.innerHTML = `
        <div class="fm-preview-empty">
          <span class="icon">${getIcon('file')}</span>
          <span>${selectedFiles.size > 1 ? `已選取 ${selectedFiles.size} 個項目` : '選取檔案以預覽'}</span>
        </div>
      `;
      return;
    }

    const selectedName = [...selectedFiles][0];
    const file = files.find(f => f.name === selectedName);
    if (!file) return;

    const iconName = getFileIcon(file.type, file.name);
    const ext = file.name.split('.').pop().toLowerCase();
    const filePath = currentPath === '/' ? `/${file.name}` : `${currentPath}/${file.name}`;

    // Build preview HTML - preview area first, then info
    let previewMainHTML = '';

    if (file.type === 'directory') {
      previewMainHTML = `
        <div class="fm-preview-icon-large">
          <span class="icon">${getIcon('folder')}</span>
        </div>
      `;
    } else if (FileUtils.isImageFile(file.name)) {
      previewMainHTML = `
        <div class="fm-preview-image">
          <img src="${window.API_BASE || ''}/api/nas/file?path=${encodeURIComponent(filePath)}&token=${encodeURIComponent(getToken())}" alt="${file.name}">
        </div>
      `;
    } else if (FileUtils.isTextFile(file.name)) {
      previewMainHTML = `<div class="fm-preview-text" id="fmPreviewText">載入中...</div>`;
    } else {
      previewMainHTML = `
        <div class="fm-preview-icon-large">
          <span class="icon">${getIcon(iconName)}</span>
        </div>
      `;
    }

    const previewHTML = `
      <div class="fm-preview-main">
        ${previewMainHTML}
      </div>
      <div class="fm-preview-info">
        <div class="fm-preview-filename">${file.name}</div>
        <div class="fm-preview-meta">
          <div class="fm-preview-meta-item">
            <span class="fm-preview-meta-label">類型:</span>
            <span class="fm-preview-meta-value">${file.type === 'directory' ? '資料夾' : ext.toUpperCase()}</span>
          </div>
          ${file.size !== null ? `
          <div class="fm-preview-meta-item">
            <span class="fm-preview-meta-label">大小:</span>
            <span class="fm-preview-meta-value">${formatSize(file.size)}</span>
          </div>
          ` : ''}
          ${file.modified ? `
          <div class="fm-preview-meta-item">
            <span class="fm-preview-meta-label">修改:</span>
            <span class="fm-preview-meta-value">${formatDate(file.modified)}</span>
          </div>
          ` : ''}
        </div>
      </div>
    `;

    previewContent.innerHTML = previewHTML;

    // Load text content async
    if (FileUtils.isTextFile(file.name)) {
      try {
        const response = await fetch(`/api/nas/file?path=${encodeURIComponent(filePath)}`, {
          headers: { 'Authorization': `Bearer ${getToken()}` }
        });
        if (response.ok) {
          const text = await response.text();
          const previewText = windowEl.querySelector('#fmPreviewText');
          if (previewText) {
            const lines = text.split('\n').slice(0, 50);
            previewText.textContent = lines.join('\n') + (text.split('\n').length > 50 ? '\n...' : '');
          }
        }
      } catch (e) {
        const previewText = windowEl.querySelector('#fmPreviewText');
        if (previewText) previewText.textContent = '無法載入預覽';
      }
    }
  }

  /**
   * Show mobile full-screen preview
   */
  async function showMobilePreview(file) {
    if (mobilePreviewOverlay) {
      closeMobilePreview();
    }

    const iconName = getFileIcon(file.type, file.name);
    const ext = file.name.split('.').pop().toLowerCase();
    const filePath = currentPath === '/' ? `/${file.name}` : `${currentPath}/${file.name}`;
    const canShare = isShareablePath(currentPath);

    // Build preview content
    let previewMainHTML = '';

    if (FileUtils.isImageFile(file.name)) {
      previewMainHTML = `
        <div class="fm-mobile-preview-image">
          <img src="${window.API_BASE || ''}/api/nas/file?path=${encodeURIComponent(filePath)}&token=${encodeURIComponent(getToken())}" alt="${file.name}">
        </div>
      `;
    } else if (FileUtils.isTextFile(file.name)) {
      previewMainHTML = `<div class="fm-mobile-preview-text" id="fmMobilePreviewText">載入中...</div>`;
    } else {
      previewMainHTML = `
        <div class="fm-mobile-preview-icon-large">
          <span class="icon">${getIcon(iconName)}</span>
          <span class="fm-preview-type">${ext}</span>
        </div>
      `;
    }

    mobilePreviewOverlay = document.createElement('div');
    mobilePreviewOverlay.className = 'fm-mobile-preview-overlay';
    mobilePreviewOverlay.innerHTML = `
      <div class="fm-mobile-preview-header">
        <button class="fm-mobile-preview-back" id="fmMobilePreviewBack">
          <span class="icon">${getIcon('chevron-left')}</span>
        </button>
        <span class="fm-mobile-preview-title">${file.name}</span>
        <div class="fm-mobile-preview-actions">
          <button class="fm-mobile-preview-action-btn" id="fmMobilePreviewDownload" title="下載">
            <span class="icon">${getIcon('download')}</span>
          </button>
          ${canShare ? `
          <button class="fm-mobile-preview-action-btn" id="fmMobilePreviewShare" title="分享">
            <span class="icon">${getIcon('share-variant')}</span>
          </button>
          ` : ''}
        </div>
      </div>
      <div class="fm-mobile-preview-content">
        <div class="fm-mobile-preview-main">
          ${previewMainHTML}
        </div>
        <div class="fm-mobile-preview-info">
          <div class="fm-preview-meta">
            <div class="fm-preview-meta-item">
              <span class="fm-preview-meta-label">類型</span>
              <span class="fm-preview-meta-value">${ext.toUpperCase()}</span>
            </div>
            ${file.size !== null ? `
            <div class="fm-preview-meta-item">
              <span class="fm-preview-meta-label">大小</span>
              <span class="fm-preview-meta-value">${formatSize(file.size)}</span>
            </div>
            ` : ''}
            ${file.modified ? `
            <div class="fm-preview-meta-item">
              <span class="fm-preview-meta-label">修改日期</span>
              <span class="fm-preview-meta-value">${formatDate(file.modified)}</span>
            </div>
            ` : ''}
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(mobilePreviewOverlay);

    // Bind events
    mobilePreviewOverlay.querySelector('#fmMobilePreviewBack').addEventListener('click', closeMobilePreview);
    mobilePreviewOverlay.querySelector('#fmMobilePreviewDownload').addEventListener('click', () => {
      downloadSelected();
      closeMobilePreview();
    });

    const shareBtn = mobilePreviewOverlay.querySelector('#fmMobilePreviewShare');
    if (shareBtn) {
      shareBtn.addEventListener('click', () => {
        closeMobilePreview();
        showShareDialog();
      });
    }

    // Load text content async
    if (FileUtils.isTextFile(file.name)) {
      try {
        const response = await fetch(`/api/nas/file?path=${encodeURIComponent(filePath)}`, {
          headers: { 'Authorization': `Bearer ${getToken()}` }
        });
        if (response.ok) {
          const text = await response.text();
          const previewText = mobilePreviewOverlay.querySelector('#fmMobilePreviewText');
          if (previewText) {
            const lines = text.split('\n').slice(0, 100);
            previewText.textContent = lines.join('\n') + (text.split('\n').length > 100 ? '\n...' : '');
          }
        }
      } catch (e) {
        const previewText = mobilePreviewOverlay.querySelector('#fmMobilePreviewText');
        if (previewText) previewText.textContent = '無法載入預覽';
      }
    }
  }

  /**
   * Close mobile preview
   */
  function closeMobilePreview() {
    if (mobilePreviewOverlay) {
      mobilePreviewOverlay.remove();
      mobilePreviewOverlay = null;
    }
  }

  /**
   * Show share dialog for selected file
   */
  function showShareDialog() {
    if (selectedFiles.size !== 1) return;
    const name = [...selectedFiles][0];
    const filePath = currentPath === '/' ? `/${name}` : `${currentPath}/${name}`;

    // 檢查是否在可分享路徑
    if (!isShareablePath(filePath)) {
      if (typeof DesktopModule !== 'undefined') {
        DesktopModule.showToast('此檔案無法產生公開連結', 'error');
      }
      return;
    }

    // 轉換為系統掛載點路徑
    const systemPath = toSystemMountPath(filePath);
    if (!systemPath) {
      if (typeof DesktopModule !== 'undefined') {
        DesktopModule.showToast('路徑轉換失敗', 'error');
      }
      return;
    }

    // 呼叫 ShareDialogModule
    if (typeof ShareDialogModule !== 'undefined') {
      ShareDialogModule.show({
        resourceType: 'nas_file',
        resourceId: systemPath,
        resourceTitle: name
      });
    } else {
      console.error('ShareDialogModule not available');
      if (typeof DesktopModule !== 'undefined') {
        DesktopModule.showToast('分享功能尚未載入', 'error');
      }
    }
  }

  /**
   * Download selected file
   */
  async function downloadSelected() {
    if (selectedFiles.size !== 1) return;
    const name = [...selectedFiles][0];
    const filePath = currentPath === '/' ? `/${name}` : `${currentPath}/${name}`;

    try {
      // 使用 fetch 帶認證 token 下載
      const response = await fetch(`/api/nas/download?path=${encodeURIComponent(filePath)}`, {
        headers: { 'Authorization': `Bearer ${getToken()}` }
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: '下載失敗' }));
        throw new Error(error.detail || '下載失敗');
      }

      // 將回應轉換為 Blob 並下載
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = name;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('下載失敗:', error);
      alert(`下載失敗：${error.message}`);
    }
  }

  /**
   * Handle file upload
   */
  async function handleUpload(e) {
    const uploadFiles = e.target.files;
    if (!uploadFiles || uploadFiles.length === 0) return;

    for (const file of uploadFiles) {
      const formData = new FormData();
      formData.append('path', currentPath);
      formData.append('file', file);

      try {
        const response = await fetch('/api/nas/upload', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${getToken()}` },
          body: formData
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || '上傳失敗');
        }
      } catch (error) {
        DesktopModule.showToast(error.message, 'error');
      }
    }

    e.target.value = '';
    refresh();
    DesktopModule.showToast('上傳成功', 'success');
  }

  /**
   * Show new folder dialog
   */
  function showNewFolderDialog() {
    showDialog({
      title: '新增資料夾',
      input: true,
      inputPlaceholder: '資料夾名稱',
      confirmText: '建立',
      onConfirm: async (name) => {
        if (!name.trim()) return;

        const path = currentPath === '/' ? `/${name}` : `${currentPath}/${name}`;
        try {
          const response = await fetch('/api/nas/mkdir', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${getToken()}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path })
          });

          if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '建立失敗');
          }

          refresh();
          DesktopModule.showToast('資料夾建立成功', 'success');
        } catch (error) {
          DesktopModule.showToast(error.message, 'error');
        }
      }
    });
  }

  /**
   * Show rename dialog
   */
  function showRenameDialog() {
    if (selectedFiles.size !== 1) return;
    const oldName = [...selectedFiles][0];

    showDialog({
      title: '重命名',
      input: true,
      inputValue: oldName,
      inputPlaceholder: '新名稱',
      confirmText: '確定',
      onConfirm: async (newName) => {
        if (!newName.trim() || newName === oldName) return;

        const path = currentPath === '/' ? `/${oldName}` : `${currentPath}/${oldName}`;
        try {
          const response = await fetch('/api/nas/rename', {
            method: 'PATCH',
            headers: {
              'Authorization': `Bearer ${getToken()}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path, new_name: newName })
          });

          if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '重命名失敗');
          }

          refresh();
          DesktopModule.showToast('重命名成功', 'success');
        } catch (error) {
          DesktopModule.showToast(error.message, 'error');
        }
      }
    });
  }

  /**
   * Show delete dialog
   */
  function showDeleteDialog() {
    if (selectedFiles.size === 0) return;

    const names = [...selectedFiles];
    const hasFolder = names.some(name => {
      const file = files.find(f => f.name === name);
      return file && file.type === 'directory';
    });

    showDialog({
      title: '確認刪除',
      message: names.length === 1
        ? `確定要刪除「${names[0]}」嗎？`
        : `確定要刪除 ${names.length} 個項目嗎？`,
      warning: hasFolder ? '警告：將會連同資料夾內所有內容一併刪除！' : null,
      confirmText: '刪除',
      confirmDanger: true,
      onConfirm: async () => {
        for (const name of names) {
          const path = currentPath === '/' ? `/${name}` : `${currentPath}/${name}`;
          try {
            const response = await fetch('/api/nas/file', {
              method: 'DELETE',
              headers: {
                'Authorization': `Bearer ${getToken()}`,
                'Content-Type': 'application/json'
              },
              body: JSON.stringify({ path, recursive: true })
            });

            if (!response.ok) {
              const error = await response.json();
              throw new Error(error.detail || '刪除失敗');
            }
          } catch (error) {
            DesktopModule.showToast(`刪除「${name}」失敗：${error.message}`, 'error');
          }
        }

        refresh();
        DesktopModule.showToast('刪除成功', 'success');
      }
    });
  }

  /**
   * Show dialog
   */
  function showDialog(options) {
    const {
      title,
      message,
      warning,
      input,
      inputValue = '',
      inputPlaceholder = '',
      confirmText = '確定',
      confirmDanger = false,
      onConfirm
    } = options;

    const overlay = document.createElement('div');
    overlay.className = 'fm-dialog-overlay';
    overlay.innerHTML = `
      <div class="fm-dialog">
        <div class="fm-dialog-header">
          <span class="fm-dialog-title">${title}</span>
          <button class="fm-dialog-close">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
        <div class="fm-dialog-body">
          ${message ? `<div class="fm-dialog-message">${message}</div>` : ''}
          ${warning ? `<div class="fm-dialog-message warning">${warning}</div>` : ''}
          ${input ? `<input type="text" class="fm-dialog-input" value="${inputValue}" placeholder="${inputPlaceholder}">` : ''}
        </div>
        <div class="fm-dialog-footer">
          <button class="fm-dialog-btn fm-dialog-btn-cancel">取消</button>
          <button class="fm-dialog-btn ${confirmDanger ? 'fm-dialog-btn-danger' : 'fm-dialog-btn-primary'}">${confirmText}</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    const closeDialog = () => overlay.remove();
    const inputEl = overlay.querySelector('.fm-dialog-input');

    overlay.querySelector('.fm-dialog-close').addEventListener('click', closeDialog);
    overlay.querySelector('.fm-dialog-btn-cancel').addEventListener('click', closeDialog);
    overlay.querySelector('.fm-dialog-footer .fm-dialog-btn:last-child').addEventListener('click', () => {
      const value = input ? inputEl.value : null;
      closeDialog();
      if (onConfirm) onConfirm(value);
    });

    if (inputEl) {
      inputEl.focus();
      inputEl.select();
      inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          closeDialog();
          if (onConfirm) onConfirm(inputEl.value);
        } else if (e.key === 'Escape') {
          closeDialog();
        }
      });
    }

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeDialog();
    });
  }

  // Public API
  return {
    open,
    close
  };
})();
