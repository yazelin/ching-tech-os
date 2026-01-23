/**
 * ChingTech OS - Prompt Editor Application
 * Prompt 管理編輯器
 */

const PromptEditorApp = (function() {
  'use strict';

  const APP_ID = 'prompt-editor';
  let windowId = null;
  let prompts = [];
  let currentPromptId = null;
  let currentCategory = null; // null 表示全部
  let isDirty = false;

  /**
   * 取得認證 headers
   */
  function getAuthHeaders() {
    const token = LoginModule?.getToken?.() || localStorage.getItem('chingtech_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  }

  /**
   * Check if current view is mobile
   */
  function isMobileView() {
    return window.innerWidth <= 768;
  }

  /**
   * Show mobile editor (slide in)
   */
  function showMobileEditor() {
    if (!isMobileView()) return;
    const editor = document.querySelector(`#${windowId} .prompt-editor`);
    if (editor) {
      editor.classList.add('showing-editor');
    }
  }

  /**
   * Hide mobile editor (slide out)
   */
  function hideMobileEditor() {
    const editor = document.querySelector(`#${windowId} .prompt-editor`);
    if (editor) {
      editor.classList.remove('showing-editor');
    }
    currentPromptId = null;
    isDirty = false;
    renderPromptList();
  }

  const categories = [
    { id: null, name: '全部' },
    { id: 'system', name: 'System' },
    { id: 'task', name: 'Task' },
    { id: 'template', name: 'Template' },
    { id: 'internal', name: 'Internal' }
  ];

  /**
   * 載入 Prompts
   */
  async function loadPrompts() {
    try {
      const response = await fetch(`/api/ai/prompts${currentCategory ? `?category=${currentCategory}` : ''}`, {
        headers: getAuthHeaders()
      });
      if (!response.ok) throw new Error('Failed to load prompts');
      const data = await response.json();
      prompts = data.items || [];
    } catch (e) {
      console.error('[PromptEditor] Failed to load prompts:', e);
      prompts = [];
    }
  }

  /**
   * 載入單一 Prompt 詳情
   */
  async function loadPromptDetail(promptId) {
    try {
      const response = await fetch(`/api/ai/prompts/${promptId}`, {
        headers: getAuthHeaders()
      });
      if (!response.ok) throw new Error('Failed to load prompt');
      return await response.json();
    } catch (e) {
      console.error('[PromptEditor] Failed to load prompt detail:', e);
      return null;
    }
  }

  /**
   * 儲存 Prompt
   */
  async function savePrompt(promptId, data) {
    try {
      const method = promptId ? 'PUT' : 'POST';
      const url = (window.API_BASE || '') + (promptId ? `/api/ai/prompts/${promptId}` : '/api/ai/prompts');

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify(data)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save prompt');
      }

      return await response.json();
    } catch (e) {
      console.error('[PromptEditor] Failed to save prompt:', e);
      throw e;
    }
  }

  /**
   * 刪除 Prompt
   */
  async function deletePrompt(promptId) {
    try {
      const response = await fetch(`/api/ai/prompts/${promptId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete prompt');
      }

      return true;
    } catch (e) {
      console.error('[PromptEditor] Failed to delete prompt:', e);
      throw e;
    }
  }

  /**
   * 建立視窗內容
   */
  function buildWindowContent() {
    return `
      <div class="prompt-editor">
        <aside class="prompt-sidebar">
          <div class="prompt-sidebar-header">
            <button class="prompt-new-btn btn btn-primary">
              <span class="icon">${getIcon('plus')}</span>
              <span>新增 Prompt</span>
            </button>
          </div>
          <div class="prompt-category-tabs">
            ${categories.map(c => `
              <button class="prompt-category-tab ${c.id === currentCategory ? 'active' : ''}"
                      data-category="${c.id || ''}">
                ${c.name}
              </button>
            `).join('')}
          </div>
          <div class="prompt-list">
            <!-- Prompt list will be rendered here -->
          </div>
        </aside>
        <main class="prompt-main">
          <div class="prompt-empty-state">
            <span class="icon">${getIcon('file-document-edit-outline')}</span>
            <h3>選擇或建立 Prompt</h3>
            <p>從左側選擇一個 Prompt 進行編輯</p>
          </div>
        </main>
      </div>
    `;
  }

  /**
   * 建立編輯表單
   */
  function buildEditForm(prompt) {
    const isNew = !prompt || !prompt.id;
    const agents = prompt?.referencing_agents || [];

    return `
      <button class="prompt-mobile-back-btn" id="promptMobileBackBtn" style="display: none;">
        <span class="icon">${getIcon('chevron-left')}</span>
        <span>返回列表</span>
      </button>
      <form class="prompt-form" data-prompt-id="${prompt?.id || ''}">
        <div class="prompt-form-row">
          <div class="prompt-form-group flex-1">
            <label class="prompt-form-label">名稱 (唯一識別)</label>
            <input type="text" class="prompt-form-input" name="name"
                   value="${prompt?.name || ''}"
                   placeholder="例: web-chat-default"
                   ${!isNew ? 'readonly' : ''}>
          </div>
          <div class="prompt-form-group flex-1">
            <label class="prompt-form-label">顯示名稱</label>
            <input type="text" class="prompt-form-input" name="display_name"
                   value="${prompt?.display_name || ''}"
                   placeholder="例: 預設對話助手">
          </div>
          <div class="prompt-form-group">
            <label class="prompt-form-label">分類</label>
            <select class="prompt-form-select" name="category">
              <option value="">未分類</option>
              <option value="system" ${prompt?.category === 'system' ? 'selected' : ''}>System</option>
              <option value="task" ${prompt?.category === 'task' ? 'selected' : ''}>Task</option>
              <option value="template" ${prompt?.category === 'template' ? 'selected' : ''}>Template</option>
              <option value="internal" ${prompt?.category === 'internal' ? 'selected' : ''}>Internal</option>
            </select>
          </div>
        </div>
        <div class="prompt-form-row">
          <div class="prompt-form-group flex-1">
            <label class="prompt-form-label">說明</label>
            <input type="text" class="prompt-form-input" name="description"
                   value="${prompt?.description || ''}"
                   placeholder="此 Prompt 的用途說明">
          </div>
        </div>
        <div class="prompt-content-wrapper">
          <label class="prompt-form-label">Prompt 內容</label>
          <textarea class="prompt-content-textarea" name="content"
                    placeholder="輸入 Prompt 內容...">${prompt?.content || ''}</textarea>
        </div>
        ${agents.length > 0 ? `
          <div class="prompt-agents-info">
            <div class="prompt-agents-info-title">被以下 Agents 引用：</div>
            <div class="prompt-agents-list">
              ${agents.map(a => `<span class="prompt-agent-tag">${a.name}</span>`).join('')}
            </div>
          </div>
        ` : ''}
      </form>
      <div class="prompt-toolbar">
        <div class="prompt-toolbar-left">
          ${prompt?.updated_at ? `最後更新：${new Date(prompt.updated_at).toLocaleString('zh-TW')}` : ''}
        </div>
        <div class="prompt-toolbar-right">
          ${!isNew ? `
            <button class="prompt-delete-btn btn btn-danger" ${agents.length > 0 ? 'disabled title="被 Agent 引用中，無法刪除"' : ''}>
              <span class="icon">${getIcon('delete')}</span>
              刪除
            </button>
          ` : ''}
          <button class="prompt-save-btn btn btn-primary">
            <span class="icon">${getIcon('content-save')}</span>
            ${isNew ? '建立' : '儲存'}
          </button>
        </div>
      </div>
    `;
  }

  /**
   * 渲染 Prompt 列表
   */
  function renderPromptList() {
    const container = document.querySelector(`#${windowId} .prompt-list`);
    if (!container) return;

    if (prompts.length === 0) {
      container.innerHTML = `
        <div class="prompt-list-empty">
          <span class="icon">${getIcon('file-document-outline')}</span>
          <p>尚無 Prompt</p>
        </div>
      `;
      return;
    }

    container.innerHTML = prompts.map(p => `
      <div class="prompt-list-item ${p.id === currentPromptId ? 'active' : ''}"
           data-prompt-id="${p.id}">
        <span class="prompt-list-item-icon icon">${getIcon('file-document-outline')}</span>
        <div class="prompt-list-item-info">
          <div class="prompt-list-item-name">${p.display_name || p.name}</div>
          <div class="prompt-list-item-category">${p.category || '未分類'}</div>
        </div>
      </div>
    `).join('');

    // 綁定點擊事件
    container.querySelectorAll('.prompt-list-item').forEach(item => {
      item.addEventListener('click', () => {
        selectPrompt(item.dataset.promptId);
      });
    });
  }

  /**
   * 選擇 Prompt
   */
  async function selectPrompt(promptId) {
    if (isDirty && !confirm('有未儲存的變更，確定要離開嗎？')) {
      return;
    }

    currentPromptId = promptId;
    isDirty = false;

    const main = document.querySelector(`#${windowId} .prompt-main`);
    if (!main) return;

    if (!promptId) {
      main.innerHTML = `
        <div class="prompt-empty-state">
          <span class="icon">${getIcon('file-document-edit-outline')}</span>
          <h3>選擇或建立 Prompt</h3>
          <p>從左側選擇一個 Prompt 進行編輯</p>
        </div>
      `;
      renderPromptList();
      return;
    }

    // 載入詳情
    const prompt = await loadPromptDetail(promptId);
    if (!prompt) {
      showToast('載入失敗', 'error');
      return;
    }

    main.innerHTML = buildEditForm(prompt);
    renderPromptList();
    bindFormEvents();
    showMobileEditor();
  }

  /**
   * 建立新 Prompt
   */
  function createNewPrompt() {
    if (isDirty && !confirm('有未儲存的變更，確定要離開嗎？')) {
      return;
    }

    currentPromptId = null;
    isDirty = false;

    const main = document.querySelector(`#${windowId} .prompt-main`);
    if (!main) return;

    main.innerHTML = buildEditForm(null);
    renderPromptList();
    bindFormEvents();
    showMobileEditor();
  }

  /**
   * 綁定表單事件
   */
  function bindFormEvents() {
    const form = document.querySelector(`#${windowId} .prompt-form`);
    if (!form) return;

    // 手機版返回按鈕
    const backBtn = document.querySelector(`#${windowId} #promptMobileBackBtn`);
    if (backBtn) {
      if (isMobileView()) {
        backBtn.style.display = 'flex';
      }
      backBtn.addEventListener('click', () => {
        if (isDirty && !confirm('有未儲存的變更，確定要離開嗎？')) {
          return;
        }
        hideMobileEditor();
      });
    }

    // 監聽變更
    form.querySelectorAll('input, textarea, select').forEach(el => {
      el.addEventListener('input', () => {
        isDirty = true;
      });
    });

    // 儲存按鈕
    const saveBtn = document.querySelector(`#${windowId} .prompt-save-btn`);
    if (saveBtn) {
      saveBtn.addEventListener('click', handleSave);
    }

    // 刪除按鈕
    const deleteBtn = document.querySelector(`#${windowId} .prompt-delete-btn`);
    if (deleteBtn && !deleteBtn.disabled) {
      deleteBtn.addEventListener('click', handleDelete);
    }
  }

  /**
   * 處理儲存
   */
  async function handleSave() {
    const form = document.querySelector(`#${windowId} .prompt-form`);
    if (!form) return;

    const formData = new FormData(form);
    const data = {
      name: formData.get('name'),
      display_name: formData.get('display_name') || null,
      category: formData.get('category') || null,
      description: formData.get('description') || null,
      content: formData.get('content')
    };

    // 驗證
    if (!data.name) {
      showToast('請輸入名稱', 'error');
      return;
    }
    if (!data.content) {
      showToast('請輸入 Prompt 內容', 'error');
      return;
    }

    const promptId = form.dataset.promptId || null;

    try {
      const result = await savePrompt(promptId, data);
      isDirty = false;
      showToast(promptId ? '儲存成功' : '建立成功', 'check');

      // 重新載入列表
      await loadPrompts();
      currentPromptId = result.id;
      await selectPrompt(result.id);
    } catch (e) {
      showToast(e.message || '儲存失敗', 'error');
    }
  }

  /**
   * 處理刪除
   */
  async function handleDelete() {
    if (!currentPromptId) return;

    if (!confirm('確定要刪除此 Prompt 嗎？')) {
      return;
    }

    try {
      await deletePrompt(currentPromptId);
      isDirty = false;
      showToast('刪除成功', 'check');

      // 重新載入列表
      await loadPrompts();
      currentPromptId = null;
      await selectPrompt(null);
    } catch (e) {
      showToast(e.message || '刪除失敗', 'error');
    }
  }

  /**
   * 顯示提示訊息
   */
  function showToast(message, icon = 'information') {
    if (typeof DesktopModule !== 'undefined') {
      DesktopModule.showToast(message, icon);
    }
  }

  /**
   * 初始化應用
   */
  async function initApp(windowEl, wId) {
    windowId = wId;

    await loadPrompts();
    renderPromptList();

    // 綁定事件
    bindEvents();
  }

  /**
   * 綁定事件
   */
  function bindEvents() {
    // 新增按鈕
    const newBtn = document.querySelector(`#${windowId} .prompt-new-btn`);
    if (newBtn) {
      newBtn.addEventListener('click', createNewPrompt);
    }

    // 分類標籤
    document.querySelectorAll(`#${windowId} .prompt-category-tab`).forEach(tab => {
      tab.addEventListener('click', async () => {
        const category = tab.dataset.category || null;
        currentCategory = category;

        // 更新標籤狀態
        document.querySelectorAll(`#${windowId} .prompt-category-tab`).forEach(t => {
          t.classList.toggle('active', (t.dataset.category || null) === category);
        });

        // 重新載入
        await loadPrompts();
        renderPromptList();
      });
    });
  }

  /**
   * 開啟應用
   */
  function open() {
    const existingWindow = WindowModule.getWindowByAppId(APP_ID);
    if (existingWindow) {
      WindowModule.focusWindow(existingWindow.windowId);
      if (existingWindow.minimized) {
        WindowModule.restoreWindow(existingWindow.windowId);
      }
      return;
    }

    WindowModule.createWindow({
      title: 'Prompt 編輯器',
      appId: APP_ID,
      icon: 'script-text',
      width: 900,
      height: 600,
      content: buildWindowContent(),
      onInit: initApp,
      onClose: () => {
        if (isDirty && !confirm('有未儲存的變更，確定要關閉嗎？')) {
          return false;
        }
        windowId = null;
        isDirty = false;
      }
    });
  }

  /**
   * 關閉應用
   */
  function close() {
    if (windowId) {
      WindowModule.closeWindow(windowId);
      windowId = null;
    }
  }

  return {
    open,
    close
  };
})();
