/**
 * ChingTech OS - Tenant Context Module
 * 管理租戶上下文，提供租戶資訊給其他模組使用
 */

const TenantContext = (function() {
  'use strict';

  const TENANT_KEY = 'chingtech_tenant';
  let _tenant = null;
  let _tenantInfo = null;  // 完整的租戶資訊（從 API 取得）
  let _isInitialized = false;

  /**
   * 從 localStorage 載入租戶資訊
   */
  function loadFromStorage() {
    const stored = localStorage.getItem(TENANT_KEY);
    if (stored) {
      try {
        _tenant = JSON.parse(stored);
      } catch (e) {
        console.warn('[TenantContext] 無法解析儲存的租戶資訊');
        _tenant = null;
      }
    }
  }

  /**
   * 從 API 取得完整的租戶資訊
   */
  async function fetchTenantInfo() {
    if (!_tenant) return null;

    try {
      const token = localStorage.getItem('chingtech_token');
      if (!token) return null;

      const response = await fetch('/api/tenant/info', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        _tenantInfo = await response.json();
        return _tenantInfo;
      }
    } catch (error) {
      console.warn('[TenantContext] 無法取得租戶詳細資訊:', error);
    }
    return null;
  }

  /**
   * 初始化租戶上下文
   * @returns {Promise<void>}
   */
  async function init() {
    if (_isInitialized) return;

    loadFromStorage();
    if (_tenant) {
      await fetchTenantInfo();
    }
    _isInitialized = true;
    console.log('[TenantContext] 初始化完成', _tenant ? `租戶: ${_tenant.name}` : '無租戶');
  }

  /**
   * 取得目前租戶 ID
   * @returns {string|null}
   */
  function getTenantId() {
    return _tenant ? _tenant.id : null;
  }

  /**
   * 取得目前租戶代碼
   * @returns {string|null}
   */
  function getTenantCode() {
    return _tenant ? _tenant.code : null;
  }

  /**
   * 取得目前租戶名稱
   * @returns {string|null}
   */
  function getTenantName() {
    return _tenant ? _tenant.name : null;
  }

  /**
   * 取得目前租戶方案
   * @returns {string|null}
   */
  function getTenantPlan() {
    return _tenant ? _tenant.plan : null;
  }

  /**
   * 取得完整租戶資訊（基本資訊，登入時儲存）
   * @returns {Object|null}
   */
  function getTenant() {
    return _tenant;
  }

  /**
   * 取得詳細租戶資訊（從 API 取得）
   * @returns {Object|null}
   */
  function getTenantInfo() {
    return _tenantInfo;
  }

  /**
   * 檢查是否有租戶
   * @returns {boolean}
   */
  function hasTenant() {
    return _tenant !== null;
  }

  /**
   * 更新租戶資訊
   * @param {Object} tenant - 租戶資訊
   */
  function setTenant(tenant) {
    _tenant = tenant;
    if (tenant) {
      localStorage.setItem(TENANT_KEY, JSON.stringify(tenant));
    } else {
      localStorage.removeItem(TENANT_KEY);
    }
  }

  /**
   * 清除租戶資訊
   */
  function clear() {
    _tenant = null;
    _tenantInfo = null;
    localStorage.removeItem(TENANT_KEY);
  }

  /**
   * 重新載入租戶資訊
   */
  async function reload() {
    loadFromStorage();
    if (_tenant) {
      await fetchTenantInfo();
    }
  }

  // Public API
  return {
    init,
    getTenantId,
    getTenantCode,
    getTenantName,
    getTenantPlan,
    getTenant,
    getTenantInfo,
    hasTenant,
    setTenant,
    clear,
    reload
  };
})();
