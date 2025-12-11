/**
 * ChingTech OS - Theme Manager
 * 主題管理模組：處理主題切換、偏好儲存與載入
 */

const ThemeManager = (function () {
  'use strict';

  const STORAGE_KEY = 'ching-tech-os-theme';
  const DEFAULT_THEME = 'dark';

  let currentTheme = DEFAULT_THEME;
  let isInitialized = false;

  /**
   * 從 localStorage 取得快取的主題
   * @returns {string} 主題名稱
   */
  function getCachedTheme() {
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
  function setCachedTheme(theme) {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {
      console.warn('無法儲存主題到 localStorage:', e);
    }
  }

  /**
   * 套用主題到 DOM
   * @param {string} theme - 主題名稱 ('dark' | 'light')
   */
  function applyTheme(theme) {
    const validTheme = theme === 'light' ? 'light' : 'dark';
    document.documentElement.dataset.theme = validTheme;
    currentTheme = validTheme;

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
   * 設定主題（僅本地套用，不儲存到後端）
   * @param {string} theme - 主題名稱 ('dark' | 'light')
   */
  function setTheme(theme) {
    applyTheme(theme);
    setCachedTheme(theme);
  }

  /**
   * 從 API 載入使用者偏好
   * @returns {Promise<string>} 使用者偏好的主題
   */
  async function loadUserPreference() {
    try {
      const response = await ApiClient.get('/user/preferences');
      const theme = response.theme || DEFAULT_THEME;
      setTheme(theme);
      return theme;
    } catch (e) {
      console.warn('無法載入使用者偏好，使用預設主題:', e);
      return DEFAULT_THEME;
    }
  }

  /**
   * 儲存使用者偏好到 API
   * @param {string} theme - 主題名稱
   * @returns {Promise<boolean>} 是否儲存成功
   */
  async function saveUserPreference(theme) {
    try {
      await ApiClient.put('/user/preferences', { theme });
      setCachedTheme(theme);
      return true;
    } catch (e) {
      console.error('無法儲存使用者偏好:', e);
      return false;
    }
  }

  /**
   * 初始化主題系統
   * 優先使用 localStorage 快取，避免頁面閃爍
   */
  function init() {
    if (isInitialized) return;

    // 立即套用快取的主題（避免閃爍）
    const cachedTheme = getCachedTheme();
    applyTheme(cachedTheme);

    isInitialized = true;
  }

  /**
   * 初始化並同步使用者偏好
   * 用於登入後載入使用者實際偏好
   */
  async function initWithUserPreference() {
    init();

    // 背景同步使用者偏好
    try {
      await loadUserPreference();
    } catch (e) {
      // 忽略錯誤，繼續使用快取主題
    }
  }

  // 立即初始化（使用快取主題）
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // 公開 API
  return {
    init,
    initWithUserPreference,
    getTheme,
    setTheme,
    loadUserPreference,
    saveUserPreference,
    DEFAULT_THEME,
  };
})();
