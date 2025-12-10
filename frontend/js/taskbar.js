/**
 * ChingTech OS - Taskbar Module
 * Handles taskbar/dock functionality
 */

const TaskbarModule = (function() {
  'use strict';

  // Quick launch applications for taskbar
  const quickLaunchApps = [
    { id: 'file-manager', name: '檔案管理', icon: 'mdi-folder' },
    { id: 'terminal', name: '終端機', icon: 'mdi-console' },
    { id: 'code-editor', name: '程式編輯器', icon: 'mdi-code-braces' },
    { id: 'ai-assistant', name: 'AI 助手', icon: 'mdi-robot' },
    { id: 'message-center', name: '訊息中心', icon: 'mdi-message-text' },
    { id: 'settings', name: '系統設定', icon: 'mdi-cog' }
  ];

  /**
   * Create a taskbar icon element
   * @param {Object} app - Application definition
   * @returns {HTMLElement}
   */
  function createIconElement(app) {
    const icon = document.createElement('div');
    icon.className = 'taskbar-icon';
    icon.dataset.appId = app.id;
    icon.dataset.tooltip = app.name;
    icon.innerHTML = `<span class="icon">${getIcon(app.icon)}</span>`;
    return icon;
  }

  /**
   * Handle taskbar icon click - Dock behavior logic
   * @param {Event} event
   */
  function handleIconClick(event) {
    const iconElement = event.currentTarget;
    const appId = iconElement.dataset.appId;

    // Check if WindowModule is available
    if (typeof WindowModule === 'undefined') {
      return;
    }

    // Check if app window is already open
    const existingWindow = WindowModule.getWindowByAppId(appId);

    if (existingWindow) {
      // App is open
      if (existingWindow.minimized) {
        // Restore minimized window
        WindowModule.restoreWindow(existingWindow.windowId);
      } else {
        // Focus the window (bring to front)
        WindowModule.focusWindow(existingWindow.windowId);
      }
    } else {
      // App is not open - open it
      if (typeof DesktopModule !== 'undefined' && typeof DesktopModule.openApp === 'function') {
        DesktopModule.openApp(appId);
      }
    }
  }

  /**
   * Update running indicator for a specific app
   * @param {string} appId
   * @param {boolean} isRunning
   */
  function updateRunningIndicator(appId, isRunning) {
    const iconElement = document.querySelector(`.taskbar-icon[data-app-id="${appId}"]`);
    if (iconElement) {
      iconElement.classList.toggle('active', isRunning);
    }
  }

  /**
   * Update all running indicators based on current windows
   */
  function updateAllRunningIndicators() {
    if (typeof WindowModule === 'undefined') return;

    const windows = WindowModule.getWindows();
    const runningAppIds = new Set(
      Object.values(windows).map(w => w.appId)
    );

    quickLaunchApps.forEach(app => {
      updateRunningIndicator(app.id, runningAppIds.has(app.id));
    });
  }

  /**
   * Handle window state change callback
   * @param {string} eventType - 'open' or 'close'
   * @param {string} appId
   */
  function onWindowStateChange(eventType, appId) {
    if (eventType === 'open') {
      updateRunningIndicator(appId, true);
    } else if (eventType === 'close') {
      updateRunningIndicator(appId, false);
    }
  }

  /**
   * Render taskbar icons
   */
  function renderIcons() {
    const taskbar = document.querySelector('.taskbar');
    if (!taskbar) return;

    quickLaunchApps.forEach((app, index) => {
      const iconElement = createIconElement(app);
      iconElement.addEventListener('click', handleIconClick);
      taskbar.appendChild(iconElement);

      // Add divider after 3rd icon (after main apps, before utilities)
      if (index === 2) {
        const divider = document.createElement('div');
        divider.className = 'taskbar-divider';
        taskbar.appendChild(divider);
      }
    });
  }

  /**
   * Initialize taskbar module
   */
  function init() {
    renderIcons();

    // Register window state change callback
    if (typeof WindowModule !== 'undefined' && typeof WindowModule.onStateChange === 'function') {
      WindowModule.onStateChange(onWindowStateChange);
    }

    // Update indicators for any already open windows
    updateAllRunningIndicators();
  }

  // Public API
  return {
    init,
    updateRunningIndicator,
    updateAllRunningIndicators
  };
})();
