/**
 * ChingTech OS - Taskbar Module
 * Handles taskbar/dock functionality
 */

const TaskbarModule = (function() {
  'use strict';

  // Active window menu reference
  let activeWindowMenu = null;

  // Quick launch applications for taskbar
  const quickLaunchApps = [
    { id: 'file-manager', name: '檔案管理', icon: 'mdi-folder' },
    { id: 'terminal', name: '終端機', icon: 'mdi-console' },
    { id: 'code-editor', name: 'VSCode', icon: 'mdi-code-braces' },
    { id: 'ai-assistant', name: 'AI 助手', icon: 'mdi-robot' },
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

    // Close any existing window menu
    closeWindowMenu();

    // Check if WindowModule is available
    if (typeof WindowModule === 'undefined') {
      return;
    }

    // Get all windows for this app
    const appWindows = WindowModule.getWindowsByAppId(appId);

    if (appWindows.length === 0) {
      // App is not open - open it
      if (typeof DesktopModule !== 'undefined' && typeof DesktopModule.openApp === 'function') {
        DesktopModule.openApp(appId);
      }
    } else if (appWindows.length === 1) {
      // Single window - focus or restore
      const win = appWindows[0];
      if (win.minimized) {
        WindowModule.restoreWindow(win.windowId);
      } else {
        WindowModule.focusWindow(win.windowId);
      }
    } else {
      // Multiple windows - show window menu
      showWindowMenu(iconElement, appWindows);
    }
  }

  /**
   * Show window selection menu for multi-window apps
   * @param {HTMLElement} iconElement - The taskbar icon element
   * @param {Array} windows - Array of window objects
   */
  function showWindowMenu(iconElement, windows) {
    const menu = document.createElement('div');
    menu.className = 'taskbar-window-menu';

    windows.forEach(win => {
      const item = document.createElement('div');
      item.className = 'taskbar-window-menu-item';
      if (win.minimized) {
        item.classList.add('minimized');
      }
      item.textContent = win.title || '無標題';
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        if (win.minimized) {
          WindowModule.restoreWindow(win.windowId);
        } else {
          WindowModule.focusWindow(win.windowId);
        }
        closeWindowMenu();
      });
      menu.appendChild(item);
    });

    // Position menu above the icon
    const iconRect = iconElement.getBoundingClientRect();
    menu.style.left = `${iconRect.left + iconRect.width / 2}px`;
    menu.style.bottom = `${window.innerHeight - iconRect.top + 8}px`;

    document.body.appendChild(menu);
    activeWindowMenu = menu;

    // Close menu when clicking outside
    setTimeout(() => {
      document.addEventListener('click', handleOutsideClick);
    }, 0);
  }

  /**
   * Close the window menu
   */
  function closeWindowMenu() {
    if (activeWindowMenu) {
      activeWindowMenu.remove();
      activeWindowMenu = null;
      document.removeEventListener('click', handleOutsideClick);
    }
  }

  /**
   * Handle click outside window menu
   */
  function handleOutsideClick(event) {
    if (activeWindowMenu && !activeWindowMenu.contains(event.target)) {
      closeWindowMenu();
    }
  }

  /**
   * Update running indicator for a specific app
   * @param {string} appId
   * @param {number} windowCount - Number of windows for this app
   */
  function updateRunningIndicator(appId, windowCount) {
    const iconElement = document.querySelector(`.taskbar-icon[data-app-id="${appId}"]`);
    if (!iconElement) return;

    // Remove existing indicators
    const existingIndicator = iconElement.querySelector('.running-indicator');
    if (existingIndicator) {
      existingIndicator.remove();
    }

    // Remove active class
    iconElement.classList.remove('active', 'multi-window');

    if (windowCount > 0) {
      iconElement.classList.add('active');

      // Create indicator container
      const indicator = document.createElement('div');
      indicator.className = 'running-indicator';

      // Add dots (max 3)
      const dotCount = Math.min(windowCount, 3);
      for (let i = 0; i < dotCount; i++) {
        const dot = document.createElement('span');
        dot.className = 'indicator-dot';
        indicator.appendChild(dot);
      }

      if (windowCount > 1) {
        iconElement.classList.add('multi-window');
      }

      iconElement.appendChild(indicator);
    }
  }

  /**
   * Update all running indicators based on current windows
   */
  function updateAllRunningIndicators() {
    if (typeof WindowModule === 'undefined') return;

    // Count windows per app
    const windowCounts = {};
    quickLaunchApps.forEach(app => {
      windowCounts[app.id] = 0;
    });

    const windows = WindowModule.getWindows();
    Object.values(windows).forEach(w => {
      if (windowCounts.hasOwnProperty(w.appId)) {
        windowCounts[w.appId]++;
      }
    });

    // Update indicators
    quickLaunchApps.forEach(app => {
      updateRunningIndicator(app.id, windowCounts[app.id]);
    });
  }

  /**
   * Handle window state change callback
   * @param {string} eventType - 'open' or 'close'
   * @param {string} appId
   */
  function onWindowStateChange(eventType, appId) {
    // Always update all indicators to ensure correct count
    updateAllRunningIndicators();
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
