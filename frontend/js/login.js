/**
 * ChingTech OS - Login Module
 * Handles user authentication via NAS SMB and session management
 */

const LoginModule = (function() {
  'use strict';

  // Session key for localStorage
  const SESSION_KEY = 'chingtech_session';
  const TOKEN_KEY = 'chingtech_token';
  const TENANT_KEY = 'chingtech_tenant';
  const LAST_TENANT_KEY = 'chingtech_last_tenant';

  // API base URL (空字串表示同源，由 config.js 自動處理)
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
   * @param {Object} tenant - 租戶資訊（可選）
   * @param {string} role - 使用者角色（user, tenant_admin, platform_admin）
   */
  function createSession(username, token, tenant = null, role = 'user') {
    const session = {
      username: username,
      timestamp: Date.now(),
      role: role
    };
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    localStorage.setItem(TOKEN_KEY, token);

    // 儲存租戶資訊
    if (tenant) {
      localStorage.setItem(TENANT_KEY, JSON.stringify(tenant));
      localStorage.setItem(LAST_TENANT_KEY, tenant.code);
    }
  }

  /**
   * Get current tenant info
   * @returns {Object|null}
   */
  function getTenant() {
    const tenant = localStorage.getItem(TENANT_KEY);
    if (!tenant) return null;

    try {
      return JSON.parse(tenant);
    } catch (e) {
      return null;
    }
  }

  /**
   * Clear the current session
   */
  function clearSession() {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TENANT_KEY);
    // 注意：不清除 LAST_TENANT_KEY，方便下次登入時自動填入
  }

  /**
   * Call login API
   * @param {string} username
   * @param {string} password
   * @param {Object} device - 裝置資訊
   * @param {string} tenantCode - 租戶代碼（多租戶模式必填）
   * @returns {Promise<{success: boolean, token?: string, username?: string, tenant?: Object, error?: string}>}
   */
  async function callLoginAPI(username, password, device = null, tenantCode = null) {
    try {
      const body = { username, password };
      if (device) {
        body.device = device;
      }
      if (tenantCode) {
        body.tenant_code = tenantCode;
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
   * Validate session with backend
   * Call this on page load to ensure token is still valid
   * @returns {Promise<boolean>} true if session is valid
   */
  async function validateSession() {
    const token = getToken();
    if (!token) return false;

    try {
      const response = await fetch(`${API_BASE}/api/user/me`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.status === 401) {
        // Token is invalid, clear local session
        clearSession();
        return false;
      }

      return response.ok;
    } catch (error) {
      console.error('Session validation error:', error);
      // Network error, assume session might still be valid
      // Let the user try to use the app
      return true;
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
   * Call change password API
   * @param {string} token - Auth token
   * @param {string} currentPassword
   * @param {string} newPassword
   * @returns {Promise<{success: boolean, error?: string}>}
   */
  async function callChangePasswordAPI(token, currentPassword, newPassword) {
    try {
      const response = await fetch(`${API_BASE}/api/auth/change-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Change password API error:', error);
      return {
        success: false,
        error: '無法連線至伺服器',
      };
    }
  }

  /**
   * Show change password dialog
   * @param {string} token - Auth token
   * @param {string} currentPassword - The password used to login
   * @returns {Promise<boolean>} true if password was changed successfully
   */
  async function showChangePasswordDialog(token, currentPassword) {
    return new Promise((resolve) => {
      // 建立對話框 HTML
      const dialogHTML = `
        <div class="change-password-overlay" id="changePasswordOverlay">
          <div class="change-password-dialog">
            <div class="change-password-header">
              <h2>變更密碼</h2>
              <p>您需要設定新的密碼才能繼續使用</p>
            </div>
            <form id="changePasswordForm" class="change-password-form">
              <div class="change-password-error" id="changePasswordError"></div>
              <div class="form-group">
                <label for="newPassword">新密碼</label>
                <input
                  type="password"
                  id="newPassword"
                  name="newPassword"
                  class="input"
                  placeholder="請輸入新密碼（至少 8 個字元）"
                  required
                  minlength="8"
                >
              </div>
              <div class="form-group">
                <label for="confirmPassword">確認新密碼</label>
                <input
                  type="password"
                  id="confirmPassword"
                  name="confirmPassword"
                  class="input"
                  placeholder="請再次輸入新密碼"
                  required
                >
              </div>
              <div class="change-password-actions">
                <button type="submit" class="btn btn-accent" id="changePasswordSubmit">
                  確認變更
                </button>
              </div>
            </form>
          </div>
        </div>
      `;

      // 加入頁面
      document.body.insertAdjacentHTML('beforeend', dialogHTML);

      const overlay = document.getElementById('changePasswordOverlay');
      const form = document.getElementById('changePasswordForm');
      const errorDiv = document.getElementById('changePasswordError');
      const submitBtn = document.getElementById('changePasswordSubmit');
      const newPasswordInput = document.getElementById('newPassword');
      const confirmPasswordInput = document.getElementById('confirmPassword');

      // Focus 新密碼輸入框
      newPasswordInput.focus();

      // 處理表單提交
      form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const newPassword = newPasswordInput.value;
        const confirmPassword = confirmPasswordInput.value;

        // 驗證密碼
        if (newPassword.length < 8) {
          errorDiv.textContent = '密碼至少需要 8 個字元';
          errorDiv.classList.add('show');
          return;
        }

        if (newPassword !== confirmPassword) {
          errorDiv.textContent = '兩次輸入的密碼不一致';
          errorDiv.classList.add('show');
          return;
        }

        // 禁用按鈕
        submitBtn.disabled = true;
        submitBtn.textContent = '變更中...';
        errorDiv.classList.remove('show');

        try {
          const result = await callChangePasswordAPI(token, currentPassword, newPassword);

          if (result.success) {
            // 移除對話框
            overlay.remove();
            resolve(true);
          } else {
            errorDiv.textContent = result.error || '變更密碼失敗';
            errorDiv.classList.add('show');
            submitBtn.disabled = false;
            submitBtn.textContent = '確認變更';
          }
        } catch (error) {
          errorDiv.textContent = '發生錯誤，請稍後再試';
          errorDiv.classList.add('show');
          submitBtn.disabled = false;
          submitBtn.textContent = '確認變更';
        }
      });
    });
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
    const tenantCodeInput = form.querySelector('#tenantCode');
    const tenantCode = tenantCodeInput ? tenantCodeInput.value.trim() : null;
    const submitBtn = form.querySelector('.login-btn');
    const errorDiv = form.querySelector('.login-error');

    // Basic validation
    if (!username || !password) {
      errorDiv.textContent = '請輸入使用者名稱和密碼';
      errorDiv.classList.add('show');
      return;
    }

    // 多租戶模式下檢查租戶代碼
    const tenantCodeGroup = document.getElementById('tenantCodeGroup');
    if (tenantCodeGroup && tenantCodeGroup.style.display !== 'none' && !tenantCode) {
      errorDiv.textContent = '請輸入公司代碼';
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

      const result = await callLoginAPI(username, password, deviceInfo, tenantCode);

      if (result.success && result.token) {
        // 檢查是否需要變更密碼
        if (result.must_change_password) {
          // 先建立 session（需要 token 來呼叫變更密碼 API）
          createSession(result.username, result.token, result.tenant, result.role);

          // 還原按鈕狀態
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<span class="icon" id="iconLogin2"></span> 登入';
          if (document.getElementById('iconLogin2')) {
            document.getElementById('iconLogin2').innerHTML = typeof getIcon === 'function' ? getIcon('login') : '';
          }

          // 顯示變更密碼對話框
          const changed = await showChangePasswordDialog(result.token, password);
          if (changed) {
            // 密碼已變更，導向桌面
            window.location.href = 'index.html';
          } else {
            // 使用者未完成密碼變更（不應該發生，因為對話框沒有取消按鈕）
            clearSession();
            errorDiv.textContent = '請完成密碼變更才能繼續使用';
            errorDiv.classList.add('show');
          }
        } else {
          // 不需要變更密碼，直接建立 session 並導向桌面
          createSession(result.username, result.token, result.tenant, result.role);
          window.location.href = 'index.html';
        }
      } else {
        errorDiv.textContent = result.error || '登入失敗';
        errorDiv.classList.add('show');
      }
    } catch (error) {
      errorDiv.textContent = '登入時發生錯誤，請稍後再試';
      errorDiv.classList.add('show');
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span class="icon" id="iconLoginFinal"></span> 登入';
      if (document.getElementById('iconLoginFinal')) {
        document.getElementById('iconLoginFinal').innerHTML = typeof getIcon === 'function' ? getIcon('login') : '';
      }
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
    validateSession,
    getSession,
    getToken,
    getTenant,
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
