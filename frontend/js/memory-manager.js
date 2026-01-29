/**
 * 記憶管理應用程式
 * 管理 Line Bot 群組和個人的自訂記憶
 */

const MemoryManagerApp = (function() {
  'use strict';

  const APP_ID = 'memory-manager';
  let currentWindowId = null;
  let currentTab = 'group';  // 'group' 或 'personal'
  let groups = [];
  let users = [];
  let memories = [];
  let selectedGroupId = null;
  let selectedUserId = null;

  /**
   * 取得圖示 HTML（包含 .icon 包裝）
   */
  function icon(name, extraClass = '') {
    if (typeof window.getIcon === 'function') {
      return `<span class="icon ${extraClass}">${window.getIcon(name)}</span>`;
    }
    return `<span class="icon ${extraClass}"><span class="mdi mdi-${name}"></span></span>`;
  }

  /**
   * 格式化日期時間
   */
  function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-TW', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  /**
   * API 請求
   */
  async function apiRequest(endpoint, options = {}) {
    const token = typeof LoginModule !== 'undefined' ? LoginModule.getToken() : null;
    const response = await fetch(`/api/bot${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...options.headers
      }
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || '請求失敗');
    }

    if (response.status === 204) {
      return null;
    }

    return response.json();
  }

  /**
   * 取得視窗內容 HTML
   */
  function getWindowContent() {
    return `
      <div class="memory-manager">
        <div class="mm-tabs">
          <button class="mm-tab active" data-tab="group">
            ${icon('account-group')}
            <span>群組記憶</span>
          </button>
          <button class="mm-tab" data-tab="personal">
            ${icon('account')}
            <span>個人記憶</span>
          </button>
        </div>
        <div class="mm-content">
          <div class="mm-sidebar">
            <div class="mm-sidebar-header">
              <span id="mmSidebarTitle">群組列表</span>
            </div>
            <div class="mm-sidebar-list" id="mmSidebarList">
              <div class="mm-loading">
                ${icon('loading', 'mdi-spin')}
              </div>
            </div>
          </div>
          <div class="mm-main">
            <div class="mm-main-header">
              <button class="mm-mobile-back-btn" id="mmBackBtn">
                ${icon('arrow-left')}
              </button>
              <span class="mm-main-title" id="mmMainTitle">請選擇群組</span>
              <button class="mm-add-btn" id="mmAddBtn" style="display: none;">
                ${icon('plus')}
                <span>新增記憶</span>
              </button>
            </div>
            <div class="mm-memory-list" id="mmMemoryList">
              <div class="mm-empty">
                ${icon('brain')}
                <p>請從左側選擇群組或用戶</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * 載入群組列表
   */
  async function loadGroups(windowEl) {
    const listEl = windowEl.querySelector('#mmSidebarList');
    if (!listEl) return;

    listEl.innerHTML = `<div class="mm-loading">${icon('loading', 'mdi-spin')}</div>`;

    try {
      const result = await apiRequest('/groups?limit=100');
      groups = result.items || [];
      renderGroupList(listEl);
    } catch (error) {
      console.error('Failed to load groups:', error);
      listEl.innerHTML = `
        <div class="mm-error">
          ${icon('alert-circle')}
          <p>${error.message}</p>
        </div>
      `;
    }
  }

  /**
   * 載入用戶列表
   */
  async function loadUsers(windowEl) {
    const listEl = windowEl.querySelector('#mmSidebarList');
    if (!listEl) return;

    listEl.innerHTML = `<div class="mm-loading">${icon('loading', 'mdi-spin')}</div>`;

    try {
      const result = await apiRequest('/users-with-binding?limit=100');
      users = result.items || [];
      renderUserList(listEl);
    } catch (error) {
      console.error('Failed to load users:', error);
      listEl.innerHTML = `
        <div class="mm-error">
          ${icon('alert-circle')}
          <p>${error.message}</p>
        </div>
      `;
    }
  }

  /**
   * 渲染群組列表
   */
  function renderGroupList(listEl) {
    if (groups.length === 0) {
      listEl.innerHTML = `
        <div class="mm-empty-sidebar">
          ${icon('account-group-outline')}
          <p>沒有群組</p>
        </div>
      `;
      return;
    }

    listEl.innerHTML = groups.map(group => `
      <div class="mm-sidebar-item ${selectedGroupId === group.id ? 'active' : ''}"
           data-id="${group.id}">
        <div class="mm-sidebar-item-icon">
          ${icon('account-group')}
        </div>
        <div class="mm-sidebar-item-info">
          <span class="mm-sidebar-item-name">${escapeHtml(group.name || '未命名群組')}</span>
          <span class="mm-sidebar-item-meta">${group.member_count} 人</span>
        </div>
      </div>
    `).join('');

    // 綁定點擊事件
    listEl.querySelectorAll('.mm-sidebar-item').forEach(item => {
      item.addEventListener('click', () => {
        const id = item.dataset.id;
        selectGroup(id, listEl.closest('.memory-manager'));
      });
    });
  }

  /**
   * 渲染用戶列表
   */
  function renderUserList(listEl) {
    if (users.length === 0) {
      listEl.innerHTML = `
        <div class="mm-empty-sidebar">
          ${icon('account-outline')}
          <p>沒有用戶</p>
        </div>
      `;
      return;
    }

    listEl.innerHTML = users.map(user => `
      <div class="mm-sidebar-item ${selectedUserId === user.id ? 'active' : ''}"
           data-id="${user.id}">
        <div class="mm-sidebar-item-avatar">
          ${user.picture_url
            ? `<img src="${escapeHtml(user.picture_url)}" alt="">`
            : icon('account')}
        </div>
        <div class="mm-sidebar-item-info">
          <span class="mm-sidebar-item-name">${escapeHtml(user.display_name || '未知用戶')}</span>
          <span class="mm-sidebar-item-meta">${user.bound_username ? '已綁定' : '未綁定'}</span>
        </div>
      </div>
    `).join('');

    // 綁定點擊事件
    listEl.querySelectorAll('.mm-sidebar-item').forEach(item => {
      item.addEventListener('click', () => {
        const id = item.dataset.id;
        selectUser(id, listEl.closest('.memory-manager'));
      });
    });
  }

  /**
   * 選擇群組
   */
  async function selectGroup(groupId, containerEl) {
    selectedGroupId = groupId;
    selectedUserId = null;

    // 更新 sidebar 選中狀態
    const listEl = containerEl.querySelector('#mmSidebarList');
    listEl.querySelectorAll('.mm-sidebar-item').forEach(item => {
      item.classList.toggle('active', item.dataset.id === groupId);
    });

    // 顯示新增按鈕
    const addBtn = containerEl.querySelector('#mmAddBtn');
    if (addBtn) addBtn.style.display = 'flex';

    // 更新標題
    const group = groups.find(g => g.id === groupId);
    const titleEl = containerEl.querySelector('#mmMainTitle');
    if (titleEl) {
      titleEl.textContent = group ? (group.name || '未命名群組') : '群組記憶';
    }

    // 手機版：顯示詳情
    containerEl.classList.add('showing-detail');

    // 載入記憶
    await loadMemories(containerEl, 'group', groupId);
  }

  /**
   * 選擇用戶
   */
  async function selectUser(userId, containerEl) {
    selectedUserId = userId;
    selectedGroupId = null;

    // 更新 sidebar 選中狀態
    const listEl = containerEl.querySelector('#mmSidebarList');
    listEl.querySelectorAll('.mm-sidebar-item').forEach(item => {
      item.classList.toggle('active', item.dataset.id === userId);
    });

    // 顯示新增按鈕
    const addBtn = containerEl.querySelector('#mmAddBtn');
    if (addBtn) addBtn.style.display = 'flex';

    // 更新標題
    const user = users.find(u => u.id === userId);
    const titleEl = containerEl.querySelector('#mmMainTitle');
    if (titleEl) {
      titleEl.textContent = user ? (user.display_name || '未知用戶') : '個人記憶';
    }

    // 手機版：顯示詳情
    containerEl.classList.add('showing-detail');

    // 載入記憶
    await loadMemories(containerEl, 'user', userId);
  }

  /**
   * 載入記憶列表
   */
  async function loadMemories(containerEl, type, id) {
    const listEl = containerEl.querySelector('#mmMemoryList');
    if (!listEl) return;

    listEl.innerHTML = `<div class="mm-loading">${icon('loading', 'mdi-spin')}</div>`;

    try {
      const endpoint = type === 'group'
        ? `/groups/${id}/memories`
        : `/users/${id}/memories`;
      const result = await apiRequest(endpoint);
      memories = result.items || [];
      renderMemories(listEl, containerEl);
    } catch (error) {
      console.error('Failed to load memories:', error);
      listEl.innerHTML = `
        <div class="mm-error">
          ${icon('alert-circle')}
          <p>${error.message}</p>
        </div>
      `;
    }
  }

  /**
   * 渲染記憶列表
   */
  function renderMemories(listEl, containerEl) {
    if (memories.length === 0) {
      listEl.innerHTML = `
        <div class="mm-empty">
          ${icon('brain')}
          <p>目前沒有設定任何記憶</p>
          <p class="mm-empty-hint">點擊「新增記憶」來建立第一筆記憶</p>
        </div>
      `;
      return;
    }

    listEl.innerHTML = memories.map(memory => `
      <div class="mm-memory-card ${memory.is_active ? '' : 'inactive'}" data-id="${memory.id}">
        <div class="mm-memory-header">
          <label class="mm-memory-checkbox">
            <input type="checkbox" ${memory.is_active ? 'checked' : ''} data-id="${memory.id}">
            <span class="mm-checkbox-mark"></span>
          </label>
          <span class="mm-memory-title">${escapeHtml(memory.title)}</span>
          <div class="mm-memory-actions">
            <button class="mm-memory-btn" data-action="edit" data-id="${memory.id}" title="編輯">
              ${icon('pencil')}
            </button>
            <button class="mm-memory-btn danger" data-action="delete" data-id="${memory.id}" title="刪除">
              ${icon('delete')}
            </button>
          </div>
        </div>
        <div class="mm-memory-content">${escapeHtml(memory.content)}</div>
        <div class="mm-memory-meta">
          <span>${icon('clock-outline')} ${formatDateTime(memory.created_at)}</span>
          ${memory.created_by_name ? `<span>${icon('account')} ${escapeHtml(memory.created_by_name)}</span>` : ''}
        </div>
      </div>
    `).join('');

    // 綁定事件
    bindMemoryEvents(listEl, containerEl);
  }

  /**
   * 綁定記憶事件
   */
  function bindMemoryEvents(listEl, containerEl) {
    // 勾選框（切換啟用狀態）
    listEl.querySelectorAll('.mm-memory-checkbox input').forEach(checkbox => {
      checkbox.addEventListener('change', async () => {
        const memoryId = checkbox.dataset.id;
        const isActive = checkbox.checked;
        await toggleMemoryActive(memoryId, isActive, containerEl);
      });
    });

    // 編輯按鈕
    listEl.querySelectorAll('[data-action="edit"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const memoryId = btn.dataset.id;
        const memory = memories.find(m => m.id === memoryId);
        if (memory) {
          showEditModal(memory, containerEl);
        }
      });
    });

    // 刪除按鈕
    listEl.querySelectorAll('[data-action="delete"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const memoryId = btn.dataset.id;
        if (!confirm('確定要刪除此記憶嗎？')) return;
        await deleteMemory(memoryId, containerEl);
      });
    });
  }

  /**
   * 切換記憶啟用狀態
   */
  async function toggleMemoryActive(memoryId, isActive, containerEl) {
    try {
      await apiRequest(`/memories/${memoryId}`, {
        method: 'PUT',
        body: JSON.stringify({ is_active: isActive })
      });

      // 更新本地狀態
      const memory = memories.find(m => m.id === memoryId);
      if (memory) memory.is_active = isActive;

      // 更新 UI
      const card = containerEl.querySelector(`.mm-memory-card[data-id="${memoryId}"]`);
      if (card) {
        card.classList.toggle('inactive', !isActive);
      }

      showToast(isActive ? '記憶已啟用' : '記憶已停用', 'check');
    } catch (error) {
      console.error('Failed to toggle memory:', error);
      showToast('更新失敗：' + error.message, 'alert-circle');
      // 恢復 checkbox 狀態
      const checkbox = containerEl.querySelector(`.mm-memory-checkbox input[data-id="${memoryId}"]`);
      if (checkbox) checkbox.checked = !isActive;
    }
  }

  /**
   * 刪除記憶
   */
  async function deleteMemory(memoryId, containerEl) {
    try {
      await apiRequest(`/memories/${memoryId}`, { method: 'DELETE' });

      // 從列表移除
      memories = memories.filter(m => m.id !== memoryId);
      const listEl = containerEl.querySelector('#mmMemoryList');
      renderMemories(listEl, containerEl);

      showToast('記憶已刪除', 'check');
    } catch (error) {
      console.error('Failed to delete memory:', error);
      showToast('刪除失敗：' + error.message, 'alert-circle');
    }
  }

  /**
   * 顯示新增/編輯 Modal
   */
  function showEditModal(memory, containerEl) {
    const isNew = !memory;
    const title = isNew ? '新增記憶' : '編輯記憶';

    const modalHtml = `
      <div class="mm-modal-overlay" id="mmModal">
        <div class="mm-modal">
          <div class="mm-modal-header">
            <span class="mm-modal-title">${title}</span>
            <button class="mm-modal-close" id="mmModalClose">
              ${icon('close')}
            </button>
          </div>
          <div class="mm-modal-body">
            <div class="mm-form-group">
              <label>標題</label>
              <input type="text" class="mm-input" id="mmMemoryTitle"
                     value="${memory ? escapeHtml(memory.title) : ''}"
                     placeholder="輸入標題（可選，會自動產生）">
            </div>
            <div class="mm-form-group">
              <label>內容 <span class="mm-required">*</span></label>
              <textarea class="mm-textarea" id="mmMemoryContent" rows="5"
                        placeholder="輸入記憶內容，例如：「回答時使用正式語氣」">${memory ? escapeHtml(memory.content) : ''}</textarea>
            </div>
          </div>
          <div class="mm-modal-footer">
            <button class="mm-btn secondary" id="mmModalCancel">取消</button>
            <button class="mm-btn primary" id="mmModalSave">
              ${icon('check')}
              <span>儲存</span>
            </button>
          </div>
        </div>
      </div>
    `;

    // 插入 Modal
    const modalContainer = document.createElement('div');
    modalContainer.innerHTML = modalHtml;
    document.body.appendChild(modalContainer.firstElementChild);

    const modal = document.getElementById('mmModal');
    const closeBtn = document.getElementById('mmModalClose');
    const cancelBtn = document.getElementById('mmModalCancel');
    const saveBtn = document.getElementById('mmModalSave');
    const contentInput = document.getElementById('mmMemoryContent');

    // 關閉事件
    const closeModal = () => modal.remove();
    closeBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });

    // 儲存事件
    saveBtn.addEventListener('click', async () => {
      const titleValue = document.getElementById('mmMemoryTitle').value.trim();
      const contentValue = contentInput.value.trim();

      if (!contentValue) {
        contentInput.focus();
        showToast('請輸入記憶內容', 'alert-circle');
        return;
      }

      saveBtn.disabled = true;
      saveBtn.innerHTML = `${icon('loading', 'mdi-spin')} 儲存中...`;

      try {
        if (isNew) {
          // 新增
          const endpoint = currentTab === 'group'
            ? `/groups/${selectedGroupId}/memories`
            : `/users/${selectedUserId}/memories`;

          const body = { content: contentValue };
          if (titleValue) body.title = titleValue;
          else body.title = contentValue.slice(0, 20) + (contentValue.length > 20 ? '...' : '');

          await apiRequest(endpoint, {
            method: 'POST',
            body: JSON.stringify(body)
          });
        } else {
          // 編輯
          const body = { content: contentValue };
          if (titleValue) body.title = titleValue;

          await apiRequest(`/memories/${memory.id}`, {
            method: 'PUT',
            body: JSON.stringify(body)
          });
        }

        closeModal();
        showToast(isNew ? '記憶已新增' : '記憶已更新', 'check');

        // 重新載入記憶
        if (currentTab === 'group' && selectedGroupId) {
          await loadMemories(containerEl, 'group', selectedGroupId);
        } else if (currentTab === 'personal' && selectedUserId) {
          await loadMemories(containerEl, 'user', selectedUserId);
        }
      } catch (error) {
        console.error('Failed to save memory:', error);
        showToast('儲存失敗：' + error.message, 'alert-circle');
        saveBtn.disabled = false;
        saveBtn.innerHTML = `${icon('check')}<span>儲存</span>`;
      }
    });

    // 自動聚焦
    contentInput.focus();
  }

  /**
   * 顯示 Toast 通知
   */
  function showToast(message, iconName = 'information') {
    if (typeof DesktopModule !== 'undefined' && DesktopModule.showToast) {
      DesktopModule.showToast(message, iconName);
    }
  }

  /**
   * HTML 跳脫
   */
  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  /**
   * 初始化視窗
   */
  function init(windowEl) {
    const containerEl = windowEl.querySelector('.memory-manager');
    if (!containerEl) return;

    // Tab 切換
    const tabs = containerEl.querySelectorAll('.mm-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const newTab = tab.dataset.tab;
        if (newTab === currentTab) return;

        currentTab = newTab;
        tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === newTab));

        // 更新 sidebar 標題
        const sidebarTitle = containerEl.querySelector('#mmSidebarTitle');
        if (sidebarTitle) {
          sidebarTitle.textContent = newTab === 'group' ? '群組列表' : '用戶列表';
        }

        // 重置選中狀態
        selectedGroupId = null;
        selectedUserId = null;

        // 手機版：回到列表
        containerEl.classList.remove('showing-detail');

        // 隱藏新增按鈕
        const addBtn = containerEl.querySelector('#mmAddBtn');
        if (addBtn) addBtn.style.display = 'none';

        // 重置主區域
        const titleEl = containerEl.querySelector('#mmMainTitle');
        if (titleEl) {
          titleEl.textContent = newTab === 'group' ? '請選擇群組' : '請選擇用戶';
        }
        const memoryListEl = containerEl.querySelector('#mmMemoryList');
        if (memoryListEl) {
          memoryListEl.innerHTML = `
            <div class="mm-empty">
              ${icon('brain')}
              <p>請從左側選擇${newTab === 'group' ? '群組' : '用戶'}</p>
            </div>
          `;
        }

        // 載入列表
        if (newTab === 'group') {
          loadGroups(windowEl);
        } else {
          loadUsers(windowEl);
        }
      });
    });

    // 新增按鈕
    const addBtn = containerEl.querySelector('#mmAddBtn');
    if (addBtn) {
      addBtn.addEventListener('click', () => {
        showEditModal(null, containerEl);
      });
    }

    // 手機版返回按鈕
    const backBtn = containerEl.querySelector('#mmBackBtn');
    if (backBtn) {
      backBtn.addEventListener('click', () => {
        containerEl.classList.remove('showing-detail');
      });
    }

    // 初始載入群組
    loadGroups(windowEl);
  }

  /**
   * 開啟應用程式
   */
  function open() {
    // 如果已開啟，則聚焦
    if (currentWindowId) {
      const windowEl = document.getElementById(currentWindowId);
      if (windowEl) {
        WindowModule.focusWindow(currentWindowId);
        return currentWindowId;
      }
    }

    // 重置狀態
    currentTab = 'group';
    selectedGroupId = null;
    selectedUserId = null;
    memories = [];

    // 建立新視窗
    currentWindowId = WindowModule.createWindow({
      title: '記憶管理',
      appId: APP_ID,
      icon: 'brain',
      width: 800,
      height: 550,
      content: getWindowContent(),
      onInit: (windowEl, windowId) => {
        init(windowEl);
      },
      onClose: (windowId) => {
        currentWindowId = null;
      }
    });

    return currentWindowId;
  }

  // 公開 API
  return {
    open
  };
})();
