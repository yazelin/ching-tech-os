/**
 * ChingTech OS - 全局配置
 * 自動檢測 API base path，支援子路徑部署
 */

(function() {
  'use strict';

  // 自動檢測 base path
  const pathName = window.location.pathname;
  let basePath = '';

  // 檢查已知的子路徑部署
  const knownBasePaths = ['/ctos', '/trial'];
  for (const known of knownBasePaths) {
    if (pathName.startsWith(known + '/') || pathName === known) {
      basePath = known;
      break;
    }
  }

  // 設定全局變數
  window.API_BASE = basePath;
  window.CTOS_CONFIG = {
    API_BASE: basePath,
    // 租戶模式（將在載入時動態設定）
    MULTI_TENANT_MODE: false,
    apiUrl: function(path) {
      if (!path.startsWith('/')) path = '/' + path;
      return this.API_BASE + path;
    },
    // 取得租戶模式
    isMultiTenantMode: function() {
      return this.MULTI_TENANT_MODE;
    }
  };

  // 外部應用程式配置
  window.EXTERNAL_APP_CONFIG = {
    md2ppt: {
      appId: 'md2ppt',
      title: 'md2ppt',
      icon: 'file-powerpoint',
      url: 'https://md-2-ppt-evolution.vercel.app/',
      maximized: true
    },
    md2doc: {
      appId: 'md2doc',
      title: 'md2doc',
      icon: 'file-word',
      url: 'https://md-2-doc-evolution.vercel.app/',
      maximized: true
    }
  };

  // 覆寫 fetch，自動為 /api/ 和 /socket.io/ 請求加上 base path
  const originalFetch = window.fetch;
  window.fetch = function(input, init) {
    let url = input;

    if (typeof input === 'string') {
      // 只處理以 /api/ 或 /socket.io/ 開頭的絕對路徑
      if (input.startsWith('/api/') || input.startsWith('/socket.io/')) {
        url = basePath + input;
      }
    } else if (input instanceof Request) {
      const originalUrl = input.url;
      const urlObj = new URL(originalUrl);
      if (urlObj.pathname.startsWith('/api/') || urlObj.pathname.startsWith('/socket.io/')) {
        urlObj.pathname = basePath + urlObj.pathname;
        url = new Request(urlObj.toString(), input);
      }
    }

    return originalFetch.call(this, url, init);
  };

  console.log('[CTOS] API Base Path:', basePath || '(root)');
})();
