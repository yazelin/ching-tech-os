/**
 * ChingTech OS — 統一回饋狀態元件 (Loading / Empty / Error)
 *
 * 提供 showLoading / showEmpty / showError 三個 API，
 * 取代各模組分散的 .kb-loading、.ai-chat-empty 等重複實作。
 *
 * 使用範例：
 *   UIHelpers.showLoading(containerEl, { text: '載入知識庫…' });
 *   UIHelpers.showEmpty(containerEl, { icon: 'book-open-page-variant', text: '尚無資料' });
 *   UIHelpers.showError(containerEl, { message: err.message, onRetry: () => loadData() });
 *   UIHelpers.showSkeleton(containerEl, { rows: 5 });
 */
const UIHelpers = (function () {
  'use strict';

  // ── 預設值 ──
  const DEFAULTS = {
    loadingIcon: 'refresh',
    loadingText: '載入中…',
    emptyIcon: 'information-outline',
    emptyText: '目前沒有資料',
    errorIcon: 'alert-circle',
    errorText: '載入失敗',
    retryText: '重試',
    skeletonRows: 3,
  };

  /**
   * 取得圖示 HTML（依賴全域 getIcon）
   * @param {string} name - icon 名稱
   * @returns {string} HTML
   */
  function icon(name) {
    return typeof getIcon === 'function' ? getIcon(name) : '';
  }

  // ── 核心 API ─────────────────────────────────────────────

  /**
   * 顯示 Loading 狀態（旋轉圖示 + 文字）
   *
   * @param {HTMLElement} container - 要填入 HTML 的容器
   * @param {Object}  [opts]
   * @param {string}  [opts.icon]      - 圖示名稱（預設 'refresh'）
   * @param {string}  [opts.text]      - 載入提示文字
   * @param {string}  [opts.variant]   - 'fill' | 'compact' | '' （預設 ''）
   * @returns {HTMLElement} 產生的 .ui-state 元素
   */
  function showLoading(container, opts = {}) {
    const variant = opts.variant ? ` ui-state--${opts.variant}` : '';
    const html = `
      <div class="ui-state ui-state--loading${variant}" role="status" aria-live="polite">
        <span class="ui-state-icon">${icon(opts.icon || DEFAULTS.loadingIcon)}</span>
        <span class="ui-state-text">${opts.text || DEFAULTS.loadingText}</span>
      </div>`;
    container.innerHTML = html;
    return container.firstElementChild;
  }

  /**
   * 顯示 Empty 狀態（圖示 + 說明文字）
   *
   * @param {HTMLElement} container
   * @param {Object}  [opts]
   * @param {string}  [opts.icon]       - 圖示名稱
   * @param {string}  [opts.text]       - 主要文字
   * @param {string}  [opts.subtext]    - 次要說明（選填）
   * @param {string}  [opts.variant]    - 'fill' | 'compact' | ''
   * @returns {HTMLElement}
   */
  function showEmpty(container, opts = {}) {
    const variant = opts.variant ? ` ui-state--${opts.variant}` : '';
    const sub = opts.subtext ? `<p class="ui-state-text">${opts.subtext}</p>` : '';
    const html = `
      <div class="ui-state ui-state--empty${variant}" role="status">
        <span class="ui-state-icon">${icon(opts.icon || DEFAULTS.emptyIcon)}</span>
        <span class="ui-state-text">${opts.text || DEFAULTS.emptyText}</span>
        ${sub}
      </div>`;
    container.innerHTML = html;
    return container.firstElementChild;
  }

  /**
   * 顯示 Error 狀態（錯誤圖示 + 訊息 + 可選重試按鈕）
   *
   * @param {HTMLElement} container
   * @param {Object}  [opts]
   * @param {string}  [opts.icon]       - 圖示名稱（預設 'alert-circle'）
   * @param {string}  [opts.message]    - 錯誤訊息
   * @param {string}  [opts.detail]     - 詳細資訊（選填，例如 error.message）
   * @param {string}  [opts.variant]    - 'fill' | 'compact' | ''
   * @param {Function} [opts.onRetry]   - 重試回呼（若提供則顯示重試按鈕）
   * @returns {HTMLElement}
   */
  function showError(container, opts = {}) {
    const variant = opts.variant ? ` ui-state--${opts.variant}` : '';
    const detail = opts.detail
      ? `<span class="ui-state-detail">${opts.detail}</span>`
      : '';
    const retryBtn = opts.onRetry
      ? `<button class="ui-state-retry" type="button">${DEFAULTS.retryText}</button>`
      : '';

    const html = `
      <div class="ui-state ui-state--error${variant}" role="alert" aria-live="assertive">
        <span class="ui-state-icon">${icon(opts.icon || DEFAULTS.errorIcon)}</span>
        <span class="ui-state-text">${opts.message || DEFAULTS.errorText}</span>
        ${detail}
        ${retryBtn}
      </div>`;
    container.innerHTML = html;

    // 綁定重試事件
    if (opts.onRetry) {
      const btn = container.querySelector('.ui-state-retry');
      if (btn) btn.addEventListener('click', opts.onRetry);
    }
    return container.firstElementChild;
  }

  /**
   * 顯示骨架屏 Loading（shimmer 佔位列）
   *
   * @param {HTMLElement} container
   * @param {Object}  [opts]
   * @param {number}  [opts.rows]   - 骨架行數（預設 3）
   * @param {number}  [opts.height] - 每行高度 px（預設 44）
   * @returns {HTMLElement}
   */
  function showSkeleton(container, opts = {}) {
    const rows = opts.rows || DEFAULTS.skeletonRows;
    const h = opts.height || 44;
    const items = Array.from({ length: rows }, (_, i) => {
      // 交替寬度讓骨架看起來更自然
      const w = i % 3 === 1 ? '90%' : i % 3 === 2 ? '75%' : '100%';
      return `<div class="skeleton" style="height:${h}px;width:${w}"></div>`;
    }).join('');

    container.innerHTML = `<div class="ui-state-skeleton">${items}</div>`;
    return container.firstElementChild;
  }

  /**
   * 清除容器的回饋狀態
   * @param {HTMLElement} container
   */
  function clear(container) {
    const el = container.querySelector('.ui-state, .ui-state-skeleton');
    if (el) el.remove();
  }

  // ── Public API ──
  return {
    showLoading,
    showEmpty,
    showError,
    showSkeleton,
    clear,
  };
})();
