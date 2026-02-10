/**
 * ChingTech OS - Header Module
 * Handles header bar functionality: time display, user info, logout
 */

const HeaderModule = (function() {
  'use strict';

  let timeInterval = null;
  let userMenuEl = null;
  let userMenuOpen = false;

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
   * Handle user name click - toggle user menu
   */
  function handleUserNameClick(e) {
    e.stopPropagation();
    if (userMenuOpen) {
      closeUserMenu();
    } else {
      openUserMenu();
    }
  }

  /**
   * 建立使用者下拉選單
   */
  function createUserMenu() {
    if (userMenuEl) return userMenuEl;

    userMenuEl = document.createElement('div');
    userMenuEl.className = 'header-user-menu';
    userMenuEl.innerHTML = `
      <button class="header-user-menu-item" data-action="profile">
        <span class="icon">${typeof getIcon === 'function' ? getIcon('account-circle') : ''}</span>
        <span>個人資料</span>
      </button>
      <div class="header-user-menu-divider"></div>
      <button class="header-user-menu-item" data-action="restart-onboarding">
        <span class="icon">${typeof getIcon === 'function' ? getIcon('refresh') : ''}</span>
        <span>重新導覽</span>
      </button>
    `;

    userMenuEl.addEventListener('click', function (e) {
      const item = e.target.closest('[data-action]');
      if (!item) return;

      const action = item.dataset.action;
      closeUserMenu();

      switch (action) {
        case 'profile':
          if (typeof UserProfileModule !== 'undefined') {
            UserProfileModule.open();
          }
          break;
        case 'restart-onboarding':
          if (typeof OnboardingModule !== 'undefined') {
            OnboardingModule.restart();
          }
          break;
      }
    });

    const userEl = document.querySelector('.header-user');
    if (userEl) {
      userEl.appendChild(userMenuEl);
    }

    return userMenuEl;
  }

  /**
   * 開啟使用者選單
   */
  function openUserMenu() {
    createUserMenu();
    userMenuOpen = true;
    userMenuEl.classList.add('open');

    setTimeout(() => {
      document.addEventListener('click', handleOutsideClick);
    }, 0);
  }

  /**
   * 關閉使用者選單
   */
  function closeUserMenu() {
    userMenuOpen = false;
    if (userMenuEl) {
      userMenuEl.classList.remove('open');
    }
    document.removeEventListener('click', handleOutsideClick);
  }

  /**
   * 點擊選單外部時關閉
   */
  function handleOutsideClick(e) {
    const userEl = document.querySelector('.header-user');
    if (userEl && !userEl.contains(e.target)) {
      closeUserMenu();
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

  // ─── Badge 微互動動畫 ───

  /**
   * 觸發 badge bump 動畫
   * 當 badge 數值更新時呼叫此函式，同時搖晃鈴鐺
   * @param {number} [count] - 新的 badge 數值（可選）
   */
  function triggerBadgeBump(count) {
    const badge = document.getElementById('messagesBadge');
    const btn = document.getElementById('messagesBtn');
    if (!badge) return;

    // 更新數值（若有傳入）
    if (typeof count === 'number') {
      badge.textContent = count > 99 ? '99+' : String(count);

      if (count > 0) {
        // 從隱藏到顯示 → 使用 appear 動畫
        if (badge.classList.contains('hidden')) {
          badge.classList.remove('hidden');
          badge.classList.add('badge-appear');
          badge.addEventListener('animationend', function onEnd() {
            badge.classList.remove('badge-appear');
            badge.removeEventListener('animationend', onEnd);
          });
          return;
        }
      } else {
        badge.classList.add('hidden');
        return;
      }
    }

    // Bump 動畫（移除再添加以重新觸發）
    badge.classList.remove('badge-bump');
    void badge.offsetWidth; // force reflow
    badge.classList.add('badge-bump');

    badge.addEventListener('animationend', function onEnd() {
      badge.classList.remove('badge-bump');
      badge.removeEventListener('animationend', onEnd);
    });

    // 鈴鐺搖晃
    if (btn) {
      btn.classList.remove('bell-ring');
      void btn.offsetWidth;
      btn.classList.add('bell-ring');
      btn.addEventListener('animationend', function onEnd() {
        btn.classList.remove('bell-ring');
        btn.removeEventListener('animationend', onEnd);
      });
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
    formatDate,
    triggerBadgeBump
  };
})();
