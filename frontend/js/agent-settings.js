/**
 * ChingTech OS - Agent Settings Application
 * AI Agent 設定管理
 */

const AgentSettingsApp = (function() {
  'use strict';

  const APP_ID = 'agent-settings';
  let windowId = null;
  let agents = [];
  let prompts = [];
  let currentAgentId = null;
  let isDirty = false;

  const availableModels = [
    { id: 'claude-opus', name: 'Claude Opus' },
    { id: 'claude-sonnet', name: 'Claude Sonnet' },
    { id: 'claude-haiku', name: 'Claude Haiku' }
  ];

  // 可用的工具列表
  const availableTools = [
    { id: 'WebSearch', name: '網路搜尋', desc: '搜尋網路資訊' },
    { id: 'WebFetch', name: '網頁抓取', desc: '抓取網頁內容' },
    { id: 'Read', name: '讀取檔案', desc: '讀取檔案/圖片' },
    { id: 'Write', name: '寫入檔案', desc: '寫入檔案' },
    { id: 'Edit', name: '編輯檔案', desc: '編輯檔案內容' },
    { id: 'Bash', name: '執行命令', desc: '執行 Shell 命令' },
    { id: 'Glob', name: '檔案匹配', desc: '檔案模式匹配' },
    { id: 'Grep', name: '內容搜尋', desc: '搜尋檔案內容' }
  ];

  /**
   * 載入 Agents
   */
  async function loadAgents() {
    try {
      const response = await fetch('/api/ai/agents');
      if (!response.ok) throw new Error('Failed to load agents');
      const data = await response.json();
      agents = data.items || [];
    } catch (e) {
      console.error('[AgentSettings] Failed to load agents:', e);
      agents = [];
    }
  }

  /**
   * 載入 Prompts（用於下拉選單）
   */
  async function loadPrompts() {
    try {
      const response = await fetch('/api/ai/prompts');
      if (!response.ok) throw new Error('Failed to load prompts');
      const data = await response.json();
      // Agent 不應選擇 internal 類別的 prompt（如 summarizer）
      prompts = (data.items || []).filter(p => p.category !== 'internal');
    } catch (e) {
      console.error('[AgentSettings] Failed to load prompts:', e);
      prompts = [];
    }
  }

  /**
   * 載入單一 Agent 詳情
   */
  async function loadAgentDetail(agentId) {
    try {
      const response = await fetch(`/api/ai/agents/${agentId}`);
      if (!response.ok) throw new Error('Failed to load agent');
      return await response.json();
    } catch (e) {
      console.error('[AgentSettings] Failed to load agent detail:', e);
      return null;
    }
  }

  /**
   * 儲存 Agent
   */
  async function saveAgent(agentId, data) {
    try {
      const method = agentId ? 'PUT' : 'POST';
      const url = (window.API_BASE || '') + (agentId ? `/api/ai/agents/${agentId}` : '/api/ai/agents');

      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save agent');
      }

      return await response.json();
    } catch (e) {
      console.error('[AgentSettings] Failed to save agent:', e);
      throw e;
    }
  }

  /**
   * 刪除 Agent
   */
  async function deleteAgent(agentId) {
    try {
      const response = await fetch(`/api/ai/agents/${agentId}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete agent');
      }

      return true;
    } catch (e) {
      console.error('[AgentSettings] Failed to delete agent:', e);
      throw e;
    }
  }

  /**
   * 測試 Agent
   */
  async function testAgent(agentId, message) {
    try {
      const response = await fetch('/api/ai/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId, message })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Test failed');
      }

      return await response.json();
    } catch (e) {
      console.error('[AgentSettings] Test failed:', e);
      throw e;
    }
  }

  /**
   * 建立視窗內容
   */
  function buildWindowContent() {
    return `
      <div class="agent-settings">
        <aside class="agent-sidebar">
          <div class="agent-sidebar-header">
            <button class="agent-new-btn btn btn-primary">
              <span class="icon">${getIcon('plus')}</span>
              <span>新增 Agent</span>
            </button>
          </div>
          <div class="agent-list">
            <!-- Agent list will be rendered here -->
          </div>
        </aside>
        <main class="agent-main">
          <div class="agent-empty-state">
            <span class="icon">${getIcon('robot-outline')}</span>
            <h3>選擇或建立 Agent</h3>
            <p>從左側選擇一個 Agent 進行設定</p>
          </div>
        </main>
      </div>
    `;
  }

  /**
   * 建立編輯表單
   */
  function buildEditForm(agent) {
    const isNew = !agent || !agent.id;

    return `
      <div class="agent-form" data-agent-id="${agent?.id || ''}">
        <div class="agent-form-section">
          <div class="agent-form-section-title">基本資訊</div>
          <div class="agent-form-row">
            <div class="agent-form-group flex-1">
              <label class="agent-form-label">名稱 (唯一識別)</label>
              <input type="text" class="agent-form-input" name="name"
                     value="${agent?.name || ''}"
                     placeholder="例: web-chat-default"
                     ${!isNew ? 'readonly' : ''}>
            </div>
            <div class="agent-form-group flex-1">
              <label class="agent-form-label">顯示名稱</label>
              <input type="text" class="agent-form-input" name="display_name"
                     value="${agent?.display_name || ''}"
                     placeholder="例: 預設對話">
            </div>
          </div>
          <div class="agent-form-row">
            <div class="agent-form-group flex-1">
              <label class="agent-form-label">說明</label>
              <input type="text" class="agent-form-input" name="description"
                     value="${agent?.description || ''}"
                     placeholder="此 Agent 的用途說明">
            </div>
          </div>
        </div>

        <div class="agent-form-section">
          <div class="agent-form-section-title">AI 設定</div>
          <div class="agent-form-row">
            <div class="agent-form-group flex-1">
              <label class="agent-form-label">Model</label>
              <select class="agent-form-select" name="model">
                ${availableModels.map(m => `
                  <option value="${m.id}" ${agent?.model === m.id ? 'selected' : ''}>
                    ${m.name}
                  </option>
                `).join('')}
              </select>
            </div>
            <div class="agent-form-group flex-1">
              <label class="agent-form-label">System Prompt</label>
              <select class="agent-form-select" name="system_prompt_id">
                <option value="">不指定</option>
                ${prompts.map(p => `
                  <option value="${p.id}" ${agent?.system_prompt_id === p.id ? 'selected' : ''}>
                    ${p.display_name || p.name}
                  </option>
                `).join('')}
              </select>
            </div>
          </div>
        </div>

        <div class="agent-form-section">
          <div class="agent-form-section-title">工具權限</div>
          <div class="agent-tools-grid">
            ${availableTools.map(t => `
              <label class="agent-tool-item">
                <input type="checkbox" name="tools" value="${t.id}"
                       ${agent?.tools?.includes(t.id) ? 'checked' : ''}>
                <span class="agent-tool-name">${t.name}</span>
                <span class="agent-tool-desc">${t.desc}</span>
              </label>
            `).join('')}
          </div>
        </div>

        <div class="agent-form-section">
          <div class="agent-form-section-title">狀態</div>
          <div class="agent-form-row">
            <div class="agent-form-group">
              <div class="agent-toggle-wrapper">
                <div class="agent-toggle ${agent?.is_active !== false ? 'active' : ''}"
                     data-field="is_active"></div>
                <span class="agent-toggle-label">${agent?.is_active !== false ? '已啟用' : '已停用'}</span>
              </div>
            </div>
          </div>
        </div>

        ${agent?.system_prompt?.content ? `
          <div class="agent-form-section">
            <div class="agent-form-section-title">Prompt 預覽</div>
            <textarea class="agent-form-textarea" readonly>${agent.system_prompt.content}</textarea>
          </div>
        ` : ''}
      </div>

      ${!isNew ? `
        <div class="agent-test-section">
          <div class="agent-test-header">
            <span class="agent-test-title">測試 Agent</span>
          </div>
          <div class="agent-test-input-wrapper">
            <input type="text" class="agent-test-input" placeholder="輸入測試訊息...">
            <button class="agent-test-btn btn btn-secondary">
              <span class="icon">${getIcon('play')}</span>
              測試
            </button>
          </div>
          <div class="agent-test-result" style="display: none;"></div>
        </div>
      ` : ''}

      <div class="agent-toolbar">
        <div class="agent-toolbar-left">
          ${agent?.updated_at ? `最後更新：${new Date(agent.updated_at).toLocaleString('zh-TW')}` : ''}
        </div>
        <div class="agent-toolbar-right">
          ${!isNew ? `
            <button class="agent-delete-btn btn btn-danger">
              <span class="icon">${getIcon('delete')}</span>
              刪除
            </button>
          ` : ''}
          <button class="agent-save-btn btn btn-primary">
            <span class="icon">${getIcon('content-save')}</span>
            ${isNew ? '建立' : '儲存'}
          </button>
        </div>
      </div>
    `;
  }

  /**
   * 渲染 Agent 列表
   */
  function renderAgentList() {
    const container = document.querySelector(`#${windowId} .agent-list`);
    if (!container) return;

    if (agents.length === 0) {
      container.innerHTML = `
        <div class="agent-list-empty">
          <span class="icon">${getIcon('robot-outline')}</span>
          <p>尚無 Agent</p>
        </div>
      `;
      return;
    }

    container.innerHTML = agents.map(a => `
      <div class="agent-list-item ${a.id === currentAgentId ? 'active' : ''}"
           data-agent-id="${a.id}">
        <div class="agent-list-item-status ${a.is_active ? 'active' : 'inactive'}"></div>
        <div class="agent-list-item-info">
          <div class="agent-list-item-name">${a.display_name || a.name}</div>
          <div class="agent-list-item-model">${a.model}</div>
        </div>
      </div>
    `).join('');

    // 綁定點擊事件
    container.querySelectorAll('.agent-list-item').forEach(item => {
      item.addEventListener('click', () => {
        selectAgent(item.dataset.agentId);
      });
    });
  }

  /**
   * 選擇 Agent
   */
  async function selectAgent(agentId) {
    if (isDirty && !confirm('有未儲存的變更，確定要離開嗎？')) {
      return;
    }

    currentAgentId = agentId;
    isDirty = false;

    const main = document.querySelector(`#${windowId} .agent-main`);
    if (!main) return;

    if (!agentId) {
      main.innerHTML = `
        <div class="agent-empty-state">
          <span class="icon">${getIcon('robot-outline')}</span>
          <h3>選擇或建立 Agent</h3>
          <p>從左側選擇一個 Agent 進行設定</p>
        </div>
      `;
      renderAgentList();
      return;
    }

    // 載入詳情
    const agent = await loadAgentDetail(agentId);
    if (!agent) {
      showToast('載入失敗', 'error');
      return;
    }

    main.innerHTML = buildEditForm(agent);
    renderAgentList();
    bindFormEvents();
  }

  /**
   * 建立新 Agent
   */
  function createNewAgent() {
    if (isDirty && !confirm('有未儲存的變更，確定要離開嗎？')) {
      return;
    }

    currentAgentId = null;
    isDirty = false;

    const main = document.querySelector(`#${windowId} .agent-main`);
    if (!main) return;

    main.innerHTML = buildEditForm(null);
    renderAgentList();
    bindFormEvents();
  }

  /**
   * 綁定表單事件
   */
  function bindFormEvents() {
    const form = document.querySelector(`#${windowId} .agent-form`);
    if (!form) return;

    // 監聽變更
    form.querySelectorAll('input, textarea, select').forEach(el => {
      el.addEventListener('input', () => {
        isDirty = true;
      });
    });

    // 開關切換
    const toggle = form.querySelector('.agent-toggle');
    if (toggle) {
      toggle.addEventListener('click', () => {
        toggle.classList.toggle('active');
        const label = toggle.nextElementSibling;
        if (label) {
          label.textContent = toggle.classList.contains('active') ? '已啟用' : '已停用';
        }
        isDirty = true;
      });
    }

    // 儲存按鈕
    const saveBtn = document.querySelector(`#${windowId} .agent-save-btn`);
    if (saveBtn) {
      saveBtn.addEventListener('click', handleSave);
    }

    // 刪除按鈕
    const deleteBtn = document.querySelector(`#${windowId} .agent-delete-btn`);
    if (deleteBtn) {
      deleteBtn.addEventListener('click', handleDelete);
    }

    // 測試按鈕
    const testBtn = document.querySelector(`#${windowId} .agent-test-btn`);
    if (testBtn) {
      testBtn.addEventListener('click', handleTest);
    }

    // 測試輸入框 Enter
    const testInput = document.querySelector(`#${windowId} .agent-test-input`);
    if (testInput) {
      testInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          handleTest();
        }
      });
    }
  }

  /**
   * 處理儲存
   */
  async function handleSave() {
    const form = document.querySelector(`#${windowId} .agent-form`);
    if (!form) return;

    const toggle = form.querySelector('.agent-toggle');
    const isActive = toggle ? toggle.classList.contains('active') : true;

    // 收集選中的工具
    const toolCheckboxes = form.querySelectorAll('[name="tools"]:checked');
    const tools = Array.from(toolCheckboxes).map(cb => cb.value);

    const data = {
      name: form.querySelector('[name="name"]').value,
      display_name: form.querySelector('[name="display_name"]').value || null,
      description: form.querySelector('[name="description"]').value || null,
      model: form.querySelector('[name="model"]').value,
      system_prompt_id: form.querySelector('[name="system_prompt_id"]').value || null,
      is_active: isActive,
      tools: tools.length > 0 ? tools : null
    };

    // 驗證
    if (!data.name) {
      showToast('請輸入名稱', 'error');
      return;
    }
    if (!data.model) {
      showToast('請選擇 Model', 'error');
      return;
    }

    const agentId = form.dataset.agentId || null;

    try {
      const result = await saveAgent(agentId, data);
      isDirty = false;
      showToast(agentId ? '儲存成功' : '建立成功', 'check');

      // 重新載入列表
      await loadAgents();
      currentAgentId = result.id;
      await selectAgent(result.id);
    } catch (e) {
      showToast(e.message || '儲存失敗', 'error');
    }
  }

  /**
   * 處理刪除
   */
  async function handleDelete() {
    if (!currentAgentId) return;

    if (!confirm('確定要刪除此 Agent 嗎？相關的 AI Log 會保留但不再關聯此 Agent。')) {
      return;
    }

    try {
      await deleteAgent(currentAgentId);
      isDirty = false;
      showToast('刪除成功', 'check');

      // 重新載入列表
      await loadAgents();
      currentAgentId = null;
      await selectAgent(null);
    } catch (e) {
      showToast(e.message || '刪除失敗', 'error');
    }
  }

  /**
   * 處理測試
   */
  async function handleTest() {
    if (!currentAgentId) return;

    const testInput = document.querySelector(`#${windowId} .agent-test-input`);
    const testResult = document.querySelector(`#${windowId} .agent-test-result`);
    const testBtn = document.querySelector(`#${windowId} .agent-test-btn`);

    if (!testInput || !testResult) return;

    const message = testInput.value.trim();
    if (!message) {
      showToast('請輸入測試訊息', 'error');
      return;
    }

    // 顯示 loading
    testResult.style.display = 'block';
    testResult.className = 'agent-test-result loading';
    testResult.textContent = '測試中...';
    testBtn.disabled = true;

    try {
      const result = await testAgent(currentAgentId, message);

      if (result.success) {
        testResult.className = 'agent-test-result';
        testResult.textContent = result.response;
      } else {
        testResult.className = 'agent-test-result error';
        testResult.textContent = result.error || '測試失敗';
      }
    } catch (e) {
      testResult.className = 'agent-test-result error';
      testResult.textContent = e.message || '測試失敗';
    } finally {
      testBtn.disabled = false;
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

    await Promise.all([loadAgents(), loadPrompts()]);
    renderAgentList();

    // 綁定事件
    bindEvents();
  }

  /**
   * 綁定事件
   */
  function bindEvents() {
    // 新增按鈕
    const newBtn = document.querySelector(`#${windowId} .agent-new-btn`);
    if (newBtn) {
      newBtn.addEventListener('click', createNewAgent);
    }
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
      title: 'Agent 設定',
      appId: APP_ID,
      icon: 'robot-outline',
      width: 850,
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
