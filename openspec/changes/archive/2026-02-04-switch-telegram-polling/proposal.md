# Change: 將 Telegram Bot 從 Webhook 模式切換為 Polling 模式

## Why
目前 Telegram Bot 使用 Webhook 模式，當伺服器 IP 變動時 webhook URL 會失效，需要手動或透過健康檢查重新註冊。改用 Polling（`getUpdates`）模式後，由伺服器主動向 Telegram 拉取訊息，完全不受 IP 變動影響，也不需要 public URL。

## What Changes
- **保留** 舊有 webhook 程式碼（endpoint、setup 函式、config 設定），不移除
- **新增** polling 服務：啟動時以 `asyncio.Task` 執行長輪詢迴圈，呼叫 `getUpdates` 拉取訊息
- **修改** 應用程式啟動流程：lifespan 改呼叫 polling 取代 `setup_telegram_webhook()`
- **停用** webhook 健康檢查排程（保留程式碼，僅不註冊排程）

## Impact
- Affected specs: `bot-platform`
- Affected code:
  - `services/bot_telegram/polling.py` — **新增** polling 迴圈
  - `main.py` — lifespan 改啟動 polling task
  - `services/scheduler.py` — 停用 webhook 健康檢查排程
  - `api/telegram_router.py` — 保留不動
  - `services/bot_telegram/handler.py` — 無變更（處理 Update 的邏輯不變）
  - `config.py` — 保留不動
