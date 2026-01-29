## Context
現有 LineBot 功能（7047 行核心程式碼）與 Line 平台深度耦合。為支援 Telegram 等多平台，需要建立抽象層。參考 Moltbot（89K stars）的 ChannelPlugin 組合模式，但簡化為 Python Protocol，符合本專案 FastAPI + asyncpg 技術棧。

## Goals / Non-Goals
- Goals:
  - 將平台無關的 AI 處理邏輯抽離為共用核心
  - 定義標準化 BotAdapter Protocol（send_text, send_image, send_file）
  - 定義可選擴展 Protocol（EditableMessage, ProgressNotifier）供 Telegram 等平台使用
  - 資料表正規化，支援多平台資料儲存
  - 確保重構前後 LineBot 功能完全不變
- Non-Goals:
  - 本次不實作 Telegram Adapter（下一階段）
  - 不修改前端管理介面的功能（只調整 API 路徑）
  - 不變更 MCP 工具的行為

## Decisions

### 1. 使用 Python Protocol 而非 Abstract Base Class
- **決定**：使用 `typing.Protocol` 定義 Adapter 介面
- **原因**：結構化子型態（structural subtyping），不需要繼承，更 Pythonic
- **替代方案**：ABC — 需要繼承，較重量級；TypedDict — 不適合定義方法

### 2. 標準化介面 + 可選擴展 Protocol
- **決定**：分兩層設計
  - `BotAdapter`：所有平台必須實作（send_text, send_image, send_file）
  - `EditableMessageAdapter`：可選（edit_message, delete_message）
  - `ProgressNotifier`：可選（send_progress, update_progress, finish_progress）
- **原因**：避免最低公約數問題，平台特有功能透過 `isinstance()` 檢查啟用
- **參考**：Moltbot 的 `capabilities` 欄位 + 可選 adapter

### 3. 資料表重新命名策略
- **決定**：使用 Alembic migration 將 `line_*` 改為 `bot_*`，加 `platform_type` 欄位
- **遷移計畫**：
  1. 新增 migration：ALTER TABLE RENAME + ADD COLUMN platform_type
  2. 設定既有資料 `platform_type = 'line'`
  3. 建立舊表名的 VIEW 做向後相容（過渡期）
- **替代方案**：建立全新表 + 資料遷移 — 風險太高，不採用

### 4. 程式碼重組結構
```
services/
├── bot/                        # 平台無關核心
│   ├── __init__.py
│   ├── adapter.py              # BotAdapter Protocol 定義
│   ├── ai.py                   # AI 處理核心（從 linebot_ai.py 抽出）
│   ├── agents.py               # Agent 管理（從 linebot_agents.py 改名）
│   ├── message.py              # BotMessage, BotContext 資料模型
│   └── media.py                # 媒體處理（暫存、NAS 存取）
├── bot_line/                   # Line 平台 Adapter
│   ├── __init__.py
│   ├── adapter.py              # LineBotAdapter 實作
│   ├── webhook.py              # Line webhook 驗證/解析
│   ├── handler.py              # Line 事件處理
│   └── service.py              # Line 專屬業務邏輯（綁定、群組管理等）
└── (未來) bot_telegram/        # Telegram 平台 Adapter
```

### 5. 測試策略
- **決定**：重構前先建立測試保護，確保核心功能不壞
- **範圍**：
  - AI 處理流程（prompt 建構、回應解析、FILE_MESSAGE 提取）
  - 訊息發送邏輯（reply、push、fallback）
  - 存取控制（綁定檢查、群組權限）
  - 資料庫操作（CRUD for groups, users, messages, files）
- **工具**：pytest + pytest-asyncio，mock Line SDK

## Risks / Trade-offs
- **風險**：資料表重新命名可能影響正在運行的服務
  - 緩解：使用 VIEW 做過渡、停機時段執行 migration
- **風險**：前端 API 路徑變更影響使用者
  - 緩解：保留舊路徑 redirect，或直接修改前端（內部系統）
- **風險**：重構範圍大（7000+ 行），可能引入 regression
  - 緩解：先建立測試保護，分階段執行，每階段驗證

## Migration Plan
1. 建立測試保護（不動任何生產程式碼）
2. 建立 `services/bot/` 核心模組（新檔案，不動舊檔案）
3. 建立 `services/bot_line/adapter.py`（包裝現有 linebot.py）
4. 逐步將 `linebot_ai.py` 的平台無關邏輯遷移到 `bot/ai.py`
5. 將 `linebot_agents.py` 遷移到 `bot/agents.py`
6. 執行資料表 migration
7. 更新 API router 和前端
8. 移除舊檔案，清理 import

## Open Questions
- ~~API 路徑是否要從 `/api/linebot/` 改為 `/api/bot/`？~~ **已完成**：前端和後端已遷移至 `/api/bot/`，webhook 在 `/api/bot/line/webhook`（PR #26, #28）
- 前端 linebot.js 是否也要改名？
  - 建議：改為 `bot-manager.js`，但可在後續階段處理
