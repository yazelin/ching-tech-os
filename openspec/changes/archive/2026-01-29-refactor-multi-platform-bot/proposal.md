# Change: 重構 LineBot 為多平台 Bot Adapter 架構

## Why
目前所有 Bot 相關邏輯（AI 處理、訊息發送、資料存取）都與 Line 平台深度耦合，無法擴展至 Telegram 等其他平台。需要將平台無關的核心邏輯抽離，建立標準化 Adapter 介面，讓未來新增平台只需實作 Adapter 而不需修改核心 AI 流程。

## What Changes
- 新增 `bot-platform` spec：定義平台無關的 BotAdapter Protocol 與 BotMessage 資料模型
- 抽離 AI 處理核心（`linebot_ai.py` → `bot_ai.py` + `linebot/ai_handler.py`）
- 抽離 Agent 管理（`linebot_agents.py` → `bot_agents.py`）
- **BREAKING**：資料表重新命名 `line_*` → `bot_*`，新增 `platform_type` 欄位
- **DONE**：API 路徑已從 `/api/linebot/` 遷移至 `/api/bot/`，webhook 移至 `/api/bot/line/webhook`（PR #26, #28）
- 新增測試保護：在重構前為現有 LineBot 核心功能建立整合測試

## Impact
- Affected specs: `line-bot`, 新增 `bot-platform`
- Affected code:
  - `services/linebot.py` (3324 行) → 拆分為 `services/bot/` 模組
  - `services/linebot_ai.py` (1473 行) → 拆分為 `services/bot_ai.py` + 平台 handler
  - `services/linebot_agents.py` (919 行) → 改名為 `services/bot_agents.py`
  - `api/linebot_router.py` (1021 行) → 重構為 `api/bot_router.py`
  - `models/linebot.py` (310 行) → 重構為 `models/bot.py`
  - `frontend/js/linebot.js` 及相關前端檔案
  - `services/mcp_server.py` — 143 處 `line_*` 表名引用
  - 所有 Alembic migration（新增 rename migration）
