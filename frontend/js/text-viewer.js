/**
 * ChingTech OS - Text Viewer Module
 * Displays text files with syntax highlighting (optional)
 */

const TextViewerModule = (function() {
  'use strict';

  // State
  let windowId = null;
  let currentPath = null;
  let currentFilename = null;
  let content = '';
  let lineCount = 0;

  /**
   * Get auth token
   */
  function getToken() {
    return localStorage.getItem('chingtech_token');
  }

  /**
   * Open text viewer
   * @param {string} filePath - Full path to the text file
   * @param {string} filename - Display filename
   */
  function open(filePath, filename) {
    currentPath = filePath;
    currentFilename = filename;
    content = '';
    lineCount = 0;

    // Check if already open
    const existing = WindowModule.getWindowByAppId('text-viewer');
    if (existing) {
      WindowModule.closeWindow(existing.windowId);
    }

    windowId = WindowModule.createWindow({
      title: filename,
      appId: 'text-viewer',
      icon: 'file-document',
      width: 800,
      height: 600,
      content: renderContent(),
      onClose: handleClose,
      onInit: handleInit
    });
  }

  /**
   * Close text viewer
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
    currentPath = null;
    currentFilename = null;
    content = '';
    lineCount = 0;
  }

  /**
   * Handle window init
   */
  function handleInit(windowEl, wId) {
    // Set windowId here since createWindow calls onInit before returning
    windowId = wId;
    loadFile();
  }

  /**
   * Render content
   */
  function renderContent() {
    return `
      <div class="viewer text-viewer">
        <div class="viewer-content text-viewer-content" id="txtViewerContent">
          <div class="text-viewer-loading">
            <span class="icon">${getIcon('file-document')}</span>
            <span>載入中...</span>
          </div>
        </div>
        <div class="viewer-statusbar">
          <span id="txtStatusInfo">${currentFilename}</span>
          <span id="txtStatusLines">-</span>
        </div>
      </div>
    `;
  }

  /**
   * Load file content
   */
  async function loadFile() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const contentEl = windowEl.querySelector('#txtViewerContent');

    try {
      const response = await fetch(`/api/nas/file?path=${encodeURIComponent(currentPath)}`, {
        headers: { 'Authorization': `Bearer ${getToken()}` }
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '載入失敗');
      }

      content = await response.text();
      lineCount = content.split('\n').length;

      // Escape HTML
      const escaped = escapeHtml(content);

      contentEl.innerHTML = `<pre>${escaped}</pre>`;

      // Update status
      updateStatus();

    } catch (error) {
      contentEl.innerHTML = `
        <div class="text-viewer-error">
          <span class="icon">${getIcon('information')}</span>
          <span>${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * Escape HTML special characters
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Update status bar
   */
  function updateStatus() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    windowEl.querySelector('#txtStatusInfo').textContent = currentFilename;
    windowEl.querySelector('#txtStatusLines').textContent = `${lineCount} 行`;
  }

  /**
   * Get file content
   */
  function getContent() {
    return content;
  }

  // Public API
  return {
    open,
    close,
    getContent
  };
})();
