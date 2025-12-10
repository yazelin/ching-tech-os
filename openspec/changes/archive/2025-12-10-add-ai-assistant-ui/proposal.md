# Change: 新增 AI 助手應用程式 UI

## Why
目前桌面上的「AI 助手」圖示點擊後僅顯示「功能開發中」提示。需要實作一個類似 ChatGPT/LINE/Messenger 風格的聊天介面，讓使用者能在 ChingTech OS 桌面環境中與 AI 進行對話。

## What Changes
- 新增視窗系統（Window Manager）以支援應用程式視窗
- 新增 AI 助手應用程式 UI，包含：
  - 左側邊欄：歷史對話列表（可展開/收合）
  - 右側主區域：對話訊息區與輸入框
  - 頂部工具列：模型選擇器、新對話按鈕
- 點擊桌面「AI 助手」圖示時開啟此應用程式視窗
- 純前端 UI，不含後端整合（後端整合另立 proposal）

## Impact
- Affected specs: `web-desktop`（新增視窗系統）、新增 `ai-assistant-ui`
- Affected code:
  - `frontend/js/window.js` - 新增視窗管理模組
  - `frontend/js/ai-assistant.js` - 新增 AI 助手應用程式模組
  - `frontend/css/window.css` - 新增視窗樣式
  - `frontend/css/ai-assistant.css` - 新增 AI 助手樣式
  - `frontend/js/desktop.js` - 修改以支援開啟應用程式視窗
  - `frontend/index.html` - 引入新增的 CSS/JS 檔案

## Dependencies
- 無外部依賴
- 需先完成視窗系統才能開啟 AI 助手應用程式

## Out of Scope
- Claude API 後端整合（見 `add-ai-agent-backend` proposal）
- 實際的 AI 對話功能
- 對話資料持久化
