# 觸控支援測試說明

## 功能範圍

本次改動在 `window.js` 與 `desktop.js` 中新增行動裝置觸控事件支援：

| 功能 | 檔案 | 事件 |
|------|------|------|
| 視窗拖曳 | `window.js` | `touchstart` / `touchmove` / `touchend` |
| 視窗調整大小 | `window.js` | `touchstart` / `touchmove` / `touchend` |
| 視窗聚焦 | `window.js` | `touchstart` |
| 桌面圖示長按選單 | `desktop.js` | `touchstart` / `touchend` / `touchmove` |

---

## Chrome DevTools 手動觸控模擬步驟

1. **開啟 Chrome DevTools**：按 `F12` 或 `Ctrl+Shift+I`（macOS: `Cmd+Option+I`）
2. **切換裝置模式**：點擊 DevTools 工具列左上角的「Toggle device toolbar」圖示（手機+平板圖示），或按 `Ctrl+Shift+M`
3. **選擇裝置**：在頂部下拉選單選擇一款行動裝置（如 iPhone 14 Pro、Pixel 7）
4. **重新整理頁面**：確保 touch 事件偵聽器正確註冊

### 測試項目

#### A. 視窗拖曳（Window Drag）
1. 開啟任一應用程式（如「AI 助手」）
2. 用模擬觸控在**視窗標題列**按住並拖動
3. ✅ 預期：視窗跟隨手指移動，放開後停在新位置
4. ✅ 預期：拖至螢幕邊緣時出現 Snap 預覽

#### B. 視窗調整大小（Window Resize）
1. 開啟任一應用程式視窗
2. 用模擬觸控在**視窗邊框/角落**按住並拖動
3. ✅ 預期：視窗大小隨手指移動改變

#### C. 長按右鍵選單（Long-Press Context Menu）
1. 在桌面圖示上**長按約 0.6 秒**（不要移動手指）
2. ✅ 預期：彈出右鍵選單，顯示「開啟」與「應用程式資訊」
3. ✅ 預期：點擊選單項目後正確執行對應動作
4. ✅ 預期：短按（< 0.6 秒）仍然正常觸發 click 開啟 App

#### D. 滑鼠相容性
1. 關閉裝置模式，使用一般滑鼠操作
2. ✅ 預期：所有原有滑鼠拖曳、調整大小、按鈕點擊均正常運作

---

## JavaScript Console 快速驗證腳本

在 Chrome DevTools Console 中貼上以下腳本，可在非觸控環境下模擬 touch 事件：

```javascript
// === 模擬 Touch 拖曳視窗 ===
(function simulateTouchDrag() {
  const titlebar = document.querySelector('.window-titlebar');
  if (!titlebar) { console.warn('請先開啟一個視窗'); return; }

  const rect = titlebar.getBoundingClientRect();
  const startX = rect.left + rect.width / 2;
  const startY = rect.top + rect.height / 2;
  const endX = startX + 150;
  const endY = startY + 100;

  function createTouch(x, y) {
    return new Touch({
      identifier: 0,
      target: titlebar,
      clientX: x,
      clientY: y,
      pageX: x,
      pageY: y
    });
  }

  titlebar.dispatchEvent(new TouchEvent('touchstart', {
    bubbles: true, cancelable: true,
    touches: [createTouch(startX, startY)],
    targetTouches: [createTouch(startX, startY)],
    changedTouches: [createTouch(startX, startY)]
  }));

  setTimeout(() => {
    document.dispatchEvent(new TouchEvent('touchmove', {
      bubbles: true, cancelable: true,
      touches: [createTouch(endX, endY)],
      targetTouches: [createTouch(endX, endY)],
      changedTouches: [createTouch(endX, endY)]
    }));
  }, 50);

  setTimeout(() => {
    document.dispatchEvent(new TouchEvent('touchend', {
      bubbles: true, cancelable: true,
      touches: [],
      targetTouches: [],
      changedTouches: [createTouch(endX, endY)]
    }));
    console.log('✅ 模擬觸控拖曳完成：視窗應已移動 150px 右、100px 下');
  }, 100);
})();
```

```javascript
// === 模擬 Long-Press 右鍵選單 ===
(function simulateLongPress() {
  const icon = document.querySelector('.desktop-icon');
  if (!icon) { console.warn('找不到桌面圖示'); return; }

  const rect = icon.getBoundingClientRect();
  const x = rect.left + rect.width / 2;
  const y = rect.top + rect.height / 2;

  function createTouch(cx, cy) {
    return new Touch({
      identifier: 0, target: icon,
      clientX: cx, clientY: cy, pageX: cx, pageY: cy
    });
  }

  icon.dispatchEvent(new TouchEvent('touchstart', {
    bubbles: true, cancelable: true,
    touches: [createTouch(x, y)],
    targetTouches: [createTouch(x, y)],
    changedTouches: [createTouch(x, y)]
  }));

  // 等待 700ms 後放開（超過 600ms 門檻）
  setTimeout(() => {
    icon.dispatchEvent(new TouchEvent('touchend', {
      bubbles: true, cancelable: true,
      touches: [],
      targetTouches: [],
      changedTouches: [createTouch(x, y)]
    }));
    console.log('✅ 長按模擬完成：應出現右鍵選單');
  }, 700);
})();
```

---

## 備註

- 所有觸控事件處理器均**不影響現有滑鼠事件**，兩者獨立運作
- `getPointerPos()` 工具函式統一處理 Mouse / Touch 座標提取
- 長按門檻 `LONG_PRESS_DELAY = 600ms`，可依需求調整
- 觸控拖曳時會呼叫 `e.preventDefault()` 防止頁面捲動
