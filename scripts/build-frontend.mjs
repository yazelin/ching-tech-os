/**
 * build-frontend.mjs
 * ------------------
 * 使用 esbuild 將 frontend/ 下的 CSS / JS 合併＆壓縮，輸出至 frontend/dist/。
 *
 * 用法：
 *   npm run build          — 一次性建構
 *   npm run build:watch    — 監聽模式（開發用）
 *
 * 產出檔案：
 *   frontend/dist/index.bundle.css   — index.html 用 CSS bundle
 *   frontend/dist/login.bundle.css   — login.html 用 CSS bundle
 *   frontend/dist/login.bundle.js    — login.html 用 JS bundle
 *
 * 備註：index.html JS 已由 Vite (src/main.js) 管理，不再另外 bundle。
 */

import * as esbuild from 'esbuild';
import { readFileSync, mkdirSync, writeFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const FRONTEND = resolve(ROOT, 'frontend');
const DIST = resolve(FRONTEND, 'dist');

// ─── 檔案清單（與 HTML 引入順序一致） ───────────────────────

const INDEX_CSS = [
  'css/main.css',
  'css/header.css',
  'css/desktop.css',
  'css/window.css',
  'css/ai-assistant.css',
  'css/user-profile.css',
  'css/file-manager.css',
  'css/viewer.css',
  'css/terminal.css',
  'css/code-editor.css',
  'css/external-app.css',
  'css/knowledge-base.css',
  'css/project-management.css',
  'css/inventory-management.css',
  'css/vendor-manager.css',
  'css/message-center.css',
  'css/settings.css',
  'css/prompt-editor.css',
  'css/agent-settings.css',
  'css/ai-log.css',
  'css/linebot.css',
  'css/file-common.css',
  'css/share-dialog.css',
  'css/share-manager.css',
  'css/memory-manager.css',
  'css/notification.css',
];

// index.html JS 已由 Vite 管理（src/main.js），此處不再需要獨立 JS bundle。
// 若未來需回退 Vite，可取消下方註解並重新啟用 index JS bundle。
// const INDEX_JS = [ /* ... */ ];

const LOGIN_CSS = [
  'css/main.css',
  'css/login.css',
];

const LOGIN_JS = [
  'js/config.js',
  'js/icons.js',
  'js/path-utils.js',
  'js/theme.js',
  'js/matrix-rain.js',
  'js/device-fingerprint.js',
  'js/login.js',
];

// ─── 工具函式 ─────────────────────────────────────────────

/** 串接多個檔案內容，加上來源分隔註解 */
function concat(files, base, commentStyle = 'js') {
  return files.map((f) => {
    const abs = resolve(base, f);
    const src = readFileSync(abs, 'utf8');
    const marker =
      commentStyle === 'css'
        ? `/* ── ${f} ── */`
        : `// ── ${f} ──`;
    return `${marker}\n${src}`;
  }).join('\n\n');
}

// ─── 主程式 ────────────────────────────────────────────────

async function build() {
  mkdirSync(DIST, { recursive: true });

  const startTime = Date.now();
  const results = [];

  // --- index.bundle.css ---
  const indexCssSrc = concat(INDEX_CSS, FRONTEND, 'css');
  const indexCssResult = await esbuild.transform(indexCssSrc, {
    loader: 'css',
    minify: true,
    sourcefile: 'index.bundle.css',
  });
  writeFileSync(resolve(DIST, 'index.bundle.css'), indexCssResult.code);
  results.push(`  ✔ index.bundle.css  (${Buffer.byteLength(indexCssResult.code)} bytes)`);

  // [備註] index.html JS 已由 Vite 管理，不需要 index.bundle.js

  // --- login.bundle.css ---
  const loginCssSrc = concat(LOGIN_CSS, FRONTEND, 'css');
  const loginCssResult = await esbuild.transform(loginCssSrc, {
    loader: 'css',
    minify: true,
    sourcefile: 'login.bundle.css',
  });
  writeFileSync(resolve(DIST, 'login.bundle.css'), loginCssResult.code);
  results.push(`  ✔ login.bundle.css  (${Buffer.byteLength(loginCssResult.code)} bytes)`);

  // --- login.bundle.js ---
  const loginJsSrc = concat(LOGIN_JS, FRONTEND, 'js');
  const loginJsResult = await esbuild.transform(loginJsSrc, {
    loader: 'js',
    minify: true,
    sourcefile: 'login.bundle.js',
  });
  writeFileSync(resolve(DIST, 'login.bundle.js'), loginJsResult.code);
  results.push(`  ✔ login.bundle.js   (${Buffer.byteLength(loginJsResult.code)} bytes)`);

  const elapsed = Date.now() - startTime;
  console.log(`\n🚀 Frontend build 完成 (${elapsed}ms)\n`);
  results.forEach((r) => console.log(r));
  console.log(`\n  輸出目錄：frontend/dist/\n`);
}

build().catch((err) => {
  console.error('❌ Build 失敗：', err);
  process.exit(1);
});
