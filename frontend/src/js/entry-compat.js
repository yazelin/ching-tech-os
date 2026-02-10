/**
 * entry-compat.js — 相容性入口（過渡期使用）
 *
 * 策略說明：
 *   此檔案以 side-effect import 的方式，按原始 index.html 中的載入順序
 *   匯入所有既有 IIFE / Revealing Module 腳本。
 *   Vite build 時 Rollup 會將它們合併為單一 chunk，
 *   大幅減少首屏 HTTP 請求數（30+ → 1~2）。
 *
 *   現階段「不」重構任何 IIFE 為 ES export；
 *   模組內部的 const（如 DesktopModule）在 Rollup bundle 後
 *   會存在同一函式作用域中，互相可見，因此全域引用不會斷裂。
 *
 * 日後遷移路線：
 *   逐步將各 IIFE 改為 named export，並在此檔案改用 named import。
 *
 * 注意：CDN 外部相依（marked / socket.io / xterm）仍透過
 *       index.html 中的非 module <script> 載入，它們會先於
 *       type="module" 執行，因此全域變數（marked, io, Terminal）
 *       在此入口執行時已可用。
 */

// ─── 基礎設施 ───
import '../../js/config.js';
import '../../js/icons.js';
import '../../js/ui-helpers.js';         // 統一回饋狀態元件（依賴 icons.js 的 getIcon）
import '../../js/file-utils.js';
import '../../js/path-utils.js';

// ─── 核心模組 ───
import '../../js/login.js';
import '../../js/header.js';
import '../../js/window.js';
import '../../js/notification.js';
import '../../js/socket-client.js';
import '../../js/api-client.js';
import '../../js/theme.js';
import '../../js/user-profile.js';

// ─── 應用程式 ───
import '../../js/ai-assistant.js';
import '../../js/image-viewer.js';
import '../../js/text-viewer.js';
import '../../js/pdf-viewer.js';
import '../../js/file-opener.js';
import '../../js/file-manager.js';
import '../../js/terminal.js';
import '../../js/code-editor.js';
import '../../js/external-app.js';
import '../../js/knowledge-base.js';
import '../../js/message-center.js';
import '../../js/settings.js';
import '../../js/prompt-editor.js';
import '../../js/agent-settings.js';
import '../../js/ai-log.js';
import '../../js/linebot.js';
import '../../js/permissions.js';
import '../../js/share-dialog.js';
import '../../js/share-manager.js';
import '../../js/memory-manager.js';

// ─── Command Palette / 全域搜尋 ───
import '../../js/command-palette.js';

// ─── 桌面 & Taskbar（最後載入，因為依賴上述模組） ───
import '../../js/desktop.js';
