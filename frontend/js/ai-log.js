/**
 * ChingTech OS - AI Log Application
 * AI 調用日誌檢視器
 */

const AILogApp = (function() {
  'use strict';

  const APP_ID = 'ai-log';
  let windowId = null;
  let logs = [];
  let agents = [];
  let stats = null;
  let currentLogId = null;
  let currentPage = 1;
  let totalPages = 1;
  let pageSize = 50;

  // 過濾條件
  let filters = {
    agent_id: null,
    context_type: null,
    success: null,
    start_date: null,
    end_date: null
  };

  const contextTypes = [
    { id: null, name: '全部類型' },
    { id: 'web-chat', name: 'Web 對話' },
    { id: 'linebot-group', name: 'Line 群組' },
    { id: 'linebot-personal', name: 'Line 個人' },
    { id: 'system', name: '系統' },
    { id: 'test', name: '測試' }
  ];

  /**
   * 載入 Agents（用於過濾器）
   */
  async function loadAgents() {
    try {
      const response = await fetch('/api/ai/agents');
      if (!response.ok) throw new Error('Failed to load agents');
      const data = await response.json();
      agents = data.items || [];
    } catch (e) {
      console.error('[AILog] Failed to load agents:', e);
      agents = [];
    }
  }

  /**
   * 載入 Logs
   */
  async function loadLogs() {
    try {
      const params = new URLSearchParams();
      params.set('page', currentPage);
      params.set('page_size', pageSize);

      if (filters.agent_id) params.set('agent_id', filters.agent_id);
      if (filters.context_type) params.set('context_type', filters.context_type);
      if (filters.success !== null) params.set('success', filters.success);
      if (filters.start_date) params.set('start_date', filters.start_date);
      if (filters.end_date) params.set('end_date', filters.end_date);

      const response = await fetch(`/api/ai/logs?${params.toString()}`);
      if (!response.ok) throw new Error('Failed to load logs');
      const data = await response.json();

      logs = data.items || [];
      totalPages = Math.ceil(data.total / pageSize) || 1;
    } catch (e) {
      console.error('[AILog] Failed to load logs:', e);
      logs = [];
    }
  }

  /**
   * 載入統計
   */
  async function loadStats() {
    try {
      const params = new URLSearchParams();
      if (filters.agent_id) params.set('agent_id', filters.agent_id);
      if (filters.start_date) params.set('start_date', filters.start_date);
      if (filters.end_date) params.set('end_date', filters.end_date);

      const response = await fetch(`/api/ai/logs/stats?${params.toString()}`);
      if (!response.ok) throw new Error('Failed to load stats');
      stats = await response.json();
    } catch (e) {
      console.error('[AILog] Failed to load stats:', e);
      stats = null;
    }
  }

  /**
   * 載入單一 Log 詳情
   */
  async function loadLogDetail(logId) {
    try {
      const response = await fetch(`/api/ai/logs/${logId}`);
      if (!response.ok) throw new Error('Failed to load log');
      return await response.json();
    } catch (e) {
      console.error('[AILog] Failed to load log detail:', e);
      return null;
    }
  }

  /**
   * 取得今天的日期字串
   */
  function getTodayString() {
    return new Date().toISOString().split('T')[0];
  }

  /**
   * 建立視窗內容
   */
  function buildWindowContent() {
    const today = getTodayString();

    return `
      <div class="ai-log">
        <div class="ai-log-filters">
          <div class="ai-log-filter-group">
            <label class="ai-log-filter-label">Agent:</label>
            <select class="ai-log-filter-select" data-filter="agent_id">
              <option value="">全部 Agent</option>
              ${agents.map(a => `<option value="${a.id}">${a.display_name || a.name}</option>`).join('')}
            </select>
          </div>
          <div class="ai-log-filter-group">
            <label class="ai-log-filter-label">類型:</label>
            <select class="ai-log-filter-select" data-filter="context_type">
              ${contextTypes.map(t => `<option value="${t.id || ''}">${t.name}</option>`).join('')}
            </select>
          </div>
          <div class="ai-log-filter-group">
            <label class="ai-log-filter-label">狀態:</label>
            <select class="ai-log-filter-select" data-filter="success">
              <option value="">全部</option>
              <option value="true">成功</option>
              <option value="false">失敗</option>
            </select>
          </div>
          <div class="ai-log-filter-group">
            <label class="ai-log-filter-label">開始:</label>
            <input type="date" class="ai-log-filter-input" data-filter="start_date" value="${today}">
          </div>
          <div class="ai-log-filter-group">
            <label class="ai-log-filter-label">結束:</label>
            <input type="date" class="ai-log-filter-input" data-filter="end_date">
          </div>
          <button class="ai-log-refresh-btn btn btn-secondary">
            <span class="icon">${getIcon('refresh')}</span>
            重新整理
          </button>
        </div>

        <div class="ai-log-stats">
          <div class="ai-log-stat-card">
            <span class="ai-log-stat-value" id="stat-total">--</span>
            <span class="ai-log-stat-label">總調用次數</span>
          </div>
          <div class="ai-log-stat-card success">
            <span class="ai-log-stat-value" id="stat-rate">--%</span>
            <span class="ai-log-stat-label">成功率</span>
          </div>
          <div class="ai-log-stat-card">
            <span class="ai-log-stat-value" id="stat-duration">--</span>
            <span class="ai-log-stat-label">平均耗時</span>
          </div>
          <div class="ai-log-stat-card">
            <span class="ai-log-stat-value" id="stat-tokens">--</span>
            <span class="ai-log-stat-label">總 Tokens</span>
          </div>
        </div>

        <div class="ai-log-content">
          <div class="ai-log-list-wrapper">
            <table class="ai-log-table">
              <thead>
                <tr>
                  <th style="width: 40px;"></th>
                  <th style="width: 160px;">時間</th>
                  <th>Agent</th>
                  <th>類型</th>
                  <th style="width: 80px;">耗時</th>
                  <th style="width: 100px;">Tokens</th>
                </tr>
              </thead>
              <tbody id="log-list-body">
                <!-- Log items will be rendered here -->
              </tbody>
            </table>
          </div>

          <div class="ai-log-detail" id="log-detail" style="display: none;">
            <!-- Detail panel will be rendered here -->
          </div>
        </div>

        <div class="ai-log-pagination">
          <button class="ai-log-page-btn" id="prev-page">
            <span class="icon">${getIcon('chevron-left')}</span>
          </button>
          <span class="ai-log-page-info" id="page-info">1 / 1</span>
          <button class="ai-log-page-btn" id="next-page">
            <span class="icon">${getIcon('chevron-right')}</span>
          </button>
        </div>
      </div>
    `;
  }

  /**
   * 渲染 Log 列表
   */
  function renderLogList() {
    const tbody = document.querySelector(`#${windowId} #log-list-body`);
    if (!tbody) return;

    if (logs.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6">
            <div class="ai-log-empty">
              <span class="icon">${getIcon('file-document-outline')}</span>
              <p>沒有符合條件的日誌</p>
            </div>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = logs.map(log => `
      <tr data-log-id="${log.id}" class="${log.id === currentLogId ? 'selected' : ''}">
        <td>
          <span class="ai-log-status ${log.success ? 'success' : 'error'}">
            ${getIcon(log.success ? 'check-circle' : 'alert-circle')}
          </span>
        </td>
        <td>${formatDateTime(log.created_at)}</td>
        <td>${log.agent_name || '-'}</td>
        <td>${log.context_type || '-'}</td>
        <td><span class="ai-log-duration">${formatDuration(log.duration_ms)}</span></td>
        <td><span class="ai-log-tokens">${formatTokens(log.input_tokens, log.output_tokens)}</span></td>
      </tr>
    `).join('');

    // 綁定點擊事件
    tbody.querySelectorAll('tr[data-log-id]').forEach(row => {
      row.addEventListener('click', () => {
        selectLog(row.dataset.logId);
      });
    });
  }

  /**
   * 渲染統計
   */
  function renderStats() {
    if (!stats) return;

    const totalEl = document.querySelector(`#${windowId} #stat-total`);
    const rateEl = document.querySelector(`#${windowId} #stat-rate`);
    const durationEl = document.querySelector(`#${windowId} #stat-duration`);
    const tokensEl = document.querySelector(`#${windowId} #stat-tokens`);

    if (totalEl) totalEl.textContent = stats.total_calls.toLocaleString();
    if (rateEl) rateEl.textContent = `${stats.success_rate}%`;
    if (durationEl) durationEl.textContent = stats.avg_duration_ms ? `${(stats.avg_duration_ms / 1000).toFixed(2)}s` : '--';
    if (tokensEl) tokensEl.textContent = (stats.total_input_tokens + stats.total_output_tokens).toLocaleString();
  }

  /**
   * 渲染分頁
   */
  function renderPagination() {
    const pageInfo = document.querySelector(`#${windowId} #page-info`);
    const prevBtn = document.querySelector(`#${windowId} #prev-page`);
    const nextBtn = document.querySelector(`#${windowId} #next-page`);

    if (pageInfo) pageInfo.textContent = `${currentPage} / ${totalPages}`;
    if (prevBtn) prevBtn.disabled = currentPage <= 1;
    if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
  }

  /**
   * 選擇 Log 顯示詳情
   */
  async function selectLog(logId) {
    currentLogId = logId;

    // 更新列表選中狀態
    document.querySelectorAll(`#${windowId} #log-list-body tr`).forEach(row => {
      row.classList.toggle('selected', row.dataset.logId === logId);
    });

    const detailPanel = document.querySelector(`#${windowId} #log-detail`);
    if (!detailPanel) return;

    if (!logId) {
      detailPanel.style.display = 'none';
      return;
    }

    // 載入詳情
    const log = await loadLogDetail(logId);
    if (!log) return;

    detailPanel.style.display = 'flex';
    detailPanel.innerHTML = `
      <div class="ai-log-detail-header">
        <span class="ai-log-detail-title">Log 詳情</span>
        <button class="ai-log-detail-close">
          <span class="icon">${getIcon('close')}</span>
        </button>
      </div>
      <div class="ai-log-detail-content">
        ${log.system_prompt ? `
          <div class="ai-log-detail-section">
            <div class="ai-log-detail-section-title">System Prompt</div>
            <div class="ai-log-detail-text system-prompt">${escapeHtml(log.system_prompt)}</div>
          </div>
        ` : ''}
        <div class="ai-log-detail-section">
          <div class="ai-log-detail-section-title">使用者輸入</div>
          <div class="ai-log-detail-text">${escapeHtml(log.input_prompt)}</div>
        </div>
        <div class="ai-log-detail-section">
          <div class="ai-log-detail-section-title">AI 輸出</div>
          <div class="ai-log-detail-text ${log.error_message ? 'error' : ''}">
            ${log.error_message ? escapeHtml(log.error_message) : escapeHtml(log.raw_response || '無回應')}
          </div>
        </div>
      </div>
      <div class="ai-log-detail-meta">
        <span>Model: ${log.model || '-'}</span>
        <span>輸入 Tokens: ${log.input_tokens || '-'}</span>
        <span>輸出 Tokens: ${log.output_tokens || '-'}</span>
        <span>耗時: ${formatDuration(log.duration_ms)}</span>
      </div>
    `;

    // 關閉按鈕
    detailPanel.querySelector('.ai-log-detail-close').addEventListener('click', () => {
      currentLogId = null;
      detailPanel.style.display = 'none';
      document.querySelectorAll(`#${windowId} #log-list-body tr`).forEach(row => {
        row.classList.remove('selected');
      });
    });
  }

  /**
   * 格式化日期時間
   */
  function formatDateTime(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString('zh-TW', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  }

  /**
   * 格式化耗時
   */
  function formatDuration(ms) {
    if (!ms) return '-';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  }

  /**
   * 格式化 Token 數
   */
  function formatTokens(input, output) {
    if (!input && !output) return '-';
    return `${input || 0}/${output || 0}`;
  }

  /**
   * HTML 轉義
   */
  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * 重新載入資料
   */
  async function refresh() {
    await Promise.all([loadLogs(), loadStats()]);
    renderLogList();
    renderStats();
    renderPagination();
  }

  /**
   * 初始化應用
   */
  async function initApp(windowEl, wId) {
    windowId = wId;

    // 設定今天為預設開始日期
    filters.start_date = getTodayString() + 'T00:00:00';

    await loadAgents();

    // 更新 Agent 下拉選單
    const agentSelect = document.querySelector(`#${windowId} [data-filter="agent_id"]`);
    if (agentSelect) {
      agentSelect.innerHTML = `
        <option value="">全部 Agent</option>
        ${agents.map(a => `<option value="${a.id}">${a.display_name || a.name}</option>`).join('')}
      `;
    }

    await refresh();
    bindEvents();
  }

  /**
   * 綁定事件
   */
  function bindEvents() {
    // 過濾器變更
    document.querySelectorAll(`#${windowId} [data-filter]`).forEach(el => {
      el.addEventListener('change', () => {
        const filter = el.dataset.filter;
        let value = el.value;

        if (filter === 'success') {
          value = value === '' ? null : value === 'true';
        } else if (filter === 'start_date' || filter === 'end_date') {
          value = value ? value + (filter === 'start_date' ? 'T00:00:00' : 'T23:59:59') : null;
        } else {
          value = value || null;
        }

        filters[filter] = value;
        currentPage = 1;
        refresh();
      });
    });

    // 重新整理按鈕
    const refreshBtn = document.querySelector(`#${windowId} .ai-log-refresh-btn`);
    if (refreshBtn) {
      refreshBtn.addEventListener('click', refresh);
    }

    // 分頁按鈕
    const prevBtn = document.querySelector(`#${windowId} #prev-page`);
    const nextBtn = document.querySelector(`#${windowId} #next-page`);

    if (prevBtn) {
      prevBtn.addEventListener('click', () => {
        if (currentPage > 1) {
          currentPage--;
          refresh();
        }
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        if (currentPage < totalPages) {
          currentPage++;
          refresh();
        }
      });
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
      title: 'AI Log',
      appId: APP_ID,
      icon: 'history',
      width: 950,
      height: 650,
      content: buildWindowContent(),
      onInit: initApp,
      onClose: () => {
        windowId = null;
        currentLogId = null;
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
