/**
 * ChingTech OS - Code Editor Module
 * Embeds code-server (VS Code) in a desktop window
 */

const CodeEditorModule = (function() {
  'use strict';

  let windowId = null;

  /**
   * Get code-server URL with theme-appropriate settings
   * 使用相對路徑，由 nginx 代理到 code-server
   */
  function getCodeServerUrl() {
    const basePath = window.API_BASE || '';
    return `${basePath}/code/`;
  }

  /**
   * Open code editor window
   */
  function open() {
    // If already open, focus it
    if (windowId && WindowModule.getWindowByAppId('code-editor')) {
      WindowModule.focusWindow(windowId);
      return;
    }

    // Create window with larger default size for better editing experience
    windowId = WindowModule.createWindow({
      title: 'VSCode',
      appId: 'code-editor',
      icon: 'mdi-code-braces',
      width: 1200,
      height: 800,
      content: `
        <div class="code-editor-container">
          <div class="code-editor-loading">
            <span class="icon">${getIcon('mdi-loading')}</span>
            <span>載入中...</span>
          </div>
          <iframe
            class="code-editor-iframe"
            src="${getCodeServerUrl()}"
            allow="clipboard-read; clipboard-write"
          ></iframe>
        </div>
      `,
      onClose: handleClose,
      onInit: handleInit
    });
  }

  /**
   * Handle window initialization
   * @param {HTMLElement} windowEl
   * @param {string} wId
   */
  function handleInit(windowEl, wId) {
    windowId = wId;

    const iframe = windowEl.querySelector('.code-editor-iframe');
    const loading = windowEl.querySelector('.code-editor-loading');

    if (iframe) {
      iframe.addEventListener('load', () => {
        // Hide loading indicator when iframe loads
        if (loading) {
          loading.style.display = 'none';
        }
        iframe.style.opacity = '1';
      });

      iframe.addEventListener('error', () => {
        if (loading) {
          /* [Sprint6] 原: loading.innerHTML = getIcon('mdi-alert-circle') + 無法連線... */
          loading.innerHTML = '';
          UIHelpers.showError(loading, { icon: 'alert-circle', message: '無法連線到 code-server', detail: '請確認服務已啟動 (./scripts/start.sh dev)' });
        }
      });
    }
  }

  /**
   * Handle window close
   */
  function handleClose() {
    windowId = null;
  }

  /**
   * Check if code-server is available
   * @returns {Promise<boolean>}
   */
  async function checkAvailability() {
    try {
      const response = await fetch(getCodeServerUrl(), {
        method: 'HEAD',
        mode: 'no-cors'
      });
      return true;
    } catch (e) {
      return false;
    }
  }

  // Public API
  return {
    open,
    checkAvailability
  };
})();
// 將模組掛載到 window，供 desktop.js lazy-loader 偵測
window.CodeEditorModule = CodeEditorModule;
