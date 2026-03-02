/**
 * ChingTech OS - Task Scheduler Application
 * 動態排程管理
 */

const TaskSchedulerApp = (function() {
  'use strict';

  const APP_ID = 'task-scheduler';
  let windowId = null;
  let tasks = [];
  let agents = [];
  let skills = [];
  let filterSource = 'all'; // all | dynamic | static

  function getAuthHeaders() {
    const token = LoginModule?.getToken?.() || localStorage.getItem('chingtech_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  }

  // ── API ───────────────────────────────────────────────────

  async function fetchTasks() {
    try {
      const res = await fetch('/api/scheduler/tasks', { headers: getAuthHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      tasks = data.tasks || [];
      renderList();
    } catch (e) {
      console.error('載入排程列表失敗:', e);
      showToast('載入排程列表失敗', 'alert-circle');
    }
  }

  async function fetchAgents() {
    try {
      const res = await fetch('/api/ai/agents', { headers: getAuthHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      agents = data.agents || data || [];
    } catch (_) { /* ignore */ }
  }

  async function fetchSkills() {
    try {
      const res = await fetch('/api/skills', { headers: getAuthHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      skills = data.skills || data || [];
    } catch (_) { /* ignore */ }
  }

  async function createTask(body) {
    const res = await fetch('/api/scheduler/tasks', {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function updateTask(id, body) {
    const res = await fetch(`/api/scheduler/tasks/${id}`, {
      method: 'PUT',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function deleteTask(id) {
    const res = await fetch(`/api/scheduler/tasks/${id}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  }

  async function toggleTask(id, isEnabled) {
    const res = await fetch(`/api/scheduler/tasks/${id}/toggle`, {
      method: 'PATCH',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_enabled: isEnabled }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async function runTask(id) {
    const res = await fetch(`/api/scheduler/tasks/${id}/run`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  // ── 渲染 ─────────────────────────────────────────────────

  function getContainer() {
    if (!windowId) return null;
    return document.querySelector(`#${windowId} .task-scheduler`);
  }

  function renderList() {
    const container = getContainer();
    if (!container) return;

    const list = container.querySelector('.ts-list');
    if (!list) return;

    // 篩選
    let filtered = tasks;
    if (filterSource === 'dynamic') {
      filtered = tasks.filter(t => t.source === 'dynamic');
    } else if (filterSource === 'static') {
      filtered = tasks.filter(t => t.source !== 'dynamic');
    }

    if (filtered.length === 0) {
      list.innerHTML = `
        <div class="ts-empty">
          <span class="icon">${getIcon('calendar-clock')}</span>
          <span>尚無排程任務</span>
        </div>`;
      return;
    }

    // 動態排程在前，靜態在後
    filtered.sort((a, b) => {
      if (a.source === 'dynamic' && b.source !== 'dynamic') return -1;
      if (a.source !== 'dynamic' && b.source === 'dynamic') return 1;
      return 0;
    });

    list.innerHTML = filtered.map(renderCard).join('');
    bindCardEvents(list);
  }

  function renderCard(task) {
    const isStatic = task.source !== 'dynamic';
    const isDisabled = !task.is_enabled;

    // 狀態
    let statusClass = 'ts-status-dot--idle';
    let statusText = '尚未執行';
    if (task.last_run_success === true) {
      statusClass = 'ts-status-dot--success';
      statusText = '成功';
    } else if (task.last_run_success === false) {
      statusClass = 'ts-status-dot--error';
      statusText = '失敗';
    }

    // Badge
    const badgeMap = {
      dynamic: { cls: 'ts-card-badge--dynamic', label: '動態' },
      system: { cls: 'ts-card-badge--system', label: '系統' },
      module: { cls: 'ts-card-badge--module', label: '模組' },
    };
    const badge = badgeMap[task.source] || badgeMap.dynamic;

    // 觸發摘要
    const triggerText = formatTrigger(task.trigger_type, task.trigger_config);

    // 執行類型
    const execText = isStatic ? '系統函式' : (task.executor_type === 'agent' ? 'Agent' : 'Skill Script');

    // 下次執行
    const nextRun = task.next_run_at ? formatTime(task.next_run_at) : '-';

    // 操作按鈕（僅動態排程）
    let actions = '';
    if (!isStatic) {
      actions = `
        <div class="ts-card-actions">
          <button class="ts-action-btn" data-action="run" data-id="${task.id}" title="立即執行">
            <span class="icon">${getIcon('play')}</span>
          </button>
          <button class="ts-action-btn" data-action="edit" data-id="${task.id}" title="編輯">
            <span class="icon">${getIcon('pencil')}</span>
          </button>
          <button class="ts-action-btn ts-action-btn--danger" data-action="delete" data-id="${task.id}" title="刪除">
            <span class="icon">${getIcon('delete')}</span>
          </button>
          <div class="ts-toggle ${task.is_enabled ? 'ts-toggle--on' : ''}" data-action="toggle" data-id="${task.id}" data-enabled="${task.is_enabled}"></div>
        </div>`;
    }

    return `
      <div class="ts-card ${isDisabled ? 'ts-card--disabled' : ''} ${isStatic ? 'ts-card--static' : ''}" data-task-id="${task.id}">
        <div class="ts-status-dot ${statusClass}" title="${statusText}${task.last_run_error ? ': ' + escapeHtml(task.last_run_error) : ''}"></div>
        <div class="ts-card-info">
          <div class="ts-card-header">
            <span class="ts-card-name" title="${escapeHtml(task.description || task.name)}">${escapeHtml(task.name)}</span>
            <span class="ts-card-badge ${badge.cls}">${badge.label}</span>
          </div>
          <div class="ts-card-detail">
            <span>${triggerText}</span>
            <span>${execText}</span>
            <span>下次: ${nextRun}</span>
          </div>
        </div>
        ${actions}
      </div>`;
  }

  function bindCardEvents(list) {
    list.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const action = btn.dataset.action;
        const id = btn.dataset.id;
        if (action === 'edit') openEditModal(id);
        else if (action === 'delete') confirmDelete(id);
        else if (action === 'run') handleRun(id);
        else if (action === 'toggle') handleToggle(btn, id);
      });
    });
  }

  // ── 操作處理 ──────────────────────────────────────────────

  async function handleRun(id) {
    try {
      await runTask(id);
      showToast('已送出執行', 'play');
      // 延遲重新載入以取得執行結果
      setTimeout(() => fetchTasks(), 3000);
    } catch (e) {
      showToast('觸發失敗: ' + e.message, 'alert-circle');
    }
  }

  async function handleToggle(btn, id) {
    const currentEnabled = btn.dataset.enabled === 'true';
    const newEnabled = !currentEnabled;
    try {
      await toggleTask(id, newEnabled);
      await fetchTasks();
    } catch (e) {
      showToast('切換失敗: ' + e.message, 'alert-circle');
    }
  }

  function confirmDelete(id) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    if (!confirm(`確定要刪除排程「${task.name}」嗎？`)) return;
    deleteTask(id)
      .then(() => {
        showToast('已刪除', 'delete');
        fetchTasks();
      })
      .catch(e => showToast('刪除失敗: ' + e.message, 'alert-circle'));
  }

  // ── Modal 表單 ────────────────────────────────────────────

  function openCreateModal() {
    openFormModal(null);
  }

  function openEditModal(id) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    openFormModal(task);
  }

  function openFormModal(editTask) {
    const isEdit = !!editTask;
    const title = isEdit ? '編輯排程' : '新增排程';

    // 預設值
    const name = editTask?.name || '';
    const desc = editTask?.description || '';
    const triggerType = editTask?.trigger_type || 'cron';
    const triggerConfig = editTask?.trigger_config || {};
    const executorType = editTask?.executor_type || 'agent';
    const executorConfig = editTask?.executor_config || {};

    const overlay = document.createElement('div');
    overlay.className = 'ts-modal-overlay';
    overlay.innerHTML = `
      <div class="ts-modal">
        <div class="ts-modal-header">
          <h3>${title}</h3>
          <button class="ts-modal-close"><span class="icon">${getIcon('close')}</span></button>
        </div>
        <div class="ts-modal-body">
          <div class="ts-field">
            <label>排程名稱 *</label>
            <input type="text" id="ts-name" value="${escapeHtml(name)}" placeholder="例: daily-report" />
          </div>
          <div class="ts-field">
            <label>說明</label>
            <input type="text" id="ts-desc" value="${escapeHtml(desc)}" placeholder="排程用途說明（選填）" />
          </div>

          <div class="ts-field">
            <label>觸發類型</label>
            <select id="ts-trigger-type">
              <option value="cron" ${triggerType === 'cron' ? 'selected' : ''}>Cron（定時）</option>
              <option value="interval" ${triggerType === 'interval' ? 'selected' : ''}>Interval（間隔）</option>
            </select>
          </div>

          <div id="ts-trigger-fields"></div>

          <div class="ts-field">
            <label>執行類型</label>
            <select id="ts-executor-type">
              <option value="agent" ${executorType === 'agent' ? 'selected' : ''}>Agent</option>
              <option value="skill_script" ${executorType === 'skill_script' ? 'selected' : ''}>Skill Script</option>
            </select>
          </div>

          <div id="ts-executor-fields"></div>
        </div>
        <div class="ts-modal-footer">
          <button class="ts-btn ts-btn--secondary ts-modal-cancel">取消</button>
          <button class="ts-btn ts-btn--primary ts-modal-save">${isEdit ? '儲存' : '建立'}</button>
        </div>
      </div>`;

    document.body.appendChild(overlay);

    // 關閉事件
    const closeModal = () => overlay.remove();
    overlay.querySelector('.ts-modal-close').addEventListener('click', closeModal);
    overlay.querySelector('.ts-modal-cancel').addEventListener('click', closeModal);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });

    // 觸發類型切換
    const triggerTypeEl = overlay.querySelector('#ts-trigger-type');
    const renderTriggerFields = () => {
      const type = triggerTypeEl.value;
      const container = overlay.querySelector('#ts-trigger-fields');
      if (type === 'cron') {
        container.innerHTML = `
          <div class="ts-field-row">
            <div class="ts-field">
              <label>分鐘</label>
              <input type="text" id="ts-cron-minute" value="${escapeHtml(triggerConfig.minute || '*')}" placeholder="*" />
            </div>
            <div class="ts-field">
              <label>小時</label>
              <input type="text" id="ts-cron-hour" value="${escapeHtml(triggerConfig.hour || '*')}" placeholder="*" />
            </div>
          </div>
          <div class="ts-field-row">
            <div class="ts-field">
              <label>日</label>
              <input type="text" id="ts-cron-day" value="${escapeHtml(triggerConfig.day || '*')}" placeholder="*" />
            </div>
            <div class="ts-field">
              <label>月</label>
              <input type="text" id="ts-cron-month" value="${escapeHtml(triggerConfig.month || '*')}" placeholder="*" />
            </div>
          </div>
          <div class="ts-field">
            <label>星期幾</label>
            <input type="text" id="ts-cron-dow" value="${escapeHtml(triggerConfig.day_of_week || '*')}" placeholder="* (0=Mon, 6=Sun)" />
          </div>`;
      } else {
        container.innerHTML = `
          <div class="ts-field-row">
            <div class="ts-field">
              <label>小時</label>
              <input type="number" id="ts-int-hours" value="${triggerConfig.hours || 0}" min="0" />
            </div>
            <div class="ts-field">
              <label>分鐘</label>
              <input type="number" id="ts-int-minutes" value="${triggerConfig.minutes || 0}" min="0" />
            </div>
          </div>
          <div class="ts-field-row">
            <div class="ts-field">
              <label>秒</label>
              <input type="number" id="ts-int-seconds" value="${triggerConfig.seconds || 0}" min="0" />
            </div>
            <div class="ts-field">
              <label>天</label>
              <input type="number" id="ts-int-days" value="${triggerConfig.days || 0}" min="0" />
            </div>
          </div>`;
      }
    };
    triggerTypeEl.addEventListener('change', renderTriggerFields);
    renderTriggerFields();

    // 執行類型切換
    const executorTypeEl = overlay.querySelector('#ts-executor-type');
    const renderExecutorFields = () => {
      const type = executorTypeEl.value;
      const container = overlay.querySelector('#ts-executor-fields');
      if (type === 'agent') {
        const agentOptions = agents.map(a => {
          const aName = a.name || a.display_name;
          const selected = executorConfig.agent_name === aName ? 'selected' : '';
          return `<option value="${escapeHtml(aName)}" ${selected}>${escapeHtml(a.display_name || aName)}</option>`;
        }).join('');
        container.innerHTML = `
          <div class="ts-field">
            <label>Agent</label>
            <select id="ts-agent-name">
              <option value="">-- 選擇 Agent --</option>
              ${agentOptions}
            </select>
          </div>
          <div class="ts-field">
            <label>Prompt *</label>
            <textarea id="ts-agent-prompt" rows="3" placeholder="要求 Agent 執行的指令">${escapeHtml(executorConfig.prompt || '')}</textarea>
          </div>`;
      } else {
        const skillOptions = skills.map(s => {
          const sName = s.name;
          const selected = executorConfig.skill === sName ? 'selected' : '';
          return `<option value="${escapeHtml(sName)}" ${selected}>${escapeHtml(sName)}</option>`;
        }).join('');
        container.innerHTML = `
          <div class="ts-field">
            <label>Skill</label>
            <select id="ts-skill-name">
              <option value="">-- 選擇 Skill --</option>
              ${skillOptions}
            </select>
          </div>
          <div class="ts-field">
            <label>Script</label>
            <input type="text" id="ts-script-name" value="${escapeHtml(executorConfig.script || '')}" placeholder="script 名稱" />
          </div>
          <div class="ts-field">
            <label>Input (JSON，選填)</label>
            <textarea id="ts-script-input" rows="2" placeholder='{"key": "value"}'>${escapeHtml(executorConfig.input || '')}</textarea>
          </div>`;
      }
    };
    executorTypeEl.addEventListener('change', renderExecutorFields);
    renderExecutorFields();

    // 儲存
    overlay.querySelector('.ts-modal-save').addEventListener('click', async () => {
      const formName = overlay.querySelector('#ts-name').value.trim();
      const formDesc = overlay.querySelector('#ts-desc').value.trim();
      const formTriggerType = triggerTypeEl.value;
      const formExecutorType = executorTypeEl.value;

      if (!formName) {
        showToast('請輸入排程名稱', 'alert-circle');
        return;
      }

      // 組裝 trigger_config
      let formTriggerConfig;
      if (formTriggerType === 'cron') {
        formTriggerConfig = {
          minute: overlay.querySelector('#ts-cron-minute')?.value || '*',
          hour: overlay.querySelector('#ts-cron-hour')?.value || '*',
          day: overlay.querySelector('#ts-cron-day')?.value || '*',
          month: overlay.querySelector('#ts-cron-month')?.value || '*',
          day_of_week: overlay.querySelector('#ts-cron-dow')?.value || '*',
        };
      } else {
        formTriggerConfig = {
          hours: parseInt(overlay.querySelector('#ts-int-hours')?.value) || 0,
          minutes: parseInt(overlay.querySelector('#ts-int-minutes')?.value) || 0,
          seconds: parseInt(overlay.querySelector('#ts-int-seconds')?.value) || 0,
          days: parseInt(overlay.querySelector('#ts-int-days')?.value) || 0,
        };
      }

      // 組裝 executor_config
      let formExecutorConfig;
      if (formExecutorType === 'agent') {
        const agentName = overlay.querySelector('#ts-agent-name')?.value;
        const prompt = overlay.querySelector('#ts-agent-prompt')?.value?.trim();
        if (!agentName || !prompt) {
          showToast('請選擇 Agent 並輸入 Prompt', 'alert-circle');
          return;
        }
        formExecutorConfig = { agent_name: agentName, prompt };
      } else {
        const skillName = overlay.querySelector('#ts-skill-name')?.value;
        const scriptName = overlay.querySelector('#ts-script-name')?.value?.trim();
        if (!skillName || !scriptName) {
          showToast('請選擇 Skill 並輸入 Script 名稱', 'alert-circle');
          return;
        }
        formExecutorConfig = {
          skill: skillName,
          script: scriptName,
          input: overlay.querySelector('#ts-script-input')?.value?.trim() || '',
        };
      }

      const body = {
        name: formName,
        description: formDesc || null,
        trigger_type: formTriggerType,
        trigger_config: formTriggerConfig,
        executor_type: formExecutorType,
        executor_config: formExecutorConfig,
      };

      try {
        if (isEdit) {
          await updateTask(editTask.id, body);
          showToast('排程已更新', 'check');
        } else {
          await createTask(body);
          showToast('排程已建立', 'check');
        }
        closeModal();
        await fetchTasks();
      } catch (e) {
        showToast(e.message, 'alert-circle');
      }
    });
  }

  // ── 工具函式 ──────────────────────────────────────────────

  function formatTrigger(type, config) {
    if (!config) return type;
    if (type === 'cron') {
      const parts = [];
      if (config.minute && config.minute !== '*') parts.push(`分:${config.minute}`);
      if (config.hour && config.hour !== '*') parts.push(`時:${config.hour}`);
      if (config.day && config.day !== '*') parts.push(`日:${config.day}`);
      if (config.day_of_week && config.day_of_week !== '*') parts.push(`週:${config.day_of_week}`);
      return parts.length ? `cron(${parts.join(' ')})` : 'cron(每分鐘)';
    }
    if (type === 'interval') {
      const parts = [];
      if (config.days) parts.push(`${config.days}天`);
      if (config.hours) parts.push(`${config.hours}時`);
      if (config.minutes) parts.push(`${config.minutes}分`);
      if (config.seconds) parts.push(`${config.seconds}秒`);
      return parts.length ? `每${parts.join('')}` : 'interval';
    }
    return type;
  }

  function formatTime(isoStr) {
    if (!isoStr) return '-';
    try {
      const d = new Date(isoStr);
      const pad = n => String(n).padStart(2, '0');
      return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    } catch {
      return isoStr;
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function showToast(msg, icon) {
    if (typeof NotificationModule !== 'undefined') {
      NotificationModule.showToast(msg, icon);
    }
  }

  function getIcon(name) {
    if (typeof window.getIcon === 'function') return window.getIcon(name);
    return '';
  }

  // ── 初始化 ────────────────────────────────────────────────

  function buildWindowContent() {
    return `
      <div class="task-scheduler">
        <div class="ts-toolbar">
          <button class="ts-btn-primary ts-add-btn">
            <span class="icon">${getIcon('plus')}</span> 新增排程
          </button>
          <select class="ts-filter-select">
            <option value="all">全部</option>
            <option value="dynamic">動態排程</option>
            <option value="static">靜態排程</option>
          </select>
          <button class="ts-refresh-btn">
            <span class="icon">${getIcon('refresh')}</span>
          </button>
        </div>
        <div class="ts-list">
          <div class="ts-loading">載入中...</div>
        </div>
      </div>`;
  }

  async function initApp(windowEl) {
    windowId = windowEl.id;

    const container = windowEl.querySelector('.task-scheduler');
    if (!container) return;

    // 工具列事件
    container.querySelector('.ts-add-btn')?.addEventListener('click', openCreateModal);
    container.querySelector('.ts-refresh-btn')?.addEventListener('click', fetchTasks);
    container.querySelector('.ts-filter-select')?.addEventListener('change', (e) => {
      filterSource = e.target.value;
      renderList();
    });

    // 載入資料
    await Promise.all([fetchTasks(), fetchAgents(), fetchSkills()]);
  }

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
      title: '排程管理',
      appId: APP_ID,
      icon: 'calendar-clock',
      width: 700,
      height: 500,
      content: buildWindowContent(),
      onInit: initApp,
      onClose: () => {
        windowId = null;
      }
    });
  }

  function close() {
    if (windowId) {
      WindowModule.closeWindow(windowId);
      windowId = null;
    }
  }

  return { open, close };
})();
// 將模組掛載到 window，供 desktop.js lazy-loader 偵測
window.TaskSchedulerApp = TaskSchedulerApp;
