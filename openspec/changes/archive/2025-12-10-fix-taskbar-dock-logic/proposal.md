# Change: 修正 Taskbar Dock 邏輯

## Why
目前 Taskbar 上的圖示點擊後只顯示「功能開發中」的 toast 訊息，並未實際開啟應用程式。需要修正為正確的 Dock 行為邏輯，讓使用者可以透過 Taskbar 快速啟動和管理應用程式。

## What Changes
- 修改 Taskbar 圖示點擊邏輯，實作正確的 Dock 行為：
  - 應用程式未開啟 → 開啟應用程式
  - 已開啟但最小化 → 恢復視窗並聚焦
  - 已開啟但在背景 → 聚焦（帶到前景）
  - 已開啟且在最上層 → 保持不變
- 新增運行指示器（底部小點）顯示哪些應用程式正在運行
- Taskbar 需要監聽視窗狀態變化以更新運行指示器

## Impact
- Affected specs: `web-desktop`（修改 Taskbar requirement）
- Affected code:
  - `frontend/js/taskbar.js` - 修改點擊邏輯、新增運行指示器
  - `frontend/css/taskbar.css` - 新增運行指示器樣式
  - `frontend/js/window.js` - 可能需要新增事件回調以通知視窗狀態變化

## Dependencies
- 依賴 `WindowModule` 的 `getWindowByAppId`、`focusWindow`、`restoreWindow` 方法
- 依賴 `DesktopModule` 的 `openApp` 方法
