# Change: 建立 Web 桌面作業系統介面

## Why
Ching-Tech OS 需要一個直覺的使用者介面作為所有功能的入口。第一階段聚焦於建立類似 NAS/平板的桌面作業系統介面，讓使用者能夠透過熟悉的桌面環境操作各種應用程式。

## What Changes
- 新增登入頁面（模擬驗證，無後端連接）
- 新增桌面主畫面，包含：
  - 最上方標題列（Header Bar）：顯示使用者資訊、登出按鈕、系統時間
  - 主要桌面區域：可放置應用程式圖示（App Icons）
  - 底部工作列（Taskbar/Dock）：類似 macOS Dock 或 Ubuntu Dock 的固定應用程式列
- 建立基本的 CSS 主題與佈局系統
- 實作基礎 JavaScript 模組架構

## Impact
- Affected specs: `web-desktop` (新增)
- Affected code:
  - `frontend/` 目錄結構
  - `frontend/index.html` - 主要入口
  - `frontend/login.html` - 登入頁面
  - `frontend/css/` - 樣式檔案
  - `frontend/js/` - JavaScript 模組

## Out of Scope
- 後端 API 整合
- 真實的使用者驗證
- 應用程式的具體功能實作
- 視窗管理系統（Window Manager）
