# Tasks: 修正 Taskbar Dock 邏輯

## 1. 修改 Taskbar 點擊邏輯
- [x] 1.1 修改 `taskbar.js` 的 `handleIconClick` 函式實作 Dock 行為邏輯
- [x] 1.2 整合 `WindowModule` 方法（getWindowByAppId、focusWindow、restoreWindow）
- [x] 1.3 整合 `DesktopModule.openApp` 方法開啟應用程式

## 2. 新增運行指示器
- [x] 2.1 在 `taskbar.css` 新增運行指示器樣式（底部小點）（已存在）
- [x] 2.2 在 `taskbar.js` 新增更新運行指示器的函式
- [x] 2.3 修改 Taskbar 圖示 HTML 結構以包含指示器元素（使用 CSS ::before）

## 3. 視窗狀態同步
- [x] 3.1 在 `window.js` 新增視窗狀態變化的回調機制
- [x] 3.2 在 `taskbar.js` 註冊回調以監聽視窗開啟/關閉事件
- [x] 3.3 視窗開啟/關閉時自動更新對應的運行指示器

## 4. 驗證
- [x] 4.1 測試點擊 Taskbar 圖示開啟應用程式
- [x] 4.2 測試已開啟應用程式的聚焦行為
- [x] 4.3 測試最小化視窗的恢復行為
- [x] 4.4 測試運行指示器正確顯示
