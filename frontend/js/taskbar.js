/**
 * ChingTech OS - Taskbar Module
 * 底部 Dock 啟動列：快速啟動、視窗聚焦、運行指示器
 */

const TaskbarModule = (function () {
  'use strict';

  // ── 狀態 ───────────────────────────────────────────────────
  let activeWindowMenu = null;

  // 快速啟動列應用程式（可依需求增減）
  const quickLaunchApps = [
    { id: 'file-manager',  name: '檔案管理', icon: 'mdi-folder' },
    { id: 'terminal',      name: '終端機',   icon: 'mdi-console' },
    { id: 'code-editor',   name: 'VSCode',   icon: 'mdi-code-braces' },
    { id: 'ai-assistant',  name: 'AI 助手',  icon: 'mdi-robot' },
    { id: 'settings',      name: '系統設定', icon: 'mdi-cog' },
  ];

  // ── DOM 建立 ───────────────────────────────────────────────

  /**
   * 建立單一 Taskbar 圖示
   * @param {Object} app - { id, name, icon }
   * @returns {HTMLElement}
   */
  function createIconElement(app) {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = 'taskbar-icon';
    el.dataset.appId = app.id;
    el.dataset.tooltip = app.name;
    el.setAttribute('aria-label', app.name);
    el.innerHTML = `<span class="icon">${typeof getIcon === 'function' ? getIcon(app.icon) : ''}</span>`;
    return el;
  }

  // ── 點擊行為（Dock 邏輯） ─────────────────────────────────

  /**
   * 處理圖示點擊
   *  - 無視窗 → 開啟 App
   *  - 單視窗 → 聚焦 / 恢復
   *  - 多視窗 → 顯示選單
   */
  function handleIconClick(event) {
    const appId = event.currentTarget.dataset.appId;
    closeWindowMenu();

    if (typeof WindowModule === 'undefined') {
      // 無視窗系統，直接開啟
      _openApp(appId);
      return;
    }

    const wins = WindowModule.getWindowsByAppId(appId);

    if (wins.length === 0) {
      _openApp(appId);
    } else if (wins.length === 1) {
      const w = wins[0];
      if (w.minimized) {
        WindowModule.restoreWindow(w.windowId);
      } else {
        WindowModule.focusWindow(w.windowId);
      }
    } else {
      showWindowMenu(event.currentTarget, wins);
    }
  }

  /** 透過 DesktopModule 開啟應用 */
  function _openApp(appId) {
    if (typeof DesktopModule !== 'undefined' && typeof DesktopModule.openApp === 'function') {
      DesktopModule.openApp(appId);
    }
  }

  // ── 多視窗選單 ─────────────────────────────────────────────

  function showWindowMenu(iconEl, windows) {
    const menu = document.createElement('div');
    menu.className = 'taskbar-window-menu';

    windows.forEach(function (win) {
      const item = document.createElement('div');
      item.className = 'taskbar-window-menu-item';
      if (win.minimized) item.classList.add('minimized');
      item.textContent = win.title || '無標題';
      item.addEventListener('click', function (e) {
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

    const rect = iconEl.getBoundingClientRect();
    menu.style.left = rect.left + rect.width / 2 + 'px';
    menu.style.bottom = (window.innerHeight - rect.top + 8) + 'px';

    document.body.appendChild(menu);
    activeWindowMenu = menu;

    setTimeout(function () {
      document.addEventListener('click', _onOutsideClick);
    }, 0);
  }

  function closeWindowMenu() {
    if (activeWindowMenu) {
      activeWindowMenu.remove();
      activeWindowMenu = null;
      document.removeEventListener('click', _onOutsideClick);
    }
  }

  function _onOutsideClick(event) {
    if (activeWindowMenu && !activeWindowMenu.contains(event.target)) {
      closeWindowMenu();
    }
  }

  // ── 運行指示器 ─────────────────────────────────────────────

  /**
   * 更新單一 App 的運行指示器
   */
  function updateRunningIndicator(appId, windowCount) {
    var iconEl = document.querySelector('.taskbar-icon[data-app-id="' + appId + '"]');
    if (!iconEl) return;

    var existing = iconEl.querySelector('.running-indicator');
    if (existing) existing.remove();
    iconEl.classList.remove('active', 'multi-window');

    if (windowCount > 0) {
      iconEl.classList.add('active');
      var indicator = document.createElement('div');
      indicator.className = 'running-indicator';
      var dots = Math.min(windowCount, 3);
      for (var i = 0; i < dots; i++) {
        var dot = document.createElement('span');
        dot.className = 'indicator-dot';
        indicator.appendChild(dot);
      }
      if (windowCount > 1) iconEl.classList.add('multi-window');
      iconEl.appendChild(indicator);
    }
  }

  /**
   * 重算所有指示器
   */
  function updateAllRunningIndicators() {
    if (typeof WindowModule === 'undefined') return;

    var counts = {};
    quickLaunchApps.forEach(function (a) { counts[a.id] = 0; });

    var allWins = WindowModule.getWindows();
    Object.values(allWins).forEach(function (w) {
      if (counts.hasOwnProperty(w.appId)) counts[w.appId]++;
    });

    quickLaunchApps.forEach(function (a) {
      updateRunningIndicator(a.id, counts[a.id]);
    });
  }

  // ── 渲染 & 初始化 ─────────────────────────────────────────

  function renderIcons() {
    var taskbar = document.querySelector('.taskbar');
    if (!taskbar) return;

    quickLaunchApps.forEach(function (app, idx) {
      var el = createIconElement(app);
      el.addEventListener('click', handleIconClick);
      taskbar.appendChild(el);

      // 在第 3 個圖示後加分隔線
      if (idx === 2) {
        var div = document.createElement('div');
        div.className = 'taskbar-divider';
        taskbar.appendChild(div);
      }
    });
  }

  function init() {
    renderIcons();

    // 註冊視窗狀態變更回呼
    if (typeof WindowModule !== 'undefined' && typeof WindowModule.onStateChange === 'function') {
      WindowModule.onStateChange(function () {
        updateAllRunningIndicators();
      });
    }

    updateAllRunningIndicators();
    console.log('[TaskbarModule] ✅ Dock 已初始化');
  }

  // Public API
  return {
    init: init,
    updateRunningIndicator: updateRunningIndicator,
    updateAllRunningIndicators: updateAllRunningIndicators,
  };
})();
