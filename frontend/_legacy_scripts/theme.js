/**
 * ChingTech OS - Theme Manager
 * 主題管理模組：處理主題切換與本地儲存
 * 主題設定僅存在 localStorage，不同步到後端
 */

const ThemeManager = (function () {
  'use strict';

  const STORAGE_KEY = 'ching-tech-os-theme';
  const DEFAULT_THEME = 'dark';

  let currentTheme = DEFAULT_THEME;
  let isInitialized = false;

  /**
   * 從 localStorage 取得主題
   * @returns {string} 主題名稱
   */
  function getStoredTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME;
    } catch (e) {
      return DEFAULT_THEME;
    }
  }

  /**
   * 將主題儲存到 localStorage
   * @param {string} theme - 主題名稱
   */
  function storeTheme(theme) {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {
      console.warn('無法儲存主題到 localStorage:', e);
    }
  }

  /**
   * 套用主題到 DOM
   * @param {string} theme - 主題名稱 ('dark' | 'light')
   * @param {boolean} animate - 是否啟用過渡動畫
   */
  function applyTheme(theme, animate = false) {
    const validTheme = theme === 'light' ? 'light' : 'dark';

    // 如果需要動畫，先加上過渡 class
    if (animate) {
      document.body.classList.add('theme-transitioning');
    }

    document.documentElement.dataset.theme = validTheme;
    currentTheme = validTheme;

    // 過渡完成後移除 class
    if (animate) {
      setTimeout(() => {
        document.body.classList.remove('theme-transitioning');
      }, 550); // 比 CSS transition 時間稍長
    }

    // 通知終端機更新主題
    updateTerminalTheme();
  }

  /**
   * 更新終端機主題（若終端機已開啟）
   */
  function updateTerminalTheme() {
    // 找到所有終端機實例並更新主題
    const terminals = document.querySelectorAll('.terminal-container .xterm');
    if (terminals.length === 0) return;

    // 終端機透過 CSS 變數取得顏色，需要重新讀取
    // 這裡透過觸發 resize 讓終端機重繪
    window.dispatchEvent(new Event('resize'));
  }

  /**
   * 取得目前主題
   * @returns {string} 目前主題名稱
   */
  function getTheme() {
    return currentTheme;
  }

  /**
   * 設定主題
   * @param {string} theme - 主題名稱 ('dark' | 'light')
   * @param {boolean} animate - 是否啟用過渡動畫（預設 true）
   */
  function setTheme(theme, animate = true) {
    applyTheme(theme, animate);
    storeTheme(theme);
  }

  /**
   * 切換主題（在 dark 和 light 之間切換）
   * @returns {string} 切換後的主題名稱
   */
  function toggleTheme() {
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    return newTheme;
  }

  /**
   * 初始化主題系統
   * 從 localStorage 讀取並套用主題
   */
  function init() {
    if (isInitialized) return;

    // 立即套用儲存的主題（避免閃爍）
    const storedTheme = getStoredTheme();
    applyTheme(storedTheme);

    isInitialized = true;
  }

  // 立即初始化
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // 公開 API
  return {
    init,
    getTheme,
    setTheme,
    toggleTheme,
    DEFAULT_THEME,
  };
})();
