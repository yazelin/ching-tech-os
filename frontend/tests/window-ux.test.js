/**
 * Window UX P6 互動測試
 *
 * 使用 Node.js 執行：node frontend/tests/window-ux.test.js
 *
 * 測試項目：
 * - CSS 動畫關鍵影格（windowOpen / windowClose）是否存在
 * - .window.focused 邊框使用 --color-primary
 * - .window.closing 類別存在且含 pointer-events: none
 * - JS closeWindow 含 closing 動畫邏輯
 * - JS 雙擊標題列 toggleMaximize 已綁定
 * - prefers-reduced-motion 媒體查詢存在
 */

const fs = require('fs');
const path = require('path');

// ── 簡單測試框架 ──
let passed = 0;
let failed = 0;
const results = [];

function assert(condition, testName) {
  if (condition) {
    passed++;
    results.push(`  ✅ ${testName}`);
  } else {
    failed++;
    results.push(`  ❌ ${testName}`);
  }
}

// ── 讀取原始檔案 ──
const cssPath = path.join(__dirname, '..', 'css', 'window.css');
const jsPath = path.join(__dirname, '..', 'js', 'window.js');

const css = fs.readFileSync(cssPath, 'utf-8');
const js = fs.readFileSync(jsPath, 'utf-8');

// ══════════════════════════════════════════
// CSS 測試
// ══════════════════════════════════════════
console.log('\n📐 CSS 測試');

// 1. windowOpen 動畫存在
assert(
  css.includes('@keyframes windowOpen'),
  '@keyframes windowOpen 已定義'
);

// 2. windowClose 動畫存在
assert(
  css.includes('@keyframes windowClose'),
  '@keyframes windowClose 已定義'
);

// 3. .window 套用 windowOpen 動畫
assert(
  /\.window\s*\{[^}]*animation:\s*windowOpen/.test(css),
  '.window 套用 windowOpen 動畫'
);

// 4. .window.closing 套用 windowClose 動畫
assert(
  /\.window\.closing\s*\{[^}]*animation:\s*windowClose/.test(css),
  '.window.closing 套用 windowClose 動畫'
);

// 5. .window.closing 含 pointer-events: none
assert(
  /\.window\.closing\s*\{[^}]*pointer-events:\s*none/.test(css),
  '.window.closing 含 pointer-events: none'
);

// 6. .window.focused 使用 --color-primary（非 --color-accent）
const focusedMatch = css.match(/\.window\.focused\s*\{[^}]*border-color:\s*([^;]+)/);
assert(
  focusedMatch && focusedMatch[1].includes('--color-primary'),
  '.window.focused border-color 使用 var(--color-primary)'
);

// 7. .window.focused box-shadow 使用 --color-primary
const focusShadowMatch = css.match(/\.window\.focused\s*\{[^}]*box-shadow:\s*([^;]+)/);
assert(
  focusShadowMatch && focusShadowMatch[1].includes('--color-primary'),
  '.window.focused box-shadow 使用 var(--color-primary)'
);

// 8. prefers-reduced-motion 媒體查詢存在
assert(
  css.includes('prefers-reduced-motion: reduce'),
  'prefers-reduced-motion 媒體查詢已定義'
);

// ══════════════════════════════════════════
// JS 測試
// ══════════════════════════════════════════
console.log('\n🔧 JS 測試');

// 9. closeWindow 加入 closing 類別
assert(
  js.includes("classList.add('closing')"),
  'closeWindow 加入 closing 類別觸發動畫'
);

// 10. closeWindow 監聽 animationend
assert(
  js.includes('animationend'),
  'closeWindow 監聽 animationend 事件'
);

// 11. closeWindow 有 setTimeout fallback
assert(
  /setTimeout\(removeWindow,\s*200\)/.test(js),
  'closeWindow 有 setTimeout 200ms fallback'
);

// 12. 雙擊標題列 dblclick → toggleMaximize
assert(
  js.includes("addEventListener('dblclick'") && js.includes('toggleMaximize'),
  '標題列 dblclick 綁定 toggleMaximize'
);

// 13. toggleMaximize 公開 API
assert(
  /return\s*\{[^}]*toggleMaximize/.test(js),
  'toggleMaximize 已匯出為公開 API'
);

// 14. 防止重複移除（guard）
assert(
  js.includes('if (removed) return') && js.includes('removed = true'),
  'closeWindow 有 guard 防止重複移除'
);

// ══════════════════════════════════════════
// 結果摘要
// ══════════════════════════════════════════
console.log('\n' + results.join('\n'));
console.log(`\n═══════════════════════════════════════`);
console.log(`結果：${passed} 通過, ${failed} 失敗（共 ${passed + failed} 項）`);
console.log(`═══════════════════════════════════════\n`);

process.exit(failed > 0 ? 1 : 0);
