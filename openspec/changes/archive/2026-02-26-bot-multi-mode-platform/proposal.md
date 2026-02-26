## Why

CTOS 目前的 Bot 系統預設「所有用戶必須綁定 CTOS 帳號才能使用」，未綁定用戶只會收到綁定提示。但未來 CTOS 將安裝到不同公司（如杰膚美診所 kb036），需要支援**未綁定用戶也能使用特定功能**（如衛教問答），並依身份走不同的 AI 處理路徑。同時，管理員/開發者缺乏快速診斷系統問題的手段，需要一個 `/debug` 指令來分析各項 logs。這些都指向同一個核心需求：**Bot 指令系統擴展 + 身份分流機制通用化**。

## What Changes

- 新增 **Bot 指令路由系統**：將現有硬編碼的 `/reset` 指令擴展為可擴充的指令框架，支援註冊新指令、權限檢查、平台共用
- 新增 **`/debug` 管理員診斷指令**：管理員專用，使用獨立的 system prompt 產生 AI Agent，可分析伺服器 logs（journalctl）、AI logs（ai_logs 表）、nginx logs，快速定位系統問題
- 新增 **身份分流路由器**：在 AI 處理入口根據 `bot_users.user_id` 是否為 NULL 判斷綁定狀態，透過可配置的**未綁定用戶策略**決定處理方式：
  - `reject`（預設，向下相容）：維持現有行為，未綁定用戶收到綁定提示，不進行 AI 處理
  - `restricted`：未綁定用戶走受限模式 Agent，使用專用 system prompt 和工具白名單
- 新增 **受限模式 Agent 框架**：當策略為 `restricted` 時，為未綁定用戶提供可配置的專用 system prompt 和工具白名單，每個 CTOS 部署可自訂受限模式的用途（衛教問答、客服、產品諮詢等）
- 新增 **Rate Limiter**：對未綁定用戶實施可配置的頻率限制（每小時/每日訊息上限），已綁定用戶不受限
- 新增 **使用量追蹤表**：記錄每個 bot_user 的訊息使用量，支援 rate limiting 判斷和後台統計

## Capabilities

### New Capabilities
- `bot-slash-commands`: Bot 斜線指令路由系統 — 可擴充的指令框架，支援指令註冊、權限檢查、平台共用。包含 `/debug` 管理員診斷指令的完整實作
- `bot-identity-router`: Bot 身份分流路由器 — 根據帳號綁定狀態（已綁定/未綁定）和可配置的未綁定用戶策略（`reject` / `restricted`），將訊息路由到對應的處理流程。預設 `reject` 維持現有行為（向下相容），設為 `restricted` 則走受限模式 Agent。包含受限模式 Agent 框架和可配置的 system prompt
- `bot-rate-limiter`: Bot 頻率限制模組 — 對未綁定用戶實施可配置的使用量限制，包含使用量追蹤資料表和限額判斷邏輯

### Modified Capabilities
- `bot-platform`: 在 BotContext 中新增 `binding_status`（bound/unbound）欄位，讓下游模組可根據綁定狀態做決策
- `line-bot`: Line Bot 存取控制邏輯調整 — 未綁定用戶不再硬編碼拒絕，改為委派身份分流路由器依策略決定處理方式（reject 或 restricted）
- `knowledge-base`: 知識庫分類新增「公開存取」權限旗標，允許標記特定分類/項目為公開，讓未綁定用戶在受限模式下可查詢。圖書館資料夾同理可標記為公開或內部

## Impact

### 後端程式碼
- `services/bot_line/trigger.py` — 重構指令判斷，接入指令路由系統
- `services/bot_telegram/handler.py` — 同步接入指令路由系統
- `services/linebot_ai.py` — AI 處理入口插入身份分流邏輯
- `services/bot/ai.py` — 通用 AI 核心新增受限模式 Agent 選擇
- `services/bot/agents.py` — 新增受限模式 prompt 模板和 `/debug` 專用 prompt
- `services/linebot_agents.py` — 新增 `bot-restricted` 和 `bot-debug` Agent 預設設定
- `config.py` — 新增 rate limiter 設定項（限額數值、啟用開關）和未綁定用戶策略設定（`BOT_UNBOUND_USER_POLICY`）

### 資料庫
- 新增 `bot_usage_tracking` 表 — 追蹤每個 bot_user 的訊息使用量
- `bot_platform` spec 的 BotContext 新增欄位

### 設計原則（通用化）
- 所有限額數值、prompt 內容、啟用開關透過**環境變數 + 資料庫設定**可配置
- 受限模式的 system prompt 存在資料庫（ai_agents 表），部署方可透過 Web UI 自行修改
- Rate limiter 的閾值透過環境變數設定，不同部署可自訂
- `/debug` 指令的可用 log 來源透過配置決定，適應不同部署環境
