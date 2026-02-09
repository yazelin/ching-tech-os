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
  let skills = [];
  let currentAgentId = null;
  let currentSkillName = null;
  let currentTab = 'agents'; // 'agents' | 'skills'
  let currentSkillsSubTab = 'installed'; // 'installed' | 'hub'
  let isDirty = false;
  let highlightSkillName = null;

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
    const settings = document.querySelector(`#${windowId} .agent-settings`);
    if (settings) {
      settings.classList.add('showing-editor');
    }
  }

  /**
   * Hide mobile editor (slide out)
   */
  function hideMobileEditor() {
    const settings = document.querySelector(`#${windowId} .agent-settings`);
    if (settings) {
      settings.classList.remove('showing-editor');
    }
    currentAgentId = null;
    isDirty = false;
    renderAgentList();
  }

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
      const response = await fetch('/api/ai/agents', {
        headers: getAuthHeaders()
      });
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
      const response = await fetch('/api/ai/prompts', {
        headers: getAuthHeaders()
      });
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
      const response = await fetch(`/api/ai/agents/${agentId}`, {
        headers: getAuthHeaders()
      });
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
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
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
        method: 'DELETE',
        headers: getAuthHeaders()
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
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
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
      <div class="agent-settings-wrapper">
        <div class="agent-settings-tabs">
          <button class="agent-settings-tab active" data-tab="agents">Agents</button>
          <button class="agent-settings-tab" data-tab="skills">Skills</button>
        </div>
        <div class="agent-settings agent-settings-tab-content active" data-tab-content="agents">
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
        <div class="agent-settings skill-settings agent-settings-tab-content" data-tab-content="skills">
          <aside class="agent-sidebar skill-sidebar">
            <div class="agent-sidebar-header">
              <div class="skill-sub-tabs">
                <button class="skill-sub-tab active" data-skill-tab="installed">已安裝</button>
                <button class="skill-sub-tab" data-skill-tab="hub">ClawHub</button>
              </div>
            </div>
            <div class="skill-sub-content" data-skill-tab-content="installed">
              <div class="skill-list-toolbar">
                <button class="btn btn-sm skill-reload-btn" data-action="reload-skills" title="重新載入">
                  <span class="icon">${getIcon('refresh')}</span>
                </button>
              </div>
              <div class="skill-list">
                <!-- Skill list will be rendered here -->
              </div>
            </div>
            <div class="skill-sub-content" data-skill-tab-content="hub" style="display:none;">
              <div class="skill-hub-search">
                <input type="text" class="agent-form-input skill-hub-search-input" placeholder="搜尋 ClawHub..." data-action="hub-search-input">
                <button class="btn btn-sm btn-primary skill-hub-search-btn" data-action="hub-search">搜尋</button>
              </div>
              <div class="skill-hub-results"></div>
            </div>
          </aside>
          <main class="agent-main skill-main">
            <div class="agent-empty-state">
              <span class="icon">${getIcon('puzzle-outline')}</span>
              <h3>選擇一個 Skill</h3>
              <p>從左側選擇一個 Skill 查看詳情</p>
            </div>
          </main>
        </div>
        <!-- Skill Edit Modal -->
        <div class="skill-edit-modal-overlay" style="display:none;">
          <div class="skill-edit-modal">
            <div class="skill-edit-modal-header">
              <span class="skill-edit-modal-title">編輯 Skill</span>
              <button class="skill-edit-modal-close" data-action="close-skill-modal">&times;</button>
            </div>
            <div class="skill-edit-modal-body"></div>
            <div class="skill-edit-modal-footer">
              <button class="btn btn-secondary" data-action="close-skill-modal">取消</button>
              <button class="btn btn-primary" data-action="save-skill">儲存</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * 建立編輯表單
   */
  function buildEditForm(agent) {
    const isNew = !agent || !agent.id;

    return `
      <button class="agent-mobile-back-btn" id="agentMobileBackBtn" style="display: none;">
        <span class="icon">${getIcon('chevron-left')}</span>
        <span>返回列表</span>
      </button>
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
    showMobileEditor();
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
    showMobileEditor();
  }

  /**
   * 綁定表單事件
   */
  function bindFormEvents() {
    const form = document.querySelector(`#${windowId} .agent-form`);
    if (!form) return;

    // 手機版返回按鈕
    const backBtn = document.querySelector(`#${windowId} #agentMobileBackBtn`);
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

  // ========== Skills ==========

  /**
   * 載入 Skills
   */
  async function loadSkills() {
    try {
      const response = await fetch('/api/skills', {
        headers: getAuthHeaders()
      });
      if (!response.ok) throw new Error('Failed to load skills');
      const data = await response.json();
      skills = data.skills || [];
      if (!Array.isArray(skills)) skills = [];
    } catch (e) {
      console.error('[AgentSettings] Failed to load skills:', e);
      skills = [];
    }
  }

  /**
   * 渲染 Skill 列表
   */
  function renderSkillList() {
    const container = document.querySelector(`#${windowId} .skill-list`);
    if (!container) return;

    if (skills.length === 0) {
      container.innerHTML = `
        <div class="agent-list-empty">
          <span class="icon">${getIcon('puzzle-outline')}</span>
          <p>尚無 Skills</p>
        </div>
      `;
      return;
    }

    container.innerHTML = skills.map(s => {
      const toolCount = s.tools_count || 0;
      const source = s.source || 'unknown';
      const sourceBadgeClass = source === 'native' ? 'skill-source-native' : source === 'openclaw' ? 'skill-source-openclaw' : 'skill-source-other';
      const isHighlighted = s.name === highlightSkillName;
      return `
        <div class="agent-list-item skill-list-item ${s.name === currentSkillName ? 'active' : ''} ${isHighlighted ? 'skill-highlight' : ''}"
             data-skill-name="${escapeHtml(s.name)}">
          <div class="agent-list-item-info">
            <div class="agent-list-item-name">
              ${escapeHtml(s.name)}
              <span class="skill-source-badge ${sourceBadgeClass}">${escapeHtml(source)}</span>
            </div>
            <div class="agent-list-item-model">${escapeHtml(s.description || '—')}</div>
            <div class="skill-list-item-meta">
              <span class="skill-badge">${escapeHtml(s.requires_app || '基礎')}</span>
              ${toolCount > 0 ? `<span class="skill-badge skill-badge-tool">${toolCount} 工具</span>` : ''}
            </div>
          </div>
          <div class="skill-list-item-actions">
            <button class="btn btn-sm skill-edit-btn" data-action="edit-skill" data-skill-name="${escapeHtml(s.name)}" title="編輯">
              <span class="icon">${getIcon('pencil')}</span>
            </button>
            ${source !== 'native' ? `
              <button class="btn btn-sm btn-danger skill-remove-btn" data-action="remove-skill" data-skill-name="${escapeHtml(s.name)}" title="移除">
                <span class="icon">${getIcon('delete')}</span>
              </button>
            ` : ''}
          </div>
        </div>
      `;
    }).join('');

    // Clear highlight after render
    if (highlightSkillName) {
      setTimeout(() => { highlightSkillName = null; }, 3000);
    }

    container.querySelectorAll('.skill-list-item').forEach(item => {
      item.addEventListener('click', (e) => {
        // Don't navigate if clicking action buttons
        if (e.target.closest('[data-action]')) return;
        showSkillDetail(item.dataset.skillName);
      });
    });
  }

  /**
   * 顯示 Skill 詳情
   */
  async function showSkillDetail(skillName) {
    currentSkillName = skillName;
    renderSkillList();

    const main = document.querySelector(`#${windowId} .skill-main`);
    if (!main) return;

    // Fetch detail with prompt
    try {
      const response = await fetch(`/api/skills/${encodeURIComponent(skillName)}`, {
        headers: getAuthHeaders()
      });
      if (!response.ok) throw new Error('Failed to load skill detail');
      const skill = await response.json();

      const tools = skill.tools || [];
      const mcpServers = skill.mcp_servers || [];

      const source = skill.source || 'unknown';
      const sourceBadgeClass = source === 'native' ? 'skill-source-native' : source === 'openclaw' ? 'skill-source-openclaw' : 'skill-source-other';

      // Collect browsable files
      const browseFiles = [];
      ['references', 'scripts', 'assets'].forEach(dir => {
        const files = skill[dir] || [];
        files.forEach(f => browseFiles.push({ dir, path: f }));
      });

      main.innerHTML = `
        <div class="agent-form skill-detail">
          <div class="skill-detail-header-bar">
            <div class="agent-form-section-title" style="margin-bottom:0;">基本資訊</div>
            <button class="btn btn-sm skill-reload-btn" data-action="reload-skills-detail" title="重新載入所有 Skills">
              <span class="icon">${getIcon('refresh')}</span> 重載
            </button>
          </div>
          <div class="agent-form-section">
            <div class="skill-detail-field">
              <span class="agent-form-label">名稱</span>
              <span class="skill-detail-value">${escapeHtml(skill.name)} <span class="skill-source-badge ${sourceBadgeClass}">${escapeHtml(source)}</span></span>
            </div>
            <div class="skill-detail-field">
              <span class="agent-form-label">說明</span>
              <span class="skill-detail-value">${escapeHtml(skill.description || '—')}</span>
            </div>
            <div class="skill-detail-field">
              <span class="agent-form-label">需要的 App 權限</span>
              <span class="skill-badge">${escapeHtml(skill.requires_app || '基礎')}</span>
            </div>
          </div>

          ${tools.length > 0 ? `
            <div class="agent-form-section">
              <div class="agent-form-section-title">工具 (${tools.length})</div>
              <div class="skill-chips">
                ${tools.map(t => `<span class="skill-chip">${escapeHtml(typeof t === 'string' ? t : t.name || String(t))}</span>`).join('')}
              </div>
            </div>
          ` : ''}

          ${mcpServers.length > 0 ? `
            <div class="agent-form-section">
              <div class="agent-form-section-title">MCP Servers</div>
              <div class="skill-chips">
                ${mcpServers.map(s => `<span class="skill-chip">${escapeHtml(typeof s === 'string' ? s : s.name || JSON.stringify(s))}</span>`).join('')}
              </div>
            </div>
          ` : ''}

          ${browseFiles.length > 0 ? `
            <div class="agent-form-section">
              <div class="agent-form-section-title">檔案</div>
              <div class="skill-file-list">
                ${browseFiles.map(f => `
                  <div class="skill-file-item" data-action="browse-file" data-skill-name="${escapeHtml(skillName)}" data-file-dir="${escapeHtml(f.dir)}" data-file-path="${escapeHtml(f.path)}">
                    <span class="icon">${getIcon('file-document-outline')}</span>
                    <span>${escapeHtml(f.dir)}/${escapeHtml(f.path)}</span>
                  </div>
                  <pre class="skill-file-content" style="display:none;"></pre>
                `).join('')}
              </div>
            </div>
          ` : ''}

          ${skill.prompt ? `
            <div class="agent-form-section">
              <div class="agent-form-section-title">Prompt</div>
              <pre class="skill-prompt-content">${escapeHtml(skill.prompt)}</pre>
            </div>
          ` : ''}
        </div>
      `;

      // Mobile support
      if (isMobileView()) {
        const settings = document.querySelector(`#${windowId} .skill-settings`);
        if (settings) settings.classList.add('showing-editor');
      }
    } catch (e) {
      main.innerHTML = `<div class="agent-empty-state"><p>載入失敗: ${e.message}</p></div>`;
    }
  }

  // ========== Skill Actions ==========

  /**
   * Reload all skills
   */
  async function reloadSkills() {
    try {
      await fetch('/api/skills/reload', {
        method: 'POST',
        headers: getAuthHeaders()
      });
      await loadSkills();
      renderSkillList();
      showToast('Skills 已重載', 'check');
    } catch (e) {
      showToast('重載失敗: ' + e.message, 'error');
    }
  }

  /**
   * Open skill edit modal
   */
  async function openSkillEditModal(skillName) {
    try {
      const response = await fetch(`/api/skills/${encodeURIComponent(skillName)}`, {
        headers: getAuthHeaders()
      });
      if (!response.ok) throw new Error('Failed to load skill');
      const skill = await response.json();

      const overlay = document.querySelector(`#${windowId} .skill-edit-modal-overlay`);
      if (!overlay) return;

      const body = overlay.querySelector('.skill-edit-modal-body');
      const allowedTools = skill.allowed_tools || skill.tools || [];
      const mcpServers = skill.mcp_servers || [];

      body.innerHTML = `
        <div class="skill-edit-form" data-skill-name="${escapeHtml(skillName)}">
          <div class="agent-form-group" style="margin-bottom:16px;">
            <label class="agent-form-label">requires_app</label>
            <input type="text" class="agent-form-input" name="requires_app" value="${escapeHtml(skill.requires_app || '')}" placeholder="留空為基礎">
          </div>
          <div class="agent-form-group" style="margin-bottom:16px;">
            <label class="agent-form-label">allowed_tools</label>
            <div class="skill-chip-editor" data-field="allowed_tools">
              <div class="skill-chips-editable">
                ${allowedTools.map(t => {
                  const name = typeof t === 'string' ? t : t.name || String(t);
                  return `<span class="skill-chip skill-chip-removable">${escapeHtml(name)}<button class="skill-chip-remove" data-action="remove-chip">&times;</button></span>`;
                }).join('')}
              </div>
              <input type="text" class="agent-form-input skill-chip-input" placeholder="輸入後按 Enter 新增" data-action="add-chip-input">
            </div>
          </div>
          <div class="agent-form-group" style="margin-bottom:16px;">
            <label class="agent-form-label">mcp_servers</label>
            <div class="skill-chip-editor" data-field="mcp_servers">
              <div class="skill-chips-editable">
                ${mcpServers.map(s => {
                  const name = typeof s === 'string' ? s : s.name || JSON.stringify(s);
                  return `<span class="skill-chip skill-chip-removable">${escapeHtml(name)}<button class="skill-chip-remove" data-action="remove-chip">&times;</button></span>`;
                }).join('')}
              </div>
              <input type="text" class="agent-form-input skill-chip-input" placeholder="輸入後按 Enter 新增" data-action="add-chip-input">
            </div>
          </div>
        </div>
      `;

      overlay.style.display = 'flex';
    } catch (e) {
      showToast('載入失敗: ' + e.message, 'error');
    }
  }

  /**
   * Save skill from modal
   */
  async function saveSkillFromModal() {
    const form = document.querySelector(`#${windowId} .skill-edit-form`);
    if (!form) return;

    const skillName = form.dataset.skillName;
    const requiresApp = form.querySelector('[name="requires_app"]').value || null;

    const getAllChips = (field) => {
      const container = form.querySelector(`.skill-chip-editor[data-field="${field}"] .skill-chips-editable`);
      if (!container) return [];
      return Array.from(container.querySelectorAll('.skill-chip-removable')).map(chip => {
        // Get text without the × button text
        return chip.firstChild.textContent.trim();
      });
    };

    const data = {
      requires_app: requiresApp,
      allowed_tools: getAllChips('allowed_tools'),
      mcp_servers: getAllChips('mcp_servers')
    };

    try {
      const response = await fetch(`/api/skills/${encodeURIComponent(skillName)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(data)
      });
      if (!response.ok) throw new Error('Failed to save');

      closeSkillEditModal();
      showToast('儲存成功', 'check');
      await loadSkills();
      renderSkillList();
      if (currentSkillName === skillName) {
        showSkillDetail(skillName);
      }
    } catch (e) {
      showToast('儲存失敗: ' + e.message, 'error');
    }
  }

  /**
   * Close skill edit modal
   */
  function closeSkillEditModal() {
    const overlay = document.querySelector(`#${windowId} .skill-edit-modal-overlay`);
    if (overlay) overlay.style.display = 'none';
  }

  /**
   * Remove a skill
   */
  async function removeSkill(skillName) {
    if (!confirm(`確定要移除 "${skillName}" 嗎？`)) return;

    try {
      const response = await fetch(`/api/skills/${encodeURIComponent(skillName)}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (!response.ok) throw new Error('Failed to delete');

      showToast('已移除 ' + skillName, 'check');
      if (currentSkillName === skillName) currentSkillName = null;
      await loadSkills();
      renderSkillList();
    } catch (e) {
      showToast('移除失敗: ' + e.message, 'error');
    }
  }

  /**
   * Search ClawHub
   */
  async function searchHub(query) {
    const resultsContainer = document.querySelector(`#${windowId} .skill-hub-results`);
    if (!resultsContainer) return;

    if (!query.trim()) {
      resultsContainer.innerHTML = '<div class="agent-list-empty"><p>輸入關鍵字搜尋</p></div>';
      return;
    }

    resultsContainer.innerHTML = '<div class="agent-list-empty"><p>搜尋中...</p></div>';

    try {
      const response = await fetch('/api/skills/hub/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ query })
      });
      if (!response.ok) throw new Error('Search failed');
      const data = await response.json();
      const results = data.results || [];

      if (results.length === 0) {
        resultsContainer.innerHTML = '<div class="agent-list-empty"><p>無搜尋結果</p></div>';
        return;
      }

      resultsContainer.innerHTML = results.map(r => `
        <div class="skill-hub-result-item">
          <div class="agent-list-item-info">
            <div class="agent-list-item-name">${escapeHtml(r.name)}</div>
            <div class="agent-list-item-model">${escapeHtml(r.description || '')}</div>
            <div class="skill-list-item-meta">
              ${r.version ? `<span class="skill-badge">${escapeHtml(r.version)}</span>` : ''}
              ${r.score != null ? `<span class="skill-badge">⭐ ${r.score}</span>` : ''}
            </div>
          </div>
          <button class="btn btn-sm btn-primary" data-action="install-skill" data-skill-name="${escapeHtml(r.name)}" data-skill-version="${escapeHtml(r.version || '')}">安裝</button>
        </div>
      `).join('');
    } catch (e) {
      resultsContainer.innerHTML = `<div class="agent-list-empty"><p>搜尋失敗: ${escapeHtml(e.message)}</p></div>`;
    }
  }

  /**
   * Install skill from ClawHub
   */
  async function installSkill(name, version) {
    try {
      const body = { name };
      if (version) body.version = version;

      const response = await fetch('/api/skills/hub/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(body)
      });
      if (!response.ok) throw new Error('Install failed');

      showToast(`已安裝 ${name}`, 'check');

      // Reload and switch to installed tab, highlight new skill
      await loadSkills();
      highlightSkillName = name;
      switchSkillSubTab('installed');
      renderSkillList();
    } catch (e) {
      showToast('安裝失敗: ' + e.message, 'error');
    }
  }

  /**
   * Browse skill file
   */
  async function browseSkillFile(skillName, filePath, contentEl) {
    if (contentEl.style.display !== 'none') {
      contentEl.style.display = 'none';
      return;
    }

    contentEl.textContent = '載入中...';
    contentEl.style.display = 'block';

    try {
      const response = await fetch(`/api/skills/${encodeURIComponent(skillName)}/files/${encodeURIComponent(filePath)}`, {
        headers: getAuthHeaders()
      });
      if (!response.ok) throw new Error('Failed to load file');
      const text = await response.text();
      contentEl.textContent = text;
    } catch (e) {
      contentEl.textContent = '載入失敗: ' + e.message;
    }
  }

  /**
   * Switch skill sub-tab (installed / hub)
   */
  function switchSkillSubTab(tab) {
    currentSkillsSubTab = tab;
    const wrapper = document.querySelector(`#${windowId} .skill-sidebar`);
    if (!wrapper) return;

    wrapper.querySelectorAll('.skill-sub-tab').forEach(t => {
      t.classList.toggle('active', t.dataset.skillTab === tab);
    });
    wrapper.querySelectorAll('.skill-sub-content').forEach(c => {
      c.style.display = c.dataset.skillTabContent === tab ? '' : 'none';
    });
  }

  /**
   * Escape HTML
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * 切換 Tab
   */
  function switchTab(tab) {
    currentTab = tab;
    const wrapper = document.querySelector(`#${windowId} .agent-settings-wrapper`);
    if (!wrapper) return;

    wrapper.querySelectorAll('.agent-settings-tab').forEach(t => {
      t.classList.toggle('active', t.dataset.tab === tab);
    });
    wrapper.querySelectorAll('.agent-settings-tab-content').forEach(c => {
      c.classList.toggle('active', c.dataset.tabContent === tab);
    });
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

    await Promise.all([loadAgents(), loadPrompts(), loadSkills()]);
    renderAgentList();
    renderSkillList();

    // 綁定事件
    bindEvents();
  }

  /**
   * 綁定事件
   */
  function bindEvents() {
    const root = document.getElementById(windowId);
    if (!root) return;

    // 新增按鈕
    const newBtn = root.querySelector('.agent-new-btn');
    if (newBtn) {
      newBtn.addEventListener('click', createNewAgent);
    }

    // Tab 切換
    root.querySelectorAll('.agent-settings-tab').forEach(tab => {
      tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Skill sub-tab 切換
    root.querySelectorAll('.skill-sub-tab').forEach(tab => {
      tab.addEventListener('click', () => switchSkillSubTab(tab.dataset.skillTab));
    });

    // Hub search
    const hubSearchBtn = root.querySelector('[data-action="hub-search"]');
    if (hubSearchBtn) {
      hubSearchBtn.addEventListener('click', () => {
        const input = root.querySelector('.skill-hub-search-input');
        if (input) searchHub(input.value);
      });
    }
    const hubSearchInput = root.querySelector('.skill-hub-search-input');
    if (hubSearchInput) {
      hubSearchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') searchHub(hubSearchInput.value);
      });
    }

    // Delegated click handler for data-action
    root.addEventListener('click', (e) => {
      const actionEl = e.target.closest('[data-action]');
      if (!actionEl) return;

      const action = actionEl.dataset.action;

      switch (action) {
        case 'edit-skill':
          e.stopPropagation();
          openSkillEditModal(actionEl.dataset.skillName);
          break;
        case 'remove-skill':
          e.stopPropagation();
          removeSkill(actionEl.dataset.skillName);
          break;
        case 'reload-skills':
        case 'reload-skills-detail':
          reloadSkills();
          break;
        case 'close-skill-modal':
          closeSkillEditModal();
          break;
        case 'save-skill':
          saveSkillFromModal();
          break;
        case 'install-skill':
          installSkill(actionEl.dataset.skillName, actionEl.dataset.skillVersion || null);
          break;
        case 'remove-chip':
          actionEl.closest('.skill-chip-removable')?.remove();
          break;
        case 'browse-file': {
          const contentEl = actionEl.nextElementSibling;
          if (contentEl && contentEl.classList.contains('skill-file-content')) {
            const dir = actionEl.dataset.fileDir;
            const filePath = actionEl.dataset.filePath;
            const fullPath = dir + '/' + filePath;
            browseSkillFile(actionEl.dataset.skillName, fullPath, contentEl);
          }
          break;
        }
      }
    });

    // Chip input Enter handler (delegated)
    root.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.target.classList.contains('skill-chip-input')) {
        e.preventDefault();
        const val = e.target.value.trim();
        if (!val) return;
        const chipsContainer = e.target.closest('.skill-chip-editor')?.querySelector('.skill-chips-editable');
        if (chipsContainer) {
          const chip = document.createElement('span');
          chip.className = 'skill-chip skill-chip-removable';
          chip.innerHTML = `${escapeHtml(val)}<button class="skill-chip-remove" data-action="remove-chip">&times;</button>`;
          chipsContainer.appendChild(chip);
          e.target.value = '';
        }
      }
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
      title: 'Agent 設定',
      appId: APP_ID,
      icon: 'tune-variant',
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
