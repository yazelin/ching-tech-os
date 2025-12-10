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
   * Handle taskbar icon click
   * @param {Event} event
   */
  function handleIconClick(event) {
    const iconElement = event.currentTarget;
    const appId = iconElement.dataset.appId;
    const app = quickLaunchApps.find(a => a.id === appId);

    if (app && typeof DesktopModule !== 'undefined') {
      DesktopModule.showToast(`「${app.name}」功能開發中`, 'wrench');
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
  }

  // Public API
  return {
    init
  };
})();
