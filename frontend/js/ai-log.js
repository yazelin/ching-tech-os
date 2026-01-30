/**
 * ChingTech OS - AI Log Application
 * AI 調用日誌檢視器
 */

const AILogApp = (function() {
  'use strict';

  const APP_ID = 'ai-log';
  const MOBILE_BREAKPOINT = 768;

  // 取得 token
  function getToken() {
    return localStorage.getItem('chingtech_token');
  }

  // API 呼叫輔助函數
  function getAuthHeaders() {
    const token = getToken();
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  }
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
    { id: 'telegram-group', name: 'Telegram 群組' },
    { id: 'telegram-personal', name: 'Telegram 個人' },
    { id: 'system', name: '系統' },
    { id: 'test', name: '測試' }
  ];

  /**
   * 載入 Agents（用於過濾器）
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

      const response = await fetch(`/api/ai/logs?${params.toString()}`, {
        headers: getAuthHeaders()
      });
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

      const response = await fetch(`/api/ai/logs/stats?${params.toString()}`, {
        headers: getAuthHeaders()
      });
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
      const response = await fetch(`/api/ai/logs/${logId}`, {
        headers: getAuthHeaders()
      });
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
   * 判斷是否為手機版
   */
  function isMobile() {
    return window.innerWidth <= MOBILE_BREAKPOINT;
  }

  /**
   * 建立視窗內容
   */
  function buildWindowContent() {
    const today = getTodayString();

    return `
      <div class="ai-log">
        <div class="ai-log-filters">
          <button class="ai-log-filter-toggle">
            <span>篩選條件</span>
            <span class="icon">${getIcon('chevron-down')}</span>
          </button>
          <div class="ai-log-filter-content">
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
            <span class="ai-log-stat-value" id="stat-input-tokens">--</span>
            <span class="ai-log-stat-label">輸入 Tokens</span>
          </div>
          <div class="ai-log-stat-card">
            <span class="ai-log-stat-value" id="stat-output-tokens">--</span>
            <span class="ai-log-stat-label">輸出 Tokens</span>
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
                  <th>Tools</th>
                  <th style="width: 80px;">耗時</th>
                  <th style="width: 100px;">Tokens</th>
                </tr>
              </thead>
              <tbody id="log-list-body">
                <!-- Log items will be rendered here -->
              </tbody>
            </table>
            <div id="log-card-list" class="ai-log-card-list">
              <!-- Card items will be rendered here (mobile) -->
            </div>
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
    const cardList = document.querySelector(`#${windowId} #log-card-list`);
    if (!tbody || !cardList) return;

    // 空狀態
    if (logs.length === 0) {
      const emptyHtml = `
        <div class="ai-log-empty">
          <span class="icon">${getIcon('file-document-outline')}</span>
          <p>沒有符合條件的日誌</p>
        </div>
      `;
      tbody.innerHTML = `<tr><td colspan="7">${emptyHtml}</td></tr>`;
      cardList.innerHTML = emptyHtml;
      return;
    }

    // 表格渲染（桌機版）
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
        <td>${renderToolsBadges(log.allowed_tools, log.used_tools)}</td>
        <td><span class="ai-log-duration">${formatDuration(log.duration_ms)}</span></td>
        <td><span class="ai-log-tokens">${formatTokens(log.input_tokens, log.output_tokens)}</span></td>
      </tr>
    `).join('');

    // 卡片渲染（手機版）
    cardList.innerHTML = logs.map(log => `
      <div class="ai-log-card ${log.id === currentLogId ? 'selected' : ''}" data-log-id="${log.id}">
        <div class="ai-log-card-header">
          <div class="ai-log-card-status">
            <span class="ai-log-status ${log.success ? 'success' : 'error'}">
              ${getIcon(log.success ? 'check-circle' : 'alert-circle')}
            </span>
            <span class="ai-log-card-agent">${log.agent_name || '-'}</span>
          </div>
          <span class="ai-log-card-time">${formatDateTime(log.created_at)}</span>
        </div>
        <div class="ai-log-card-body">
          <span class="ai-log-card-type">${log.context_type || '-'}</span>
          <div class="ai-log-card-tools">${renderToolsBadges(log.allowed_tools, log.used_tools)}</div>
        </div>
        <div class="ai-log-card-footer">
          <span>耗時: ${formatDuration(log.duration_ms)}</span>
          <span>Tokens: ${formatTokens(log.input_tokens, log.output_tokens)}</span>
        </div>
      </div>
    `).join('');

    // 綁定點擊事件（表格）
    tbody.querySelectorAll('tr[data-log-id]').forEach(row => {
      row.addEventListener('click', () => {
        selectLog(row.dataset.logId);
      });
    });

    // 綁定點擊事件（卡片）
    cardList.querySelectorAll('.ai-log-card[data-log-id]').forEach(card => {
      card.addEventListener('click', () => {
        selectLog(card.dataset.logId);
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
    const inputTokensEl = document.querySelector(`#${windowId} #stat-input-tokens`);
    const outputTokensEl = document.querySelector(`#${windowId} #stat-output-tokens`);

    if (totalEl) totalEl.textContent = stats.total_calls.toLocaleString();
    if (rateEl) rateEl.textContent = `${stats.success_rate}%`;
    if (durationEl) durationEl.textContent = stats.avg_duration_ms ? `${(stats.avg_duration_ms / 1000).toFixed(2)}s` : '--';
    if (inputTokensEl) inputTokensEl.textContent = (stats.total_input_tokens || 0).toLocaleString();
    if (outputTokensEl) outputTokensEl.textContent = (stats.total_output_tokens || 0).toLocaleString();
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

    // 更新列表選中狀態（表格和卡片）
    document.querySelectorAll(`#${windowId} #log-list-body tr`).forEach(row => {
      row.classList.toggle('selected', row.dataset.logId === logId);
    });
    document.querySelectorAll(`#${windowId} .ai-log-card`).forEach(card => {
      card.classList.toggle('selected', card.dataset.logId === logId);
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

    // 判斷是否有執行流程
    const hasFlow = log.parsed_response?.tool_calls?.length > 0;

    detailPanel.style.display = 'flex';

    // 手機版使用 Tab 結構
    if (isMobile()) {
      detailPanel.innerHTML = renderMobileDetailPanel(log, hasFlow);
      bindMobileDetailEvents(detailPanel, log);
    } else {
      // 桌機版使用原本結構
      detailPanel.innerHTML = renderDesktopDetailPanel(log, hasFlow);
      bindDesktopDetailEvents(detailPanel, log);
    }
  }

  /**
   * 渲染手機版詳情面板（Tab 結構）
   */
  function renderMobileDetailPanel(log, hasFlow) {
    const tabs = [];
    const panels = [];

    // Tab 1: System Prompt（如果有）
    if (log.system_prompt) {
      tabs.push(`<button class="ai-log-detail-tab active" data-tab="system">System</button>`);
      panels.push(`
        <div class="ai-log-detail-panel active" data-panel="system">
          <div class="ai-log-detail-section">
            <div class="ai-log-detail-text system-prompt">${escapeHtml(log.system_prompt)}</div>
          </div>
        </div>
      `);
    }

    // Tab 2: 使用者輸入
    const isInputActive = !log.system_prompt;
    tabs.push(`<button class="ai-log-detail-tab ${isInputActive ? 'active' : ''}" data-tab="input">輸入</button>`);
    panels.push(`
      <div class="ai-log-detail-panel ${isInputActive ? 'active' : ''}" data-panel="input">
        <div class="ai-log-detail-section">
          <div class="ai-log-detail-text">${escapeHtml(log.input_prompt)}</div>
        </div>
      </div>
    `);

    // Tab 3: AI 輸出 或 執行流程
    tabs.push(`<button class="ai-log-detail-tab" data-tab="output">${hasFlow ? '流程' : '輸出'}</button>`);
    panels.push(`
      <div class="ai-log-detail-panel" data-panel="output">
        ${hasFlow ? renderExecutionFlow(log) : `
          <div class="ai-log-detail-section">
            <div class="ai-log-detail-text ${log.error_message ? 'error' : ''}">
              ${log.error_message ? escapeHtml(log.error_message) : escapeHtml(log.raw_response || '無回應')}
            </div>
          </div>
        `}
      </div>
    `);

    return `
      <div class="ai-log-detail-header">
        <span class="ai-log-detail-title">Log 詳情</span>
        <button class="ai-log-detail-close">
          <span class="icon">${getIcon('close')}</span>
        </button>
      </div>
      <div class="ai-log-detail-tabs">
        ${tabs.join('')}
      </div>
      <div class="ai-log-detail-content">
        ${panels.join('')}
      </div>
      <div class="ai-log-detail-meta">
        <span>Model: ${log.model || '-'}</span>
        <span>Tokens: ${log.input_tokens || 0}/${log.output_tokens || 0}</span>
        <span>耗時: ${formatDuration(log.duration_ms)}</span>
      </div>
    `;
  }

  /**
   * 綁定手機版詳情面板事件
   */
  function bindMobileDetailEvents(detailPanel, log) {
    // 關閉按鈕
    detailPanel.querySelector('.ai-log-detail-close').addEventListener('click', () => {
      currentLogId = null;
      detailPanel.style.display = 'none';
      document.querySelectorAll(`#${windowId} #log-list-body tr`).forEach(row => {
        row.classList.remove('selected');
      });
      document.querySelectorAll(`#${windowId} .ai-log-card`).forEach(card => {
        card.classList.remove('selected');
      });
    });

    // Tab 切換
    detailPanel.querySelectorAll('.ai-log-detail-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const tabName = tab.dataset.tab;
        // 更新 Tab 狀態
        detailPanel.querySelectorAll('.ai-log-detail-tab').forEach(t => {
          t.classList.toggle('active', t.dataset.tab === tabName);
        });
        // 更新 Panel 狀態
        detailPanel.querySelectorAll('.ai-log-detail-panel').forEach(p => {
          p.classList.toggle('active', p.dataset.panel === tabName);
        });
      });
    });
  }

  /**
   * 渲染桌機版詳情面板
   */
  function renderDesktopDetailPanel(log, hasFlow) {
    return `
      <div class="ai-log-detail-resizer" title="拖曳調整高度"></div>
      <div class="ai-log-detail-header">
        <span class="ai-log-detail-title">Log 詳情</span>
        <div style="display: flex; align-items: center; gap: 8px;">
          <button class="ai-log-copy-full-btn" data-copy="full-request" title="複製完整請求（含 System Prompt、Tools、Messages）">
            <span class="icon">${getIcon('copy')}</span>
            複製完整請求
          </button>
          <button class="ai-log-detail-close">
            <span class="icon">${getIcon('close')}</span>
          </button>
        </div>
      </div>
      <div class="ai-log-detail-content">
        ${log.system_prompt ? `
          <div class="ai-log-detail-section">
            <div class="ai-log-detail-section-title">
              System Prompt
              <button class="ai-log-copy-btn" data-copy="system-prompt" title="複製 System Prompt">
                <span class="icon">${getIcon('copy')}</span>
              </button>
            </div>
            <div class="ai-log-detail-text system-prompt">${escapeHtml(log.system_prompt)}</div>
          </div>
        ` : ''}
        <div class="ai-log-detail-section">
          <div class="ai-log-detail-section-title">使用者輸入</div>
          <div class="ai-log-detail-text">${escapeHtml(log.input_prompt)}</div>
        </div>
        ${hasFlow ? renderExecutionFlow(log) : `
          <div class="ai-log-detail-section">
            <div class="ai-log-detail-section-title">AI 輸出</div>
            <div class="ai-log-detail-text ${log.error_message ? 'error' : ''}">
              ${log.error_message ? escapeHtml(log.error_message) : escapeHtml(log.raw_response || '無回應')}
            </div>
          </div>
        `}
      </div>
      <div class="ai-log-detail-meta">
        <span>Model: ${log.model || '-'}</span>
        <span>輸入 Tokens: ${log.input_tokens || '-'}</span>
        <span>輸出 Tokens: ${log.output_tokens || '-'}</span>
        <span>耗時: ${formatDuration(log.duration_ms)}</span>
      </div>
    `;
  }

  /**
   * 綁定桌機版詳情面板事件
   */
  function bindDesktopDetailEvents(detailPanel, log) {

    // 關閉按鈕
    detailPanel.querySelector('.ai-log-detail-close').addEventListener('click', () => {
      currentLogId = null;
      detailPanel.style.display = 'none';
      document.querySelectorAll(`#${windowId} #log-list-body tr`).forEach(row => {
        row.classList.remove('selected');
      });
    });

    // 複製 System Prompt 按鈕
    const copyBtn = detailPanel.querySelector('.ai-log-copy-btn[data-copy="system-prompt"]');
    if (copyBtn) {
      copyBtn.addEventListener('click', async () => {
        await copyToClipboard(log.system_prompt, copyBtn);
      });
    }

    // 複製完整請求按鈕
    const copyFullBtn = detailPanel.querySelector('.ai-log-copy-full-btn[data-copy="full-request"]');
    if (copyFullBtn) {
      copyFullBtn.addEventListener('click', async () => {
        const fullRequest = buildFullRequest(log);
        await copyToClipboard(fullRequest, copyFullBtn);
      });
    }

    // 拖曳調整高度
    const resizer = detailPanel.querySelector('.ai-log-detail-resizer');
    let isResizing = false;
    let startY = 0;
    let startHeight = 0;

    resizer.addEventListener('mousedown', (e) => {
      isResizing = true;
      startY = e.clientY;
      startHeight = detailPanel.offsetHeight;
      document.body.style.cursor = 'ns-resize';
      document.body.style.userSelect = 'none';
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!isResizing) return;
      // 往上拖 = 增加高度（因為面板在底部）
      const deltaY = startY - e.clientY;
      const newHeight = Math.max(200, Math.min(startHeight + deltaY, window.innerHeight * 0.7));
      detailPanel.style.height = `${newHeight}px`;
    });

    document.addEventListener('mouseup', () => {
      if (isResizing) {
        isResizing = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
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
   * 渲染 Tools 標籤
   * @param {string[]|null} allowedTools - 允許使用的工具
   * @param {string[]|null} usedTools - 實際使用的工具
   */
  function renderToolsBadges(allowedTools, usedTools) {
    if (!allowedTools || allowedTools.length === 0) {
      return '<span class="ai-log-no-tools">-</span>';
    }

    const usedSet = new Set(usedTools || []);

    return allowedTools.map(tool => {
      const isUsed = usedSet.has(tool);
      const className = isUsed ? 'ai-log-tool-badge used' : 'ai-log-tool-badge';
      return `<span class="${className}" title="${tool}">${tool}</span>`;
    }).join('');
  }

  /**
   * 複製文字到剪貼簿
   * @param {string} text - 要複製的文字
   * @param {HTMLElement} btn - 按鈕元素（用於顯示成功狀態）
   */
  async function copyToClipboard(text, btn) {
    try {
      // 使用 fallback 方案支援非 HTTPS 環境
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        // fallback: 使用 textarea + execCommand
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      // 顯示複製成功提示
      const originalTitle = btn.title;
      btn.title = '已複製！';
      btn.classList.add('copied');
      setTimeout(() => {
        btn.title = originalTitle;
        btn.classList.remove('copied');
      }, 2000);
    } catch (e) {
      console.error('[AILog] Failed to copy:', e);
    }
  }

  /**
   * 建立完整請求文字（用於複製）
   * @param {Object} log - Log 物件
   * @returns {string} 完整請求文字
   */
  function buildFullRequest(log) {
    const parts = [];

    // System Prompt
    if (log.system_prompt) {
      parts.push('=== System Prompt ===');
      parts.push(log.system_prompt);
      parts.push('');
    }

    // Allowed Tools
    if (log.allowed_tools && log.allowed_tools.length > 0) {
      parts.push('=== Allowed Tools ===');
      parts.push(log.allowed_tools.join(', '));
      parts.push('');
    }

    // Messages (完整輸入)
    parts.push('=== Messages ===');
    parts.push(log.input_prompt || '');

    return parts.join('\n');
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
   * 格式化 JSON 為可讀格式
   */
  function formatJson(obj) {
    if (obj === null || obj === undefined) {
      return '<span style="color: var(--text-muted)">(無資料)</span>';
    }
    if (typeof obj === 'string') {
      // 如果是長字串，直接顯示（不嘗試 JSON 解析）
      if (obj.length > 500) {
        return escapeHtml(obj);
      }
      try {
        obj = JSON.parse(obj);
      } catch (e) {
        return escapeHtml(obj);
      }
    }
    return escapeHtml(JSON.stringify(obj, null, 2));
  }

  /**
   * 渲染執行流程區塊
   */
  function renderExecutionFlow(log) {
    const toolCalls = log.parsed_response?.tool_calls;
    if (!toolCalls || toolCalls.length === 0) {
      return '';
    }

    // 建立 tool timing 查詢表（依照順序對應）
    const toolTimings = log.parsed_response?.tool_timings || [];

    const toolItems = toolCalls.map((tc, index) => {
      // 從 timings 陣列中取得對應的時間（按順序對應）
      const timing = toolTimings[index];
      const durationText = timing?.duration_ms
        ? `<span class="ai-log-flow-duration">${formatDuration(timing.duration_ms)}</span>`
        : '';

      return `
        <div class="ai-log-flow-item" data-expanded="false">
          <div class="ai-log-flow-header" onclick="this.parentElement.dataset.expanded = this.parentElement.dataset.expanded === 'true' ? 'false' : 'true'">
            <span class="ai-log-flow-number">${index + 1}</span>
            <span class="ai-log-flow-icon">${getIcon('wrench')}</span>
            <span class="ai-log-flow-name">${escapeHtml(tc.name)}</span>
            ${durationText}
            <span class="ai-log-flow-toggle">${getIcon('chevron-down')}</span>
          </div>
          <div class="ai-log-flow-body">
            <div class="ai-log-flow-section">
              <div class="ai-log-flow-section-label">輸入</div>
              <pre class="ai-log-flow-code">${formatJson(tc.input)}</pre>
            </div>
            <div class="ai-log-flow-section">
              <div class="ai-log-flow-section-label">輸出</div>
              <pre class="ai-log-flow-code">${formatJson(tc.output)}</pre>
            </div>
          </div>
        </div>
      `;
    }).join('');

    // 最終回應
    const finalResponse = `
      <div class="ai-log-flow-item ai-log-flow-final" data-expanded="true">
        <div class="ai-log-flow-header">
          <span class="ai-log-flow-number">${toolCalls.length + 1}</span>
          <span class="ai-log-flow-icon">${getIcon('chat')}</span>
          <span class="ai-log-flow-name">最終回應</span>
        </div>
        <div class="ai-log-flow-body">
          <div class="ai-log-flow-response">${escapeHtml(log.raw_response || '')}</div>
        </div>
      </div>
    `;

    return `
      <div class="ai-log-detail-section">
        <div class="ai-log-detail-section-title">
          <span class="icon">${getIcon('list-status')}</span>
          執行流程
        </div>
        <div class="ai-log-flow">
          ${toolItems}
          ${finalResponse}
        </div>
      </div>
    `;
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
    // 加上時區偏移，確保篩選範圍對應本地時間
    const tzOffset = new Date().getTimezoneOffset();
    const tzSign = tzOffset <= 0 ? '+' : '-';
    const tzHours = String(Math.floor(Math.abs(tzOffset) / 60)).padStart(2, '0');
    const tzMins = String(Math.abs(tzOffset) % 60).padStart(2, '0');
    const tzSuffix = `${tzSign}${tzHours}:${tzMins}`;
    filters.start_date = getTodayString() + 'T00:00:00' + tzSuffix;

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
    // 篩選器切換按鈕（手機版）
    const filterToggle = document.querySelector(`#${windowId} .ai-log-filter-toggle`);
    const filtersContainer = document.querySelector(`#${windowId} .ai-log-filters`);
    if (filterToggle && filtersContainer) {
      filterToggle.addEventListener('click', () => {
        filtersContainer.classList.toggle('expanded');
      });
    }

    // 過濾器變更
    document.querySelectorAll(`#${windowId} [data-filter]`).forEach(el => {
      el.addEventListener('change', () => {
        const filter = el.dataset.filter;
        let value = el.value;

        if (filter === 'success') {
          value = value === '' ? null : value === 'true';
        } else if (filter === 'start_date' || filter === 'end_date') {
          if (value) {
            const tzOffset = new Date().getTimezoneOffset();
            const tzSign = tzOffset <= 0 ? '+' : '-';
            const tzHours = String(Math.floor(Math.abs(tzOffset) / 60)).padStart(2, '0');
            const tzMins = String(Math.abs(tzOffset) % 60).padStart(2, '0');
            const tzSuffix = `${tzSign}${tzHours}:${tzMins}`;
            value = value + (filter === 'start_date' ? 'T00:00:00' : 'T23:59:59') + tzSuffix;
          } else {
            value = null;
          }
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
