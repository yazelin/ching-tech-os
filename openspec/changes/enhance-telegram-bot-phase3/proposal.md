# Change: Telegram Bot Phase 3 — 完整功能實作

## Why
Phase 2 完成了基本的 AI 文字對話（單輪、無歷史、無綁定、無群組），但缺少以下關鍵功能：
1. **AI Log 記錄**：Telegram 對話沒有寫入 `ai_logs`，無法追蹤用量與除錯
2. **對話歷史**：每次都是全新對話，AI 沒有上下文記憶
3. **用戶綁定**：任何人都能使用 Bot，沒有存取控制
4. **群組支援**：只處理私訊，群組 @Bot 沒有反應
5. **圖片/檔案接收**：只處理文字，忽略圖片和檔案訊息

這些功能在 Line Bot 端已經完整實作，Telegram Bot 需要對齊。

## What Changes

### 後端修改
- **handler.py**：大幅擴充，加入綁定檢查、群組處理、圖片/檔案接收、對話歷史、AI Log
- **adapter.py**：無重大變更（Phase 1 已完整實作）
- **新增 `services/bot_telegram/media.py`**：Telegram 圖片/檔案下載與 NAS 儲存
- **linebot_ai.py**：抽取可共用的函式（`get_conversation_context`、`log_ai_call`）為平台無關版本，或 Telegram handler 直接呼叫

### 資料庫
- 不需要新的 migration（Phase 0 已完成欄位重命名，現有表結構支援 `platform_type='telegram'`）
- Telegram 訊息寫入 `bot_messages`（`platform_type='telegram'`）
- Telegram 用戶寫入 `bot_users`（`platform_type='telegram'`）
- Telegram 群組寫入 `bot_groups`（`platform_type='telegram'`）

### 不在此次範圍
- 前端管理介面（Phase 4）
- 文件更新（Phase 5）
- ProgressNotifier 整合（可在 Phase 3 後獨立加入）

## Impact
- 修改 spec：`telegram-bot`（已有完整 spec，此 change 是實作）
- 受影響程式碼：
  - 大幅修改：`services/bot_telegram/handler.py`
  - 新增：`services/bot_telegram/media.py`
  - 可能修改：`services/linebot_ai.py`（抽取共用邏輯）
