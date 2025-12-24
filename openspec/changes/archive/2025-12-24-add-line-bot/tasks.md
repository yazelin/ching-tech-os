## 前置依賴

> ⚠️ 此提案依賴 `add-ai-management` 提案，需先完成 AI Management 的實作。

## 1. 環境設定與依賴

- [x] 1.1 新增 `line-bot-sdk>=3.0.0` 和 `mcp` 到 `pyproject.toml`
- [x] 1.2 在 `config.py` 新增 Line Bot 相關設定（Channel Secret、Channel Access Token）
- [x] 1.3 在 `.env.example` 新增 Line Bot 環境變數範例

## 2. 資料庫 Migration

- [x] 2.1 建立 migration 檔案（編號在 ai-management 之後）
- [x] 2.2 建立 `line_groups` 資料表（群組資訊、專案綁定）
- [x] 2.3 建立 `line_users` 資料表（用戶資訊、Line user_id 對應）
- [x] 2.4 建立 `line_messages` 資料表（所有訊息：群組+個人）
- [x] 2.5 建立 `line_files` 資料表（圖片/檔案記錄）
- [x] 2.6 執行 migration 驗證

## 3. 後端 Models

- [x] 3.1 建立 `models/linebot.py` Pydantic 模型
  - LineGroup, LineUser, LineMessage, LineFile
  - 請求/回應模型

## 4. 後端 Services - 基礎功能

- [x] 4.1 建立 `services/linebot.py` 業務邏輯
- [x] 4.2 實作 Webhook 簽章驗證
- [x] 4.3 實作訊息儲存功能（所有訊息必須存入資料庫：群組+個人）
- [x] 4.4 實作群組加入/離開事件處理
- [x] 4.5 實作 NAS 檔案儲存功能（圖片/檔案）

## 5. 後端 Services - MCP Server

- [x] 5.1 建立 `services/mcp_server.py` MCP Server（使用 FastMCP）
- [x] 5.2 實作 MCP 工具：`query_project`（查詢專案狀態、進度、成員）
- [x] 5.3 實作 MCP 工具：`search_knowledge`（搜尋知識庫）
- [x] 5.4 實作 MCP 工具：`add_note`（新增筆記到知識庫）
- [x] 5.5 實作 MCP 工具：`summarize_chat`（摘要群組對話）
- [x] 5.6 支援 Claude Code CLI stdio 模式（透過 .mcp.json 配置）
- [x] 5.7 測試 MCP Server 連接

## 6. 後端 Services - AI 助理整合

- [x] 6.1 實作 AI 觸發判斷邏輯
  - 個人對話：所有訊息都觸發 AI
  - 群組對話：僅被 @ 提及時觸發（支援多個觸發名稱）
- [x] 6.2 實作 Claude CLI + MCP 調用流程
- [x] 6.3 整合 AI Log 記錄（使用 ai-management 的 AI Log）

## 7. 後端 API

- [x] 7.1 建立 `api/linebot_router.py` 路由模組
- [x] 7.2 實作 `POST /api/linebot/webhook` Webhook 端點
- [x] 7.3 實作群組 CRUD API
  - `GET /api/linebot/groups`
  - `GET /api/linebot/groups/{id}`
- [x] 7.4 實作群組專案綁定 API
  - `POST /api/linebot/groups/{id}/bind-project`
  - `DELETE /api/linebot/groups/{id}/bind-project`
- [x] 7.5 實作群組訊息 API
  - `GET /api/linebot/messages`
- [x] 7.6 實作群組檔案 API
  - `GET /api/linebot/groups/{id}/files`
  - `GET /api/linebot/files/{id}/download`
- [x] 7.7 實作使用者 API
  - `GET /api/linebot/users`
  - `GET /api/linebot/users/{id}`
- [x] 7.8 在 `main.py` 註冊 linebot 路由

## 8. 前端介面

- [x] 8.1 建立 `css/linebot.css` 樣式檔案
- [x] 8.2 建立 `js/linebot.js` 應用程式模組
- [x] 8.3 實作群組列表頁面
- [x] 8.4 實作群組詳情與專案綁定頁面
- [x] 8.5 實作對話歷史頁面（支援群組+個人）
- [x] 8.6 實作檔案庫覽頁面
- [x] 8.7 在 `index.html` 引入 CSS/JS 檔案
- [x] 8.8 在 `desktop.js` 註冊 Line Bot 應用程式

## 9. 整合測試

- [x] 9.1 設定 Line Channel 並註冊 Webhook URL
- [x] 9.2 測試 Webhook 接收訊息（群組+個人）
- [x] 9.3 測試訊息儲存到資料庫
- [x] 9.4 測試圖片/檔案上傳到 NAS
- [x] 9.5 測試 MCP 工具（query_project, get_project_members, summarize_chat）
- [x] 9.6 測試 AI 觸發邏輯（個人全回應、群組@才回應）
- [x] 9.7 測試前端管理介面

## 10. 文件更新

- [x] 10.1 更新 `docs/backend.md` API 文件
- [x] 10.2 建立 `docs/linebot.md` Line Bot 設定與使用說明
- [x] 10.3 建立 `docs/mcp-server.md` MCP Server 說明
