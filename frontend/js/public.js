/**
 * 公開分享頁面邏輯
 * 完全獨立，不依賴其他模組
 */

(function() {
    'use strict';

    // ============================================
    // 工具函式
    // ============================================

    /**
     * 取得 URL 參數
     */
    function getUrlParam(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    }

    /**
     * 取得 API 基礎路徑（處理子路徑部署）
     */
    function getApiBase() {
        // 從當前 URL 推斷 base path
        const path = window.location.pathname;
        // 如果路徑包含 /ctos/，則 base path 是 /ctos
        const match = path.match(/^(\/[^/]+)?\/public\.html/);
        if (match && match[1]) {
            return match[1];
        }
        // 檢查是否在 /s/ 路徑下
        const sMatch = path.match(/^(\/[^/]+)?\/s\//);
        if (sMatch && sMatch[1]) {
            return sMatch[1];
        }
        return '';
    }

    /**
     * 發送 API 請求
     */
    async function fetchApi(endpoint) {
        const base = getApiBase();
        const url = `${base}${endpoint}`;
        const response = await fetch(url);
        return response;
    }

    /**
     * 格式化日期
     */
    function formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        return date.toLocaleDateString('zh-TW', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
    }

    /**
     * 格式化日期時間
     */
    function formatDateTime(dateStr) {
        if (!dateStr) return '';
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
     * 將表格包裹在可捲動的容器中（解決手機版表格被截斷問題）
     */
    function wrapTablesForScroll(containerEl) {
        const tables = containerEl.querySelectorAll('table');
        tables.forEach(table => {
            // 如果已經被包裹，跳過
            if (table.parentElement.classList.contains('table-wrapper')) {
                return;
            }
            const wrapper = document.createElement('div');
            wrapper.className = 'table-wrapper';
            table.parentNode.insertBefore(wrapper, table);
            wrapper.appendChild(table);
        });
    }

    /**
     * 取得附件圖示
     */
    function getAttachmentIcon(type, filename) {
        const ext = filename.split('.').pop().toLowerCase();

        // 圖片
        if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].includes(ext)) {
            return '🖼️';
        }
        // PDF
        if (ext === 'pdf') {
            return '📄';
        }
        // 文件
        if (['doc', 'docx', 'txt', 'md'].includes(ext)) {
            return '📝';
        }
        // 表格
        if (['xls', 'xlsx', 'csv'].includes(ext)) {
            return '📊';
        }
        // 簡報
        if (['ppt', 'pptx'].includes(ext)) {
            return '📽️';
        }
        // 壓縮檔
        if (['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) {
            return '📦';
        }
        // 預設
        return '📎';
    }

    /**
     * 格式化檔案大小
     */
    function formatFileSize(sizeStr) {
        if (!sizeStr) return '';
        return sizeStr;
    }

    // ============================================
    // DOM 元素
    // ============================================

    const loadingEl = document.getElementById('loading');
    const errorPageEl = document.getElementById('error-page');
    const errorTitleEl = document.getElementById('error-title');
    const errorMessageEl = document.getElementById('error-message');
    const contentEl = document.getElementById('content-container');
    const docTitleEl = document.getElementById('doc-title');
    const docMetaEl = document.getElementById('doc-meta-info');
    const docContentEl = document.getElementById('doc-content');
    const attachmentsSectionEl = document.getElementById('attachments-section');
    const attachmentsListEl = document.getElementById('attachments-list');
    const milestonesSectionEl = document.getElementById('milestones-section');
    const milestonesListEl = document.getElementById('milestones-list');
    const membersSectionEl = document.getElementById('members-section');
    const membersListEl = document.getElementById('members-list');
    const relatedSectionEl = document.getElementById('related-section');
    const relatedListEl = document.getElementById('related-list');
    const footerInfoEl = document.getElementById('footer-info');
    const printBtn = document.getElementById('print-btn');
    const imageModal = document.getElementById('image-modal');
    const imageModalImg = document.getElementById('image-modal-img');

    // ============================================
    // 渲染函式
    // ============================================

    /**
     * 顯示錯誤
     */
    function showError(title, message) {
        loadingEl.style.display = 'none';
        contentEl.style.display = 'none';
        errorPageEl.style.display = 'flex';
        errorTitleEl.textContent = title;
        errorMessageEl.textContent = message;
    }

    /**
     * 渲染知識庫內容
     */
    function renderKnowledge(data, sharedBy, sharedAt, expiresAt) {
        // 標題
        docTitleEl.textContent = data.title;

        // 元資訊
        docMetaEl.textContent = `分享者：${sharedBy} | ${formatDateTime(sharedAt)}`;

        // Markdown 內容
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                highlight: function(code, lang) {
                    if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
                        return hljs.highlight(code, { language: lang }).value;
                    }
                    return code;
                },
                breaks: true,
                gfm: true
            });
            docContentEl.innerHTML = marked.parse(data.content || '');
            // 包裹表格以支援手機版水平捲動
            wrapTablesForScroll(docContentEl);
        } else {
            docContentEl.innerHTML = `<pre>${data.content || ''}</pre>`;
        }

        // 附件
        if (data.attachments && data.attachments.length > 0) {
            attachmentsSectionEl.style.display = 'block';
            renderAttachments(data.attachments);
        }

        // 相關知識
        if (data.related && data.related.length > 0) {
            relatedSectionEl.style.display = 'block';
            renderRelated(data.related);
        }

        // 底部資訊
        updateFooter(sharedBy, expiresAt);
    }

    /**
     * 渲染專案內容
     */
    function renderProject(data, sharedBy, sharedAt, expiresAt) {
        // 標題
        docTitleEl.textContent = data.name;

        // 元資訊
        const statusText = {
            'active': '進行中',
            'completed': '已完成',
            'on_hold': '暫停',
            'cancelled': '已取消'
        }[data.status] || data.status;
        docMetaEl.textContent = `狀態：${statusText} | 分享者：${sharedBy}`;

        // 描述
        if (data.description) {
            if (typeof marked !== 'undefined') {
                docContentEl.innerHTML = marked.parse(data.description);
                // 包裹表格以支援手機版水平捲動
                wrapTablesForScroll(docContentEl);
            } else {
                docContentEl.innerHTML = `<p>${data.description}</p>`;
            }
        } else {
            docContentEl.innerHTML = '<p class="no-content">暫無描述</p>';
        }

        // 里程碑
        if (data.milestones && data.milestones.length > 0) {
            milestonesSectionEl.style.display = 'block';
            renderMilestones(data.milestones);
        }

        // 成員
        if (data.members && data.members.length > 0) {
            membersSectionEl.style.display = 'block';
            renderMembers(data.members);
        }

        // 底部資訊
        updateFooter(sharedBy, expiresAt);
    }

    /**
     * 渲染附件列表
     */
    function renderAttachments(attachments) {
        attachmentsListEl.innerHTML = attachments.map(att => {
            const filename = att.path.split('/').pop();
            const icon = getAttachmentIcon(att.type, filename);
            const isImage = ['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(
                filename.split('.').pop().toLowerCase()
            );
            // 顯示描述或檔名
            const displayName = att.description || filename;

            return `
                <div class="attachment-item" data-path="${att.path}" data-is-image="${isImage}">
                    <div class="attachment-icon">${icon}</div>
                    <div class="attachment-info">
                        <div class="attachment-name">${displayName}</div>
                        ${att.description ? `<div class="attachment-filename">${filename}</div>` : ''}
                    </div>
                    ${att.size ? `<div class="attachment-size">${formatFileSize(att.size)}</div>` : ''}
                    <div class="attachment-actions">
                        ${isImage ? '<button class="attachment-btn preview-btn">預覽</button>' : ''}
                        <button class="attachment-btn download-btn">下載</button>
                    </div>
                </div>
            `;
        }).join('');

        // 綁定事件
        attachmentsListEl.querySelectorAll('.attachment-item').forEach(item => {
            const path = item.dataset.path;
            const isImage = item.dataset.isImage === 'true';

            item.querySelector('.preview-btn')?.addEventListener('click', (e) => {
                e.stopPropagation();
                previewImage(path);
            });

            item.querySelector('.download-btn')?.addEventListener('click', (e) => {
                e.stopPropagation();
                downloadAttachment(path);
            });
        });
    }

    /**
     * 渲染里程碑列表
     */
    function renderMilestones(milestones) {
        milestonesListEl.innerHTML = milestones.map(m => {
            let statusIcon, statusClass;

            if (m.actual_date) {
                statusIcon = '✅';
                statusClass = 'milestone-completed';
            } else if (m.status === 'delayed') {
                statusIcon = '🔴';
                statusClass = 'milestone-delayed';
            } else if (m.status === 'in_progress') {
                statusIcon = '🔵';
                statusClass = 'milestone-in-progress';
            } else {
                statusIcon = '⚪';
                statusClass = 'milestone-pending';
            }

            const dateText = m.actual_date
                ? formatDate(m.actual_date)
                : m.planned_date
                    ? `預計 ${formatDate(m.planned_date)}`
                    : '';

            return `
                <div class="milestone-item">
                    <div class="milestone-status ${statusClass}">${statusIcon}</div>
                    <div class="milestone-info">
                        <div class="milestone-name">${m.name}</div>
                        <div class="milestone-date">${dateText}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * 渲染成員列表
     */
    function renderMembers(members) {
        membersListEl.innerHTML = members.map(m => {
            const initial = m.name.charAt(0);
            return `
                <div class="member-item">
                    <div class="member-avatar">${initial}</div>
                    <div class="member-info">
                        <div class="member-name">${m.name}</div>
                        <div class="member-role">${m.role || ''}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * 渲染相關知識
     */
    function renderRelated(relatedIds) {
        // 目前只顯示 ID，因為沒有公開連結資訊
        relatedListEl.innerHTML = relatedIds.map(id => {
            return `<li>${id}</li>`;
        }).join('');
    }

    /**
     * 渲染 NAS 檔案內容
     */
    function renderNasFile(data, sharedBy, sharedAt, expiresAt) {
        const base = getApiBase();
        const downloadUrl = `${base}${data.download_url}`;
        const ext = data.file_name.split('.').pop().toLowerCase();

        // HTML 簡報：直接在 iframe 中顯示（全螢幕模式）
        if (ext === 'html' || ext === 'htm') {
            // 隱藏一般的內容容器，改用全螢幕 iframe
            document.querySelector('.public-header').style.display = 'none';
            document.querySelector('.public-footer').style.display = 'none';
            contentEl.style.display = 'none';
            loadingEl.style.display = 'none';

            // 建立全螢幕 iframe
            const iframe = document.createElement('iframe');
            iframe.src = downloadUrl;
            iframe.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; border: none; z-index: 9999;';
            document.body.appendChild(iframe);
            return;
        }

        // 標題
        docTitleEl.textContent = data.file_name;

        // 元資訊
        docMetaEl.textContent = `分享者：${sharedBy} | ${formatDateTime(sharedAt)}`;

        // 檔案資訊與下載
        const icon = getAttachmentIcon('file', data.file_name);

        docContentEl.innerHTML = `
            <div class="nas-file-container">
                <div class="nas-file-icon">${icon}</div>
                <div class="nas-file-info">
                    <div class="nas-file-name">${data.file_name}</div>
                    <div class="nas-file-size">${data.file_size_str}</div>
                </div>
                <a href="${downloadUrl}" class="nas-file-download-btn" download="${data.file_name}">
                    下載檔案
                </a>
            </div>
        `;

        // 底部資訊
        updateFooter(sharedBy, expiresAt);
    }

    /**
     * 更新底部資訊
     */
    function updateFooter(sharedBy, expiresAt) {
        let text = `此內容由 ${sharedBy} 分享`;
        if (expiresAt) {
            text += ` | 連結有效至 ${formatDateTime(expiresAt)}`;
        }
        footerInfoEl.textContent = text;
    }

    // ============================================
    // 附件操作
    // ============================================

    let currentToken = '';

    /**
     * 預覽圖片
     */
    function previewImage(path) {
        const base = getApiBase();
        const url = `${base}/api/public/${currentToken}/attachments/${path}`;
        imageModalImg.src = url;
        imageModal.style.display = 'flex';
    }

    /**
     * 下載附件
     */
    function downloadAttachment(path) {
        const base = getApiBase();
        const url = `${base}/api/public/${currentToken}/attachments/${path}`;
        const filename = path.split('/').pop();

        // 建立隱藏的 a 標籤來下載
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    // ============================================
    // 事件綁定
    // ============================================

    // 列印按鈕
    printBtn?.addEventListener('click', () => {
        window.print();
    });

    // 圖片 Modal 關閉
    imageModal?.addEventListener('click', (e) => {
        if (e.target === imageModal ||
            e.target.classList.contains('image-modal-backdrop') ||
            e.target.classList.contains('image-modal-close')) {
            imageModal.style.display = 'none';
            imageModalImg.src = '';
        }
    });

    // ESC 關閉 Modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && imageModal.style.display === 'flex') {
            imageModal.style.display = 'none';
            imageModalImg.src = '';
        }
    });

    // ============================================
    // 初始化
    // ============================================

    async function init() {
        // 取得 token
        let token = getUrlParam('t');

        // 如果沒有 t 參數，嘗試從路徑取得（/s/{token}）
        if (!token) {
            const pathMatch = window.location.pathname.match(/\/s\/([a-zA-Z0-9]+)/);
            if (pathMatch) {
                token = pathMatch[1];
            }
        }

        if (!token) {
            showError('連結無效', '缺少必要的參數');
            return;
        }

        currentToken = token;

        try {
            const response = await fetchApi(`/api/public/${token}`);

            if (!response.ok) {
                const data = await response.json().catch(() => ({}));

                if (response.status === 404) {
                    showError('連結無效', data.detail || '此連結不存在或已被撤銷');
                } else if (response.status === 410) {
                    showError('連結已過期', data.detail || '此連結已過期，請聯繫分享者重新產生');
                } else {
                    showError('載入失敗', data.detail || '無法載入內容');
                }
                return;
            }

            const result = await response.json();

            // 隱藏載入中，顯示內容
            loadingEl.style.display = 'none';
            contentEl.style.display = 'block';

            // 根據類型渲染
            if (result.type === 'knowledge') {
                renderKnowledge(result.data, result.shared_by, result.shared_at, result.expires_at);
            } else if (result.type === 'project') {
                renderProject(result.data, result.shared_by, result.shared_at, result.expires_at);
            } else if (result.type === 'nas_file' || result.type === 'project_attachment') {
                // NAS 檔案和專案附件使用相同的渲染方式
                renderNasFile(result.data, result.shared_by, result.shared_at, result.expires_at);
            } else {
                showError('不支援的類型', `無法顯示此類型的內容：${result.type}`);
            }

        } catch (error) {
            console.error('載入錯誤:', error);
            showError('載入失敗', '發生網路錯誤，請稍後再試');
        }
    }

    // 頁面載入後初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
