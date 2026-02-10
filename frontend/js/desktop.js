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

  /**
   * Create a desktop icon element
   * @param {Object} app - Application definition
   * @returns {HTMLElement}
   */
  function createIconElement(app) {
    const icon = document.createElement('div');
    icon.className = 'desktop-icon';
    icon.dataset.appId = app.id;
    icon.innerHTML = `
      <div class="desktop-icon-image">
        <span class="icon">${getIcon(app.icon)}</span>
      </div>
      <span class="desktop-icon-label">${app.name}</span>
    `;
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
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `
      <span class="icon">${getIcon(icon)}</span>
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
   * Open an application
   * @param {string} appId
   */
  function openApp(appId) {
    switch (appId) {
      case 'ai-assistant':
        if (typeof AIAssistantApp !== 'undefined') {
          AIAssistantApp.open();
        }
        break;
      case 'prompt-editor':
        if (typeof PromptEditorApp !== 'undefined') {
          PromptEditorApp.open();
        }
        break;
      case 'agent-settings':
        if (typeof AgentSettingsApp !== 'undefined') {
          AgentSettingsApp.open();
        }
        break;
      case 'ai-log':
        if (typeof AILogApp !== 'undefined') {
          AILogApp.open();
        }
        break;
      case 'file-manager':
        if (typeof FileManagerModule !== 'undefined') {
          FileManagerModule.open();
        }
        break;
      case 'terminal':
        if (typeof TerminalApp !== 'undefined') {
          TerminalApp.open();
        }
        break;
      case 'code-editor':
        if (typeof CodeEditorModule !== 'undefined') {
          CodeEditorModule.open();
        }
        break;
      case 'knowledge-base':
        if (typeof KnowledgeBaseModule !== 'undefined') {
          KnowledgeBaseModule.open();
        }
        break;
      case 'erpnext':
        // ERPNext 開新視窗
        window.open('http://ct.erp', '_blank');
        break;
      case 'settings':
        if (typeof SettingsApp !== 'undefined') {
          SettingsApp.open();
        }
        break;
      case 'linebot':
        openLineBotWindow();
        break;
      case 'share-manager':
        if (typeof ShareManagerApp !== 'undefined') {
          ShareManagerApp.open();
        }
        break;
      case 'memory-manager':
        if (typeof MemoryManagerApp !== 'undefined') {
          MemoryManagerApp.open();
        }
        break;
      case 'md2ppt':
        if (typeof ExternalAppModule !== 'undefined' && window.EXTERNAL_APP_CONFIG?.md2ppt) {
          ExternalAppModule.open(window.EXTERNAL_APP_CONFIG.md2ppt);
        }
        break;
      case 'md2doc':
        if (typeof ExternalAppModule !== 'undefined' && window.EXTERNAL_APP_CONFIG?.md2doc) {
          ExternalAppModule.open(window.EXTERNAL_APP_CONFIG.md2doc);
        }
        break;
      default:
        const app = applications.find(a => a.id === appId);
        if (app) {
          showToast(`「${app.name}」功能開發中`, 'wrench');
        }
        break;
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
      <div class="ctx-item" data-action="open" style="padding:8px 16px;cursor:pointer;color:var(--text-color,#eee);">
        開啟「${app.name}」
      </div>
      <div class="ctx-item" data-action="info" style="padding:8px 16px;cursor:pointer;color:var(--text-color,#eee);">
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

    // 根據權限過濾應用程式
    const visibleApps = typeof PermissionsModule !== 'undefined'
      ? PermissionsModule.getAccessibleApps(applications)
      : applications;

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
