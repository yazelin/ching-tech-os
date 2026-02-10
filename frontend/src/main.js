/**
 * src/main.js — Vite 建置入口
 *
 * 此檔案為 Vite 的 JavaScript 入口點。
 * 透過 entry-compat.js 載入所有既有 IIFE 腳本（保守遷移策略）。
 *
 * 未來可在此處逐步加入：
 *   - CSS import（將 <link> 標籤遷移至 JS import）
 *   - 新的 ES module
 *   - 動態 import() 做 code splitting
 */

// 載入相容性入口（按原始順序匯入所有既有腳本）
import './js/entry-compat.js';

// ─── 初始化 Header Icons ───
// 原本位於 index.html 的 inline <script>
document.getElementById('iconClock').innerHTML = getIcon('clock-outline');
document.getElementById('iconMessages').innerHTML = getIcon('bell-outline');
document.getElementById('iconUser').innerHTML = getIcon('account-circle');
document.getElementById('iconLogout').innerHTML = getIcon('logout');

// ─── DOMContentLoaded 初始化 ───
// 原本位於 index.html 的 inline <script>
document.addEventListener('DOMContentLoaded', async function () {
  // 先檢查本地 session
  if (!LoginModule.isLoggedIn()) {
    window.location.href = 'login.html';
    return;
  }

  // 與後端驗證 session 是否仍有效
  const isValid = await LoginModule.validateSession();
  if (!isValid) {
    window.location.href = 'login.html';
    return;
  }

  // 載入使用者資訊（包含權限）
  await PermissionsModule.init();

  // Initialize all modules
  WindowModule.init();
  HeaderModule.init();
  DesktopModule.init();
  TaskbarModule.init();
  SocketClient.connect();
});
