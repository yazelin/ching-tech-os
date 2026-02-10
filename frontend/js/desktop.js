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
    openApp
  };
})();
