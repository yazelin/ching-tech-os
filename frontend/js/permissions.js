/**
 * ChingTech OS - Permissions Module
 * 使用者權限管理
 */

const PermissionsModule = (function() {
  'use strict';

  // 目前使用者資訊
  let currentUser = null;

  /**
   * 載入目前使用者資訊（包含權限）
   * @returns {Promise<Object|null>}
   */
  async function loadCurrentUser() {
    const token = LoginModule.getToken();
    if (!token) return null;

    try {
      const response = await fetch('/api/user/me', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          LoginModule.clearSession();
          window.location.href = 'login.html';
        }
        return null;
      }

      currentUser = await response.json();
      // 同時設定到 window 以便其他模組存取
      window.currentUser = currentUser;
      return currentUser;
    } catch (error) {
      console.error('Failed to load user info:', error);
      return null;
    }
  }

  /**
   * 取得目前使用者
   * @returns {Object|null}
   */
  function getCurrentUser() {
    return currentUser || window.currentUser;
  }

  /**
   * 檢查是否為管理員（租戶管理員或平台管理員）
   * @returns {boolean}
   */
  function isAdmin() {
    const user = getCurrentUser();
    const session = typeof LoginModule !== 'undefined' ? LoginModule.getSession() : null;
    // 優先使用 session 的 role，因為它更準確
    const role = session?.role || user?.role;
    return role === 'tenant_admin' || role === 'platform_admin';
  }

  /**
   * 檢查是否有應用程式權限
   * @param {string} appId - 應用程式 ID
   * @returns {boolean}
   */
  function canAccessApp(appId) {
    const user = getCurrentUser();
    const session = typeof LoginModule !== 'undefined' ? LoginModule.getSession() : null;
    if (!user && !session) return false;

    const role = session?.role || user?.role;

    // 平台管理員擁有所有權限
    if (role === 'platform_admin') return true;

    // 租戶管理員擁有所有權限（除了平台管理）
    if (role === 'tenant_admin') {
      const platformOnlyApps = ['platform-admin'];
      if (platformOnlyApps.includes(appId)) return false;
      return true;
    }

    // 一般使用者：檢查權限設定，預設為 false
    if (!user?.permissions?.apps) return false;
    return user.permissions.apps[appId] === true;
  }

  /**
   * 檢查是否有知識庫權限
   * @param {string} action - 操作類型（global_write、global_delete）
   * @returns {boolean}
   */
  function canAccessKnowledge(action) {
    const user = getCurrentUser();
    if (!user) return false;

    // 管理員擁有所有權限
    if (user.is_admin) return true;

    return user.permissions?.knowledge?.[action] ?? false;
  }

  /**
   * 檢查是否為平台管理員
   * @returns {boolean}
   */
  function isPlatformAdmin() {
    const session = typeof LoginModule !== 'undefined' ? LoginModule.getSession() : null;
    return session?.role === 'platform_admin';
  }

  /**
   * 檢查是否為租戶管理員
   * @returns {boolean}
   */
  function isTenantAdmin() {
    const session = typeof LoginModule !== 'undefined' ? LoginModule.getSession() : null;
    return session?.role === 'tenant_admin' || session?.role === 'platform_admin';
  }

  /**
   * 取得可存取的應用程式列表
   * @param {Array} allApps - 所有應用程式列表
   * @returns {Array}
   */
  function getAccessibleApps(allApps) {
    const session = typeof LoginModule !== 'undefined' ? LoginModule.getSession() : null;
    const userRole = session?.role;

    return allApps.filter(app => {
      // 檢查角色要求
      if (app.requireRole) {
        if (app.requireRole === 'platform_admin' && userRole !== 'platform_admin') {
          return false;
        }
        if (app.requireRole === 'tenant_admin' && userRole !== 'tenant_admin' && userRole !== 'platform_admin') {
          return false;
        }
      }
      // 檢查一般權限
      return canAccessApp(app.id);
    });
  }

  /**
   * 初始化（載入使用者資訊）
   * @returns {Promise<Object|null>}
   */
  async function init() {
    return await loadCurrentUser();
  }

  // Public API
  return {
    init,
    loadCurrentUser,
    getCurrentUser,
    isAdmin,
    isPlatformAdmin,
    isTenantAdmin,
    canAccessApp,
    canAccessKnowledge,
    getAccessibleApps,
  };
})();
