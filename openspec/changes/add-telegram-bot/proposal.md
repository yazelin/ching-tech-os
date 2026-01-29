# Change: 新增 Telegram Bot 支援

## Why
系統已完成多平台架構重構（BotAdapter Protocol），現在需要實際加入第二個平台 — Telegram Bot，讓使用者可以透過 Telegram 使用與 Line Bot 相同的 AI 助手功能。Telegram 原生支援訊息編輯和刪除，可以提供更好的 AI 處理進度體驗。

## What Changes

### 資料庫修正（前置作業）
- **BREAKING**：重命名殘留的 `line_*` 欄位名為平台無關名稱
  - `bot_users.line_user_id` → `platform_user_id`
  - `bot_messages.line_user_id` → `bot_user_id`
  - `bot_binding_codes.used_by_line_user_id` → `used_by_bot_user_id`
  - `bot_user_memories.line_user_id` → `bot_user_id`
  - `bot_groups.line_group_id`（若存在）→ `platform_group_id`
- 修正唯一索引：`(tenant_id, line_user_id)` → `(tenant_id, platform_type, platform_user_id)`
- 新增 `platform_type` 複合索引以提升查詢效能

### 後端新增
- 新增 `services/bot_telegram/` 模組（adapter、webhook、handler）
- 新增 Telegram Webhook 路由 `/api/bot/telegram/webhook`
- 新增 Telegram 設定項到 `config.py`
- 從 `linebot_ai.py` 抽取共享 AI 處理協調器到 `bot/processor.py`
- 整合現有 AI 處理核心（`bot/ai.py`、`bot/agents.py`）

### 綁定與存取控制
- 1 個 CTOS 用戶可以同時綁定 Line + Telegram（各自獨立的 bot_user 記錄）
- 綁定流程共用 `bot_binding_codes`（產生驗證碼 API 不變，每次綁定建立對應平台的 bot_user）
- Telegram 來的訊息只回 Telegram，Line 來的只回 Line
- 對話歷史按平台完全隔離（各自的 bot_user → 各自的 bot_messages）

### 前端修改
- Bot 管理 App 擴展支援平台篩選（全部 / Line / Telegram）
- 綁定頁面顯示各平台綁定狀態（可同時綁定多個平台）

### 測試
- 單元測試：TelegramBotAdapter 各方法
- 整合測試：Webhook 處理流程（mock telegram API）
- 回歸測試：Line Bot 功能不受影響（欄位重命名 + AI 核心抽取後）

## Impact
- 新增 spec：`telegram-bot`
- 修改 spec：`bot-platform`（共享 AI 處理協調器、欄位重命名）
- 修改 spec：`line-bot`（受欄位重命名影響）
- 受影響程式碼：
  - 新增：`services/bot_telegram/`、`api/telegram_router.py`、`bot/processor.py`
  - 修改：`config.py`、`main.py`、`linebot_ai.py`、`linebot_router.py`（欄位名更新）
  - 修改：所有引用 `line_user_id` 欄位的程式碼
  - 新增：migration `007_rename_line_columns_and_add_telegram_indexes.py`
  - 新增：`tests/test_telegram_bot.py`
