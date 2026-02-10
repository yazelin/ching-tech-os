/**
 * ChingTech OS - Desktop Module
 * Handles desktop area functionality: app icons, click events
 */

const DesktopModule = (function() {
  'use strict';

  // Application definitions
  const applications = [
    { id: 'file-manager', name: '檔案管理', icon: 'mdi-folder' },
    { id: 'terminal', name: '終端機', icon: 'mdi-console' },
    { id: 'code-editor', name: 'VSCode', icon: 'mdi-code-braces' },
    { id: 'erpnext', name: 'ERPNext', icon: 'erpnext' },  // 整合專案/物料/廠商管理
    { id: 'ai-assistant', name: 'AI 助手', icon: 'mdi-robot' },
    { id: 'prompt-editor', name: 'Prompt 編輯器', icon: 'mdi-script-text' },
    { id: 'agent-settings', name: 'Agent 設定', icon: 'mdi-tune-variant' },
    { id: 'ai-log', name: 'AI Log', icon: 'mdi-history' },
    { id: 'knowledge-base', name: '知識庫', icon: 'mdi-book-open-page-variant' },
    { id: 'linebot', name: 'Bot 管理', icon: 'mdi-message-text' },
    { id: 'memory-manager', name: '記憶管理', icon: 'mdi-brain' },
    { id: 'share-manager', name: '分享管理', icon: 'mdi-share-variant' },
    { id: 'settings', name: '系統設定', icon: 'mdi-cog' },
    { id: 'md2ppt', name: 'md2ppt', icon: 'file-powerpoint' },
    { id: 'md2doc', name: 'md2doc', icon: 'file-word' }
  ];

  // ── Lazy-Loading 機制 ─────────────────────────────────────────────
  // appLoaders：定義大型模組的動態 import 路徑與對應全域變數名稱
  // 當使用者首次點擊 App 時才載入對應的 JS，避免初始頁面載入過多腳本。
  const appLoaders = {
    'ai-assistant':   { src: './js/ai-assistant.js',   globalName: 'AIAssistantApp' },
    'file-manager':   { src: './js/file-manager.js',   globalName: 'FileManagerModule' },
    'prompt-editor':  { src: './js/prompt-editor.js',  globalName: 'PromptEditorApp' },
    'agent-settings': { src: './js/agent-settings.js', globalName: 'AgentSettingsApp' },
    'ai-log':         { src: './js/ai-log.js',         globalName: 'AILogApp' },
    'knowledge-base': { src: './js/knowledge-base.js', globalName: 'KnowledgeBaseModule' },
    'terminal':       { src: './js/terminal.js',       globalName: 'TerminalApp' },
    'code-editor':    { src: './js/code-editor.js',    globalName: 'CodeEditorModule' },
    'memory-manager': { src: './js/memory-manager.js', globalName: 'MemoryManagerApp' },
    'share-manager':  { src: './js/share-manager.js',  globalName: 'ShareManagerApp' },
    'settings':       { src: './js/settings.js',       globalName: 'SettingsApp' },
    'linebot':        { src: './js/linebot.js',        globalName: 'LineBotApp' },
  };

  // 已載入模組的快取，避免重複載入
  const _loadedModules = new Set();

  /**
   * 顯示 Loading Skeleton（在桌面區域中央）
   * @param {string} appId
   * @returns {HTMLElement} skeleton DOM 節點（供後續移除）
   */
  function showLoadingSkeleton(appId) {
    const overlay = document.createElement('div');
    overlay.className = 'app-loading-overlay';
    overlay.dataset.loadingFor = appId;
    overlay.innerHTML = `
      <div class="app-loading-skeleton">
        <div class="skeleton-spinner"></div>
        <span class="skeleton-label">正在載入模組…</span>
      </div>
    `;
    document.body.appendChild(overlay);
    return overlay;
  }

  /**
   * 移除 Loading Skeleton
   * @param {HTMLElement} overlay
   */
  function removeLoadingSkeleton(overlay) {
    if (overlay && overlay.parentNode) {
      overlay.classList.add('fade-out');
      setTimeout(() => overlay.remove(), 200);
    }
  }

  /**
   * 動態載入模組（使用 <script> 注入，相容非 ESM 架構）
   * @param {string} src - 腳本路徑
   * @returns {Promise<void>}
   */
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      // 檢查是否已有相同 src 的 script 標籤
      if (document.querySelector(`script[src="${src}"]`)) {
        resolve();
        return;
      }
      const script = document.createElement('script');
      script.src = src;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error(`模組載入失敗: ${src}`));
      document.head.appendChild(script);
    });
  }

  /**
   * 確保指定 App 的模組已載入（lazy-load 核心）
   * @param {string} appId
   * @returns {Promise<boolean>} 是否成功
   */
  async function ensureModuleLoaded(appId) {
    const loader = appLoaders[appId];
    if (!loader) return true; // 不在 lazy-load 清單中，直接放行

    // 已存在全域變數 → 已載入
    if (window[loader.globalName]) {
      _loadedModules.add(appId);
      return true;
    }

    // 已在快取中（曾成功載入）
    if (_loadedModules.has(appId)) return true;

    try {
      await loadScript(loader.src);
      _loadedModules.add(appId);
      console.log(`[LazyLoad] ✅ 模組已載入: ${appId} (${loader.src})`);
      return true;
    } catch (err) {
      console.error(`[LazyLoad] ❌ ${err.message}`);
      showToast(`模組載入失敗：${appId}`, 'alert-circle');
      return false;
    }
  }

  /**
   * Create a desktop icon element
   * @param {Object} app - Application definition
   * @returns {HTMLElement}
   */
  function createIconElement(app) {
    const icon = document.createElement('button');
    icon.type = 'button';
    icon.className = 'desktop-icon';
    icon.dataset.appId = app.id;
    icon.setAttribute('aria-label', `開啟${app.name}`);
    icon.innerHTML = `
      <div class="desktop-icon-image">
        <span class="icon">${getIcon(app.icon)}</span>
      </div>
      <span class="desktop-icon-label">${app.name}</span>
    `;

    // 鍵盤事件：Enter / Space 觸發點擊
    icon.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        icon.click();
      }
    });

    return icon;
  }

  /**
   * Show a toast notification
   * @param {string} message
   * @param {string} icon - MDI icon class
   */
  function showToast(message, icon = 'information') {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      container.setAttribute('role', 'status');
      container.setAttribute('aria-live', 'polite');
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
      <span class="icon" aria-hidden="true">${getIcon(icon)}</span>
      <span>${message}</span>
    `;
    container.appendChild(toast);

    // Remove toast after animation
    setTimeout(() => {
      toast.remove();
    }, 3000);
  }

  /**
   * Handle icon click - directly open the app
   * @param {Event} event
   */
  function handleIconClick(event) {
    const iconElement = event.currentTarget;
    const appId = iconElement.dataset.appId;
    openApp(appId);
  }

  /**
   * Open an application（含 lazy-loading 支援）
   * 流程：顯示 skeleton → 動態載入模組 → 移除 skeleton → 開啟 App
   * @param {string} appId
   */
  async function openApp(appId) {
    // ── 不需要 lazy-load 的特殊 App ──
    if (appId === 'erpnext') {
      window.open('http://ct.erp', '_blank');
      return;
    }
    if (appId === 'md2ppt') {
      if (typeof ExternalAppModule !== 'undefined' && window.EXTERNAL_APP_CONFIG?.md2ppt) {
        ExternalAppModule.open(window.EXTERNAL_APP_CONFIG.md2ppt);
      }
      return;
    }
    if (appId === 'md2doc') {
      if (typeof ExternalAppModule !== 'undefined' && window.EXTERNAL_APP_CONFIG?.md2doc) {
        ExternalAppModule.open(window.EXTERNAL_APP_CONFIG.md2doc);
      }
      return;
    }

    // ── Lazy-load 流程 ──
    const loader = appLoaders[appId];
    const needsLoad = loader && !window[loader.globalName] && !_loadedModules.has(appId);
    let skeleton = null;

    if (needsLoad) {
      skeleton = showLoadingSkeleton(appId);
    }

    const ok = await ensureModuleLoaded(appId);
    if (skeleton) removeLoadingSkeleton(skeleton);
    if (!ok) return;

    // ── 開啟 App ──
    if (appId === 'linebot') {
      openLineBotWindow();
      return;
    }

    // 通用：透過 appLoaders 查表取得全域變數名稱並呼叫 .open()
    if (loader) {
      const mod = window[loader.globalName];
      if (mod && typeof mod.open === 'function') {
        mod.open();
      } else {
        console.warn(`[LazyLoad] 模組 ${loader.globalName} 已載入但缺少 open() 方法`);
      }
      return;
    }

    // 未在 appLoaders 中的 App → 開發中提示
    const app = applications.find(a => a.id === appId);
    if (app) {
      showToast(`「${app.name}」功能開發中`, 'wrench');
    }
  }

  /**
   * Open Bot 管理 window
   */
  function openLineBotWindow() {
    const existingWindow = WindowModule.getWindowByAppId('linebot');
    if (existingWindow) {
      WindowModule.focusWindow(existingWindow.windowId);
      return;
    }

    WindowModule.createWindow({
      title: 'Bot 管理',
      icon: 'mdi-message-text',
      width: 900,
      height: 600,
      appId: 'linebot',
      onInit: (windowEl) => {
        const content = windowEl.querySelector('.window-content');
        if (content && typeof LineBotApp !== 'undefined') {
          LineBotApp.init(content);
        }
      },
    });
  }


  // Long-press 觸控狀態（用於模擬右鍵選單）
  const LONG_PRESS_DELAY = 600; // 毫秒
  let longPressTimer = null;
  let longPressTriggered = false;

  /**
   * Open context menu for an app icon
   * @param {string} appId
   * @param {number} x - viewport X position
   * @param {number} y - viewport Y position
   */
  function openContextMenu(appId, x, y) {
    // 先移除任何已存在的右鍵選單
    closeContextMenu();

    const app = applications.find(a => a.id === appId);
    if (!app) return;

    const menu = document.createElement('div');
    menu.className = 'touch-context-menu';
    menu.setAttribute('role', 'menu');
    menu.setAttribute('aria-label', `${app.name} 選單`);
    menu.style.position = 'fixed';
    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;
    menu.style.zIndex = '10000';
    menu.style.background = 'var(--surface-color, #2d2d2d)';
    menu.style.border = '1px solid var(--border-color, #555)';
    menu.style.borderRadius = '6px';
    menu.style.padding = '4px 0';
    menu.style.boxShadow = '0 4px 12px rgba(0,0,0,0.4)';
    menu.style.minWidth = '140px';

    menu.innerHTML = `
      <div class="ctx-item" data-action="open" role="menuitem" tabindex="0" style="padding:8px 16px;cursor:pointer;color:var(--text-color,#eee);">
        開啟「${app.name}」
      </div>
      <div class="ctx-item" data-action="info" role="menuitem" tabindex="0" style="padding:8px 16px;cursor:pointer;color:var(--text-color,#eee);">
        應用程式資訊
      </div>
    `;

    document.body.appendChild(menu);

    // 確保選單不超出視窗
    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      menu.style.left = `${window.innerWidth - rect.width - 8}px`;
    }
    if (rect.bottom > window.innerHeight) {
      menu.style.top = `${window.innerHeight - rect.height - 8}px`;
    }

    // 綁定選單項目點擊
    menu.querySelectorAll('.ctx-item').forEach(item => {
      item.addEventListener('click', () => {
        const action = item.dataset.action;
        if (action === 'open') {
          openApp(appId);
        } else if (action === 'info') {
          showToast(`${app.name}（${app.id}）`, app.icon);
        }
        closeContextMenu();
      });
      // 鍵盤操作：Enter / Space 觸發、Escape 關閉
      item.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          item.click();
        } else if (e.key === 'Escape') {
          closeContextMenu();
        }
      });
      // hover 效果
      item.addEventListener('mouseenter', () => { item.style.background = 'rgba(255,255,255,0.1)'; });
      item.addEventListener('mouseleave', () => { item.style.background = 'transparent'; });
    });

    // 點擊其他區域關閉選單
    setTimeout(() => {
      document.addEventListener('click', closeContextMenu, { once: true });
      document.addEventListener('touchstart', closeContextMenu, { once: true });
    }, 50);
  }

  /**
   * Close any open context menu
   */
  function closeContextMenu() {
    const existing = document.querySelector('.touch-context-menu');
    if (existing) existing.remove();
  }

  /**
   * Render all desktop icons
   */
  function renderIcons() {
    const desktopArea = document.querySelector('.desktop-area');
    if (!desktopArea) return;

    // 設定桌面區域的無障礙屬性
    desktopArea.setAttribute('role', 'region');
    desktopArea.setAttribute('aria-label', '桌面應用程式');

    // 插入 skeleton 骨架佔位元素
    const skeletonCount = 8;
    const skeletons = [];
    for (let i = 0; i < skeletonCount; i++) {
      const sk = document.createElement('div');
      sk.className = 'skeleton skeleton--icon';
      sk.setAttribute('aria-hidden', 'true');
      desktopArea.appendChild(sk);
      skeletons.push(sk);
    }

    // 根據權限過濾應用程式
    const visibleApps = typeof PermissionsModule !== 'undefined'
      ? PermissionsModule.getAccessibleApps(applications)
      : applications;

    // 移除 skeleton 並渲染真實圖示
    skeletons.forEach(sk => sk.remove());

    visibleApps.forEach(app => {
      const iconElement = createIconElement(app);
      iconElement.addEventListener('click', handleIconClick);

      // 長按觸控 → 右鍵選單
      iconElement.addEventListener('touchstart', (e) => {
        longPressTriggered = false;
        const touch = e.touches[0];
        const tx = touch.clientX;
        const ty = touch.clientY;
        longPressTimer = setTimeout(() => {
          longPressTriggered = true;
          openContextMenu(app.id, tx, ty);
          // 觸發震動回饋（若瀏覽器支援）
          if (navigator.vibrate) navigator.vibrate(30);
        }, LONG_PRESS_DELAY);
      }, { passive: true });

      iconElement.addEventListener('touchend', () => {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      });

      iconElement.addEventListener('touchmove', () => {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      });

      // 長按觸發後阻止後續 click
      iconElement.addEventListener('click', (e) => {
        if (longPressTriggered) {
          e.preventDefault();
          e.stopImmediatePropagation();
          longPressTriggered = false;
        }
      }, true);

      desktopArea.appendChild(iconElement);
    });
  }

  /**
   * Initialize desktop module
   */
  function init() {
    renderIcons();
  }

  /**
   * Get application list
   * @returns {Array}
   */
  function getApplications() {
    return [...applications];
  }

  // Public API
  return {
    init,
    getApplications,
    showToast,
    openApp,
    openContextMenu,
    closeContextMenu
  };
})();
