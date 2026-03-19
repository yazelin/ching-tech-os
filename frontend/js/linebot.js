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

    const MOBILE_BREAKPOINT = 768;

    // 判斷是否為手機版
    function isMobile() {
        return window.innerWidth <= MOBILE_BREAKPOINT;
    }

    // 狀態
    let state = {
        currentTab: 'binding',  // 預設顯示綁定分頁
        platformFilter: null,   // null = 全部, 'line', 'telegram'
        groups: [],
        users: [],
        messages: [],
        files: [],
        selectedGroup: null,
        projects: [],
        bindingStatus: null,
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

    // 取得平台篩選的 query 參數
    function platformQuery() {
        return state.platformFilter ? `&platform_type=${state.platformFilter}` : '';
    }

    // 取得平台圖示 HTML
    function platformBadge(platformType) {
        const pt = platformType || 'line';
        const iconName = pt === 'telegram' ? 'telegram' : 'line';
        return `<span class="linebot-platform-badge ${pt}"><span class="icon">${typeof getIcon !== 'undefined' ? getIcon(iconName) : pt}</span></span>`;
    }

    // 取得 token
    function getToken() {
        return localStorage.getItem('chingtech_token');
    }

    // API 呼叫
    async function api(endpoint, options = {}) {
        const url = `/api/bot${endpoint}`;
        const token = getToken();
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...(token && { 'Authorization': `Bearer ${token}` }),
                ...options.headers,
            },
            credentials: 'include',
        });

        if (!response.ok) {
            throw new Error(`API 錯誤: ${response.status}`);
        }

        return response.json();
    }

    // 載入綁定狀態
    async function loadBindingStatus() {
        try {
            const data = await api('/binding/status');
            state.bindingStatus = data;
            renderBindingStatus();
        } catch (error) {
            console.error('載入綁定狀態失敗:', error);
            state.bindingStatus = { is_bound: false };
            renderBindingStatus();
        }
    }

    // 產生綁定驗證碼
    async function generateBindingCode(platformType = 'line') {
        try {
            const data = await api(`/binding/generate-code?platform_type=${platformType}`, { method: 'POST' });
            const platformName = platformType === 'telegram' ? 'Telegram' : 'Line';
            showBindingCodeModal(data.code, data.expires_at, platformName, platformType);
        } catch (error) {
            console.error('產生驗證碼失敗:', error);
            alert(`產生驗證碼失敗: ${error.message}`);
        }
    }

    // 解除綁定
    async function unbindLine(platformKey = 'line') {
        const platformName = platformKey === 'telegram' ? 'Telegram' : 'Line';
        if (!confirm(`確定要解除 ${platformName} 綁定嗎？\n解除後需要重新綁定才能使用 ${platformName} Bot。`)) {
            return;
        }

        try {
            await api(`/binding?platform_type=${platformKey}`, { method: 'DELETE' });
            await loadBindingStatus();
            alert(`已解除 ${platformName} 綁定`);
        } catch (error) {
            console.error('解除綁定失敗:', error);
            alert('解除綁定失敗');
        }
    }

    // 顯示驗證碼彈窗
    function showBindingCodeModal(code, expiresAt, platformName = 'Line', platformKey = 'line') {
        const modal = document.createElement('div');
        modal.className = 'linebot-modal-overlay';
        modal.innerHTML = `
            <div class="linebot-modal">
                <div class="linebot-modal-header">
                    <h3>${platformName} 綁定驗證碼</h3>
                    <button class="linebot-modal-close">&times;</button>
                </div>
                <div class="linebot-modal-body">
                    <div class="linebot-binding-code-display">${code}</div>
                    <p class="linebot-binding-instruction">
                        請在 ${platformName} 私訊 Bot 發送此驗證碼完成綁定
                    </p>
                    <p class="linebot-binding-expires">
                        有效期限：${new Date(expiresAt).toLocaleString()}
                    </p>
                    <p class="linebot-binding-status-hint">等待綁定中...</p>
                </div>
                <div class="linebot-modal-footer">
                    <button class="linebot-btn linebot-btn-primary linebot-copy-code">複製驗證碼</button>
                    <button class="linebot-btn linebot-modal-close-btn">關閉</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // 自動檢測綁定狀態（每 3 秒）
        let pollInterval = null;
        const startPolling = () => {
            pollInterval = setInterval(async () => {
                try {
                    const status = await api('/binding/status');
                    const platformStatus = status[platformKey];
                    if (platformStatus && platformStatus.is_bound) {
                        // 綁定成功！
                        clearInterval(pollInterval);
                        state.bindingStatus = status;
                        state.users = [];  // 清除用戶快取，讓下次切換時重新載入
                        modal.remove();
                        renderBindingStatus();
                    }
                } catch (e) {
                    // 忽略錯誤，繼續 polling
                }
            }, 3000);
        };
        startPolling();

        // 關閉時清除 polling
        const closeModal = () => {
            if (pollInterval) clearInterval(pollInterval);
            modal.remove();
            loadBindingStatus();
        };

        // 關閉事件
        modal.querySelector('.linebot-modal-close').addEventListener('click', closeModal);
        modal.querySelector('.linebot-modal-close-btn').addEventListener('click', closeModal);

        // 複製驗證碼
        modal.querySelector('.linebot-copy-code').addEventListener('click', () => {
            navigator.clipboard.writeText(code).then(() => {
                const btn = modal.querySelector('.linebot-copy-code');
                btn.textContent = '已複製！';
                setTimeout(() => { btn.textContent = '複製驗證碼'; }, 2000);
            });
        });

        // 點擊背景關閉
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });
    }

    // 渲染單一平台綁定區塊
    function renderPlatformBinding(platformName, platformKey, platformStatus) {
        const iconHtml = platformBadge(platformKey);
        if (platformStatus && platformStatus.is_bound) {
            return `
                <div class="linebot-binding-status bound">
                    <div class="linebot-binding-icon">${iconHtml}</div>
                    <div class="linebot-binding-info">
                        <div class="linebot-binding-label">已綁定 ${platformName} 帳號</div>
                        <div class="linebot-binding-detail">
                            ${platformStatus.picture_url
                                ? `<img class="linebot-binding-avatar" src="${platformStatus.picture_url}" alt="" loading="lazy">`
                                : ''
                            }
                            <span>${platformStatus.display_name || `${platformName} 用戶`}</span>
                        </div>
                        <div class="linebot-binding-time">
                            綁定時間：${platformStatus.bound_at ? new Date(platformStatus.bound_at).toLocaleString() : '未知'}
                        </div>
                    </div>
                    <button class="linebot-btn linebot-btn-danger linebot-unbind-btn" data-platform="${platformKey}">解除綁定</button>
                </div>
            `;
        } else {
            return `
                <div class="linebot-binding-status unbound">
                    <div class="linebot-binding-icon">${iconHtml}</div>
                    <div class="linebot-binding-info">
                        <div class="linebot-binding-label">尚未綁定 ${platformName} 帳號</div>
                        <div class="linebot-binding-instruction">
                            <p>綁定 ${platformName} 帳號後，即可使用 ${platformName} Bot 的 AI 功能。</p>
                            <ol>
                                <li>點擊「產生驗證碼」按鈕</li>
                                <li>在 ${platformName} 私訊 Bot 發送驗證碼</li>
                                <li>完成綁定！</li>
                            </ol>
                        </div>
                    </div>
                    <button class="linebot-btn linebot-btn-primary linebot-generate-code-btn" data-platform="${platformKey}">產生驗證碼</button>
                </div>
            `;
        }
    }

    // 渲染綁定狀態
    function renderBindingStatus() {
        const container = document.querySelector('.linebot-binding-content');
        if (!container) return;

        const status = state.bindingStatus;

        if (!status) {
            UIHelpers.showLoading(container, { text: '載入中…', variant: 'compact' });
            return;
        }

        // 多平台綁定區塊
        const lineStatus = status.line || {
            is_bound: status.is_bound,
            display_name: status.line_display_name,
            picture_url: status.line_picture_url,
            bound_at: status.bound_at,
        };
        const telegramStatus = status.telegram || { is_bound: false };

        container.innerHTML = `
            <h3 style="margin: 0 0 16px 0; color: var(--text-primary); font-size: 16px;">帳號綁定</h3>
            ${renderPlatformBinding('Line', 'line', lineStatus)}
            <div style="height: 16px;"></div>
            ${renderPlatformBinding('Telegram', 'telegram', telegramStatus)}
        `;

        // 綁定事件
        container.querySelectorAll('.linebot-unbind-btn').forEach(btn => {
            btn.addEventListener('click', () => unbindLine(btn.dataset.platform || 'line'));
        });
        container.querySelectorAll('.linebot-generate-code-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                generateBindingCode(btn.dataset.platform || 'line');
            });
        });
    }

    // 更新群組 AI 回應設定
    async function updateGroupAiResponse(groupId, allowAiResponse) {
        try {
            await api(`/groups/${groupId}`, {
                method: 'PATCH',
                body: JSON.stringify({ allow_ai_response: allowAiResponse }),
            });
            // 更新本地狀態
            const group = state.groups.find(g => g.id === groupId);
            if (group) {
                group.allow_ai_response = allowAiResponse;
            }
        } catch (error) {
            console.error('更新群組設定失敗:', error);
            alert('更新失敗');
            // 恢復開關狀態
            renderGroups();
        }
    }

    // 載入群組列表
    async function loadGroups(page = 1) {
        state.loading = true;
        renderLoading('groups');

        try {
            const data = await api(`/groups?limit=20&offset=${(page - 1) * 20}${platformQuery()}`);
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

    // 載入用戶列表（含綁定狀態）
    async function loadUsers(page = 1) {
        state.loading = true;
        renderLoading('users');

        try {
            const data = await api(`/users-with-binding?limit=20&offset=${(page - 1) * 20}${platformQuery()}`);
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

    // 載入黑名單
    async function loadBlocklist(page = 1) {
        state.loading = true;
        renderLoading('blocklist');

        try {
            const data = await api(`/users?blocked=true&limit=20&offset=${(page - 1) * 20}${platformQuery()}`);
            state.blocklist = data.items;
            state.pagination.blocklist = { page, total: data.total };
            renderBlocklist();
        } catch (error) {
            console.error('載入黑名單失敗:', error);
            renderError('blocklist', '載入黑名單失敗');
        } finally {
            state.loading = false;
        }
    }

    // 封鎖用戶
    async function blockUser(userId) {
        const reason = prompt('請輸入封鎖原因（可留空）：');
        if (reason === null) return; // 取消

        try {
            await api(`/users/${userId}/block`, {
                method: 'PATCH',
                body: JSON.stringify({ reason: reason || null }),
            });
            // 重新載入用戶列表和黑名單
            loadUsers(state.pagination.users.page);
            if (state.currentTab === 'blocklist') loadBlocklist(state.pagination.blocklist.page);
        } catch (error) {
            console.error('封鎖用戶失敗:', error);
            alert('封鎖用戶失敗');
        }
    }

    // 解除封鎖
    async function unblockUser(userId) {
        if (!confirm('確定要解除此用戶的封鎖嗎？')) return;

        try {
            await api(`/users/${userId}/unblock`, {
                method: 'PATCH',
            });
            // 重新載入黑名單
            loadBlocklist(state.pagination.blocklist.page);
        } catch (error) {
            console.error('解除封鎖失敗:', error);
            alert('解除封鎖失敗');
        }
    }

    // 載入訊息列表
    async function loadMessages(groupId = null, page = 1) {
        state.loading = true;
        renderLoading('messages');

        try {
            let endpoint = `/messages?page=${page}&page_size=50${platformQuery()}`;
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
            let endpoint = `/files?page=${page}&page_size=30${platformQuery()}`;

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
            const data = await APIClient.request('/projects?limit=100');
            state.projects = data.items || [];
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

        // 手機版：顯示詳情面板
        if (isMobile()) {
            const detailPanel = document.querySelector('.linebot-split-right');
            if (detailPanel) {
                detailPanel.classList.add('visible');
            }
        }
    }

    // 關閉群組詳情（手機版返回）
    function closeGroupDetail() {
        state.selectedGroup = null;
        renderGroups();

        const detailPanel = document.querySelector('.linebot-split-right');
        if (detailPanel) {
            detailPanel.classList.remove('visible');
        }
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
                        ? `<img src="${group.picture_url}" alt="${group.name || '群組'}" loading="lazy">`
                        : '👥'
                    }
                </div>
                <div class="linebot-group-info">
                    <div class="linebot-group-name">${platformBadge(group.platform_type)} ${group.name || '未命名群組'}</div>
                    <div class="linebot-group-meta">
                        <span>${group.member_count} 位成員</span>
                        <span class="linebot-group-status">
                            <span class="linebot-status-dot ${group.is_active ? 'active' : 'inactive'}"></span>
                            ${group.is_active ? '使用中' : '已離開'}
                        </span>
                    </div>
                    <div class="linebot-group-ai-toggle">
                        <label class="linebot-toggle" title="${group.allow_ai_response ? '點擊關閉 AI 回應' : '點擊開啟 AI 回應'}">
                            <input type="checkbox"
                                   class="linebot-ai-toggle-input"
                                   data-group-id="${group.id}"
                                   ${group.allow_ai_response ? 'checked' : ''}>
                            <span class="linebot-toggle-slider"></span>
                        </label>
                        <span class="linebot-ai-toggle-label">AI 回應</span>
                    </div>
                </div>
            </div>
        `).join('');

        // 綁定點擊事件（排除 toggle 區域）
        container.querySelectorAll('.linebot-group-card').forEach(card => {
            card.addEventListener('click', (e) => {
                // 忽略 toggle 的點擊
                if (e.target.closest('.linebot-group-ai-toggle')) return;
                const group = state.groups.find(g => g.id === card.dataset.id);
                if (group) selectGroup(group);
            });
        });

        // 綁定 AI 回應開關事件
        container.querySelectorAll('.linebot-ai-toggle-input').forEach(toggle => {
            toggle.addEventListener('change', (e) => {
                console.log('Toggle changed:', toggle.dataset.groupId, toggle.checked);
                updateGroupAiResponse(toggle.dataset.groupId, toggle.checked);
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
            <button class="linebot-back-btn" onclick="LineBotApp.closeGroupDetail && LineBotApp.closeGroupDetail()">
                <span class="icon">${typeof getIcon !== 'undefined' ? getIcon('arrow-left') : '←'}</span>
                返回群組列表
            </button>
            <div class="linebot-detail-header">
                <div class="linebot-detail-avatar">
                    ${group.picture_url
                        ? `<img src="${group.picture_url}" alt="${group.name || '群組'}" loading="lazy">`
                        : '👥'
                    }
                </div>
                <div class="linebot-detail-info">
                    <h3>${group.name || '未命名群組'}</h3>
                    <div class="linebot-detail-meta">
                        <div>成員數：${group.member_count}</div>
                        <div>狀態：${group.is_active ? '使用中' : '已離開'}</div>
                        <div>加入時間：${new Date(group.joined_at).toLocaleDateString()}</div>
                        ${!group.is_active && group.left_at
                            ? `<div>離開時間：${new Date(group.left_at).toLocaleDateString()}</div>`
                            : ''
                        }
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

            <div class="linebot-group-actions">
                <h4>群組管理</h4>
                <button class="linebot-btn linebot-btn-danger linebot-delete-group-btn" data-group-id="${group.id}">
                    <span class="icon">${typeof getIcon !== 'undefined' ? getIcon('delete') : '🗑'}</span>
                    刪除群組
                </button>
                <p class="linebot-action-hint">刪除群組將同時刪除所有訊息記錄</p>
            </div>
        `;

        // 綁定專案選擇事件
        const select = container.querySelector('.linebot-project-select');
        select.addEventListener('change', () => {
            bindProject(select.dataset.groupId, select.value || null);
        });

        // 綁定刪除按鈕事件
        const deleteBtn = container.querySelector('.linebot-delete-group-btn');
        deleteBtn.addEventListener('click', () => {
            confirmDeleteGroup(group.id, group.name || '未命名群組');
        });

        // 載入該群組的訊息
        loadGroupMessages(group.id);
    }

    // 載入群組訊息
    async function loadGroupMessages(groupId) {
        const container = document.querySelector('.linebot-group-messages-list');
        if (!container) return;

        UIHelpers.showLoading(container, { text: '載入中…', variant: 'compact' });

        try {
            const data = await api(`/messages?group_id=${groupId}&page=1&page_size=20`);
            renderGroupMessages(container, data.items);
        } catch (error) {
            UIHelpers.showError(container, {
              message: '載入失敗',
              onRetry: () => loadGroupMessages(groupId),
            });
        }
    }

    // 渲染群組訊息
    function renderGroupMessages(container, messages) {
        if (messages.length === 0) {
            UIHelpers.showEmpty(container, { text: '暫無訊息', variant: 'compact' });
            return;
        }

        container.innerHTML = messages.map(msg => `
            <div class="linebot-message ${msg.is_from_bot ? 'from-bot' : ''}">
                <div class="linebot-message-avatar">
                    ${msg.user_picture_url
                        ? `<img src="${msg.user_picture_url}" alt="" loading="lazy">`
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
                        ? `<img src="${user.picture_url}" alt="${user.display_name || '用戶'}" loading="lazy">`
                        : '👤'
                    }
                </div>
                <div class="linebot-user-info">
                    <div class="linebot-user-name">${platformBadge(user.platform_type)} ${user.display_name || '未知用戶'}</div>
                    <div class="linebot-user-status">
                        ${user.is_friend ? '好友' : '非好友'}
                        ${user.status_message ? ` · ${user.status_message}` : ''}
                    </div>
                    <div class="linebot-user-binding ${user.bound_username ? 'bound' : 'unbound'}">
                        ${user.bound_username
                            ? `<span class="linebot-binding-badge bound">✓ 已綁定 ${user.bound_display_name || user.bound_username}</span>`
                            : '<span class="linebot-binding-badge unbound">未綁定</span>'
                        }
                        ${user.is_blocked
                            ? '<span class="linebot-binding-badge blocked">已封鎖</span>'
                            : ''
                        }
                    </div>
                </div>
                ${!user.is_blocked ? `
                    <div class="linebot-user-actions">
                        <button class="linebot-block-btn" data-user-id="${user.id}" title="封鎖用戶">
                            <span class="icon">${typeof getIcon !== 'undefined' ? getIcon('account-cancel') : '🚫'}</span>
                        </button>
                    </div>
                ` : ''}
            </div>
        `).join('');

        renderPagination('users');

        // 綁定封鎖按鈕事件
        container.querySelectorAll('.linebot-block-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                blockUser(btn.dataset.userId);
            });
        });
    }

    // 渲染黑名單列表
    function renderBlocklist() {
        const container = document.querySelector('.linebot-blocklist-list');
        if (!container) return;

        if (state.blocklist.length === 0) {
            container.innerHTML = `
                <div class="linebot-empty">
                    <div class="linebot-empty-icon">✅</div>
                    <div class="linebot-empty-text">目前沒有被封鎖的用戶</div>
                </div>
            `;
            return;
        }

        container.innerHTML = state.blocklist.map(user => `
            <div class="linebot-user-card linebot-blocked-card" data-id="${user.id}">
                <div class="linebot-user-avatar">
                    ${user.picture_url
                        ? `<img src="${user.picture_url}" alt="${user.display_name || '用戶'}" loading="lazy">`
                        : '👤'
                    }
                </div>
                <div class="linebot-user-info">
                    <div class="linebot-user-name">${platformBadge(user.platform_type)} ${user.display_name || '未知用戶'}</div>
                    <div class="linebot-user-status linebot-blocked-reason">
                        封鎖原因：${user.blocked_reason ? escapeHtml(user.blocked_reason) : '未填寫'}
                    </div>
                    <div class="linebot-user-status">
                        封鎖時間：${user.blocked_at ? new Date(user.blocked_at).toLocaleString() : '未知'}
                    </div>
                </div>
                <div class="linebot-user-actions">
                    <button class="linebot-unblock-btn" data-user-id="${user.id}" title="解除封鎖">
                        <span class="icon">${typeof getIcon !== 'undefined' ? getIcon('account-check') : '✅'}</span> 解除封鎖
                    </button>
                </div>
            </div>
        `).join('');

        renderPagination('blocklist');

        // 綁定解除封鎖按鈕事件
        container.querySelectorAll('.linebot-unblock-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                unblockUser(btn.dataset.userId);
            });
        });
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
                        ? `<img src="${msg.user_picture_url}" alt="" loading="lazy">`
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
            const fileName = file.file_name || `${file.file_type}_${file.id.slice(0, 8)}`;
            // 使用 FileUtils 取得圖示和類型 class
            const iconName = FileUtils.getFileIcon(fileName, file.file_type);
            const typeClass = FileUtils.getFileTypeClass(fileName, file.file_type);
            const fileSize = FileUtils.formatFileSize(file.file_size);
            const hasNas = !!file.nas_path;

            return `
                <div class="linebot-file-card ${hasNas ? '' : 'expired'}" data-id="${file.id}">
                    <div class="file-icon-wrapper ${typeClass}">
                        <span class="icon">${getIcon(iconName)}</span>
                    </div>
                    <div class="linebot-file-info">
                        <div class="linebot-file-name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div>
                        <div class="linebot-file-meta">
                            ${fileSize !== '-' ? `<span>${fileSize}</span>` : ''}
                            ${hasNas
                                ? `<span class="storage-badge nas">NAS</span>`
                                : `<span class="storage-badge expired">已過期</span>`
                            }
                        </div>
                        <div class="linebot-file-source">
                            <span class="icon">${getIcon(file.group_name ? 'account-group' : 'account')}</span>
                            ${file.group_name || '個人'}
                            <span class="linebot-file-date">${new Date(file.created_at).toLocaleDateString()}</span>
                        </div>
                    </div>
                    <div class="linebot-file-actions">
                        ${hasNas ? `
                            <button class="file-icon-btn" data-action="preview" title="預覽">
                                <span class="icon">${getIcon('eye')}</span>
                            </button>
                            <button class="file-icon-btn" data-action="download" title="下載">
                                <span class="icon">${getIcon('download')}</span>
                            </button>
                        ` : ''}
                        <button class="file-icon-btn danger" data-action="delete" title="刪除">
                            <span class="icon">${getIcon('delete')}</span>
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        renderPagination('files');
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
            UIHelpers.showLoading(container, { text: '載入中…', variant: 'compact' });
        }
    }

    // 渲染錯誤（UIHelpers 統一元件）
    function renderError(type, message) {
        const selectors = {
            groups: '.linebot-groups-list',
            users: '.linebot-users-list',
            messages: '.linebot-messages-list',
            files: '.linebot-files-grid',
        };
        const container = document.querySelector(selectors[type]);

        if (container) {
            UIHelpers.showError(container, { message });
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

        // 載入資料（每次切換 tab 都重新載入，以反映平台篩選）
        if (tab === 'binding') {
            if (state.bindingStatus === null) loadBindingStatus();
        } else if (tab === 'groups') {
            loadGroups();
        } else if (tab === 'users') {
            loadUsers();
        } else if (tab === 'messages') {
            loadMessages();
        } else if (tab === 'files') {
            loadFiles();
        } else if (tab === 'blocklist') {
            loadBlocklist();
        }
    }

    // HTML 轉義
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 重新載入當前分頁資料（平台切換時使用）
    function reloadCurrentTab() {
        const tab = state.currentTab;
        // 清除快取，強制重新載入
        if (tab === 'groups') {
            state.groups = [];
            loadGroups();
        } else if (tab === 'users') {
            state.users = [];
            loadUsers();
        } else if (tab === 'messages') {
            state.messages = [];
            loadMessages();
        } else if (tab === 'files') {
            state.files = [];
            loadFiles();
        } else if (tab === 'blocklist') {
            state.blocklist = [];
            loadBlocklist();
        }
        // binding 不受平台篩選影響（已顯示所有平台）
    }

    // 初始化
    async function init(container) {
        // 重置 state（視窗重新打開時需要）
        state.currentTab = 'binding';
        state.platformFilter = null;
        state.groups = [];
        state.users = [];
        state.messages = [];
        state.files = [];
        state.selectedGroup = null;
        state.bindingStatus = null;
        state.blocklist = [];
        state.pagination = {
            groups: { page: 1, total: 0 },
            users: { page: 1, total: 0 },
            messages: { page: 1, total: 0 },
            files: { page: 1, total: 0 },
            blocklist: { page: 1, total: 0 },
        };

        container.innerHTML = `
            <div class="linebot-container">
                <div class="linebot-tabs">
                    <button class="linebot-tab active" data-tab="binding">我的綁定</button>
                    <button class="linebot-tab" data-tab="groups">群組</button>
                    <button class="linebot-tab" data-tab="users">用戶</button>
                    <button class="linebot-tab" data-tab="messages">訊息</button>
                    <button class="linebot-tab" data-tab="files">檔案</button>
                    <button class="linebot-tab" data-tab="blocklist">黑名單</button>
                </div>

                <div class="linebot-platform-filter">
                    <button class="linebot-platform-btn active" data-platform="">全部</button>
                    <button class="linebot-platform-btn" data-platform="line">
                        <span class="icon">${typeof getIcon !== 'undefined' ? getIcon('line') : 'L'}</span> Line
                    </button>
                    <button class="linebot-platform-btn" data-platform="telegram">
                        <span class="icon">${typeof getIcon !== 'undefined' ? getIcon('telegram') : 'T'}</span> Telegram
                    </button>
                </div>

                <div class="linebot-content">
                    <!-- 綁定面板 -->
                    <div class="linebot-panel active" data-panel="binding">
                        <div class="linebot-binding-content">
                            <div class="linebot-loading">載入中...</div>
                        </div>
                    </div>

                    <!-- 群組面板 -->
                    <div class="linebot-panel" data-panel="groups">
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
                    <!-- 黑名單面板 -->
                    <div class="linebot-panel" data-panel="blocklist">
                        <div class="linebot-blocklist-list"></div>
                        <div class="linebot-pagination linebot-pagination-blocklist"></div>
                    </div>
                </div>
            </div>
        `;

        // 綁定標籤點擊事件
        container.querySelectorAll('.linebot-tab').forEach(tab => {
            tab.addEventListener('click', () => switchTab(tab.dataset.tab));
        });

        // 綁定平台篩選事件
        container.querySelectorAll('.linebot-platform-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const platform = btn.dataset.platform || null;
                state.platformFilter = platform;

                // 更新按鈕樣式
                container.querySelectorAll('.linebot-platform-btn').forEach(b => {
                    b.classList.toggle('active', (b.dataset.platform || null) === platform);
                });

                // 重新載入當前分頁資料
                reloadCurrentTab();
            });
        });

        // 載入專案列表
        await loadProjects();

        // 載入綁定狀態（預設分頁）
        await loadBindingStatus();

        // 填充群組篩選器（需先載入群組）
        loadGroups().then(() => {
            updateGroupFilter();
            updateFilesFilter();
            renderGroupDetail();
        });

        // 設置檔案刪除事件
        setupFileDeleteEvents();

        // 處理頭像圖片載入失敗（使用 capture 因為 error 事件不冒泡）
        container.addEventListener('error', (e) => {
            if (e.target.tagName === 'IMG' && e.target.closest('.linebot-user-avatar, .linebot-group-avatar, .linebot-message-avatar, .linebot-binding-avatar, .linebot-detail-avatar')) {
                // 隱藏壞掉的圖片，顯示預設 emoji
                e.target.style.display = 'none';
                const parent = e.target.parentElement;
                if (parent && !parent.querySelector('.avatar-fallback')) {
                    const fallback = document.createElement('span');
                    fallback.className = 'avatar-fallback';
                    fallback.textContent = parent.classList.contains('linebot-group-avatar') ? '👥' : '👤';
                    parent.appendChild(fallback);
                }
            }
        }, true);
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
            const response = await fetch(`/api/bot/files/${fileId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${getToken()}`,
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

    // 刪除群組
    async function deleteGroup(groupId) {
        try {
            const response = await fetch(`/api/bot/groups/${groupId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${getToken()}`,
                },
            });

            if (!response.ok) {
                throw new Error('刪除失敗');
            }

            const result = await response.json();

            // 清除選擇狀態
            state.selectedGroup = null;

            // 重新載入群組列表
            await loadGroups(state.pagination.groups.page);

            // 更新詳情面板
            renderGroupDetail();

            // 手機版：關閉詳情面板
            closeGroupDetail();

            // 顯示成功訊息
            if (typeof NotificationModule !== 'undefined') {
                NotificationModule.show({
                    title: '刪除成功',
                    message: result.message,
                    icon: 'check',
                });
            } else {
                alert(result.message);
            }

            return true;
        } catch (error) {
            console.error('刪除群組失敗:', error);
            alert('刪除群組失敗：' + error.message);
            return false;
        }
    }

    // 確認刪除群組對話框
    function confirmDeleteGroup(groupId, groupName) {
        const confirmed = confirm(
            `確定要刪除群組「${groupName}」嗎？\n\n` +
            `此操作將刪除：\n` +
            `• 群組記錄\n` +
            `• 所有訊息記錄\n` +
            `• 所有檔案記錄\n\n` +
            `（NAS 上的實體檔案會保留）\n\n` +
            `此操作無法復原！`
        );
        if (confirmed) {
            deleteGroup(groupId);
        }
    }

    // 設置檔案事件委派
    function setupFileDeleteEvents() {
        const container = document.querySelector('.linebot-files-grid');
        if (!container) return;

        // 點擊按鈕
        container.addEventListener('click', (e) => {
            const btn = e.target.closest('.file-icon-btn');
            if (!btn) return;

            e.preventDefault();
            e.stopPropagation();

            const action = btn.dataset.action;
            const card = btn.closest('.linebot-file-card');
            const fileId = card?.dataset.id;
            const file = state.files.find(f => f.id === fileId);

            if (!file) return;

            switch (action) {
                case 'preview':
                    openFile(file);
                    break;
                case 'download':
                    FileUtils.downloadWithAuth(`/api/bot/files/${file.id}/download`, file.file_name);
                    break;
                case 'delete':
                    const fileName = card?.querySelector('.linebot-file-name')?.textContent || '此檔案';
                    confirmDeleteFile(file.id, fileName);
                    break;
            }
        });

        // 雙擊開啟檔案
        container.addEventListener('dblclick', (e) => {
            const card = e.target.closest('.linebot-file-card');
            if (!card) return;

            // 避免在按鈕上雙擊時觸發
            if (e.target.closest('.linebot-file-actions')) return;

            const fileId = card.dataset.id;
            const file = state.files.find(f => f.id === fileId);
            if (!file || !file.nas_path) {
                NotificationModule?.show?.('此檔案無法開啟', 'warning');
                return;
            }

            openFile(file);
        });
    }

    // 開啟檔案（使用 FileOpener）
    function openFile(file) {
        if (!file.nas_path) {
            NotificationModule?.show?.('此檔案無法開啟', 'warning');
            return;
        }

        let fileName = file.file_name || `${file.file_type}_${file.id.slice(0, 8)}`;
        const fileUrl = `/api/bot/files/${file.id}/download`;

        // 如果檔名沒有副檔名，根據 file_type 加上預設副檔名
        if (!fileName.includes('.')) {
            const defaultExt = { image: '.jpg', video: '.mp4', audio: '.mp3', file: '.bin' };
            fileName += defaultExt[file.file_type] || '';
        }

        // 使用 FileOpener 開啟
        if (typeof FileOpener !== 'undefined' && FileOpener.canOpen(fileName)) {
            FileOpener.open(fileUrl, fileName);
        } else {
            // 不支援的類型，直接下載
            FileUtils.downloadWithAuth(fileUrl, fileName);
        }
    }

    return {
        init,
        loadGroups,
        loadUsers,
        loadMessages,
        loadFiles,
        setupFileDeleteEvents,
        closeGroupDetail,
    };
})();

// 匯出供 desktop.js 使用
window.LineBotApp = LineBotApp;
