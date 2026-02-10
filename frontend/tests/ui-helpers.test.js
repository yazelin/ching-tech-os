/**
 * UIHelpers — Smoke Test
 *
 * 在 Node.js 環境下驗證 UIHelpers API 的基本正確性：
 *   - showLoading / showEmpty / showError / showSkeleton / clear
 *   - 產出 HTML 結構包含正確的 CSS class 與 ARIA 屬性
 */

/* ── 模擬瀏覽器最小 DOM 環境 ── */
function createElement(tag) {
  const children = [];
  let html = '';
  const el = {
    tagName: tag,
    className: '',
    innerHTML: '',
    children,
    get firstElementChild() {
      // 簡易解析：回傳自身作為代理（僅檢查 HTML 字串）
      return el;
    },
    querySelector(sel) {
      // 極簡：若 innerHTML 包含匹配的 class 名就回傳一個 stub
      const classMatch = sel.match(/\.([\w-]+)/);
      if (classMatch && el.innerHTML.includes(classMatch[1])) {
        return {
          remove() { el.innerHTML = el.innerHTML.replace(new RegExp(`<[^>]*${classMatch[1]}[^>]*>[\\s\\S]*?<\\/[^>]+>`), ''); },
          addEventListener() {},
        };
      }
      return null;
    },
  };
  return el;
}

// 模擬全域 getIcon
globalThis.getIcon = (name) => `<svg data-icon="${name}"></svg>`;

// 載入模組（IIFE 會將 UIHelpers 註冊到 globalThis）
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync(require('path').join(__dirname, '..', 'js', 'ui-helpers.js'), 'utf8');
vm.runInThisContext(code, { filename: 'ui-helpers.js' });

/* ── 測試工具 ── */
let passed = 0;
let failed = 0;

function assert(condition, label) {
  if (condition) {
    passed++;
    console.log(`  ✅ ${label}`);
  } else {
    failed++;
    console.error(`  ❌ ${label}`);
  }
}

/* ── 測試案例 ── */
console.log('🧪 UIHelpers Smoke Tests\n');

// 1. showLoading
console.log('── showLoading ──');
{
  const c = createElement('div');
  UIHelpers.showLoading(c, { text: '載入知識庫…' });
  assert(c.innerHTML.includes('ui-state--loading'), 'has .ui-state--loading class');
  assert(c.innerHTML.includes('role="status"'), 'has role="status"');
  assert(c.innerHTML.includes('載入知識庫…'), 'renders custom text');
  assert(c.innerHTML.includes('data-icon="refresh"'), 'renders default refresh icon');
}

// 2. showLoading with variant
console.log('── showLoading (compact) ──');
{
  const c = createElement('div');
  UIHelpers.showLoading(c, { variant: 'compact' });
  assert(c.innerHTML.includes('ui-state--compact'), 'has .ui-state--compact class');
  assert(c.innerHTML.includes('載入中'), 'renders default text');
}

// 3. showEmpty
console.log('── showEmpty ──');
{
  const c = createElement('div');
  UIHelpers.showEmpty(c, { icon: 'book-open-page-variant', text: '沒有找到資料', subtext: '請嘗試其他篩選條件' });
  assert(c.innerHTML.includes('ui-state--empty'), 'has .ui-state--empty class');
  assert(c.innerHTML.includes('沒有找到資料'), 'renders main text');
  assert(c.innerHTML.includes('請嘗試其他篩選條件'), 'renders subtext');
  assert(c.innerHTML.includes('data-icon="book-open-page-variant"'), 'renders custom icon');
}

// 4. showEmpty with fill variant
console.log('── showEmpty (fill) ──');
{
  const c = createElement('div');
  UIHelpers.showEmpty(c, { variant: 'fill', text: '選擇項目' });
  assert(c.innerHTML.includes('ui-state--fill'), 'has .ui-state--fill class');
}

// 5. showError
console.log('── showError ──');
{
  const c = createElement('div');
  let retryCalled = false;
  UIHelpers.showError(c, {
    message: '載入失敗',
    detail: 'Network timeout',
    onRetry: () => { retryCalled = true; },
  });
  assert(c.innerHTML.includes('ui-state--error'), 'has .ui-state--error class');
  assert(c.innerHTML.includes('role="alert"'), 'has role="alert"');
  assert(c.innerHTML.includes('載入失敗'), 'renders error message');
  assert(c.innerHTML.includes('Network timeout'), 'renders error detail');
  assert(c.innerHTML.includes('ui-state-retry'), 'renders retry button');
  assert(c.innerHTML.includes('data-icon="alert-circle"'), 'renders default error icon');
}

// 6. showError without retry
console.log('── showError (no retry) ──');
{
  const c = createElement('div');
  UIHelpers.showError(c, { message: '伺服器錯誤' });
  assert(!c.innerHTML.includes('ui-state-retry'), 'no retry button when onRetry omitted');
}

// 7. showSkeleton
console.log('── showSkeleton ──');
{
  const c = createElement('div');
  UIHelpers.showSkeleton(c, { rows: 5, height: 40 });
  assert(c.innerHTML.includes('ui-state-skeleton'), 'has .ui-state-skeleton class');
  const skeletonCount = (c.innerHTML.match(/class="skeleton"/g) || []).length;
  assert(skeletonCount === 5, `renders 5 skeleton rows (got ${skeletonCount})`);
  assert(c.innerHTML.includes('height:40px'), 'uses custom height');
}

// 8. showSkeleton defaults
console.log('── showSkeleton (defaults) ──');
{
  const c = createElement('div');
  UIHelpers.showSkeleton(c);
  const skeletonCount = (c.innerHTML.match(/class="skeleton"/g) || []).length;
  assert(skeletonCount === 3, `renders 3 default skeleton rows (got ${skeletonCount})`);
}

// 9. clear
console.log('── clear ──');
{
  const c = createElement('div');
  UIHelpers.showLoading(c);
  UIHelpers.clear(c);
  // 因為我們的簡易 DOM，clear 會嘗試移除；檢查沒有拋錯即可
  assert(true, 'clear() runs without error');
}

// 10. defaults
console.log('── defaults ──');
{
  const c = createElement('div');
  UIHelpers.showLoading(c);
  assert(c.innerHTML.includes('載入中'), 'default loading text');
  
  const c2 = createElement('div');
  UIHelpers.showEmpty(c2);
  assert(c2.innerHTML.includes('目前沒有資料'), 'default empty text');
}

/* ── 結果 ── */
console.log(`\n📊 結果：${passed} 通過, ${failed} 失敗`);
process.exit(failed > 0 ? 1 : 0);
