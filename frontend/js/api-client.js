/**
 * ChingTech OS - API Client
 * REST API wrapper for backend communication
 */

const APIClient = (function() {
  'use strict';

  const BASE_URL = '/api';

  /**
   * 取得認證 token
   * @returns {string|null}
   */
  function getToken() {
    return localStorage.getItem('chingtech_token');
  }

  /**
   * Make an API request
   * @param {string} endpoint
   * @param {Object} options
   * @returns {Promise}
   */
  async function request(endpoint, options = {}) {
    const url = `${BASE_URL}${endpoint}`;
    const token = getToken();
    const defaultOptions = {
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
      },
      credentials: 'include',
    };

    const response = await fetch(url, { ...defaultOptions, ...options });

    if (!response.ok) {
      // 401 未授權：清除 token 並導向登入頁面
      if (response.status === 401) {
        localStorage.removeItem('chingtech_token');
        localStorage.removeItem('chingtech_user');
        window.location.href = 'login.html';
        return;
      }

      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return null;
    }

    return response.json();
  }

  // ========== AI Chat API ==========

  /**
   * Get user's chat list
   * @returns {Promise<Array>}
   */
  async function getChats() {
    return request('/ai/chats');
  }

  /**
   * Create a new chat
   * @param {Object} data - { title, model, prompt_name }
   * @returns {Promise<Object>}
   */
  async function createChat(data = {}) {
    return request('/ai/chats', {
      method: 'POST',
      body: JSON.stringify({
        title: data.title || '新對話',
        model: data.model || 'claude-sonnet',
        prompt_name: data.prompt_name || 'default',
      }),
    });
  }

  /**
   * Get chat details
   * @param {string} chatId
   * @returns {Promise<Object>}
   */
  async function getChat(chatId) {
    return request(`/ai/chats/${chatId}`);
  }

  /**
   * Delete a chat
   * @param {string} chatId
   * @returns {Promise}
   */
  async function deleteChat(chatId) {
    return request(`/ai/chats/${chatId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Update a chat
   * @param {string} chatId
   * @param {Object} data - { title, model, prompt_name }
   * @returns {Promise<Object>}
   */
  async function updateChat(chatId, data) {
    return request(`/ai/chats/${chatId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  /**
   * Get available prompts
   * @returns {Promise<Array>}
   */
  async function getPrompts() {
    return request('/ai/prompts');
  }

  // ========== Tenant API ==========

  /**
   * Get current tenant info
   * @returns {Promise<Object>}
   */
  async function getTenantInfo() {
    return request('/tenant/info');
  }

  /**
   * Get tenant usage statistics
   * @returns {Promise<Object>}
   */
  async function getTenantUsage() {
    return request('/tenant/usage');
  }

  /**
   * Update tenant settings
   * @param {Object} data - { name?, settings? }
   * @returns {Promise<Object>}
   */
  async function updateTenantSettings(data) {
    return request('/tenant/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  /**
   * List tenant admins
   * @returns {Promise<Array>}
   */
  async function getTenantAdmins() {
    return request('/tenant/admins');
  }

  /**
   * Add tenant admin
   * @param {Object} data - { user_id, role }
   * @returns {Promise<Object>}
   */
  async function addTenantAdmin(data) {
    return request('/tenant/admins', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /**
   * Remove tenant admin
   * @param {string} userId
   * @returns {Promise<Object>}
   */
  async function removeTenantAdmin(userId) {
    return request(`/tenant/admins/${userId}`, {
      method: 'DELETE',
    });
  }

  // ========== Generic HTTP Methods ==========

  /**
   * Generic GET request
   * @param {string} endpoint
   * @returns {Promise}
   */
  async function get(endpoint) {
    return request(endpoint, { method: 'GET' });
  }

  /**
   * Generic POST request
   * @param {string} endpoint
   * @param {Object} data
   * @returns {Promise}
   */
  async function post(endpoint, data) {
    return request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /**
   * Generic PUT request
   * @param {string} endpoint
   * @param {Object} data
   * @returns {Promise}
   */
  async function put(endpoint, data) {
    return request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  /**
   * Generic DELETE request
   * @param {string} endpoint
   * @returns {Promise}
   */
  async function del(endpoint) {
    return request(endpoint, { method: 'DELETE' });
  }

  // Public API
  return {
    // Generic HTTP methods
    request,
    get,
    post,
    put,
    delete: del,

    // AI Chats
    getChats,
    createChat,
    getChat,
    deleteChat,
    updateChat,
    getPrompts,

    // Tenant
    getTenantInfo,
    getTenantUsage,
    updateTenantSettings,
    getTenantAdmins,
    addTenantAdmin,
    removeTenantAdmin,
  };
})();

// Alias for compatibility
const ApiClient = APIClient;
