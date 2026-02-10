/**
 * 通知模組 - Toast 通知系統
 */
const NotificationModule = (function () {
  // 通知容器
  let container = null;

  /**
   * 初始化通知容器
   * 樣式已抽出至 css/notification.css，此處僅建立 DOM 容器
   */
  function init() {
    if (container) return;

    container = document.createElement('div');
    container.className = 'notification-container';
    document.body.appendChild(container);
  }

  /**
   * 顯示 Toast 通知
   * @param {Object} options - 通知選項
   * @param {string} options.title - 標題
   * @param {string} options.message - 訊息內容
   * @param {string} [options.icon] - 圖示名稱（MDI icon name）
   * @param {number} [options.duration] - 顯示時間（毫秒），0 表示不自動關閉
   * @param {Function} [options.onClick] - 點擊回調
   * @returns {HTMLElement} - 通知元素
   */
  function show(options) {
    init();

    const {
      title = '',
      message = '',
      icon = 'robot',
      duration = 5000,
      onClick = null,
    } = options;

    // 建立通知元素
    const toast = document.createElement('div');
    toast.className = 'notification-toast';

    // 圖示
    const iconEl = document.createElement('div');
    iconEl.className = 'notification-icon';
    iconEl.innerHTML = typeof getIcon === 'function' ? getIcon(icon) : '';

    // 內容
    const contentEl = document.createElement('div');
    contentEl.className = 'notification-content';

    if (title) {
      const titleEl = document.createElement('div');
      titleEl.className = 'notification-title';
      titleEl.textContent = title;
      contentEl.appendChild(titleEl);
    }

    if (message) {
      const messageEl = document.createElement('div');
      messageEl.className = 'notification-message';
      messageEl.textContent = message;
      contentEl.appendChild(messageEl);
    }

    // 關閉按鈕
    const closeBtn = document.createElement('button');
    closeBtn.className = 'notification-close';
    closeBtn.innerHTML = typeof getIcon === 'function' ? getIcon('close') : 'x';
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      hide(toast);
    });

    // 組裝
    toast.appendChild(iconEl);
    toast.appendChild(contentEl);
    toast.appendChild(closeBtn);

    // 點擊處理
    if (onClick) {
      toast.addEventListener('click', () => {
        onClick();
        hide(toast);
      });
    }

    // 加入容器
    container.appendChild(toast);

    // 觸發動畫
    requestAnimationFrame(() => {
      toast.classList.add('show');
    });

    // 自動關閉
    if (duration > 0) {
      setTimeout(() => hide(toast), duration);
    }

    return toast;
  }

  /**
   * 隱藏通知
   * @param {HTMLElement} toast - 通知元素
   */
  function hide(toast) {
    if (!toast || toast.classList.contains('hiding')) return;

    toast.classList.add('hiding');
    toast.classList.remove('show');

    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }

  /**
   * AI 助手回應通知
   * @param {string} chatId - 對話 ID
   */
  function showAIResponse(chatId) {
    show({
      title: 'AI 助手',
      message: '已回覆您的訊息',
      icon: 'robot',
      duration: 8000,
      onClick: () => {
        // 開啟 AI 助手視窗並切換到對應對話
        if (typeof AIAssistantApp !== 'undefined') {
          AIAssistantApp.open();
          if (chatId) {
            AIAssistantApp.switchToChat(chatId);
          }
        }
      },
    });
  }

  return {
    init,
    show,
    hide,
    showAIResponse,
  };
})();
