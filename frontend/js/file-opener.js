/**
 * ChingTech OS - FileOpener 統一檔案開啟入口
 * 自動判斷檔案類型並路由到對應的 Viewer 模組
 *
 * [Sprint8] 此模組為檔案路由模組，錯誤回饋使用 NotificationModule（全域 Toast），
 * 因本模組不管理視窗容器，故不直接使用 UIHelpers 容器狀態。
 * Viewer 模組（ImageViewer、TextViewer 等）已各自採用 UIHelpers。
 */

const FileOpener = (function() {
  'use strict';

  // 檔案類型與副檔名對應
  const FILE_TYPES = {
    image: ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp', 'ico'],
    text: ['txt', 'md', 'markdown', 'json', 'yaml', 'yml', 'xml', 'html', 'xhtml', 'css', 'js', 'ts', 'py', 'log', 'ini', 'conf', 'sh', 'sql', 'csv'],
    pdf: ['pdf']
  };

  // Viewer 模組對應（使用函數延遲取得，確保模組已載入）
  const VIEWERS = {
    image: () => (typeof ImageViewerModule !== 'undefined' ? ImageViewerModule : null),
    text: () => (typeof TextViewerModule !== 'undefined' ? TextViewerModule : null),
    pdf: () => (typeof PdfViewerModule !== 'undefined' ? PdfViewerModule : null)
  };

  /**
   * 取得副檔名
   * @param {string} filename
   * @returns {string}
   */
  function getExtension(filename) {
    if (!filename) return '';
    const parts = filename.split('.');
    return parts.length > 1 ? parts.pop().toLowerCase() : '';
  }

  /**
   * 取得檔案對應的 Viewer 類型
   * @param {string} filename
   * @returns {string|null} 'image', 'text', 'pdf', 或 null
   */
  function getViewerType(filename) {
    const ext = getExtension(filename);
    if (!ext) return null;

    for (const [type, extensions] of Object.entries(FILE_TYPES)) {
      if (extensions.includes(ext)) {
        return type;
      }
    }
    return null;
  }

  /**
   * 判斷檔案是否支援開啟
   * @param {string} filename
   * @returns {boolean}
   */
  function canOpen(filename) {
    return getViewerType(filename) !== null;
  }

  /**
   * 開啟檔案
   * @param {string} filePath - 檔案路徑或 URL
   * @param {string} [filename] - 檔案名稱（若不提供則從 filePath 取得）
   * @returns {boolean} 是否成功開啟
   */
  function open(filePath, filename) {
    // 若沒有提供 filename，從 filePath 取得
    const displayName = filename || filePath.split('/').pop().split('?')[0];

    const viewerType = getViewerType(displayName);

    if (!viewerType) {
      NotificationModule?.show?.(`不支援的檔案類型: ${displayName}`, 'warning');
      console.warn(`[FileOpener] 不支援的檔案類型: ${displayName}`);
      return false;
    }

    const viewer = VIEWERS[viewerType]?.();

    if (!viewer) {
      NotificationModule?.show?.(`檢視器尚未載入: ${viewerType}`, 'error');
      console.error(`[FileOpener] 檢視器尚未載入: ${viewerType}`);
      return false;
    }

    try {
      viewer.open(filePath, displayName);
      return true;
    } catch (error) {
      console.error(`[FileOpener] 開啟檔案失敗:`, error);
      NotificationModule?.show?.(`開啟檔案失敗: ${error.message}`, 'error');
      return false;
    }
  }

  /**
   * 註冊新的 Viewer 類型（擴展用）
   * @param {string} type - 類型名稱
   * @param {Object} config - 設定
   * @param {string[]} config.extensions - 支援的副檔名
   * @param {Function} config.getModule - 取得模組的函數
   */
  function registerViewer(type, config) {
    if (!type || !config.extensions || !config.getModule) {
      console.error('[FileOpener] 註冊 Viewer 失敗: 缺少必要參數');
      return false;
    }

    FILE_TYPES[type] = config.extensions;
    VIEWERS[type] = config.getModule;
    console.log(`[FileOpener] 已註冊 Viewer: ${type}`);
    return true;
  }

  /**
   * 取得所有支援的副檔名
   * @returns {string[]}
   */
  function getSupportedExtensions() {
    return Object.values(FILE_TYPES).flat();
  }

  /**
   * 取得檔案類型對應表（唯讀副本）
   * @returns {Object}
   */
  function getFileTypes() {
    return JSON.parse(JSON.stringify(FILE_TYPES));
  }

  /**
   * 取得外部 App 配置
   * @param {string} appType - 'md2ppt' 或 'md2doc'
   * @returns {Object|null}
   */
  function getExternalAppConfig(appType) {
    return window.EXTERNAL_APP_CONFIG?.[appType] || null;
  }

  /**
   * 取得認證 Token（使用 FileUtils 或回退到本地實作）
   * @returns {string}
   */
  function getToken() {
    // 優先使用 FileUtils 的實作
    if (typeof FileUtils !== 'undefined' && FileUtils.getToken) {
      return FileUtils.getToken();
    }
    return (typeof LoginModule !== 'undefined' && LoginModule.getToken?.())
      || localStorage.getItem('chingtech_token')
      || '';
  }

  /**
   * 開啟 md2ppt / md2doc 檔案
   * @param {string} filePath - 檔案路徑或 URL
   * @param {string} filename - 檔案名稱
   * @param {string} appType - 'md2ppt' 或 'md2doc'
   * @returns {Promise<boolean>}
   */
  async function openExternalApp(filePath, filename, appType) {
    const config = getExternalAppConfig(appType);
    if (!config) {
      console.error(`[FileOpener] 未知的外部 App 類型: ${appType}`);
      return false;
    }

    try {
      // 讀取檔案內容（帶認證 token）
      const token = getToken();
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      const response = await fetch(filePath, { headers });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const content = await response.text();

      // 開啟外部 App 並傳送內容
      if (typeof ExternalAppModule !== 'undefined') {
        ExternalAppModule.openWithContent(config, {
          filename,
          content
        });
        return true;
      } else {
        console.error('[FileOpener] ExternalAppModule 未載入');
        return false;
      }
    } catch (error) {
      console.error(`[FileOpener] 開啟 ${appType} 檔案失敗:`, error);
      NotificationModule?.show?.(`開啟檔案失敗: ${error.message}`, 'error');
      return false;
    }
  }

  /**
   * 開啟檔案（擴充版，支援外部 App）
   * @param {string} filePath - 檔案路徑或 URL
   * @param {string} [filename] - 檔案名稱
   * @returns {boolean|Promise<boolean>}
   */
  function openExtended(filePath, filename) {
    const displayName = filename || filePath.split('/').pop().split('?')[0];
    const ext = getExtension(displayName);

    // 檢查是否為 md2ppt / md2doc 檔案
    if (ext === 'md2ppt') {
      return openExternalApp(filePath, displayName, 'md2ppt');
    }
    if (ext === 'md2doc') {
      return openExternalApp(filePath, displayName, 'md2doc');
    }

    // 使用原有的 open 方法
    return open(filePath, filename);
  }

  /**
   * 判斷檔案是否支援開啟（擴充版）
   * @param {string} filename
   * @returns {boolean}
   */
  function canOpenExtended(filename) {
    const ext = getExtension(filename);
    // 加入 md2ppt / md2doc 支援
    if (ext === 'md2ppt' || ext === 'md2doc') {
      return true;
    }
    return canOpen(filename);
  }

  // 公開 API
  return {
    open: openExtended,  // 使用擴充版
    canOpen: canOpenExtended,  // 使用擴充版
    getViewerType,
    registerViewer,
    getSupportedExtensions,
    getFileTypes,
    // 保留原始方法供內部使用
    openOriginal: open,
    canOpenOriginal: canOpen
  };
})();
