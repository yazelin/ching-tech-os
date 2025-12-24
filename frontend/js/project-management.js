/**
 * ChingTech OS - Project Management Module
 * Provides project management with members, meetings, attachments, and links
 */

const ProjectManagementModule = (function() {
  'use strict';

  const API_BASE = '/api/projects';

  // State
  let windowId = null;
  let projectList = [];
  let selectedProject = null;
  let currentTab = 'overview';
  let isEditing = false;
  let editingData = null;
  let listWidth = 280;

  // Filters
  let searchQuery = '';
  let filterStatus = '';

  /**
   * Make API request
   */
  async function apiRequest(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    if (response.status === 204) return null;
    return response.json();
  }

  /**
   * Open project management window
   */
  function open() {
    const existing = WindowModule.getWindowByAppId('project-management');
    if (existing) {
      WindowModule.focusWindow(existing.windowId);
      if (!existing.minimized) return;
      WindowModule.restoreWindow(existing.windowId);
      return;
    }

    windowId = WindowModule.createWindow({
      title: '專案管理',
      appId: 'project-management',
      icon: 'briefcase',
      width: 1100,
      height: 750,
      content: renderContent(),
      onClose: handleClose,
      onInit: handleInit,
    });
  }

  /**
   * Close window
   */
  function close() {
    if (windowId) {
      WindowModule.closeWindow(windowId);
    }
  }

  /**
   * Handle window close
   */
  function handleClose() {
    windowId = null;
    projectList = [];
    selectedProject = null;
    currentTab = 'overview';
    isEditing = false;
    editingData = null;
  }

  /**
   * Handle window init
   */
  function handleInit(windowEl, wId) {
    windowId = wId;
    bindEvents(windowEl);
    loadProjects();
  }

  /**
   * Render main content
   */
  function renderContent() {
    return `
      <div class="pm-container">
        <div class="pm-toolbar">
          <div class="pm-search-container">
            <span class="pm-search-icon">
              <span class="icon">${getIcon('search')}</span>
            </span>
            <input type="text" class="pm-search-input" id="pmSearchInput" placeholder="搜尋專案...">
            <button class="pm-search-clear" id="pmSearchClear" style="display: none;">
              <span class="icon">${getIcon('close')}</span>
            </button>
          </div>
          <div class="pm-filters">
            <select class="pm-filter-select" id="pmFilterStatus">
              <option value="">所有狀態</option>
              <option value="active">進行中</option>
              <option value="completed">已完成</option>
              <option value="on_hold">暫停</option>
              <option value="cancelled">已取消</option>
            </select>
          </div>
          <div class="pm-toolbar-actions">
            <button class="pm-action-btn" id="pmBtnRefresh" title="重新載入">
              <span class="icon">${getIcon('refresh')}</span>
            </button>
            <button class="pm-action-btn primary" id="pmBtnNew" title="新增專案">
              <span class="icon">${getIcon('plus')}</span>
              <span>新增</span>
            </button>
          </div>
        </div>

        <div class="pm-main">
          <div class="pm-list-panel" id="pmListPanel">
            <div class="pm-list-header">
              <span>專案列表</span>
              <span class="pm-list-count" id="pmListCount">0 個</span>
            </div>
            <div class="pm-list" id="pmList">
              <div class="pm-loading">
                <span class="icon spinning">${getIcon('refresh')}</span>
                <span>載入中...</span>
              </div>
            </div>
          </div>

          <div class="pm-resizer" id="pmResizer"></div>

          <div class="pm-content-panel" id="pmContentPanel">
            <div class="pm-content-empty" id="pmContentEmpty">
              <span class="icon">${getIcon('briefcase')}</span>
              <p>選擇一個專案來查看詳情</p>
              <p>或點擊「新增」建立新專案</p>
            </div>
            <div class="pm-content-view" id="pmContentView" style="display: none;"></div>
            <div class="pm-editor" id="pmEditor" style="display: none;"></div>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Bind events
   */
  function bindEvents(windowEl) {
    // Search
    const searchInput = windowEl.querySelector('#pmSearchInput');
    const searchClear = windowEl.querySelector('#pmSearchClear');
    let searchTimer = null;

    searchInput.addEventListener('input', () => {
      searchClear.style.display = searchInput.value ? 'flex' : 'none';
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        searchQuery = searchInput.value;
        loadProjects();
      }, 300);
    });

    searchClear.addEventListener('click', () => {
      searchInput.value = '';
      searchClear.style.display = 'none';
      searchQuery = '';
      loadProjects();
    });

    // Status filter
    windowEl.querySelector('#pmFilterStatus').addEventListener('change', (e) => {
      filterStatus = e.target.value;
      loadProjects();
    });

    // Actions
    windowEl.querySelector('#pmBtnRefresh').addEventListener('click', () => loadProjects());
    windowEl.querySelector('#pmBtnNew').addEventListener('click', () => startNewProject());

    // Resizer
    const resizer = windowEl.querySelector('#pmResizer');
    const listPanel = windowEl.querySelector('#pmListPanel');
    let isResizing = false;

    resizer.addEventListener('mousedown', () => {
      isResizing = true;
      resizer.classList.add('dragging');
      document.addEventListener('mousemove', handleResize);
      document.addEventListener('mouseup', stopResize);
    });

    function handleResize(e) {
      if (!isResizing) return;
      const rect = windowEl.querySelector('.pm-main').getBoundingClientRect();
      const newWidth = Math.max(220, Math.min(e.clientX - rect.left, rect.width * 0.4));
      listPanel.style.width = newWidth + 'px';
      listWidth = newWidth;
    }

    function stopResize() {
      isResizing = false;
      resizer.classList.remove('dragging');
      document.removeEventListener('mousemove', handleResize);
      document.removeEventListener('mouseup', stopResize);
    }
  }

  /**
   * Load projects
   */
  async function loadProjects() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const listEl = windowEl.querySelector('#pmList');
    listEl.innerHTML = `
      <div class="pm-loading">
        <span class="icon spinning">${getIcon('refresh')}</span>
        <span>載入中...</span>
      </div>
    `;

    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append('q', searchQuery);
      if (filterStatus) params.append('status', filterStatus);

      const result = await apiRequest(`?${params.toString()}`);
      projectList = result.items;
      renderProjectList(windowEl);
    } catch (error) {
      console.error('Failed to load projects:', error);
      listEl.innerHTML = `
        <div class="pm-empty">
          <span class="icon">${getIcon('alert-circle')}</span>
          <span>載入失敗: ${error.message}</span>
        </div>
      `;
    }
  }

  /**
   * Render project list
   */
  function renderProjectList(windowEl) {
    const listEl = windowEl.querySelector('#pmList');
    const countEl = windowEl.querySelector('#pmListCount');

    countEl.textContent = `${projectList.length} 個`;

    if (projectList.length === 0) {
      listEl.innerHTML = `
        <div class="pm-empty">
          <span class="icon">${getIcon('briefcase')}</span>
          <span>沒有找到專案</span>
        </div>
      `;
      return;
    }

    listEl.innerHTML = projectList.map(item => `
      <div class="pm-list-item ${selectedProject?.id === item.id ? 'selected' : ''}"
           data-id="${item.id}">
        <div class="pm-list-item-header">
          <span class="pm-list-item-name">${item.name}</span>
          <span class="pm-status-badge ${item.status}">${getStatusText(item.status)}</span>
        </div>
        <div class="pm-list-item-meta">
          <span>${item.member_count} 成員</span>
          <span>${item.meeting_count} 會議</span>
          <span>${item.attachment_count} 附件</span>
        </div>
        <div class="pm-list-item-date">
          ${formatDate(item.updated_at)}
        </div>
      </div>
    `).join('');

    // Bind click events
    listEl.querySelectorAll('.pm-list-item').forEach(el => {
      el.addEventListener('click', () => selectProject(el.dataset.id));
    });
  }

  /**
   * Get status text
   */
  function getStatusText(status) {
    const map = {
      active: '進行中',
      completed: '已完成',
      on_hold: '暫停',
      cancelled: '已取消',
    };
    return map[status] || status;
  }

  /**
   * Get milestone type text
   */
  function getMilestoneTypeText(type) {
    const map = {
      design: '設計',
      manufacture: '製造',
      delivery: '交機',
      field_test: '場測',
      acceptance: '驗收',
      custom: '自訂',
    };
    return map[type] || type;
  }

  /**
   * Get milestone status text
   */
  function getMilestoneStatusText(status) {
    const map = {
      pending: '待進行',
      in_progress: '進行中',
      completed: '已完成',
      delayed: '延遲',
    };
    return map[status] || status;
  }

  /**
   * Format date
   */
  function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-TW');
  }

  /**
   * Select project
   */
  async function selectProject(id) {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    try {
      selectedProject = await apiRequest(`/${id}`);
      isEditing = false;
      currentTab = 'overview';
      renderContentView(windowEl);

      // Update list selection
      windowEl.querySelectorAll('.pm-list-item').forEach(el => {
        el.classList.toggle('selected', el.dataset.id === id);
      });
    } catch (error) {
      console.error('Failed to load project:', error);
      NotificationModule.show({ title: '載入失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  /**
   * Render content view
   */
  function renderContentView(windowEl) {
    const emptyEl = windowEl.querySelector('#pmContentEmpty');
    const viewEl = windowEl.querySelector('#pmContentView');
    const editorEl = windowEl.querySelector('#pmEditor');

    emptyEl.style.display = 'none';
    editorEl.style.display = 'none';
    viewEl.style.display = 'flex';

    const p = selectedProject;
    viewEl.innerHTML = `
      <div class="pm-content-header">
        <div class="pm-content-title-section">
          <h2 class="pm-content-title">${p.name}</h2>
          <span class="pm-status-badge large ${p.status}">${getStatusText(p.status)}</span>
        </div>
        <div class="pm-content-actions">
          <button class="pm-action-btn" id="pmBtnEdit" title="編輯">
            <span class="icon">${getIcon('edit')}</span>
          </button>
          <button class="pm-action-btn danger" id="pmBtnDelete" title="刪除">
            <span class="icon">${getIcon('delete')}</span>
          </button>
        </div>
      </div>

      <div class="pm-tabs">
        <button class="pm-tab ${currentTab === 'overview' ? 'active' : ''}" data-tab="overview">
          <span class="icon">${getIcon('information')}</span>
          概覽
        </button>
        <button class="pm-tab ${currentTab === 'members' ? 'active' : ''}" data-tab="members">
          <span class="icon">${getIcon('account-group')}</span>
          成員 (${p.members.length})
        </button>
        <button class="pm-tab ${currentTab === 'meetings' ? 'active' : ''}" data-tab="meetings">
          <span class="icon">${getIcon('calendar')}</span>
          會議 (${p.meetings.length})
        </button>
        <button class="pm-tab ${currentTab === 'attachments' ? 'active' : ''}" data-tab="attachments">
          <span class="icon">${getIcon('attachment')}</span>
          附件 (${p.attachments.length})
        </button>
        <button class="pm-tab ${currentTab === 'links' ? 'active' : ''}" data-tab="links">
          <span class="icon">${getIcon('link')}</span>
          連結 (${p.links.length})
        </button>
      </div>

      <div class="pm-tab-content" id="pmTabContent"></div>
    `;

    // Bind events
    viewEl.querySelector('#pmBtnEdit').addEventListener('click', () => startEditProject());
    viewEl.querySelector('#pmBtnDelete').addEventListener('click', () => confirmDeleteProject());

    viewEl.querySelectorAll('.pm-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        currentTab = tab.dataset.tab;
        renderContentView(windowEl);
      });
    });

    // Render tab content
    renderTabContent(viewEl);
  }

  /**
   * Render tab content
   */
  function renderTabContent(viewEl) {
    const contentEl = viewEl.querySelector('#pmTabContent');
    const p = selectedProject;

    switch (currentTab) {
      case 'overview':
        contentEl.innerHTML = `
          <div class="pm-overview">
            <div class="pm-info-section">
              <h3>專案資訊</h3>
              <div class="pm-info-grid">
                <div class="pm-info-item">
                  <label>開始日期</label>
                  <span>${p.start_date || '未設定'}</span>
                </div>
                <div class="pm-info-item">
                  <label>結束日期</label>
                  <span>${p.end_date || '未設定'}</span>
                </div>
                <div class="pm-info-item">
                  <label>建立時間</label>
                  <span>${formatDate(p.created_at)}</span>
                </div>
                <div class="pm-info-item">
                  <label>更新時間</label>
                  <span>${formatDate(p.updated_at)}</span>
                </div>
              </div>
            </div>
            <div class="pm-info-section">
              <h3>專案描述</h3>
              <div class="pm-description">${p.description || '無描述'}</div>
            </div>
            <div class="pm-milestones-section" id="pmMilestonesSection"></div>
          </div>
        `;
        renderMilestonesSection(contentEl.querySelector('#pmMilestonesSection'));
        break;

      case 'members':
        renderMembersTab(contentEl);
        break;

      case 'meetings':
        renderMeetingsTab(contentEl);
        break;

      case 'attachments':
        renderAttachmentsTab(contentEl);
        break;

      case 'links':
        renderLinksTab(contentEl);
        break;
    }
  }

  // ============================================
  // Members Tab
  // ============================================

  function renderMembersTab(contentEl) {
    const members = selectedProject.members;

    contentEl.innerHTML = `
      <div class="pm-tab-header">
        <h3>專案成員</h3>
        <button class="pm-action-btn primary" id="pmBtnAddMember">
          <span class="icon">${getIcon('plus')}</span>
          新增成員
        </button>
      </div>
      <div class="pm-members-list">
        ${members.length === 0 ? '<div class="pm-empty-tab">尚無成員</div>' : members.map(m => `
          <div class="pm-member-card" data-id="${m.id}">
            <div class="pm-member-avatar">
              <span class="icon">${getIcon('account')}</span>
            </div>
            <div class="pm-member-info">
              <div class="pm-member-name">${m.name}</div>
              <div class="pm-member-role">${m.role || '未指定角色'}</div>
              ${m.company ? `<div class="pm-member-company">${m.company}</div>` : ''}
              <div class="pm-member-contact">
                ${m.email ? `<span><span class="icon">${getIcon('email')}</span>${m.email}</span>` : ''}
                ${m.phone ? `<span><span class="icon">${getIcon('phone')}</span>${m.phone}</span>` : ''}
              </div>
            </div>
            <div class="pm-member-badge ${m.is_internal ? 'internal' : 'external'}">
              ${m.is_internal ? '內部' : '外部'}
            </div>
            <div class="pm-member-actions">
              <button class="pm-icon-btn" data-action="edit" title="編輯">
                <span class="icon">${getIcon('edit')}</span>
              </button>
              <button class="pm-icon-btn danger" data-action="delete" title="刪除">
                <span class="icon">${getIcon('delete')}</span>
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    `;

    // Bind events
    contentEl.querySelector('#pmBtnAddMember')?.addEventListener('click', () => showMemberModal());
    contentEl.querySelectorAll('.pm-member-card').forEach(card => {
      card.querySelectorAll('.pm-icon-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const memberId = card.dataset.id;
          const member = selectedProject.members.find(m => m.id === memberId);
          if (btn.dataset.action === 'edit') showMemberModal(member);
          else if (btn.dataset.action === 'delete') confirmDeleteMember(memberId);
        });
      });
    });
  }

  function showMemberModal(member = null) {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const isEdit = !!member;
    const modal = document.createElement('div');
    modal.className = 'pm-modal';
    modal.innerHTML = `
      <div class="pm-modal-content">
        <div class="pm-modal-header">
          <h3>${isEdit ? '編輯成員' : '新增成員'}</h3>
          <button class="pm-modal-close"><span class="icon">${getIcon('close')}</span></button>
        </div>
        <div class="pm-modal-body">
          <div class="pm-form-group">
            <label>姓名 *</label>
            <input type="text" id="memberName" value="${member?.name || ''}" required>
          </div>
          <div class="pm-form-group">
            <label>角色</label>
            <input type="text" id="memberRole" value="${member?.role || ''}" placeholder="例如：PM、工程師、客戶">
          </div>
          <div class="pm-form-group">
            <label>公司</label>
            <input type="text" id="memberCompany" value="${member?.company || ''}">
          </div>
          <div class="pm-form-row">
            <div class="pm-form-group">
              <label>Email</label>
              <input type="email" id="memberEmail" value="${member?.email || ''}">
            </div>
            <div class="pm-form-group">
              <label>電話</label>
              <input type="tel" id="memberPhone" value="${member?.phone || ''}">
            </div>
          </div>
          <div class="pm-form-group">
            <label>備註</label>
            <textarea id="memberNotes" rows="2">${member?.notes || ''}</textarea>
          </div>
          <div class="pm-form-group">
            <label class="pm-checkbox">
              <input type="checkbox" id="memberInternal" ${member?.is_internal !== false ? 'checked' : ''}>
              <span>內部人員</span>
            </label>
          </div>
        </div>
        <div class="pm-modal-footer">
          <button class="pm-btn" id="memberCancel">取消</button>
          <button class="pm-btn primary" id="memberSave">${isEdit ? '儲存' : '新增'}</button>
        </div>
      </div>
    `;

    windowEl.appendChild(modal);

    const closeModal = () => modal.remove();
    modal.querySelector('.pm-modal-close').addEventListener('click', closeModal);
    modal.querySelector('#memberCancel').addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

    modal.querySelector('#memberSave').addEventListener('click', async () => {
      const data = {
        name: modal.querySelector('#memberName').value.trim(),
        role: modal.querySelector('#memberRole').value.trim() || null,
        company: modal.querySelector('#memberCompany').value.trim() || null,
        email: modal.querySelector('#memberEmail').value.trim() || null,
        phone: modal.querySelector('#memberPhone').value.trim() || null,
        notes: modal.querySelector('#memberNotes').value.trim() || null,
        is_internal: modal.querySelector('#memberInternal').checked,
      };

      if (!data.name) {
        NotificationModule.show({ title: '提醒', message: '請輸入姓名', icon: 'alert' });
        return;
      }

      try {
        if (isEdit) {
          await apiRequest(`/${selectedProject.id}/members/${member.id}`, {
            method: 'PUT',
            body: JSON.stringify(data),
          });
        } else {
          await apiRequest(`/${selectedProject.id}/members`, {
            method: 'POST',
            body: JSON.stringify(data),
          });
        }
        closeModal();
        await selectProject(selectedProject.id);
        NotificationModule.show({ title: '成功', message: isEdit ? '成員已更新' : '成員已新增', icon: 'check-circle' });
      } catch (error) {
        NotificationModule.show({ title: '失敗', message: error.message, icon: 'alert-circle' });
      }
    });
  }

  async function confirmDeleteMember(memberId) {
    if (!confirm('確定要刪除此成員嗎？')) return;
    try {
      await apiRequest(`/${selectedProject.id}/members/${memberId}`, { method: 'DELETE' });
      await selectProject(selectedProject.id);
      NotificationModule.show({ title: '成功', message: '成員已刪除', icon: 'check-circle' });
    } catch (error) {
      NotificationModule.show({ title: '失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  // ============================================
  // Meetings Tab
  // ============================================

  function renderMeetingsTab(contentEl) {
    const meetings = selectedProject.meetings;

    contentEl.innerHTML = `
      <div class="pm-tab-header">
        <h3>會議記錄</h3>
        <button class="pm-action-btn primary" id="pmBtnAddMeeting">
          <span class="icon">${getIcon('plus')}</span>
          新增會議
        </button>
      </div>
      <div class="pm-meetings-list">
        ${meetings.length === 0 ? '<div class="pm-empty-tab">尚無會議記錄</div>' : meetings.map(m => `
          <div class="pm-meeting-card" data-id="${m.id}">
            <div class="pm-meeting-date">
              <div class="pm-meeting-day">${new Date(m.meeting_date).getDate()}</div>
              <div class="pm-meeting-month">${new Date(m.meeting_date).toLocaleDateString('zh-TW', { month: 'short' })}</div>
            </div>
            <div class="pm-meeting-info">
              <div class="pm-meeting-title">${m.title}</div>
              <div class="pm-meeting-meta">
                ${m.location ? `<span><span class="icon">${getIcon('map-marker')}</span>${m.location}</span>` : ''}
                <span><span class="icon">${getIcon('account-group')}</span>${m.attendees?.length || 0} 人</span>
              </div>
            </div>
            <div class="pm-meeting-actions">
              <button class="pm-icon-btn" data-action="view" title="查看">
                <span class="icon">${getIcon('eye')}</span>
              </button>
              <button class="pm-icon-btn" data-action="edit" title="編輯">
                <span class="icon">${getIcon('edit')}</span>
              </button>
              <button class="pm-icon-btn danger" data-action="delete" title="刪除">
                <span class="icon">${getIcon('delete')}</span>
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    `;

    // Bind events
    contentEl.querySelector('#pmBtnAddMeeting')?.addEventListener('click', () => showMeetingModal());
    contentEl.querySelectorAll('.pm-meeting-card').forEach(card => {
      card.querySelectorAll('.pm-icon-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const meetingId = card.dataset.id;
          if (btn.dataset.action === 'view') await showMeetingDetail(meetingId);
          else if (btn.dataset.action === 'edit') await showMeetingModal(meetingId);
          else if (btn.dataset.action === 'delete') await confirmDeleteMeeting(meetingId);
        });
      });
    });
  }

  async function showMeetingDetail(meetingId) {
    try {
      const meeting = await apiRequest(`/${selectedProject.id}/meetings/${meetingId}`);
      const windowEl = document.getElementById(windowId);
      if (!windowEl) return;

      const modal = document.createElement('div');
      modal.className = 'pm-modal';
      modal.innerHTML = `
        <div class="pm-modal-content large">
          <div class="pm-modal-header">
            <h3>${meeting.title}</h3>
            <button class="pm-modal-close"><span class="icon">${getIcon('close')}</span></button>
          </div>
          <div class="pm-modal-body">
            <div class="pm-meeting-detail-meta">
              <span><span class="icon">${getIcon('calendar')}</span>${new Date(meeting.meeting_date).toLocaleString('zh-TW')}</span>
              ${meeting.location ? `<span><span class="icon">${getIcon('map-marker')}</span>${meeting.location}</span>` : ''}
            </div>
            ${meeting.attendees?.length ? `
              <div class="pm-meeting-attendees">
                <strong>參與人員：</strong> ${meeting.attendees.join('、')}
              </div>
            ` : ''}
            <div class="pm-meeting-content">
              ${meeting.content ? (typeof marked !== 'undefined' ? marked.parse(meeting.content) : `<pre>${meeting.content}</pre>`) : '<p>無會議內容</p>'}
            </div>
          </div>
        </div>
      `;

      windowEl.appendChild(modal);
      const closeModal = () => modal.remove();
      modal.querySelector('.pm-modal-close').addEventListener('click', closeModal);
      modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });
    } catch (error) {
      NotificationModule.show({ title: '載入失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  async function showMeetingModal(meetingId = null) {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    let meeting = null;
    if (meetingId) {
      try {
        meeting = await apiRequest(`/${selectedProject.id}/meetings/${meetingId}`);
      } catch (error) {
        NotificationModule.show({ title: '載入失敗', message: error.message, icon: 'alert-circle' });
        return;
      }
    }

    const isEdit = !!meeting;
    const modal = document.createElement('div');
    modal.className = 'pm-modal';
    modal.innerHTML = `
      <div class="pm-modal-content large">
        <div class="pm-modal-header">
          <h3>${isEdit ? '編輯會議' : '新增會議'}</h3>
          <button class="pm-modal-close"><span class="icon">${getIcon('close')}</span></button>
        </div>
        <div class="pm-modal-body">
          <div class="pm-form-group">
            <label>會議標題 *</label>
            <input type="text" id="meetingTitle" value="${meeting?.title || ''}" required>
          </div>
          <div class="pm-form-row">
            <div class="pm-form-group">
              <label>日期時間 *</label>
              <input type="datetime-local" id="meetingDate" value="${meeting ? new Date(meeting.meeting_date).toISOString().slice(0, 16) : ''}" required>
            </div>
            <div class="pm-form-group">
              <label>地點</label>
              <input type="text" id="meetingLocation" value="${meeting?.location || ''}">
            </div>
          </div>
          <div class="pm-form-group">
            <label>參與人員（以逗號分隔）</label>
            <input type="text" id="meetingAttendees" value="${meeting?.attendees?.join(', ') || ''}" placeholder="例如：張三, 李四, 王五">
          </div>
          <div class="pm-form-group">
            <label>會議內容（支援 Markdown）</label>
            <textarea id="meetingContent" rows="10">${meeting?.content || ''}</textarea>
          </div>
        </div>
        <div class="pm-modal-footer">
          <button class="pm-btn" id="meetingCancel">取消</button>
          <button class="pm-btn primary" id="meetingSave">${isEdit ? '儲存' : '新增'}</button>
        </div>
      </div>
    `;

    windowEl.appendChild(modal);

    const closeModal = () => modal.remove();
    modal.querySelector('.pm-modal-close').addEventListener('click', closeModal);
    modal.querySelector('#meetingCancel').addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

    modal.querySelector('#meetingSave').addEventListener('click', async () => {
      const title = modal.querySelector('#meetingTitle').value.trim();
      const dateValue = modal.querySelector('#meetingDate').value;
      const attendeesValue = modal.querySelector('#meetingAttendees').value;

      if (!title || !dateValue) {
        NotificationModule.show({ title: '提醒', message: '請填寫標題和日期', icon: 'alert' });
        return;
      }

      const data = {
        title,
        meeting_date: new Date(dateValue).toISOString(),
        location: modal.querySelector('#meetingLocation').value.trim() || null,
        attendees: attendeesValue ? attendeesValue.split(',').map(s => s.trim()).filter(Boolean) : [],
        content: modal.querySelector('#meetingContent').value || null,
      };

      try {
        if (isEdit) {
          await apiRequest(`/${selectedProject.id}/meetings/${meeting.id}`, {
            method: 'PUT',
            body: JSON.stringify(data),
          });
        } else {
          await apiRequest(`/${selectedProject.id}/meetings`, {
            method: 'POST',
            body: JSON.stringify(data),
          });
        }
        closeModal();
        await selectProject(selectedProject.id);
        NotificationModule.show({ title: '成功', message: isEdit ? '會議已更新' : '會議已新增', icon: 'check-circle' });
      } catch (error) {
        NotificationModule.show({ title: '失敗', message: error.message, icon: 'alert-circle' });
      }
    });
  }

  async function confirmDeleteMeeting(meetingId) {
    if (!confirm('確定要刪除此會議記錄嗎？')) return;
    try {
      await apiRequest(`/${selectedProject.id}/meetings/${meetingId}`, { method: 'DELETE' });
      await selectProject(selectedProject.id);
      NotificationModule.show({ title: '成功', message: '會議已刪除', icon: 'check-circle' });
    } catch (error) {
      NotificationModule.show({ title: '失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  // ============================================
  // Attachments Tab
  // ============================================

  function renderAttachmentsTab(contentEl) {
    const attachments = selectedProject.attachments;

    contentEl.innerHTML = `
      <div class="pm-tab-header">
        <h3>專案附件</h3>
        <button class="pm-action-btn primary" id="pmBtnUpload">
          <span class="icon">${getIcon('upload')}</span>
          上傳附件
        </button>
      </div>
      <div class="pm-attachments-grid">
        ${attachments.length === 0 ? '<div class="pm-empty-tab">尚無附件</div>' : attachments.map(a => `
          <div class="pm-attachment-card" data-id="${a.id}">
            <div class="pm-attachment-icon ${a.file_type}">
              <span class="icon">${getIcon(getAttachmentIcon(a.file_type))}</span>
            </div>
            <div class="pm-attachment-info">
              <div class="pm-attachment-name" title="${a.filename}">${a.filename}</div>
              <div class="pm-attachment-meta">
                <span>${formatFileSize(a.file_size)}</span>
                <span class="pm-storage-badge ${a.storage_path.startsWith('nas://') ? 'nas' : 'local'}">
                  ${a.storage_path.startsWith('nas://') ? 'NAS' : '本機'}
                </span>
              </div>
              ${a.description ? `<div class="pm-attachment-desc">${a.description}</div>` : ''}
            </div>
            <div class="pm-attachment-actions">
              <button class="pm-icon-btn" data-action="preview" title="預覽">
                <span class="icon">${getIcon('eye')}</span>
              </button>
              <button class="pm-icon-btn" data-action="download" title="下載">
                <span class="icon">${getIcon('download')}</span>
              </button>
              <button class="pm-icon-btn danger" data-action="delete" title="刪除">
                <span class="icon">${getIcon('delete')}</span>
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    `;

    // Bind events
    contentEl.querySelector('#pmBtnUpload')?.addEventListener('click', () => showUploadModal());
    contentEl.querySelectorAll('.pm-attachment-card').forEach(card => {
      card.querySelectorAll('.pm-icon-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const attId = card.dataset.id;
          if (btn.dataset.action === 'preview') previewAttachment(attId);
          else if (btn.dataset.action === 'download') downloadAttachment(attId);
          else if (btn.dataset.action === 'delete') confirmDeleteAttachment(attId);
        });
      });
    });
  }

  function getAttachmentIcon(fileType) {
    const map = {
      image: 'image',
      pdf: 'file-pdf-box',
      cad: 'ruler-square',
      document: 'file-document',
    };
    return map[fileType] || 'file';
  }

  function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
  }

  function showUploadModal() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const modal = document.createElement('div');
    modal.className = 'pm-modal';
    modal.innerHTML = `
      <div class="pm-modal-content">
        <div class="pm-modal-header">
          <h3>上傳附件</h3>
          <button class="pm-modal-close"><span class="icon">${getIcon('close')}</span></button>
        </div>
        <div class="pm-modal-body">
          <div class="pm-upload-dropzone" id="pmUploadDropzone">
            <span class="icon">${getIcon('upload')}</span>
            <div>拖放檔案至此處</div>
            <div class="pm-upload-hint">或點擊選擇檔案</div>
            <div class="pm-upload-note">小於 1MB 存本機，大於等於 1MB 存 NAS</div>
            <input type="file" id="pmUploadInput" style="display: none;" multiple>
          </div>
          <div class="pm-upload-progress" id="pmUploadProgress" style="display: none;">
            <div class="pm-progress-info">
              <span id="pmUploadFileName">準備上傳...</span>
              <span id="pmUploadPercent">0%</span>
            </div>
            <div class="pm-progress-bar">
              <div class="pm-progress-fill" id="pmUploadFill"></div>
            </div>
          </div>
        </div>
      </div>
    `;

    windowEl.appendChild(modal);

    const closeModal = () => modal.remove();
    modal.querySelector('.pm-modal-close').addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

    const dropzone = modal.querySelector('#pmUploadDropzone');
    const fileInput = modal.querySelector('#pmUploadInput');

    dropzone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        uploadFiles(modal, Array.from(e.target.files));
      }
    });

    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files.length > 0) {
        uploadFiles(modal, Array.from(e.dataTransfer.files));
      }
    });
  }

  async function uploadFiles(modal, files) {
    const dropzone = modal.querySelector('#pmUploadDropzone');
    const progressEl = modal.querySelector('#pmUploadProgress');
    const fillEl = modal.querySelector('#pmUploadFill');
    const percentEl = modal.querySelector('#pmUploadPercent');
    const fileNameEl = modal.querySelector('#pmUploadFileName');

    dropzone.style.display = 'none';
    progressEl.style.display = 'block';

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const progress = Math.round((i / files.length) * 100);
      fillEl.style.width = `${progress}%`;
      percentEl.textContent = `${progress}%`;
      fileNameEl.textContent = `上傳中: ${file.name} (${i + 1}/${files.length})`;

      try {
        const formData = new FormData();
        formData.append('file', file);

        await fetch(`${API_BASE}/${selectedProject.id}/attachments`, {
          method: 'POST',
          body: formData,
        });
      } catch (error) {
        NotificationModule.show({ title: '上傳失敗', message: `${file.name}: ${error.message}`, icon: 'alert-circle' });
      }
    }

    fillEl.style.width = '100%';
    percentEl.textContent = '100%';
    fileNameEl.textContent = '上傳完成！';

    setTimeout(async () => {
      modal.remove();
      await selectProject(selectedProject.id);
      NotificationModule.show({ title: '上傳完成', message: `已上傳 ${files.length} 個檔案`, icon: 'check-circle' });
    }, 500);
  }

  function previewAttachment(attachmentId) {
    const att = selectedProject.attachments.find(a => a.id === attachmentId);
    if (!att) return;

    const basePath = window.API_BASE || '';
    const url = `${basePath}${API_BASE}/${selectedProject.id}/attachments/${attachmentId}/preview`;

    if (att.file_type === 'image') {
      if (typeof ImageViewerModule !== 'undefined') {
        ImageViewerModule.open(url);
      } else {
        window.open(url, '_blank');
      }
    } else if (att.file_type === 'pdf') {
      // TODO: PDF viewer
      window.open(url, '_blank');
    } else {
      window.open(url, '_blank');
    }
  }

  function downloadAttachment(attachmentId) {
    const basePath = window.API_BASE || '';
    window.open(`${basePath}${API_BASE}/${selectedProject.id}/attachments/${attachmentId}/download`, '_blank');
  }

  async function confirmDeleteAttachment(attachmentId) {
    if (!confirm('確定要刪除此附件嗎？')) return;
    try {
      await apiRequest(`/${selectedProject.id}/attachments/${attachmentId}`, { method: 'DELETE' });
      await selectProject(selectedProject.id);
      NotificationModule.show({ title: '成功', message: '附件已刪除', icon: 'check-circle' });
    } catch (error) {
      NotificationModule.show({ title: '失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  // ============================================
  // Links Tab
  // ============================================

  function renderLinksTab(contentEl) {
    const links = selectedProject.links;

    contentEl.innerHTML = `
      <div class="pm-tab-header">
        <h3>專案連結</h3>
        <button class="pm-action-btn primary" id="pmBtnAddLink">
          <span class="icon">${getIcon('plus')}</span>
          新增連結
        </button>
      </div>
      <div class="pm-links-list">
        ${links.length === 0 ? '<div class="pm-empty-tab">尚無連結</div>' : links.map(l => {
          const isNas = l.url.startsWith('/') || l.url.startsWith('nas://');
          return `
            <div class="pm-link-card" data-id="${l.id}" data-url="${l.url}">
              <div class="pm-link-icon ${isNas ? 'nas' : 'external'}">
                <span class="icon">${getIcon(isNas ? 'folder-network' : 'web')}</span>
              </div>
              <div class="pm-link-info">
                <div class="pm-link-title">${l.title}</div>
                <div class="pm-link-url">${l.url}</div>
                ${l.description ? `<div class="pm-link-desc">${l.description}</div>` : ''}
              </div>
              <div class="pm-link-actions">
                <button class="pm-icon-btn" data-action="open" title="開啟">
                  <span class="icon">${getIcon('open-in-new')}</span>
                </button>
                <button class="pm-icon-btn" data-action="edit" title="編輯">
                  <span class="icon">${getIcon('edit')}</span>
                </button>
                <button class="pm-icon-btn danger" data-action="delete" title="刪除">
                  <span class="icon">${getIcon('delete')}</span>
                </button>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;

    // Bind events
    contentEl.querySelector('#pmBtnAddLink')?.addEventListener('click', () => showLinkModal());
    contentEl.querySelectorAll('.pm-link-card').forEach(card => {
      card.querySelectorAll('.pm-icon-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const linkId = card.dataset.id;
          const link = selectedProject.links.find(l => l.id === linkId);
          if (btn.dataset.action === 'open') openLink(card.dataset.url);
          else if (btn.dataset.action === 'edit') showLinkModal(link);
          else if (btn.dataset.action === 'delete') confirmDeleteLink(linkId);
        });
      });

      // Click on card to open link
      card.addEventListener('click', (e) => {
        if (!e.target.closest('.pm-icon-btn')) {
          openLink(card.dataset.url);
        }
      });
    });
  }

  function openLink(url) {
    if (url.startsWith('/') || url.startsWith('nas://')) {
      // NAS link - open file manager
      const path = url.replace('nas://', '/');
      if (typeof FileManagerModule !== 'undefined') {
        FileManagerModule.open(path);
      } else {
        NotificationModule.show({ title: '提示', message: '檔案管理器未載入', icon: 'alert' });
      }
    } else {
      // External link - open in new window
      window.open(url, '_blank');
    }
  }

  function showLinkModal(link = null) {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const isEdit = !!link;
    const modal = document.createElement('div');
    modal.className = 'pm-modal';
    modal.innerHTML = `
      <div class="pm-modal-content">
        <div class="pm-modal-header">
          <h3>${isEdit ? '編輯連結' : '新增連結'}</h3>
          <button class="pm-modal-close"><span class="icon">${getIcon('close')}</span></button>
        </div>
        <div class="pm-modal-body">
          <div class="pm-form-group">
            <label>連結標題 *</label>
            <input type="text" id="linkTitle" value="${link?.title || ''}" required>
          </div>
          <div class="pm-form-group">
            <label>URL / 路徑 *</label>
            <input type="text" id="linkUrl" value="${link?.url || ''}" placeholder="例如：/擎添開發/專案A 或 https://..." required>
            <div class="pm-form-hint">NAS 路徑以 / 開頭，外部連結以 http:// 開頭</div>
          </div>
          <div class="pm-form-group">
            <label>描述</label>
            <textarea id="linkDesc" rows="2">${link?.description || ''}</textarea>
          </div>
        </div>
        <div class="pm-modal-footer">
          <button class="pm-btn" id="linkCancel">取消</button>
          <button class="pm-btn primary" id="linkSave">${isEdit ? '儲存' : '新增'}</button>
        </div>
      </div>
    `;

    windowEl.appendChild(modal);

    const closeModal = () => modal.remove();
    modal.querySelector('.pm-modal-close').addEventListener('click', closeModal);
    modal.querySelector('#linkCancel').addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

    modal.querySelector('#linkSave').addEventListener('click', async () => {
      const data = {
        title: modal.querySelector('#linkTitle').value.trim(),
        url: modal.querySelector('#linkUrl').value.trim(),
        description: modal.querySelector('#linkDesc').value.trim() || null,
      };

      if (!data.title || !data.url) {
        NotificationModule.show({ title: '提醒', message: '請填寫標題和 URL', icon: 'alert' });
        return;
      }

      try {
        if (isEdit) {
          await apiRequest(`/${selectedProject.id}/links/${link.id}`, {
            method: 'PUT',
            body: JSON.stringify(data),
          });
        } else {
          await apiRequest(`/${selectedProject.id}/links`, {
            method: 'POST',
            body: JSON.stringify(data),
          });
        }
        closeModal();
        await selectProject(selectedProject.id);
        NotificationModule.show({ title: '成功', message: isEdit ? '連結已更新' : '連結已新增', icon: 'check-circle' });
      } catch (error) {
        NotificationModule.show({ title: '失敗', message: error.message, icon: 'alert-circle' });
      }
    });
  }

  async function confirmDeleteLink(linkId) {
    if (!confirm('確定要刪除此連結嗎？')) return;
    try {
      await apiRequest(`/${selectedProject.id}/links/${linkId}`, { method: 'DELETE' });
      await selectProject(selectedProject.id);
      NotificationModule.show({ title: '成功', message: '連結已刪除', icon: 'check-circle' });
    } catch (error) {
      NotificationModule.show({ title: '失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  // ============================================
  // Milestones Section
  // ============================================

  function renderMilestonesSection(containerEl) {
    const milestones = selectedProject.milestones || [];

    containerEl.innerHTML = `
      <div class="pm-milestones-header">
        <h3>專案里程碑</h3>
        <button class="pm-action-btn primary" id="pmBtnAddMilestone">
          <span class="icon">${getIcon('plus')}</span>
          新增里程碑
        </button>
      </div>
      ${milestones.length === 0 ? `
        <div class="pm-milestones-empty">
          <span>尚無里程碑，點擊上方按鈕新增</span>
        </div>
      ` : `
        <div class="pm-milestones-timeline">
          ${milestones.map(m => {
            const isOverdue = m.planned_date && !m.actual_date && new Date(m.planned_date) < new Date() && m.status !== 'completed';
            return `
              <div class="pm-milestone-item ${m.status}" data-id="${m.id}">
                <div class="pm-milestone-content">
                  <div class="pm-milestone-info">
                    <div class="pm-milestone-name">
                      ${m.name}
                      <span class="pm-milestone-type ${m.milestone_type}">${getMilestoneTypeText(m.milestone_type)}</span>
                    </div>
                    <div class="pm-milestone-meta">
                      <div class="pm-milestone-dates">
                        ${m.planned_date ? `
                          <span class="pm-milestone-date ${isOverdue ? 'overdue' : 'planned'}">
                            <span class="icon">${getIcon('calendar')}</span>
                            預定：${m.planned_date}
                          </span>
                        ` : ''}
                        ${m.actual_date ? `
                          <span class="pm-milestone-date actual">
                            <span class="icon">${getIcon('check-circle')}</span>
                            實際：${m.actual_date}
                          </span>
                        ` : ''}
                      </div>
                      <span class="pm-milestone-status ${m.status}">${getMilestoneStatusText(m.status)}</span>
                    </div>
                    ${m.notes ? `<div class="pm-milestone-notes">${m.notes}</div>` : ''}
                  </div>
                  <div class="pm-milestone-actions">
                    <button class="pm-icon-btn" data-action="edit" title="編輯">
                      <span class="icon">${getIcon('edit')}</span>
                    </button>
                    <button class="pm-icon-btn danger" data-action="delete" title="刪除">
                      <span class="icon">${getIcon('delete')}</span>
                    </button>
                  </div>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      `}
    `;

    // Bind events
    containerEl.querySelector('#pmBtnAddMilestone')?.addEventListener('click', () => showMilestoneModal());
    containerEl.querySelectorAll('.pm-milestone-item').forEach(item => {
      item.querySelectorAll('.pm-icon-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const milestoneId = item.dataset.id;
          const milestone = selectedProject.milestones.find(m => m.id === milestoneId);
          if (btn.dataset.action === 'edit') showMilestoneModal(milestone);
          else if (btn.dataset.action === 'delete') confirmDeleteMilestone(milestoneId);
        });
      });
    });
  }

  function showMilestoneModal(milestone = null) {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const isEdit = !!milestone;
    const modal = document.createElement('div');
    modal.className = 'pm-modal';
    modal.innerHTML = `
      <div class="pm-modal-content">
        <div class="pm-modal-header">
          <h3>${isEdit ? '編輯里程碑' : '新增里程碑'}</h3>
          <button class="pm-modal-close"><span class="icon">${getIcon('close')}</span></button>
        </div>
        <div class="pm-modal-body">
          <div class="pm-form-group">
            <label>里程碑名稱 *</label>
            <input type="text" id="milestoneName" value="${milestone?.name || ''}" required>
          </div>
          <div class="pm-form-row">
            <div class="pm-form-group">
              <label>類型</label>
              <select id="milestoneType">
                <option value="design" ${milestone?.milestone_type === 'design' ? 'selected' : ''}>設計</option>
                <option value="manufacture" ${milestone?.milestone_type === 'manufacture' ? 'selected' : ''}>製造</option>
                <option value="delivery" ${milestone?.milestone_type === 'delivery' ? 'selected' : ''}>交機</option>
                <option value="field_test" ${milestone?.milestone_type === 'field_test' ? 'selected' : ''}>場測</option>
                <option value="acceptance" ${milestone?.milestone_type === 'acceptance' ? 'selected' : ''}>驗收</option>
                <option value="custom" ${milestone?.milestone_type === 'custom' || !milestone ? 'selected' : ''}>自訂</option>
              </select>
            </div>
            <div class="pm-form-group">
              <label>狀態</label>
              <select id="milestoneStatus">
                <option value="pending" ${milestone?.status === 'pending' || !milestone ? 'selected' : ''}>待進行</option>
                <option value="in_progress" ${milestone?.status === 'in_progress' ? 'selected' : ''}>進行中</option>
                <option value="completed" ${milestone?.status === 'completed' ? 'selected' : ''}>已完成</option>
                <option value="delayed" ${milestone?.status === 'delayed' ? 'selected' : ''}>延遲</option>
              </select>
            </div>
          </div>
          <div class="pm-form-row">
            <div class="pm-form-group">
              <label>預定日期</label>
              <input type="date" id="milestonePlannedDate" value="${milestone?.planned_date || ''}">
            </div>
            <div class="pm-form-group">
              <label>實際完成日期</label>
              <input type="date" id="milestoneActualDate" value="${milestone?.actual_date || ''}">
            </div>
          </div>
          <div class="pm-form-group">
            <label>備註</label>
            <textarea id="milestoneNotes" rows="2">${milestone?.notes || ''}</textarea>
          </div>
        </div>
        <div class="pm-modal-footer">
          <button class="pm-btn" id="milestoneCancel">取消</button>
          <button class="pm-btn primary" id="milestoneSave">${isEdit ? '儲存' : '新增'}</button>
        </div>
      </div>
    `;

    windowEl.appendChild(modal);

    const closeModal = () => modal.remove();
    modal.querySelector('.pm-modal-close').addEventListener('click', closeModal);
    modal.querySelector('#milestoneCancel').addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

    modal.querySelector('#milestoneSave').addEventListener('click', async () => {
      const data = {
        name: modal.querySelector('#milestoneName').value.trim(),
        milestone_type: modal.querySelector('#milestoneType').value,
        status: modal.querySelector('#milestoneStatus').value,
        planned_date: modal.querySelector('#milestonePlannedDate').value || null,
        actual_date: modal.querySelector('#milestoneActualDate').value || null,
        notes: modal.querySelector('#milestoneNotes').value.trim() || null,
      };

      if (!data.name) {
        NotificationModule.show({ title: '提醒', message: '請輸入里程碑名稱', icon: 'alert' });
        return;
      }

      try {
        if (isEdit) {
          await apiRequest(`/${selectedProject.id}/milestones/${milestone.id}`, {
            method: 'PUT',
            body: JSON.stringify(data),
          });
        } else {
          await apiRequest(`/${selectedProject.id}/milestones`, {
            method: 'POST',
            body: JSON.stringify(data),
          });
        }
        closeModal();
        await selectProject(selectedProject.id);
        NotificationModule.show({ title: '成功', message: isEdit ? '里程碑已更新' : '里程碑已新增', icon: 'check-circle' });
      } catch (error) {
        NotificationModule.show({ title: '失敗', message: error.message, icon: 'alert-circle' });
      }
    });
  }

  async function confirmDeleteMilestone(milestoneId) {
    if (!confirm('確定要刪除此里程碑嗎？')) return;
    try {
      await apiRequest(`/${selectedProject.id}/milestones/${milestoneId}`, { method: 'DELETE' });
      await selectProject(selectedProject.id);
      NotificationModule.show({ title: '成功', message: '里程碑已刪除', icon: 'check-circle' });
    } catch (error) {
      NotificationModule.show({ title: '失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  // ============================================
  // Project CRUD
  // ============================================

  function startNewProject() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    selectedProject = null;
    isEditing = true;
    editingData = {
      name: '',
      description: '',
      status: 'active',
      start_date: null,
      end_date: null,
    };

    renderEditor(windowEl);
  }

  function startEditProject() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl || !selectedProject) return;

    isEditing = true;
    editingData = {
      name: selectedProject.name,
      description: selectedProject.description || '',
      status: selectedProject.status,
      start_date: selectedProject.start_date,
      end_date: selectedProject.end_date,
    };

    renderEditor(windowEl);
  }

  function renderEditor(windowEl) {
    const emptyEl = windowEl.querySelector('#pmContentEmpty');
    const viewEl = windowEl.querySelector('#pmContentView');
    const editorEl = windowEl.querySelector('#pmEditor');

    emptyEl.style.display = 'none';
    viewEl.style.display = 'none';
    editorEl.style.display = 'flex';

    const isNew = !selectedProject;
    editorEl.innerHTML = `
      <div class="pm-editor-header">
        <h2>${isNew ? '新增專案' : '編輯專案'}</h2>
      </div>
      <div class="pm-editor-body">
        <div class="pm-form-group">
          <label>專案名稱 *</label>
          <input type="text" id="pmEditName" value="${editingData.name}" required>
        </div>
        <div class="pm-form-row">
          <div class="pm-form-group">
            <label>狀態</label>
            <select id="pmEditStatus">
              <option value="active" ${editingData.status === 'active' ? 'selected' : ''}>進行中</option>
              <option value="completed" ${editingData.status === 'completed' ? 'selected' : ''}>已完成</option>
              <option value="on_hold" ${editingData.status === 'on_hold' ? 'selected' : ''}>暫停</option>
              <option value="cancelled" ${editingData.status === 'cancelled' ? 'selected' : ''}>已取消</option>
            </select>
          </div>
        </div>
        <div class="pm-form-row">
          <div class="pm-form-group">
            <label>開始日期</label>
            <input type="date" id="pmEditStartDate" value="${editingData.start_date || ''}">
          </div>
          <div class="pm-form-group">
            <label>結束日期</label>
            <input type="date" id="pmEditEndDate" value="${editingData.end_date || ''}">
          </div>
        </div>
        <div class="pm-form-group">
          <label>專案描述</label>
          <textarea id="pmEditDesc" rows="5">${editingData.description}</textarea>
        </div>
      </div>
      <div class="pm-editor-footer">
        <button class="pm-btn" id="pmEditCancel">取消</button>
        <button class="pm-btn primary" id="pmEditSave">${isNew ? '建立' : '儲存'}</button>
      </div>
    `;

    editorEl.querySelector('#pmEditCancel').addEventListener('click', cancelEdit);
    editorEl.querySelector('#pmEditSave').addEventListener('click', saveProject);
  }

  function cancelEdit() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    isEditing = false;
    editingData = null;

    if (selectedProject) {
      renderContentView(windowEl);
    } else {
      windowEl.querySelector('#pmContentEmpty').style.display = 'flex';
      windowEl.querySelector('#pmContentView').style.display = 'none';
      windowEl.querySelector('#pmEditor').style.display = 'none';
    }
  }

  async function saveProject() {
    const windowEl = document.getElementById(windowId);
    if (!windowEl) return;

    const name = windowEl.querySelector('#pmEditName').value.trim();
    if (!name) {
      NotificationModule.show({ title: '提醒', message: '請輸入專案名稱', icon: 'alert' });
      return;
    }

    const data = {
      name,
      description: windowEl.querySelector('#pmEditDesc').value.trim() || null,
      status: windowEl.querySelector('#pmEditStatus').value,
      start_date: windowEl.querySelector('#pmEditStartDate').value || null,
      end_date: windowEl.querySelector('#pmEditEndDate').value || null,
    };

    try {
      if (selectedProject) {
        await apiRequest(`/${selectedProject.id}`, {
          method: 'PUT',
          body: JSON.stringify(data),
        });
        NotificationModule.show({ title: '成功', message: '專案已更新', icon: 'check-circle' });
      } else {
        const result = await apiRequest('', {
          method: 'POST',
          body: JSON.stringify(data),
        });
        selectedProject = { id: result.id };
        NotificationModule.show({ title: '成功', message: '專案已建立', icon: 'check-circle' });
      }

      isEditing = false;
      editingData = null;
      loadProjects();
      if (selectedProject) {
        selectProject(selectedProject.id);
      }
    } catch (error) {
      NotificationModule.show({ title: '儲存失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  async function confirmDeleteProject() {
    if (!selectedProject) return;
    if (!confirm(`確定要刪除「${selectedProject.name}」嗎？\n此操作將同時刪除所有成員、會議、附件和連結。`)) return;

    try {
      await apiRequest(`/${selectedProject.id}`, { method: 'DELETE' });
      NotificationModule.show({ title: '成功', message: '專案已刪除', icon: 'check-circle' });

      selectedProject = null;
      const windowEl = document.getElementById(windowId);
      if (windowEl) {
        windowEl.querySelector('#pmContentEmpty').style.display = 'flex';
        windowEl.querySelector('#pmContentView').style.display = 'none';
        windowEl.querySelector('#pmEditor').style.display = 'none';
      }
      loadProjects();
    } catch (error) {
      NotificationModule.show({ title: '刪除失敗', message: error.message, icon: 'alert-circle' });
    }
  }

  // Public API
  return {
    open,
    close,
  };
})();
