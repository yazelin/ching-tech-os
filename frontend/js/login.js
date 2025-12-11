/**
 * ChingTech OS - Login Module
 * Handles user authentication via NAS SMB and session management
 */

const LoginModule = (function() {
  'use strict';

  // Session key for localStorage
  const SESSION_KEY = 'chingtech_session';
  const TOKEN_KEY = 'chingtech_token';

  // API base URL (空字串表示同源)
  const API_BASE = '';

  /**
   * Check if user is already logged in
   * @returns {boolean}
   */
  function isLoggedIn() {
    const token = localStorage.getItem(TOKEN_KEY);
    const session = localStorage.getItem(SESSION_KEY);
    if (!token || !session) return false;

    try {
      const data = JSON.parse(session);
      return data && data.username && data.timestamp;
    } catch (e) {
      return false;
    }
  }

  /**
   * Get current session data
   * @returns {Object|null}
   */
  function getSession() {
    const session = localStorage.getItem(SESSION_KEY);
    if (!session) return null;

    try {
      return JSON.parse(session);
    } catch (e) {
      return null;
    }
  }

  /**
   * Get authentication token
   * @returns {string|null}
   */
  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  /**
   * Create a new session
   * @param {string} username
   * @param {string} token
   */
  function createSession(username, token) {
    const session = {
      username: username,
      timestamp: Date.now()
    };
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    localStorage.setItem(TOKEN_KEY, token);
  }

  /**
   * Clear the current session
   */
  function clearSession() {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(TOKEN_KEY);
  }

  /**
   * Call login API
   * @param {string} username
   * @param {string} password
   * @param {Object} device - 裝置資訊
   * @returns {Promise<{success: boolean, token?: string, username?: string, error?: string}>}
   */
  async function callLoginAPI(username, password, device = null) {
    try {
      const body = { username, password };
      if (device) {
        body.device = device;
      }

      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      if (response.status === 503) {
        return {
          success: false,
          error: '無法連線至檔案伺服器'
        };
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Login API error:', error);
      return {
        success: false,
        error: '無法連線至伺服器'
      };
    }
  }

  /**
   * Call logout API
   * @returns {Promise<void>}
   */
  async function callLogoutAPI() {
    const token = getToken();
    if (!token) return;

    try {
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
    } catch (error) {
      console.error('Logout API error:', error);
    }
  }

  /**
   * Handle login form submission
   * @param {Event} event
   */
  async function handleLogin(event) {
    event.preventDefault();

    const form = event.target;
    const username = form.querySelector('#username').value.trim();
    const password = form.querySelector('#password').value;
    const submitBtn = form.querySelector('.login-btn');
    const errorDiv = form.querySelector('.login-error');

    // Basic validation
    if (!username || !password) {
      errorDiv.textContent = '請輸入使用者名稱和密碼';
      errorDiv.classList.add('show');
      return;
    }

    // Disable button during submission
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="mdi mdi-loading mdi-spin"></span> 登入中...';
    errorDiv.classList.remove('show');

    try {
      // 產生裝置指紋
      let deviceInfo = null;
      if (window.DeviceFingerprint) {
        try {
          deviceInfo = await DeviceFingerprint.generate();
        } catch (e) {
          console.warn('無法產生裝置指紋:', e);
        }
      }

      const result = await callLoginAPI(username, password, deviceInfo);

      if (result.success && result.token) {
        createSession(result.username, result.token);
        // Redirect to desktop
        window.location.href = 'index.html';
      } else {
        errorDiv.textContent = result.error || '登入失敗';
        errorDiv.classList.add('show');
      }
    } catch (error) {
      errorDiv.textContent = '登入時發生錯誤，請稍後再試';
      errorDiv.classList.add('show');
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span class="mdi mdi-login"></span> 登入';
    }
  }

  /**
   * Logout and redirect to login page
   */
  async function logout() {
    await callLogoutAPI();
    clearSession();
    window.location.href = 'login.html';
  }

  /**
   * Initialize login page
   */
  function init() {
    // Check if already logged in
    if (isLoggedIn()) {
      window.location.href = 'index.html';
      return;
    }

    // Attach form handler
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
      loginForm.addEventListener('submit', handleLogin);
    }
  }

  // Public API
  return {
    init,
    isLoggedIn,
    getSession,
    getToken,
    clearSession,
    logout
  };
})();

// Initialize only on login page
document.addEventListener('DOMContentLoaded', function() {
  // Only run init on login.html page
  if (window.location.pathname.endsWith('login.html') ||
      window.location.pathname === '/' ||
      window.location.pathname.endsWith('/')) {
    LoginModule.init();
  }
});
