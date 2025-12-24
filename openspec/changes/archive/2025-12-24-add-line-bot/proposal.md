# Change: 新增 Line Bot 整合功能

## Why
專案目標已包含「LINEBot 聊天訊息整理」功能。需要一個 Line Bot 來收集群組對話、圖片、檔案，將資料歸檔到專案管理系統中，並提供個人對話的助理功能（查詢知識庫、專案狀態、新增筆記/待辦）。

## What Changes
- **ADDED** 新增 `line-bot` 能力規格
  - Line Bot Webhook 處理（訊息、加入/離開群組事件）
  - **訊息儲存**：所有訊息（群組+個人）都必須儲存到資料庫
  - 群組與專案手動綁定機制
  - 圖片/檔案收集並儲存至 NAS
  - **AI 助理功能（使用 MCP Server 架構）**：
    - 個人對話：所有訊息都經過 AI 處理並回應
    - 群組對話：僅在被 @ 提及時才觸發 AI 回應
    - MCP 工具：查詢專案、搜尋知識庫、新增筆記、摘要對話
- **ADDED** 新增 MCP Server
  - 整合到現有 FastAPI（HTTP 模式），不需額外進程
  - 提供標準化工具介面，未來可供 Claude Desktop 等其他 AI 客戶端使用
- **ADDED** 新增 Line Bot 前端管理介面（作為桌面應用程式）
  - 群組列表與專案綁定管理
  - 對話歷史瀏覽（群組+個人）
  - 檔案/圖片庫覽
- **MODIFIED** 擴充專案管理，支援 Line 訊息整合

## Architecture Decision: MCP vs JSON 解析

選擇 **MCP (Model Context Protocol)** 而非 JSON 解析的原因：
1. **維護性**：工具定義在 Python 裝飾器中，不需同步更新 System Prompt
2. **類型安全**：參數有型別註解，自動驗證
3. **可重用性**：同一套 MCP 工具可供 Line Bot、Claude Desktop、其他 AI 客戶端使用
4. **標準化**：採用 Anthropic 官方 MCP 協議

## Impact
- Affected specs: `line-bot` (新增), `project-management` (可能修改)
- Affected code:
  - 後端：新增 `api/linebot.py`, `services/linebot.py`, `models/linebot.py`
  - 後端：新增 `services/mcp_server.py` MCP Server
  - 前端：新增 `js/apps/linebot.js`, `css/apps/linebot.css`
  - 資料庫：新增 migration 建立 Line 相關資料表
- 外部依賴：`line-bot-sdk`, `mcp` Python 套件

## Dependencies
- **依賴 `add-ai-management` 提案**：使用 AI Agent 設定和 AI Log 記錄功能
- 需要 Line Messaging API Channel 設定（Channel Secret、Channel Access Token）
- 需要 NAS 儲存空間用於圖片/檔案
