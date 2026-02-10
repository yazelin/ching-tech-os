/**
 * 分享對話框模組
 * 提供知識庫與專案的公開分享連結功能
 */

const ShareDialogModule = (function() {
  'use strict';

  // QR Code 庫（使用 qrcode-generator）
  let qrcode = null;

  /**
   * 動態載入 QR Code 庫
   */
  async function loadQRCodeLib() {
    if (qrcode) return;

    return new Promise((resolve, reject) => {
      if (typeof qrcodegen !== 'undefined') {
        qrcode = qrcodegen;
        resolve();
        return;
      }

      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.min.js';
      script.onload = () => {
        qrcode = window.qrcode;
        resolve();
      };
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  /**
   * 產生 QR Code Canvas
   * @param {string} text - 要編碼的文字
   * @param {number} size - 尺寸（像素）
   * @returns {HTMLCanvasElement}
   */
  function generateQRCode(text, size = 150) {
    if (!qrcode) {
      console.error('QR Code library not loaded');
      return null;
    }

    const typeNumber = 0; // Auto
    const errorCorrectionLevel = 'M';
    const qr = qrcode(typeNumber, errorCorrectionLevel);
    qr.addData(text);
    qr.make();

    // 建立 canvas
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const cellSize = Math.floor(size / (qr.getModuleCount() + 2));
    const actualSize = cellSize * (qr.getModuleCount() + 2);

    canvas.width = actualSize;
    canvas.height = actualSize;

    // 繪製白色背景
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, actualSize, actualSize);

    // 繪製 QR Code
    ctx.fillStyle = '#000000';
    const moduleCount = qr.getModuleCount();
    for (let row = 0; row < moduleCount; row++) {
      for (let col = 0; col < moduleCount; col++) {
        if (qr.isDark(row, col)) {
          ctx.fillRect(
            (col + 1) * cellSize,
            (row + 1) * cellSize,
            cellSize,
            cellSize
          );
        }
      }
    }

    return canvas;
  }

  /**
   * 取得圖示 HTML（包含 .icon 包裝）
   * @param {string} name - 圖示名稱
   * @param {string} extraClass - 額外 class
   * @returns {string}
   */
  function icon(name, extraClass = '') {
    if (typeof window.icon === 'function') {
      return `<span class="icon ${extraClass}">${window.icon(name)}</span>`;
    }
    // Fallback
    return `<span class="icon ${extraClass}"><span class="mdi mdi-${name}"></span></span>`;
  }

  /**
   * 格式化日期時間
   * @param {string} dateStr - ISO 日期字串
   * @returns {string}
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
   * 複製文字到剪貼簿
   * @param {string} text - 要複製的文字
   * @returns {Promise<boolean>}
   */
  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      // Fallback
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      const result = document.execCommand('copy');
      document.body.removeChild(textarea);
      return result;
    }
  }

  /**
   * 建立分享連結 API 呼叫
   * @param {string} resourceType - 資源類型（knowledge/project）
   * @param {string} resourceId - 資源 ID
   * @param {number|null} expiresInHours - 過期時間（小時），null 為永不過期
   * @returns {Promise<Object>}
   */
  async function createShareLink(resourceType, resourceId, expiresInHours) {
    const token = typeof LoginModule !== 'undefined' ? LoginModule.getToken() : null;

    const response = await fetch('/api/share', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
      },
      body: JSON.stringify({
        resource_type: resourceType,
        resource_id: resourceId,
        expires_in_hours: expiresInHours
      })
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || '建立分享連結失敗');
    }

    return response.json();
  }

  /**
   * 顯示分享對話框
   * @param {Object} options - 選項
   * @param {string} options.resourceType - 資源類型（knowledge/project）
   * @param {string} options.resourceId - 資源 ID
   * @param {string} options.resourceTitle - 資源標題（用於顯示）
   */
  async function show(options) {
    const { resourceType, resourceId, resourceTitle } = options;

    // 載入 QR Code 庫
    try {
      await loadQRCodeLib();
    } catch (err) {
      console.error('Failed to load QR code library:', err);
    }

    // 建立對話框
    const overlay = document.createElement('div');
    overlay.className = 'share-dialog-overlay';
    overlay.innerHTML = `
      <div class="share-dialog">
        <div class="share-dialog-header">
          <h3>
            ${icon('share-variant')}
            分享「${escapeHtml(resourceTitle || '')}」
          </h3>
          <button class="share-dialog-close">${icon('close')}</button>
        </div>
        <div class="share-dialog-body">
          <div class="share-form">
            <div class="share-form-group">
              <label>連結有效期限</label>
              <select id="share-expires-select">
                <option value="1">1 小時</option>
                <option value="6">6 小時</option>
                <option value="24" selected>24 小時</option>
                <option value="72">3 天</option>
                <option value="168">7 天</option>
                <option value="720">30 天</option>
                <option value="">永不過期</option>
              </select>
            </div>
            <button class="share-create-btn" id="share-create-btn">
              ${icon('link-plus')}
              產生分享連結
            </button>
          </div>
        </div>
        <div class="share-dialog-footer">
          <button class="btn btn-ghost share-cancel-btn">關閉</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    // 動畫顯示
    requestAnimationFrame(() => {
      overlay.classList.add('show');
    });

    // 取得元素
    const expiresSelect = overlay.querySelector('#share-expires-select');
    const createBtn = overlay.querySelector('#share-create-btn');
    const closeBtn = overlay.querySelector('.share-dialog-close');
    const cancelBtn = overlay.querySelector('.share-cancel-btn');
    const body = overlay.querySelector('.share-dialog-body');

    // 關閉函式
    function close() {
      overlay.classList.remove('show');
      setTimeout(() => overlay.remove(), 200);
    }

    // 綁定關閉事件
    closeBtn.addEventListener('click', close);
    cancelBtn.addEventListener('click', close);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) close();
    });

    // ESC 關閉
    function handleKeydown(e) {
      if (e.key === 'Escape') {
        close();
        document.removeEventListener('keydown', handleKeydown);
      }
    }
    document.addEventListener('keydown', handleKeydown);

    // 產生連結
    createBtn.addEventListener('click', async () => {
      const expiresValue = expiresSelect.value;
      const expiresInHours = expiresValue ? parseInt(expiresValue) : null;

      // 顯示載入狀態
      /* [Sprint6] 原: <div class="share-loading">${icon('loading', 'mdi-spin')}... 正在產生分享連結... */
      UIHelpers.showLoading(body, { text: '正在產生分享連結...' });

      try {
        const result = await createShareLink(resourceType, resourceId, expiresInHours);
        showResult(body, result);
      } catch (error) {
        showError(body, error.message, () => {
          // 重試
          body.innerHTML = `
            <div class="share-form">
              <div class="share-form-group">
                <label>連結有效期限</label>
                <select id="share-expires-select">
                  <option value="1">1 小時</option>
                  <option value="6">6 小時</option>
                  <option value="24" selected>24 小時</option>
                  <option value="72">3 天</option>
                  <option value="168">7 天</option>
                  <option value="720">30 天</option>
                  <option value="">永不過期</option>
                </select>
              </div>
              <button class="share-create-btn" id="share-create-btn">
                ${icon('link-plus')}
                產生分享連結
              </button>
            </div>
          `;
          // 重新綁定事件
          const newBtn = body.querySelector('#share-create-btn');
          newBtn.addEventListener('click', arguments.callee);
        });
      }
    });
  }

  /**
   * 顯示分享結果
   * @param {HTMLElement} container - 容器
   * @param {Object} result - API 回應
   */
  function showResult(container, result) {
    const url = result.full_url;
    const expiresAt = result.expires_at;

    // 產生 QR Code
    let qrHtml = '';
    if (qrcode) {
      const canvas = generateQRCode(url, 180);
      if (canvas) {
        qrHtml = `
          <div class="share-qr-container">
            <div class="share-qr-code" id="share-qr-code"></div>
            <span class="share-qr-hint">掃描 QR Code 開啟連結</span>
          </div>
        `;
      }
    }

    container.innerHTML = `
      <div class="share-result">
        ${qrHtml}
        <div class="share-link-container">
          <span class="share-link-label">分享連結</span>
          <div class="share-link-input-group">
            <input type="text" class="share-link-input" value="${escapeHtml(url)}" readonly>
            <button class="share-copy-btn" id="share-copy-btn">
              ${icon('content-copy')}
              複製
            </button>
          </div>
        </div>
        <div class="share-expires-info">
          ${icon('clock-outline')}
          ${expiresAt ? `有效至 ${formatDateTime(expiresAt)}` : '永不過期'}
        </div>
      </div>
    `;

    // 插入 QR Code canvas
    if (qrcode && url) {
      const qrContainer = container.querySelector('#share-qr-code');
      if (qrContainer) {
        const canvas = generateQRCode(url, 180);
        if (canvas) {
          qrContainer.appendChild(canvas);
        }
      }
    }

    // 複製按鈕事件
    const copyBtn = container.querySelector('#share-copy-btn');
    const linkInput = container.querySelector('.share-link-input');

    copyBtn.addEventListener('click', async () => {
      const success = await copyToClipboard(url);
      if (success) {
        copyBtn.classList.add('copied');
        copyBtn.innerHTML = `${icon('check')} 已複製`;

        // 顯示 toast
        if (typeof DesktopModule !== 'undefined') {
          DesktopModule.showToast('連結已複製到剪貼簿', 'check');
        }

        setTimeout(() => {
          copyBtn.classList.remove('copied');
          copyBtn.innerHTML = `${icon('content-copy')} 複製`;
        }, 2000);
      }
    });

    // 點擊輸入框全選
    linkInput.addEventListener('click', () => {
      linkInput.select();
    });
  }

  /**
   * 顯示錯誤
   * @param {HTMLElement} container - 容器
   * @param {string} message - 錯誤訊息
   * @param {Function} onRetry - 重試回調
   */
  function showError(container, message, onRetry) {
    /* [Sprint6] 原: <div class="share-error">${icon('alert-circle')}... + retry btn */
    UIHelpers.showError(container, { message: escapeHtml(message), onRetry: onRetry });
  }

  /**
   * HTML 跳脫
   * @param {string} str
   * @returns {string}
   */
  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // 公開 API
  return {
    show
  };
})();
