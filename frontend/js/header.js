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
