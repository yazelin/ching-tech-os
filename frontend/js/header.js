/**
 * ChingTech OS - Header Module
 * Handles header bar functionality: time display, user info, logout
 */

const HeaderModule = (function() {
  'use strict';

  let timeInterval = null;

  /**
   * Format current time as HH:MM:SS
   * @returns {string}
   */
  function formatTime() {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    return `${hours}:${minutes}:${seconds}`;
  }

  /**
   * Format current date as YYYY/MM/DD
   * @returns {string}
   */
  function formatDate() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}/${month}/${day}`;
  }

  /**
   * Update the time display
   */
  function updateTime() {
    const timeElement = document.getElementById('headerTime');
    if (timeElement) {
      timeElement.textContent = formatTime();
    }
  }

  /**
   * Start the time update interval
   */
  function startClock() {
    updateTime(); // Initial update
    timeInterval = setInterval(updateTime, 1000);
  }

  /**
   * Stop the time update interval
   */
  function stopClock() {
    if (timeInterval) {
      clearInterval(timeInterval);
      timeInterval = null;
    }
  }

  /**
   * Display the current user's name
   * Fetches display_name from API first, falls back to session username
   */
  async function displayUsername() {
    const userNameElement = document.getElementById('headerUserName');
    if (!userNameElement || typeof LoginModule === 'undefined') return;

    const session = LoginModule.getSession();
    if (!session || !session.username) return;

    // Try to fetch display_name from API first (avoid flicker)
    try {
      const token = LoginModule.getToken();
      if (token) {
        const response = await fetch('/api/user/me', {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
          const user = await response.json();
          userNameElement.textContent = user.display_name || session.username;
          return;
        }
      }
    } catch (error) {
      // Fall through to fallback
    }

    // Fallback: show username from session
    userNameElement.textContent = session.username;
  }

  /**
   * Display tenant information in header (if available)
   */
  function displayTenantInfo() {
    const tenantElement = document.getElementById('headerTenant');
    const tenantNameElement = document.getElementById('headerTenantName');
    const tenantDivider = document.getElementById('tenantDivider');

    if (!tenantElement || !tenantNameElement) return;

    // 檢查是否有租戶資訊
    if (typeof TenantContext !== 'undefined' && TenantContext.hasTenant()) {
      const tenantName = TenantContext.getTenantName();
      if (tenantName) {
        tenantNameElement.textContent = tenantName;
        tenantElement.style.display = '';
        if (tenantDivider) tenantDivider.style.display = '';
        return;
      }
    }

    // 嘗試從 LoginModule 取得
    if (typeof LoginModule !== 'undefined') {
      const tenant = LoginModule.getTenant();
      if (tenant && tenant.name) {
        tenantNameElement.textContent = tenant.name;
        tenantElement.style.display = '';
        if (tenantDivider) tenantDivider.style.display = '';
        return;
      }
    }

    // 隱藏租戶區塊
    tenantElement.style.display = 'none';
    if (tenantDivider) tenantDivider.style.display = 'none';
  }

  /**
   * Handle user name click - open profile window
   */
  function handleUserNameClick() {
    if (typeof UserProfileModule !== 'undefined') {
      UserProfileModule.open();
    }
  }

  /**
   * Handle logout button click
   */
  async function handleLogout() {
    if (typeof LoginModule !== 'undefined') {
      await LoginModule.logout();
    } else {
      window.location.href = 'login.html';
    }
  }

  /**
   * Handle messages button click - open message center
   */
  function handleMessagesClick() {
    if (typeof MessageCenterApp !== 'undefined') {
      MessageCenterApp.open();
    }
  }

  /**
   * Handle logo click - close current window and return to desktop
   */
  function handleLogoClick() {
    if (typeof WindowModule === 'undefined') return;

    // 取得最上層的視窗並關閉
    const windows = WindowModule.getWindows();
    const windowIds = Object.keys(windows);

    if (windowIds.length > 0) {
      // 找到最上層的視窗（z-index 最大）
      let topWindowId = windowIds[0];
      let topZIndex = 0;

      windowIds.forEach(id => {
        const zIndex = parseInt(windows[id].element.style.zIndex) || 0;
        if (zIndex > topZIndex) {
          topZIndex = zIndex;
          topWindowId = id;
        }
      });

      WindowModule.closeWindow(topWindowId);
    }
  }

  /**
   * Initialize header module
   */
  function init() {
    // Start clock
    startClock();

    // Display username
    displayUsername();

    // Display tenant info
    displayTenantInfo();

    // Attach logout handler
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', handleLogout);
    }

    // Attach user name click handler
    const userNameElement = document.getElementById('headerUserName');
    if (userNameElement) {
      userNameElement.style.cursor = 'pointer';
      userNameElement.addEventListener('click', handleUserNameClick);
    }

    // Attach messages button handler
    const messagesBtn = document.getElementById('messagesBtn');
    if (messagesBtn) {
      messagesBtn.addEventListener('click', handleMessagesClick);
    }

    // Load initial unread count
    if (typeof SocketClient !== 'undefined') {
      setTimeout(() => {
        SocketClient.updateMessageBadge();
      }, 1000);
    }

    // Attach logo click handler
    const logoElement = document.querySelector('.header-logo');
    if (logoElement) {
      logoElement.style.cursor = 'pointer';
      logoElement.addEventListener('click', handleLogoClick);
    }
  }

  /**
   * Cleanup function
   */
  function destroy() {
    stopClock();
  }

  // Public API
  return {
    init,
    destroy,
    formatTime,
    formatDate
  };
})();
