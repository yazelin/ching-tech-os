## Why

目前具備 start/check 模式的背景長時間任務（`/research`、影片下載、音訊轉錄）完成後，使用者必須主動詢問才能取得結果，體驗不佳。新增「主動推送」開關，讓 Bot 在任務完成後自動通知使用者，減少等待摩擦。

## What Changes

- 新增 `bot_settings` 設定項目：每個平台可獨立設定是否啟用主動推送
  - Line：預設 **關閉**（因 Line Push API 有費用/配額考量）
  - Telegram：預設 **開啟**（Telegram 無此限制）
- 所有具 start/check 模式的背景任務（research-skill、media-downloader、media-transcription）完成後，若平台啟用主動推送，自動向發起任務的使用者/群組推送結果
- 未啟用時維持現有行為：使用者主動詢問時才回覆結果
- 新增前端管理介面：在系統設定 Bot 設定頁面加入主動推送開關

## Capabilities

### New Capabilities
- `bot-proactive-push`：主動推送設定管理（讀寫 `bot_settings`）、推送執行介面（供背景任務呼叫）、Line/Telegram 各平台推送實作

### Modified Capabilities
- `line-bot`：新增主動推送行為 — 任務完成時依設定決定是否主動推送結果
- `bot-platform`：Telegram 主動推送預設開啟，背景任務完成通知機制
- `research-skill`：研究任務完成後呼叫推送介面，通知發起任務的使用者
- `media-downloader`：影片下載完成後呼叫推送介面
- `media-transcription`：音訊/影片轉錄完成後呼叫推送介面

## Impact

- **資料庫**：`bot_settings` 新增 key `proactive_push_enabled`（per platform，value `"true"` / `"false"`）
- **後端服務**：新增 `proactive_push_service.py`（或在 `linebot_agents.py` / `telegram handler` 擴充），提供 `notify_user(platform, user_id, group_id, message)` 介面
- **背景 skill**：`research-skill`、`media-downloader`、`media-transcription` 的背景 worker 完成時呼叫推送介面
- **前端**：系統設定 Bot 設定頁面新增主動推送開關（每個平台獨立）
- **API**：`PUT /api/admin/bot-settings/{platform}` 擴充支援 `proactive_push_enabled` 欄位
