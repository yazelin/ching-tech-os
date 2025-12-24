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
    { id: 'code-editor', name: '程式編輯器', icon: 'mdi-code-braces' },
    { id: 'project-management', name: '專案管理', icon: 'mdi-briefcase' },
    { id: 'ai-assistant', name: 'AI 助手', icon: 'mdi-robot' },
    { id: 'prompt-editor', name: 'Prompt 編輯器', icon: 'mdi-file-document-edit-outline' },
    { id: 'agent-settings', name: 'Agent 設定', icon: 'mdi-robot-outline' },
    { id: 'ai-log', name: 'AI Log', icon: 'mdi-chart-timeline-variant' },
    { id: 'knowledge-base', name: '知識庫', icon: 'mdi-book-open-page-variant' },
    { id: 'linebot', name: 'Line Bot', icon: 'mdi-message-text' },
    { id: 'settings', name: '系統設定', icon: 'mdi-cog' }
  ];

  let selectedIcon = null;

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
   * Handle icon click
   * @param {Event} event
   */
  function handleIconClick(event) {
    const iconElement = event.currentTarget;
    const appId = iconElement.dataset.appId;

    // Deselect previous icon
    if (selectedIcon) {
      selectedIcon.classList.remove('selected');
    }

    // Select current icon
    iconElement.classList.add('selected');
    selectedIcon = iconElement;
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
      case 'project-management':
        if (typeof ProjectManagementModule !== 'undefined') {
          ProjectManagementModule.open();
        }
        break;
      case 'settings':
        if (typeof SettingsApp !== 'undefined') {
          SettingsApp.open();
        }
        break;
      case 'linebot':
        openLineBotWindow();
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
   * Open Line Bot management window
   */
  function openLineBotWindow() {
    const existingWindow = WindowModule.getWindowByAppId('linebot');
    if (existingWindow) {
      WindowModule.focusWindow(existingWindow.windowId);
      return;
    }

    WindowModule.createWindow({
      title: 'Line Bot',
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
   * Handle icon double-click (open app)
   * @param {Event} event
   */
  function handleIconDoubleClick(event) {
    const iconElement = event.currentTarget;
    const appId = iconElement.dataset.appId;
    openApp(appId);
  }

  /**
   * Handle click on desktop area (deselect icons)
   * @param {Event} event
   */
  function handleDesktopClick(event) {
    if (event.target.classList.contains('desktop-area')) {
      if (selectedIcon) {
        selectedIcon.classList.remove('selected');
        selectedIcon = null;
      }
    }
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
      iconElement.addEventListener('dblclick', handleIconDoubleClick);
      desktopArea.appendChild(iconElement);
    });

    // Handle desktop area click
    desktopArea.addEventListener('click', handleDesktopClick);
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
