/**
 * ChingTech OS - External App Module
 * 通用外部應用程式模組，用於以 iframe 方式整合外部 Web 服務
 */

const ExternalAppModule = (function() {
  'use strict';

  // 追蹤已開啟的視窗
  const openWindows = {};

  // 追蹤待傳送的檔案內容（等待 iframe ready）
  const pendingContent = {};

  // 追蹤 iframe 元素
  const iframeRefs = {};

  /**
   * 開啟外部應用程式視窗
   * @param {Object} config - 應用程式配置
   * @param {string} config.appId - 應用程式 ID
   * @param {string} config.title - 視窗標題
   * @param {string} config.icon - 圖示名稱
   * @param {string} config.url - 外部服務 URL
   * @param {number} [config.width=1000] - 視窗寬度
   * @param {number} [config.height=700] - 視窗高度
   * @param {boolean} [config.maximized=false] - 是否預設最大化
   */
  function open(config) {
    const { appId, title, icon, url, width = 1000, height = 700, maximized = false } = config;

    // 如果已開啟，聚焦到該視窗
    if (openWindows[appId] && WindowModule.getWindowByAppId(appId)) {
      WindowModule.focusWindow(openWindows[appId]);
      return;
    }

    // 建立視窗
    const windowId = WindowModule.createWindow({
      title,
      appId,
      icon,
      width,
      height,
      content: `
        <div class="external-app-container">
          <div class="external-app-loading">
            <span class="icon">${getIcon('mdi-loading')}</span>
            <span>載入中...</span>
          </div>
          <iframe
            class="external-app-iframe"
            src="${url}"
            allow="clipboard-read; clipboard-write"
          ></iframe>
          <div class="external-app-error" style="display: none;">
            <span class="icon">${getIcon('mdi-alert-circle')}</span>
            <span>無法載入外部服務</span>
            <a href="${url}" target="_blank" class="external-app-open-link">
              <span class="icon">${getIcon('mdi-open-in-new')}</span>
              在新視窗開啟
            </a>
          </div>
        </div>
      `,
      onClose: () => handleClose(appId),
      onInit: (windowEl, wId) => handleInit(windowEl, wId, appId, url, maximized)
    });

    openWindows[appId] = windowId;
  }

  /**
   * 處理視窗初始化
   * @param {HTMLElement} windowEl - 視窗元素
   * @param {string} windowId - 視窗 ID
   * @param {string} appId - 應用程式 ID
   * @param {string} url - 外部服務 URL
   * @param {boolean} maximized - 是否最大化
   */
  function handleInit(windowEl, windowId, appId, url, maximized) {
    openWindows[appId] = windowId;

    // 如果需要最大化，在初始化後立即最大化視窗
    if (maximized && typeof WindowModule !== 'undefined') {
      WindowModule.maximizeWindow(windowId);
    }

    const iframe = windowEl.querySelector('.external-app-iframe');
    const loading = windowEl.querySelector('.external-app-loading');
    const error = windowEl.querySelector('.external-app-error');

    if (iframe) {
      // 儲存 iframe 參考供 postMessage 使用
      iframeRefs[appId] = iframe;

      iframe.addEventListener('load', () => {
        // 隱藏載入狀態，顯示 iframe
        if (loading) {
          loading.style.display = 'none';
        }
        iframe.style.opacity = '1';
      });

      // 設定超時檢測（某些跨域情況下 load 事件可能不觸發）
      setTimeout(() => {
        // 如果載入狀態還在顯示，假設載入成功
        if (loading && loading.style.display !== 'none') {
          loading.style.display = 'none';
          iframe.style.opacity = '1';
        }
        // 超時後如果有待傳送內容，嘗試傳送（外部 App 可能沒有實作 ready 訊號）
        if (pendingContent[appId]) {
          sendContentToIframe(appId);
        }
      }, 3000);
    }
  }

  /**
   * 處理視窗關閉
   * @param {string} appId - 應用程式 ID
   */
  function handleClose(appId) {
    delete openWindows[appId];
    delete pendingContent[appId];
    delete iframeRefs[appId];
  }

  /**
   * 開啟外部應用程式並傳送檔案內容
   * @param {Object} config - 應用程式配置（同 open 方法）
   * @param {Object} fileInfo - 檔案資訊
   * @param {string} fileInfo.filename - 檔案名稱
   * @param {string} fileInfo.content - 檔案內容
   */
  function openWithContent(config, fileInfo) {
    const { appId } = config;

    // 儲存待傳送的檔案內容
    pendingContent[appId] = fileInfo;

    // 如果視窗已開啟，直接傳送內容
    if (openWindows[appId] && WindowModule.getWindowByAppId(appId)) {
      WindowModule.focusWindow(openWindows[appId]);
      // 嘗試傳送內容（如果 iframe 已 ready）
      sendContentToIframe(appId);
      return;
    }

    // 開啟視窗
    open(config);
  }

  /**
   * 傳送檔案內容給 iframe
   * @param {string} appId - 應用程式 ID
   */
  function sendContentToIframe(appId) {
    const iframe = iframeRefs[appId];
    const fileInfo = pendingContent[appId];

    if (!iframe || !fileInfo) return;

    try {
      iframe.contentWindow.postMessage({
        type: 'load-file',
        filename: fileInfo.filename,
        content: fileInfo.content
      }, '*');
      console.log(`[ExternalAppModule] 已傳送檔案內容至 ${appId}:`, fileInfo.filename);
      // 傳送後清除待傳送內容
      delete pendingContent[appId];
    } catch (error) {
      console.error(`[ExternalAppModule] 傳送檔案內容失敗:`, error);
    }
  }

  /**
   * 處理來自 iframe 的訊息
   * @param {MessageEvent} event
   */
  function handleMessage(event) {
    const { data } = event;

    if (!data || typeof data !== 'object') return;

    // 處理 ready 訊號
    if (data.type === 'ready' && data.appId) {
      console.log(`[ExternalAppModule] 收到 ${data.appId} ready 訊號`);
      // 傳送待傳送的檔案內容
      sendContentToIframe(data.appId);
    }
  }

  // 監聽來自 iframe 的訊息
  window.addEventListener('message', handleMessage);

  // Public API
  return {
    open,
    openWithContent,
    sendContentToIframe
  };
})();
