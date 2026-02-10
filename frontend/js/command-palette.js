/**
 * ChingTech OS - Command Palette / 全域搜尋 (P10)
 *
 * Client-only 實作：搜尋已註冊的應用程式名稱與已開啟視窗標題。
 *
 * 限制（需後端支援時再擴充）：
 *  - 目前僅搜尋前端已載入的應用清單（DesktopModule.getApplications()）
 *  - 僅搜尋目前已開啟視窗標題（WindowModule.getWindows()）
 *  - 不包含檔案搜尋、知識庫全文搜尋等需後端 API 的功能
 */

const CommandPaletteModule = (function () {
  'use strict';

  // ── DOM refs ───────────────────────────────────────────────
  let overlayEl = null;
  let inputEl = null;
  let resultsEl = null;
  let activeIndex = -1;
  let flatItems = [];   // 目前搜尋結果的扁平陣列 { type, data, element }

  // ── Build DOM ──────────────────────────────────────────────

  /**
   * 在 header-center 插入觸發按鈕
   */
  function createTriggerButton() {
    const headerCenter = document.querySelector('.header-center');
    if (!headerCenter) return;

    const btn = document.createElement('button');
    btn.className = 'command-palette-trigger';
    btn.type = 'button';
    btn.setAttribute('aria-label', '全域搜尋');

    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
    const modKey = isMac ? '⌘' : 'Ctrl';

    btn.innerHTML = `
      <span class="icon">${typeof getIcon === 'function' ? getIcon('search') : '🔍'}</span>
      <span class="command-palette-trigger-text">搜尋…</span>
      <span class="command-palette-trigger-kbd">
        <kbd>${modKey}</kbd><kbd>K</kbd>
      </span>
    `;

    btn.addEventListener('click', open);
    headerCenter.appendChild(btn);
  }

  /**
   * 建立 overlay + dialog DOM（附加到 body）
   */
  function createOverlay() {
    overlayEl = document.createElement('div');
    overlayEl.className = 'command-palette-overlay';
    overlayEl.setAttribute('role', 'dialog');
    overlayEl.setAttribute('aria-label', '全域搜尋');

    overlayEl.innerHTML = `
      <div class="command-palette-dialog">
        <div class="command-palette-input-wrap">
          <span class="icon">${typeof getIcon === 'function' ? getIcon('search') : '🔍'}</span>
          <input class="command-palette-input"
                 type="text"
                 placeholder="搜尋應用程式或視窗…"
                 autocomplete="off"
                 spellcheck="false" />
        </div>
        <div class="command-palette-results"></div>
        <div class="command-palette-footer">
          <span><kbd>↑↓</kbd> 瀏覽</span>
          <span><kbd>Enter</kbd> 開啟</span>
          <span><kbd>Esc</kbd> 關閉</span>
        </div>
      </div>
    `;

    // Cache refs
    inputEl = overlayEl.querySelector('.command-palette-input');
    resultsEl = overlayEl.querySelector('.command-palette-results');

    // Events
    overlayEl.addEventListener('click', (e) => {
      if (e.target === overlayEl) close();
    });
    inputEl.addEventListener('input', () => handleSearch(inputEl.value));
    inputEl.addEventListener('keydown', handleInputKeydown);

    document.body.appendChild(overlayEl);
  }

  // ── Open / Close ───────────────────────────────────────────

  function open() {
    if (!overlayEl) createOverlay();
    overlayEl.classList.add('open');
    inputEl.value = '';
    handleSearch('');
    // Delay focus to let the CSS transition start
    requestAnimationFrame(() => inputEl.focus());
  }

  function close() {
    if (!overlayEl) return;
    overlayEl.classList.remove('open');
    activeIndex = -1;
  }

  function toggle() {
    if (overlayEl && overlayEl.classList.contains('open')) {
      close();
    } else {
      open();
    }
  }

  // ── Search Logic ───────────────────────────────────────────

  /**
   * 收集所有可搜尋項目並回傳分類結果
   */
  function collectItems(query) {
    const q = query.trim().toLowerCase();
    const results = { apps: [], windows: [] };

    // 1. 已註冊應用程式
    if (typeof DesktopModule !== 'undefined' && DesktopModule.getApplications) {
      const apps = DesktopModule.getApplications();
      apps.forEach((app) => {
        if (!q || app.name.toLowerCase().includes(q) || app.id.toLowerCase().includes(q)) {
          results.apps.push(app);
        }
      });
    }

    // 2. 已開啟的視窗
    if (typeof WindowModule !== 'undefined' && WindowModule.getWindows) {
      const windows = WindowModule.getWindows();
      Object.entries(windows).forEach(([winId, win]) => {
        const title = win.title || '';
        if (!q || title.toLowerCase().includes(q) || (win.appId && win.appId.toLowerCase().includes(q))) {
          results.windows.push({ winId, ...win });
        }
      });
    }

    return results;
  }

  /**
   * 高亮匹配文字
   */
  function highlight(text, query) {
    if (!query) return escapeHtml(text);
    const escaped = escapeHtml(text);
    const q = escapeHtml(query);
    const regex = new RegExp(`(${escapeRegex(q)})`, 'gi');
    return escaped.replace(regex, '<mark>$1</mark>');
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  /**
   * 取得應用程式的圖示 HTML
   */
  function getAppIconHtml(app) {
    if (typeof getIcon === 'function') {
      // 嘗試直接用 icon id
      const svg = getIcon(app.icon);
      if (svg) return svg;
    }
    return getIcon ? getIcon('application') || getIcon('apps') || '' : '';
  }

  /**
   * 渲染搜尋結果至 DOM
   */
  function handleSearch(query) {
    const q = query.trim();
    const { apps, windows } = collectItems(q);
    resultsEl.innerHTML = '';
    flatItems = [];
    activeIndex = -1;

    const hasResults = apps.length > 0 || windows.length > 0;

    if (!hasResults) {
      // [Sprint7] 原始: resultsEl.innerHTML = '<div class="command-palette-empty">...(找不到符合的結果|輸入關鍵字開始搜尋)</div>'
      UIHelpers.showEmpty(resultsEl, { icon: 'magnify', text: q ? '找不到符合的結果' : '輸入關鍵字開始搜尋' });
      return;
    }

    // ── 應用程式 ──
    if (apps.length > 0) {
      const section = document.createElement('div');
      section.className = 'command-palette-section';
      section.textContent = '應用程式';
      resultsEl.appendChild(section);

      apps.forEach((app) => {
        const item = createResultItem({
          iconHtml: getAppIconHtml(app),
          name: highlight(app.name, q),
          desc: app.id,
          badge: '開啟',
          type: 'app',
          data: app,
        });
        resultsEl.appendChild(item);
      });
    }

    // ── 開啟中的視窗 ──
    if (windows.length > 0) {
      const section = document.createElement('div');
      section.className = 'command-palette-section';
      section.textContent = '開啟中的視窗';
      resultsEl.appendChild(section);

      windows.forEach((win) => {
        const item = createResultItem({
          iconHtml: typeof getIcon === 'function' ? (getIcon('window-maximize') || getIcon('application') || '') : '',
          name: highlight(win.title || '(無標題)', q),
          desc: win.appId || '',
          badge: '切換',
          type: 'window',
          data: win,
        });
        resultsEl.appendChild(item);
      });
    }

    // 預設選取第一項
    if (flatItems.length > 0) {
      activeIndex = 0;
      flatItems[0].element.classList.add('active');
    }
  }

  /**
   * 建立單一結果項目 DOM
   */
  function createResultItem({ iconHtml, name, desc, badge, type, data }) {
    const el = document.createElement('div');
    el.className = 'command-palette-item';
    el.innerHTML = `
      <span class="icon">${iconHtml}</span>
      <div class="command-palette-item-text">
        <span class="command-palette-item-name">${name}</span>
        ${desc ? `<span class="command-palette-item-desc">${escapeHtml(desc)}</span>` : ''}
      </div>
      ${badge ? `<span class="command-palette-item-badge">${escapeHtml(badge)}</span>` : ''}
    `;

    const entry = { type, data, element: el };
    flatItems.push(entry);

    el.addEventListener('click', () => executeItem(entry));
    el.addEventListener('mouseenter', () => {
      setActiveIndex(flatItems.indexOf(entry));
    });

    return el;
  }

  // ── Keyboard Navigation ────────────────────────────────────

  function handleInputKeydown(e) {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIndex(activeIndex + 1);
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIndex(activeIndex - 1);
        break;
      case 'Enter':
        e.preventDefault();
        if (activeIndex >= 0 && activeIndex < flatItems.length) {
          executeItem(flatItems[activeIndex]);
        }
        break;
      case 'Escape':
        e.preventDefault();
        close();
        break;
    }
  }

  function setActiveIndex(newIndex) {
    if (flatItems.length === 0) return;
    // Clamp
    if (newIndex < 0) newIndex = flatItems.length - 1;
    if (newIndex >= flatItems.length) newIndex = 0;

    // Remove old active
    if (activeIndex >= 0 && activeIndex < flatItems.length) {
      flatItems[activeIndex].element.classList.remove('active');
    }

    activeIndex = newIndex;
    flatItems[activeIndex].element.classList.add('active');

    // Scroll into view
    flatItems[activeIndex].element.scrollIntoView({ block: 'nearest' });
  }

  // ── Execute ────────────────────────────────────────────────

  function executeItem(entry) {
    close();

    if (entry.type === 'app') {
      // 開啟應用程式
      if (typeof DesktopModule !== 'undefined' && DesktopModule.openApp) {
        DesktopModule.openApp(entry.data.id);
      }
    } else if (entry.type === 'window') {
      // 切換至已開啟的視窗
      if (typeof WindowModule !== 'undefined') {
        const winId = entry.data.winId;
        // 如果視窗被最小化，先還原
        if (entry.data.minimized && WindowModule.restoreWindow) {
          WindowModule.restoreWindow(winId);
        }
        if (WindowModule.focusWindow) {
          WindowModule.focusWindow(winId);
        }
      }
    }
  }

  // ── Global Shortcut ────────────────────────────────────────

  function handleGlobalKeydown(e) {
    // Ctrl+K / Cmd+K
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      e.stopPropagation();
      toggle();
    }
  }

  // ── Init / Destroy ─────────────────────────────────────────

  function init() {
    createTriggerButton();
    // 全域快捷鍵在 overlay 建立前就要監聽
    document.addEventListener('keydown', handleGlobalKeydown, true);
  }

  function destroy() {
    document.removeEventListener('keydown', handleGlobalKeydown, true);
    if (overlayEl && overlayEl.parentNode) {
      overlayEl.parentNode.removeChild(overlayEl);
    }
    overlayEl = null;
    inputEl = null;
    resultsEl = null;
  }

  // ── Public API ─────────────────────────────────────────────
  return {
    init,
    destroy,
    open,
    close,
    toggle,
  };
})();
