/**
 * ChingTech OS - Login Module
 * Handles user authentication (simulated) and session management
 */

const LoginModule = (function() {
  'use strict';

  // Session key for localStorage
  const SESSION_KEY = 'chingtech_session';

  /**
   * Check if user is already logged in
   * @returns {boolean}
   */
  function isLoggedIn() {
    const session = localStorage.getItem(SESSION_KEY);
    if (!session) return false;

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
   * Create a new session
   * @param {string} username
   */
  function createSession(username) {
    const session = {
      username: username,
      timestamp: Date.now()
    };
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }

  /**
   * Clear the current session
   */
  function clearSession() {
    localStorage.removeItem(SESSION_KEY);
  }

  /**
   * Simulate login validation
   * In a real application, this would make an API call
   * @param {string} username
   * @param {string} password
   * @returns {Promise<{success: boolean, message?: string}>}
   */
  async function validateLogin(username, password) {
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 500));

    // Basic validation (simulated - accepts any non-empty credentials)
    if (!username || !password) {
      return {
        success: false,
        message: '請輸入使用者名稱和密碼'
      };
    }

    if (username.length < 2) {
      return {
        success: false,
        message: '使用者名稱至少需要 2 個字元'
      };
    }

    if (password.length < 4) {
      return {
        success: false,
        message: '密碼至少需要 4 個字元'
      };
    }

    // Simulated success
    return {
      success: true
    };
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

    // Disable button during submission
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="mdi mdi-loading mdi-spin"></span> 登入中...';
    errorDiv.classList.remove('show');

    try {
      const result = await validateLogin(username, password);

      if (result.success) {
        createSession(username);
        // Redirect to desktop
        window.location.href = 'index.html';
      } else {
        errorDiv.textContent = result.message;
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
    clearSession
  };
})();

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', LoginModule.init);
