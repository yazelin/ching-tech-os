## 1. 資料庫 Migration

- [x] 1.1 建立 `007_create_ai_management.py` migration 檔案
- [x] 1.2 建立 `ai_prompts` 資料表
- [x] 1.3 建立 `ai_agents` 資料表
- [x] 1.4 建立 `ai_logs` 分區主表
- [x] 1.5 建立初始月份分區（當月與下月）
- [x] 1.6 建立分區管理函數（自動建立新分區）
- [x] 1.7 執行 migration 驗證

## 2. 後端 Models

- [x] 2.1 建立 `models/ai.py` Pydantic 模型
  - AiPrompt, AiAgent, AiLog 資料模型
  - 請求/回應模型（Create, Update, Response）
  - 列表查詢參數模型

## 3. 後端 Services

- [x] 3.1 建立 `services/ai_manager.py` AI 管理服務
- [x] 3.2 實作 Prompt CRUD 操作
- [x] 3.3 實作 Agent CRUD 操作
- [x] 3.4 實作 AI Log 記錄與查詢
- [x] 3.5 實作統一 AI 調用介面（透過 agent 調用，自動記錄 log）
- [x] 3.6 實作分區表自動管理
- [x] 3.7 修改 `services/ai_chat.py` 使用新的 Agent/Prompt 設定（保持向後相容）

## 4. 後端 API

- [x] 4.1 建立 `api/ai_management.py` 路由模組
- [x] 4.2 實作 Prompt API
  - `GET /api/ai/prompts` - 列表（支援分類過濾）
  - `POST /api/ai/prompts` - 新增
  - `GET /api/ai/prompts/{id}` - 詳情
  - `PUT /api/ai/prompts/{id}` - 更新
  - `DELETE /api/ai/prompts/{id}` - 刪除
- [x] 4.3 實作 Agent API
  - `GET /api/ai/agents` - 列表
  - `POST /api/ai/agents` - 新增
  - `GET /api/ai/agents/{id}` - 詳情
  - `GET /api/ai/agents/by-name/{name}` - 依名稱查詢
  - `PUT /api/ai/agents/{id}` - 更新
  - `DELETE /api/ai/agents/{id}` - 刪除
- [x] 4.4 實作 Log API
  - `GET /api/ai/logs` - 列表（分頁、過濾）
  - `GET /api/ai/logs/{id}` - 詳情
  - `GET /api/ai/logs/stats` - 統計
- [x] 4.5 實作測試 API
  - `POST /api/ai/test` - 測試 agent
- [x] 4.6 在 `main.py` 註冊 ai_management 路由

## 5. 前端應用 - Prompt 編輯器

- [x] 5.1 建立 `css/prompt-editor.css` 樣式檔案
- [x] 5.2 建立 `js/prompt-editor.js` 應用程式模組
- [x] 5.3 實作 Prompt 列表（左側）
- [x] 5.4 實作分類過濾功能
- [x] 5.5 實作 Prompt 編輯表單（右側）
- [x] 5.6 實作新增/儲存/刪除功能
- [x] 5.7 在 `index.html` 引入 CSS/JS 檔案
- [x] 5.8 在 `desktop.js` 註冊應用程式

## 6. 前端應用 - Agent 設定

- [x] 6.1 建立 `css/agent-settings.css` 樣式檔案
- [x] 6.2 建立 `js/agent-settings.js` 應用程式模組
- [x] 6.3 實作 Agent 列表（左側，含啟用狀態指示）
- [x] 6.4 實作 Agent 編輯表單（右側）
  - Model 選擇下拉選單
  - Prompt 選擇下拉選單
  - 啟用/停用開關
- [x] 6.5 實作測試功能
- [x] 6.6 實作新增/儲存/刪除功能
- [x] 6.7 在 `index.html` 引入 CSS/JS 檔案
- [x] 6.8 在 `desktop.js` 註冊應用程式

## 7. 前端應用 - AI Log

- [x] 7.1 建立 `css/ai-log.css` 樣式檔案
- [x] 7.2 建立 `js/ai-log.js` 應用程式模組
- [x] 7.3 實作過濾器（Agent、類型、日期範圍）
- [x] 7.4 實作統計卡片（今日次數、成功率、平均耗時）
- [x] 7.5 實作 Log 列表
- [x] 7.6 實作 Log 詳情面板
- [x] 7.7 實作分頁功能
- [x] 7.8 在 `index.html` 引入 CSS/JS 檔案
- [x] 7.9 在 `desktop.js` 註冊應用程式

## 8. 修改現有 AI 對話應用

- [x] 8.1 修改 `js/ai-assistant.js`
  - 新增 Agent 選擇下拉選單
  - 載入時取得 Agent 列表
  - 建立對話時使用選擇的 Agent
- [x] 8.2 修改 `css/ai-assistant.css`（如需樣式調整）
- [x] 8.3 實作舊對話的向後相容（prompt_name → Agent 映射）

## 9. 預設資料

- [x] 9.1 建立預設 Prompts（在 migration 中建立）
  - `web-chat-default`: 預設對話 system prompt
  - `web-chat-code`: 程式碼助手 system prompt
  - `linebot-group`: Line Bot 群組對話
  - `linebot-personal`: Line Bot 個人助理
  - `system-task`: 系統任務
- [x] 9.2 建立預設 Agents（在 migration 中建立）
  - `web-chat-default`: 前端預設對話
  - `web-chat-code`: 前端程式碼助手
  - `linebot-group`: Line Bot 群組
  - `linebot-personal`: Line Bot 個人
  - `system-scheduler`: 系統排程任務

## 10. 整合測試

- [x] 10.1 測試 Prompt CRUD API
- [x] 10.2 測試 Agent CRUD API
- [x] 10.3 測試 Log 記錄與查詢
- [x] 10.4 測試 Agent 調用功能（需手動測試）
- [x] 10.5 測試 Prompt 編輯器應用（需手動測試）
- [x] 10.6 測試 Agent 設定應用（需手動測試）
- [x] 10.7 測試 AI Log 應用（需手動測試）
- [x] 10.8 測試 AI 對話 Agent 整合（需手動測試）
- [x] 10.9 測試分區表自動建立

## 11. 文件更新

- [x] 11.1 更新 `docs/backend.md` API 文件
- [x] 11.2 建立 `docs/ai-management.md` 說明文件
