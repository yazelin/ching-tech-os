/**
 * Line Bot 管理介面
 *
 * 功能：
 * - 群組列表與詳情
 * - 用戶列表
 * - 訊息瀏覽
 * - 專案綁定
 */

const LineBotApp = (function () {
    'use strict';

    // 狀態
    let state = {
        currentTab: 'groups',
        groups: [],
        users: [],
        messages: [],
        files: [],
        selectedGroup: null,
        projects: [],
        pagination: {
            groups: { page: 1, total: 0 },
            users: { page: 1, total: 0 },
            messages: { page: 1, total: 0 },
            files: { page: 1, total: 0 },
        },
        loading: false,
        filters: {
            files: { groupId: null, fileType: null },
        },
    };

    // API 呼叫
    async function api(endpoint, options = {}) {
        const url = `/api/linebot${endpoint}`;
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            credentials: 'include',
        });

        if (!response.ok) {
            throw new Error(`API 錯誤: ${response.status}`);
        }

        return response.json();
    }

    // 載入群組列表
    async function loadGroups(page = 1) {
        state.loading = true;
        renderLoading('groups');

        try {
            const data = await api(`/groups?limit=20&offset=${(page - 1) * 20}`);
            state.groups = data.items;
            state.pagination.groups = { page, total: data.total };
            renderGroups();
        } catch (error) {
            console.error('載入群組失敗:', error);
            renderError('groups', '載入群組失敗');
        } finally {
            state.loading = false;
        }
    }

    // 載入用戶列表
    async function loadUsers(page = 1) {
        state.loading = true;
        renderLoading('users');

        try {
            const data = await api(`/users?limit=20&offset=${(page - 1) * 20}`);
            state.users = data.items;
            state.pagination.users = { page, total: data.total };
            renderUsers();
        } catch (error) {
            console.error('載入用戶失敗:', error);
            renderError('users', '載入用戶失敗');
        } finally {
            state.loading = false;
        }
    }

    // 載入訊息列表
    async function loadMessages(groupId = null, page = 1) {
        state.loading = true;
        renderLoading('messages');

        try {
            let endpoint = `/messages?page=${page}&page_size=50`;
            if (groupId) {
                endpoint += `&group_id=${groupId}`;
            }

            const data = await api(endpoint);
            state.messages = data.items;
            state.pagination.messages = { page, total: data.total };
            renderMessages();
        } catch (error) {
            console.error('載入訊息失敗:', error);
            renderError('messages', '載入訊息失敗');
        } finally {
            state.loading = false;
        }
    }

    // 載入檔案列表
    async function loadFiles(page = 1) {
        state.loading = true;
        renderLoading('files');

        try {
            const { groupId, fileType } = state.filters.files;
            let endpoint = `/files?page=${page}&page_size=30`;

            if (groupId) {
                endpoint += `&group_id=${groupId}`;
            }
            if (fileType) {
                endpoint += `&file_type=${fileType}`;
            }

            const data = await api(endpoint);
            state.files = data.items;
            state.pagination.files = { page, total: data.total };
            renderFiles();
        } catch (error) {
            console.error('載入檔案失敗:', error);
            renderError('files', '載入檔案失敗');
        } finally {
            state.loading = false;
        }
    }

    // 載入專案列表
    async function loadProjects() {
        try {
            const response = await fetch('/api/projects?limit=100', {
                credentials: 'include',
            });
            if (response.ok) {
                const data = await response.json();
                state.projects = data.items || [];
            }
        } catch (error) {
            console.error('載入專案失敗:', error);
        }
    }

    // 綁定專案
    async function bindProject(groupId, projectId) {
        try {
            if (projectId) {
                await api(`/groups/${groupId}/bind-project`, {
                    method: 'POST',
                    body: JSON.stringify({ project_id: projectId }),
                });
            } else {
                await api(`/groups/${groupId}/bind-project`, {
                    method: 'DELETE',
                });
            }

            // 重新載入群組資訊
            await loadGroups(state.pagination.groups.page);

            if (state.selectedGroup && state.selectedGroup.id === groupId) {
                const group = state.groups.find(g => g.id === groupId);
                if (group) {
                    state.selectedGroup = group;
                    renderGroupDetail();
                }
            }
        } catch (error) {
            console.error('綁定專案失敗:', error);
            alert('綁定專案失敗');
        }
    }

    // 選擇群組
    function selectGroup(group) {
        state.selectedGroup = group;
        renderGroups();
        renderGroupDetail();
    }

    // 渲染群組列表
    function renderGroups() {
        const container = document.querySelector('.linebot-groups-list');
        if (!container) return;

        if (state.groups.length === 0) {
            container.innerHTML = `
                <div class="linebot-empty">
                    <div class="linebot-empty-icon">👥</div>
                    <div class="linebot-empty-text">尚無群組資料</div>
                </div>
            `;
            return;
        }

        container.innerHTML = state.groups.map(group => `
            <div class="linebot-group-card ${state.selectedGroup?.id === group.id ? 'selected' : ''}"
                 data-id="${group.id}">
                <div class="linebot-group-avatar">
                    ${group.picture_url
                        ? `<img src="${group.picture_url}" alt="${group.name || '群組'}">`
                        : '👥'
                    }
                </div>
                <div class="linebot-group-info">
                    <div class="linebot-group-name">${group.name || '未命名群組'}</div>
                    <div class="linebot-group-meta">
                        <span>${group.member_count} 位成員</span>
                        <span class="linebot-group-status">
                            <span class="linebot-status-dot ${group.is_active ? 'active' : 'inactive'}"></span>
                            ${group.is_active ? '使用中' : '已離開'}
                        </span>
                    </div>
                </div>
            </div>
        `).join('');

        // 綁定點擊事件
        container.querySelectorAll('.linebot-group-card').forEach(card => {
            card.addEventListener('click', () => {
                const group = state.groups.find(g => g.id === card.dataset.id);
                if (group) selectGroup(group);
            });
        });

        renderPagination('groups');
    }

    // 渲染群組詳情
    function renderGroupDetail() {
        const container = document.querySelector('.linebot-group-detail');
        if (!container) return;

        if (!state.selectedGroup) {
            container.innerHTML = `
                <div class="linebot-empty">
                    <div class="linebot-empty-icon">👈</div>
                    <div class="linebot-empty-text">請選擇一個群組</div>
                </div>
            `;
            return;
        }

        const group = state.selectedGroup;

        container.innerHTML = `
            <div class="linebot-detail-header">
                <div class="linebot-detail-avatar">
                    ${group.picture_url
                        ? `<img src="${group.picture_url}" alt="${group.name || '群組'}">`
                        : '👥'
                    }
                </div>
                <div class="linebot-detail-info">
                    <h3>${group.name || '未命名群組'}</h3>
                    <div class="linebot-detail-meta">
                        <div>成員數：${group.member_count}</div>
                        <div>狀態：${group.is_active ? '使用中' : '已離開'}</div>
                        <div>加入時間：${new Date(group.joined_at).toLocaleDateString()}</div>
                    </div>
                </div>
            </div>

            <div class="linebot-project-binding">
                <h4>專案綁定</h4>
                <select class="linebot-project-select" data-group-id="${group.id}">
                    <option value="">-- 未綁定專案 --</option>
                    ${state.projects.map(p => `
                        <option value="${p.id}" ${group.project_id === p.id ? 'selected' : ''}>
                            ${p.name}
                        </option>
                    `).join('')}
                </select>
            </div>

            <div class="linebot-messages-container">
                <h4>最近訊息</h4>
                <div class="linebot-group-messages-list"></div>
            </div>
        `;

        // 綁定專案選擇事件
        const select = container.querySelector('.linebot-project-select');
        select.addEventListener('change', () => {
            bindProject(select.dataset.groupId, select.value || null);
        });

        // 載入該群組的訊息
        loadGroupMessages(group.id);
    }

    // 載入群組訊息
    async function loadGroupMessages(groupId) {
        const container = document.querySelector('.linebot-group-messages-list');
        if (!container) return;

        container.innerHTML = '<div class="linebot-loading">載入中...</div>';

        try {
            const data = await api(`/messages?group_id=${groupId}&page=1&page_size=20`);
            renderGroupMessages(container, data.items);
        } catch (error) {
            container.innerHTML = '<div class="linebot-empty"><div class="linebot-empty-text">載入失敗</div></div>';
        }
    }

    // 渲染群組訊息
    function renderGroupMessages(container, messages) {
        if (messages.length === 0) {
            container.innerHTML = `
                <div class="linebot-empty">
                    <div class="linebot-empty-text">暫無訊息</div>
                </div>
            `;
            return;
        }

        container.innerHTML = messages.map(msg => `
            <div class="linebot-message ${msg.is_from_bot ? 'from-bot' : ''}">
                <div class="linebot-message-avatar">
                    ${msg.user_picture_url
                        ? `<img src="${msg.user_picture_url}" alt="">`
                        : (msg.is_from_bot ? '🤖' : '👤')
                    }
                </div>
                <div class="linebot-message-content">
                    <div class="linebot-message-header">
                        <span class="linebot-message-sender">
                            ${msg.is_from_bot ? 'Bot' : (msg.user_display_name || '未知用戶')}
                        </span>
                        <span class="linebot-message-time">
                            ${new Date(msg.created_at).toLocaleString()}
                        </span>
                    </div>
                    ${msg.message_type === 'text'
                        ? `<div class="linebot-message-text">${escapeHtml(msg.content || '')}</div>`
                        : `<div class="linebot-message-type">[${msg.message_type}]</div>`
                    }
                </div>
            </div>
        `).join('');
    }

    // 渲染用戶列表
    function renderUsers() {
        const container = document.querySelector('.linebot-users-list');
        if (!container) return;

        if (state.users.length === 0) {
            container.innerHTML = `
                <div class="linebot-empty">
                    <div class="linebot-empty-icon">👤</div>
                    <div class="linebot-empty-text">尚無用戶資料</div>
                </div>
            `;
            return;
        }

        container.innerHTML = state.users.map(user => `
            <div class="linebot-user-card" data-id="${user.id}">
                <div class="linebot-user-avatar">
                    ${user.picture_url
                        ? `<img src="${user.picture_url}" alt="${user.display_name || '用戶'}">`
                        : '👤'
                    }
                </div>
                <div class="linebot-user-info">
                    <div class="linebot-user-name">${user.display_name || '未知用戶'}</div>
                    <div class="linebot-user-status">
                        ${user.is_friend ? '好友' : '非好友'}
                        ${user.status_message ? ` · ${user.status_message}` : ''}
                    </div>
                </div>
            </div>
        `).join('');

        renderPagination('users');
    }

    // 渲染訊息列表
    function renderMessages() {
        const container = document.querySelector('.linebot-messages-list');
        if (!container) return;

        if (state.messages.length === 0) {
            container.innerHTML = `
                <div class="linebot-empty">
                    <div class="linebot-empty-icon">💬</div>
                    <div class="linebot-empty-text">尚無訊息</div>
                </div>
            `;
            return;
        }

        container.innerHTML = state.messages.map(msg => `
            <div class="linebot-message ${msg.is_from_bot ? 'from-bot' : ''}">
                <div class="linebot-message-avatar">
                    ${msg.user_picture_url
                        ? `<img src="${msg.user_picture_url}" alt="">`
                        : (msg.is_from_bot ? '🤖' : '👤')
                    }
                </div>
                <div class="linebot-message-content">
                    <div class="linebot-message-header">
                        <span class="linebot-message-sender">
                            ${msg.is_from_bot ? 'Bot' : (msg.user_display_name || '未知用戶')}
                        </span>
                        <span class="linebot-message-time">
                            ${new Date(msg.created_at).toLocaleString()}
                        </span>
                    </div>
                    ${msg.message_type === 'text'
                        ? `<div class="linebot-message-text">${escapeHtml(msg.content || '')}</div>`
                        : `<div class="linebot-message-type">[${msg.message_type}]</div>`
                    }
                </div>
            </div>
        `).join('');

        renderPagination('messages');
    }

    // 渲染檔案列表
    function renderFiles() {
        const container = document.querySelector('.linebot-files-grid');
        if (!container) return;

        if (state.files.length === 0) {
            container.innerHTML = `
                <div class="linebot-empty">
                    <div class="linebot-empty-icon">📁</div>
                    <div class="linebot-empty-text">尚無檔案</div>
                </div>
            `;
            return;
        }

        container.innerHTML = state.files.map(file => {
            const typeIcon = getFileTypeIcon(file.file_type);
            const fileName = file.file_name || `${file.file_type}_${file.id.slice(0, 8)}`;
            const fileSize = formatFileSize(file.file_size);

            // 圖片預覽 URL（如果有 NAS 路徑）
            const previewUrl = file.nas_path ? `${window.API_BASE || ''}/api/linebot/files/${file.id}/download` : null;

            return `
                <div class="linebot-file-card" data-id="${file.id}">
                    <div class="linebot-file-preview">
                        ${file.file_type === 'image' && previewUrl
                            ? `<img src="${previewUrl}" alt="${fileName}" loading="lazy">`
                            : `<div class="linebot-file-icon">${typeIcon}</div>`
                        }
                    </div>
                    <div class="linebot-file-info">
                        <div class="linebot-file-name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div>
                        <div class="linebot-file-meta">
                            <span>${file.group_name || '個人'}</span>
                            ${fileSize ? `<span>${fileSize}</span>` : ''}
                        </div>
                        <div class="linebot-file-date">
                            ${new Date(file.created_at).toLocaleDateString()}
                        </div>
                    </div>
                    <div class="linebot-file-actions">
                        ${file.nas_path
                            ? `<a href="${window.API_BASE || ''}/api/linebot/files/${file.id}/download" class="linebot-file-download" title="下載">⬇️</a>`
                            : '<span class="linebot-file-unavailable" title="檔案未儲存">❌</span>'
                        }
                        <button class="linebot-file-delete" data-file-id="${file.id}" title="刪除">🗑️</button>
                    </div>
                </div>
            `;
        }).join('');

        renderPagination('files');
    }

    // 取得檔案類型圖示
    function getFileTypeIcon(fileType) {
        const icons = {
            image: '🖼️',
            video: '🎬',
            audio: '🎵',
            file: '📄',
        };
        return icons[fileType] || '📄';
    }

    // 格式化檔案大小
    function formatFileSize(bytes) {
        if (!bytes) return null;
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    }

    // 渲染分頁
    function renderPagination(type) {
        const container = document.querySelector(`.linebot-pagination-${type}`);
        if (!container) return;

        const { page, total } = state.pagination[type];
        const pageSizes = { groups: 20, users: 20, messages: 50, files: 30 };
        const pageSize = pageSizes[type] || 20;
        const totalPages = Math.ceil(total / pageSize);

        container.innerHTML = `
            <button ${page <= 1 ? 'disabled' : ''} data-action="prev">上一頁</button>
            <span class="linebot-pagination-info">第 ${page} / ${totalPages || 1} 頁（共 ${total} 筆）</span>
            <button ${page >= totalPages ? 'disabled' : ''} data-action="next">下一頁</button>
        `;

        container.querySelectorAll('button').forEach(btn => {
            btn.addEventListener('click', () => {
                const newPage = btn.dataset.action === 'prev' ? page - 1 : page + 1;
                if (type === 'groups') loadGroups(newPage);
                else if (type === 'users') loadUsers(newPage);
                else if (type === 'messages') loadMessages(null, newPage);
                else if (type === 'files') loadFiles(newPage);
            });
        });
    }

    // 渲染載入中
    function renderLoading(type) {
        const selectors = {
            groups: '.linebot-groups-list',
            users: '.linebot-users-list',
            messages: '.linebot-messages-list',
            files: '.linebot-files-grid',
        };
        const container = document.querySelector(selectors[type]);

        if (container) {
            container.innerHTML = '<div class="linebot-loading">載入中...</div>';
        }
    }

    // 渲染錯誤
    function renderError(type, message) {
        const selectors = {
            groups: '.linebot-groups-list',
            users: '.linebot-users-list',
            messages: '.linebot-messages-list',
            files: '.linebot-files-grid',
        };
        const container = document.querySelector(selectors[type]);

        if (container) {
            container.innerHTML = `
                <div class="linebot-empty">
                    <div class="linebot-empty-icon">⚠️</div>
                    <div class="linebot-empty-text">${message}</div>
                </div>
            `;
        }
    }

    // 切換標籤頁
    function switchTab(tab) {
        state.currentTab = tab;

        // 更新標籤樣式
        document.querySelectorAll('.linebot-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.tab === tab);
        });

        // 顯示對應面板
        document.querySelectorAll('.linebot-panel').forEach(p => {
            p.classList.toggle('active', p.dataset.panel === tab);
        });

        // 載入資料
        if (tab === 'groups' && state.groups.length === 0) {
            loadGroups();
        } else if (tab === 'users' && state.users.length === 0) {
            loadUsers();
        } else if (tab === 'messages' && state.messages.length === 0) {
            loadMessages();
        } else if (tab === 'files' && state.files.length === 0) {
            loadFiles();
        }
    }

    // HTML 轉義
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 初始化
    async function init(container) {
        container.innerHTML = `
            <div class="linebot-container">
                <div class="linebot-tabs">
                    <button class="linebot-tab active" data-tab="groups">群組</button>
                    <button class="linebot-tab" data-tab="users">用戶</button>
                    <button class="linebot-tab" data-tab="messages">訊息</button>
                    <button class="linebot-tab" data-tab="files">檔案</button>
                </div>

                <div class="linebot-content">
                    <!-- 群組面板 -->
                    <div class="linebot-panel active" data-panel="groups">
                        <div class="linebot-split-layout">
                            <div class="linebot-split-left">
                                <div class="linebot-groups-list"></div>
                                <div class="linebot-pagination linebot-pagination-groups"></div>
                            </div>
                            <div class="linebot-split-right">
                                <div class="linebot-group-detail"></div>
                            </div>
                        </div>
                    </div>

                    <!-- 用戶面板 -->
                    <div class="linebot-panel" data-panel="users">
                        <div class="linebot-users-list"></div>
                        <div class="linebot-pagination linebot-pagination-users"></div>
                    </div>

                    <!-- 訊息面板 -->
                    <div class="linebot-panel" data-panel="messages">
                        <div class="linebot-messages-container">
                            <div class="linebot-messages-filters">
                                <select class="linebot-filter-select" id="linebot-group-filter">
                                    <option value="">所有個人對話</option>
                                </select>
                            </div>
                            <div class="linebot-messages-list"></div>
                            <div class="linebot-pagination linebot-pagination-messages"></div>
                        </div>
                    </div>

                    <!-- 檔案面板 -->
                    <div class="linebot-panel" data-panel="files">
                        <div class="linebot-files-container">
                            <div class="linebot-files-filters">
                                <select class="linebot-filter-select" id="linebot-files-group-filter">
                                    <option value="">所有群組</option>
                                </select>
                                <select class="linebot-filter-select" id="linebot-files-type-filter">
                                    <option value="">所有類型</option>
                                    <option value="image">圖片</option>
                                    <option value="video">影片</option>
                                    <option value="audio">音訊</option>
                                    <option value="file">檔案</option>
                                </select>
                            </div>
                            <div class="linebot-files-grid"></div>
                            <div class="linebot-pagination linebot-pagination-files"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 綁定標籤點擊事件
        container.querySelectorAll('.linebot-tab').forEach(tab => {
            tab.addEventListener('click', () => switchTab(tab.dataset.tab));
        });

        // 載入專案列表
        await loadProjects();

        // 載入群組
        await loadGroups();

        // 渲染群組詳情初始狀態
        renderGroupDetail();

        // 填充群組篩選器
        updateGroupFilter();

        // 填充檔案篩選器
        updateFilesFilter();

        // 設置檔案刪除事件
        setupFileDeleteEvents();
    }

    // 更新群組篩選器
    function updateGroupFilter() {
        const filter = document.getElementById('linebot-group-filter');
        if (!filter) return;

        const options = ['<option value="">所有個人對話</option>'];
        state.groups.forEach(group => {
            options.push(`<option value="${group.id}">${group.name || '未命名群組'}</option>`);
        });
        filter.innerHTML = options.join('');

        filter.addEventListener('change', () => {
            loadMessages(filter.value || null, 1);
        });
    }

    // 更新檔案篩選器
    function updateFilesFilter() {
        // 群組篩選器
        const groupFilter = document.getElementById('linebot-files-group-filter');
        if (groupFilter) {
            const options = ['<option value="">所有群組</option>'];
            state.groups.forEach(group => {
                options.push(`<option value="${group.id}">${group.name || '未命名群組'}</option>`);
            });
            groupFilter.innerHTML = options.join('');

            groupFilter.addEventListener('change', () => {
                state.filters.files.groupId = groupFilter.value || null;
                loadFiles(1);
            });
        }

        // 類型篩選器
        const typeFilter = document.getElementById('linebot-files-type-filter');
        if (typeFilter) {
            typeFilter.addEventListener('change', () => {
                state.filters.files.fileType = typeFilter.value || null;
                loadFiles(1);
            });
        }
    }

    // 刪除檔案
    async function deleteFile(fileId) {
        try {
            const token = LoginModule.getToken();
            const response = await fetch(`/api/linebot/files/${fileId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });

            if (!response.ok) {
                throw new Error('刪除失敗');
            }

            // 重新載入檔案列表
            await loadFiles(state.pagination.files.page);
            return true;
        } catch (error) {
            console.error('刪除檔案失敗:', error);
            alert('刪除檔案失敗：' + error.message);
            return false;
        }
    }

    // 確認刪除對話框
    function confirmDeleteFile(fileId, fileName) {
        const confirmed = confirm(`確定要刪除檔案「${fileName}」嗎？\n此操作無法復原。`);
        if (confirmed) {
            deleteFile(fileId);
        }
    }

    // 設置檔案刪除事件委派
    function setupFileDeleteEvents() {
        const container = document.querySelector('.linebot-files-grid');
        if (!container) return;

        container.addEventListener('click', (e) => {
            const deleteBtn = e.target.closest('.linebot-file-delete');
            if (deleteBtn) {
                e.preventDefault();
                e.stopPropagation();
                const fileId = deleteBtn.dataset.fileId;
                const card = deleteBtn.closest('.linebot-file-card');
                const fileName = card?.querySelector('.linebot-file-name')?.textContent || '此檔案';
                confirmDeleteFile(fileId, fileName);
            }
        });
    }

    return {
        init,
        loadGroups,
        loadUsers,
        loadMessages,
        loadFiles,
        setupFileDeleteEvents,
    };
})();

// 匯出供 desktop.js 使用
window.LineBotApp = LineBotApp;
