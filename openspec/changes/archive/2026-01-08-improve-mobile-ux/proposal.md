# Change: 改進手機版 UI/UX 體驗

## Why

目前系統主要針對桌機設計，在手機上有多個使用問題：
1. 桌面圖示無法單擊開啟（只能雙擊，但手機上雙擊體驗差）
2. 應用程式視窗在手機上未全螢幕顯示，畫面太小難以操作
3. 底部 Dock 列佔用寶貴的手機螢幕空間
4. 各應用程式內部佈局未針對手機優化

## What Changes

### 1. 移除 Dock 列
- **移除底部 Dock 列**：簡化介面，增加可用空間
- 原因：應用程式無需保存狀態、資料皆來自後端、手機畫面空間寶貴
- Dock 的「顯示運行中視窗」功能可移至 Header Bar

### 2. 桌面圖示互動行為
- **統一使用單擊開啟應用程式**：取消雙擊需求
- 手機與桌機行為一致，降低學習成本

### 3. 手機版應用程式全螢幕
- **手機上應用程式自動全螢幕開啟**
- 隱藏視窗標題列的拖曳、縮放功能（手機不需要）
- 提供返回桌面按鈕

### 4. 手機版應用程式內部佈局規則
- 定義響應式設計斷點與規則
- 各應用程式依規則逐步調整

## Impact

- Affected specs: `web-desktop`
- Affected code:
  - `frontend/js/desktop.js` - 桌面與圖示互動
  - `frontend/js/taskbar.js` - Dock 列（待移除或重構）
  - `frontend/js/window.js` - 視窗管理
  - `frontend/css/desktop.css` - 桌面樣式
  - `frontend/css/taskbar.css` - Dock 樣式
  - 各應用程式 CSS/JS 檔案
