/**
 * PathUtils 單元測試
 *
 * 使用 Node.js 執行：node frontend/tests/path-utils.test.js
 *
 * 測試項目：
 * - parse() - 解析新舊格式路徑
 * - toApiUrl() - 轉換為 API URL
 * - toUri() - 轉換為標準 URI
 * - 檔案類型判斷函數
 */

// Mock window.API_BASE
global.window = { API_BASE: '' };

// 載入 PathUtils
const PathUtils = require('../js/path-utils.js');

// 簡單的測試框架
let passed = 0;
let failed = 0;
const errors = [];

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`✓ ${name}`);
  } catch (e) {
    failed++;
    errors.push({ name, error: e.message });
    console.log(`✗ ${name}`);
    console.log(`  Error: ${e.message}`);
  }
}

function assertEqual(actual, expected, message = '') {
  if (actual !== expected) {
    throw new Error(`${message}\n  Expected: ${expected}\n  Actual: ${actual}`);
  }
}

function assertThrows(fn, expectedMessage = '') {
  try {
    fn();
    throw new Error(`Expected function to throw, but it didn't`);
  } catch (e) {
    if (expectedMessage && !e.message.includes(expectedMessage)) {
      throw new Error(
        `Expected error message to include "${expectedMessage}", got: ${e.message}`
      );
    }
  }
}

console.log('\n=== PathUtils 單元測試 ===\n');

// ============================================================
// parse() 新格式測試
// ============================================================

console.log('--- parse() 新格式測試 ---');

test('ctos:// 格式解析', () => {
  const result = PathUtils.parse('ctos://linebot/files/xxx.pdf');
  assertEqual(result.zone, 'ctos');
  assertEqual(result.path, 'linebot/files/xxx.pdf');
  assertEqual(result.raw, 'ctos://linebot/files/xxx.pdf');
});

test('shared:// 格式解析', () => {
  const result = PathUtils.parse('shared://亦達光學/doc.pdf');
  assertEqual(result.zone, 'shared');
  assertEqual(result.path, '亦達光學/doc.pdf');
});

test('temp:// 格式解析', () => {
  const result = PathUtils.parse('temp://abc123/page1.png');
  assertEqual(result.zone, 'temp');
  assertEqual(result.path, 'abc123/page1.png');
});

test('local:// 格式解析', () => {
  const result = PathUtils.parse('local://knowledge/assets/x.jpg');
  assertEqual(result.zone, 'local');
  assertEqual(result.path, 'knowledge/assets/x.jpg');
});

// ============================================================
// parse() 舊格式測試
// ============================================================

console.log('\n--- parse() 舊格式測試 ---');

test('nas://knowledge/attachments/ 格式', () => {
  const result = PathUtils.parse('nas://knowledge/attachments/kb-001/file.pdf');
  assertEqual(result.zone, 'ctos');
  assertEqual(result.path, 'knowledge/kb-001/file.pdf');
});

test('nas://knowledge/ 格式', () => {
  const result = PathUtils.parse('nas://knowledge/assets/image.jpg');
  assertEqual(result.zone, 'ctos');
  assertEqual(result.path, 'knowledge/assets/image.jpg');
});

test('nas://linebot/files/ 格式', () => {
  const result = PathUtils.parse('nas://linebot/files/test.jpg');
  assertEqual(result.zone, 'ctos');
  assertEqual(result.path, 'linebot/test.jpg');
});

test('../assets/ 相對路徑格式', () => {
  const result = PathUtils.parse('../assets/xxx.jpg');
  assertEqual(result.zone, 'local');
  assertEqual(result.path, 'knowledge/xxx.jpg');
});

test('groups/ 相對路徑（Line Bot）', () => {
  const result = PathUtils.parse('groups/C123/images/photo.jpg');
  assertEqual(result.zone, 'ctos');
  assertEqual(result.path, 'linebot/groups/C123/images/photo.jpg');
});

test('users/ 相對路徑（Line Bot）', () => {
  const result = PathUtils.parse('users/U123/files/doc.pdf');
  assertEqual(result.zone, 'ctos');
  assertEqual(result.path, 'linebot/users/U123/files/doc.pdf');
});

test('ai-images/ 相對路徑', () => {
  const result = PathUtils.parse('ai-images/abc123.jpg');
  assertEqual(result.zone, 'ctos');
  assertEqual(result.path, 'linebot/ai-images/abc123.jpg');
});

// ============================================================
// parse() 系統路徑測試
// ============================================================

console.log('\n--- parse() 系統路徑測試 ---');

test('/tmp/ 路徑', () => {
  const result = PathUtils.parse('/tmp/ctos/converted/page1.png');
  assertEqual(result.zone, 'temp');
  assertEqual(result.path, 'ctos/converted/page1.png');
});

test('/tmp/.../nanobanana-output/ 特殊路徑', () => {
  const result = PathUtils.parse('/tmp/ching-tech-os-cli/nanobanana-output/abc.jpg');
  assertEqual(result.zone, 'temp');
  assertEqual(result.path, 'ai-generated/abc.jpg');
});

test('/tmp/linebot-files/ 特殊路徑', () => {
  const result = PathUtils.parse('/tmp/linebot-files/msg123.pdf');
  assertEqual(result.zone, 'temp');
  assertEqual(result.path, 'linebot/msg123.pdf');
});

test('以 / 開頭的非系統路徑（search_nas_files 回傳格式）', () => {
  const result = PathUtils.parse('/亦達光學/文件/report.pdf');
  assertEqual(result.zone, 'shared');
  assertEqual(result.path, '亦達光學/文件/report.pdf');
});

// ============================================================
// parse() 邊界情況測試
// ============================================================

console.log('\n--- parse() 邊界情況測試 ---');

test('空路徑應拋出錯誤', () => {
  assertThrows(() => PathUtils.parse(''), '路徑不可為空');
});

test('null 應拋出錯誤', () => {
  assertThrows(() => PathUtils.parse(null), '路徑不可為空');
});

test('純相對路徑預設為 CTOS', () => {
  const result = PathUtils.parse('some/random/path.txt');
  assertEqual(result.zone, 'ctos');
  assertEqual(result.path, 'some/random/path.txt');
});

test('中文路徑處理', () => {
  const result = PathUtils.parse('shared://擎添專案/設計圖/圖紙v1.dwg');
  assertEqual(result.zone, 'shared');
  assertEqual(result.path, '擎添專案/設計圖/圖紙v1.dwg');
});

// ============================================================
// toApiUrl() 測試
// ============================================================

console.log('\n--- toApiUrl() 測試 ---');

test('ctos:// 轉換為 API URL', () => {
  const result = PathUtils.toApiUrl('ctos://linebot/files/test.jpg');
  assertEqual(result, '/api/files/ctos/linebot/files/test.jpg');
});

test('shared:// 轉換為 API URL', () => {
  const result = PathUtils.toApiUrl('shared://亦達光學/doc.pdf');
  assertEqual(result, '/api/files/shared/亦達光學/doc.pdf');
});

test('舊格式轉換為 API URL', () => {
  const result = PathUtils.toApiUrl('nas://knowledge/assets/img.jpg');
  assertEqual(result, '/api/files/ctos/knowledge/assets/img.jpg');
});

// ============================================================
// toUri() 測試
// ============================================================

console.log('\n--- toUri() 測試 ---');

test('新格式應保持不變', () => {
  const result = PathUtils.toUri('ctos://linebot/test.jpg');
  assertEqual(result, 'ctos://linebot/test.jpg');
});

test('舊格式應轉換為新格式', () => {
  const result = PathUtils.toUri('nas://knowledge/assets/img.jpg');
  assertEqual(result, 'ctos://knowledge/assets/img.jpg');
});

// ============================================================
// 檔案類型判斷測試
// ============================================================

console.log('\n--- 檔案類型判斷測試 ---');

test('isImage() - JPG', () => {
  assertEqual(PathUtils.isImage('photo.jpg'), true);
  assertEqual(PathUtils.isImage('photo.JPG'), true);
});

test('isImage() - PNG', () => {
  assertEqual(PathUtils.isImage('image.png'), true);
});

test('isImage() - 非圖片', () => {
  assertEqual(PathUtils.isImage('doc.pdf'), false);
});

test('isPdf()', () => {
  assertEqual(PathUtils.isPdf('document.pdf'), true);
  assertEqual(PathUtils.isPdf('document.PDF'), true);
  assertEqual(PathUtils.isPdf('image.jpg'), false);
});

test('isVideo()', () => {
  assertEqual(PathUtils.isVideo('video.mp4'), true);
  assertEqual(PathUtils.isVideo('video.mov'), true);
  assertEqual(PathUtils.isVideo('image.jpg'), false);
});

test('isAudio()', () => {
  assertEqual(PathUtils.isAudio('audio.mp3'), true);
  assertEqual(PathUtils.isAudio('audio.wav'), true);
  assertEqual(PathUtils.isAudio('image.jpg'), false);
});

test('isText()', () => {
  assertEqual(PathUtils.isText('readme.txt'), true);
  assertEqual(PathUtils.isText('data.json'), true);
  assertEqual(PathUtils.isText('image.jpg'), false);
});

// ============================================================
// getZone() 和 isReadonly() 測試
// ============================================================

console.log('\n--- getZone() 和 isReadonly() 測試 ---');

test('getZone() - ctos', () => {
  assertEqual(PathUtils.getZone('ctos://test.jpg'), 'ctos');
});

test('getZone() - shared', () => {
  assertEqual(PathUtils.getZone('shared://test.pdf'), 'shared');
});

test('isReadonly() - shared 應為唯讀', () => {
  assertEqual(PathUtils.isReadonly('shared://test.pdf'), true);
});

test('isReadonly() - ctos 應可寫入', () => {
  assertEqual(PathUtils.isReadonly('ctos://test.pdf'), false);
});

test('isReadonly() - temp 應可寫入', () => {
  assertEqual(PathUtils.isReadonly('temp://test.pdf'), false);
});

// ============================================================
// 測試結果
// ============================================================

console.log('\n=== 測試結果 ===');
console.log(`通過: ${passed}`);
console.log(`失敗: ${failed}`);

if (errors.length > 0) {
  console.log('\n失敗的測試:');
  errors.forEach(({ name, error }) => {
    console.log(`  - ${name}: ${error}`);
  });
}

process.exit(failed > 0 ? 1 : 0);
