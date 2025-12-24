/**
 * ChingTech OS - Settings Application
 * 系統設定應用程式：主題設定、偏好管理
 */

const SettingsApp = (function () {
  'use strict';

  const APP_ID = 'settings';
  let currentWindowId = null;

  /**
   * 取得視窗內容 HTML
   * @returns {string}
   */
  function getWindowContent() {
    const currentTheme = ThemeManager.getTheme();

    return `
      <div class="settings-container">
        <nav class="settings-sidebar">
          <ul class="settings-nav">
            <li class="settings-nav-item active" data-section="appearance">
              <span class="icon">${getIcon('palette')}</span>
              <span>外觀</span>
            </li>
          </ul>
        </nav>

        <main class="settings-content">
          <!-- 外觀設定 -->
          <section class="settings-section active" id="section-appearance">
            <h2 class="settings-section-title">外觀設定</h2>

            <div class="settings-group">
              <h3 class="settings-group-title">主題</h3>
              <div class="theme-cards">
                <div class="theme-card ${currentTheme === 'dark' ? 'selected' : ''}" data-theme="dark">
                  <div class="theme-card-preview">
                    <div class="preview-header"></div>
                    <div class="preview-content">
                      <div class="preview-accent"></div>
                    </div>
                  </div>
                  <div class="theme-card-info">
                    <span class="theme-card-name">暗色主題</span>
                    <span class="theme-card-check">
                      <span class="icon">${getIcon('check')}</span>
                    </span>
                  </div>
                </div>

                <div class="theme-card ${currentTheme === 'light' ? 'selected' : ''}" data-theme="light">
                  <div class="theme-card-preview">
                    <div class="preview-header"></div>
                    <div class="preview-content">
                      <div class="preview-accent"></div>
                    </div>
                  </div>
                  <div class="theme-card-info">
                    <span class="theme-card-name">亮色主題</span>
                    <span class="theme-card-check">
                      <span class="icon">${getIcon('check')}</span>
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div class="settings-group">
              <h3 class="settings-group-title">預覽</h3>
              <div class="preview-panel">
                <div class="preview-panel-title">UI 元件預覽</div>
                <div class="preview-elements">
                  <div class="preview-element">
                    <span class="preview-element-label">按鈕</span>
                    <div style="display: flex; gap: 8px;">
                      <button class="btn btn-primary">主要</button>
                      <button class="btn btn-accent">強調</button>
                      <button class="btn btn-ghost">幽靈</button>
                    </div>
                  </div>

                  <div class="preview-element">
                    <span class="preview-element-label">標籤</span>
                    <div class="preview-badges">
                      <span class="preview-badge success">已完成</span>
                      <span class="preview-badge warning">待處理</span>
                      <span class="preview-badge error">緊急</span>
                      <span class="preview-badge info">進行中</span>
                    </div>
                  </div>

                  <div class="preview-element">
                    <span class="preview-element-label">輸入框</span>
                    <input type="text" class="input preview-input" placeholder="輸入文字...">
                  </div>
                </div>
              </div>
            </div>
          </section>
        </main>
      </div>
    `;
  }

  /**
   * 初始化設定視窗
   * @param {HTMLElement} windowEl - 視窗元素
   */
  function init(windowEl) {
    // 綁定主題卡片點擊事件
    const themeCards = windowEl.querySelectorAll('.theme-card');
    themeCards.forEach(card => {
      card.addEventListener('click', () => {
        const theme = card.dataset.theme;
        selectTheme(windowEl, theme);
      });
    });

    // 綁定側邊欄導航
    const navItems = windowEl.querySelectorAll('.settings-nav-item');
    navItems.forEach(item => {
      item.addEventListener('click', () => {
        const section = item.dataset.section;
        switchSection(windowEl, section);
      });
    });
  }

  /**
   * 選擇主題（即時套用並儲存）
   * @param {HTMLElement} windowEl
   * @param {string} theme
   */
  function selectTheme(windowEl, theme) {
    // 更新 UI 選中狀態
    const themeCards = windowEl.querySelectorAll('.theme-card');
    themeCards.forEach(card => {
      card.classList.toggle('selected', card.dataset.theme === theme);
    });

    // 即時套用並儲存主題
    ThemeManager.setTheme(theme);
  }

  /**
   * 切換設定區段
   * @param {HTMLElement} windowEl
   * @param {string} sectionId
   */
  function switchSection(windowEl, sectionId) {
    // 更新導航狀態
    const navItems = windowEl.querySelectorAll('.settings-nav-item');
    navItems.forEach(item => {
      item.classList.toggle('active', item.dataset.section === sectionId);
    });

    // 切換顯示區段
    const sections = windowEl.querySelectorAll('.settings-section');
    sections.forEach(section => {
      section.classList.toggle('active', section.id === `section-${sectionId}`);
    });
  }

  /**
   * 開啟設定應用程式
   */
  function open() {
    // 如果已開啟，則聚焦
    if (currentWindowId) {
      const windowEl = document.getElementById(currentWindowId);
      if (windowEl) {
        WindowModule.focusWindow(currentWindowId);
        return currentWindowId;
      }
    }

    // 建立新視窗
    currentWindowId = WindowModule.createWindow({
      title: '系統設定',
      appId: APP_ID,
      icon: 'settings',
      width: 700,
      height: 500,
      content: getWindowContent(),
      onInit: (windowEl, windowId) => {
        init(windowEl);
      },
      onClose: (windowId) => {
        currentWindowId = null;
      }
    });

    return currentWindowId;
  }

  // 公開 API
  return {
    open
  };
})();
