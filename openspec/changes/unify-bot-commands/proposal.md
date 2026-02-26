## Why

LINE 和 Telegram 的 `/start`、`/help` 各自獨立實作（Telegram 寫死在 handler，LINE 完全沒有），導致使用者體驗不一致。LINE 使用者加好友後沒有歡迎訊息，不知道要去 CTOS 綁定帳號。此外，目前沒有機制可以停用特定指令，運營上缺乏彈性。

## What Changes

- 將 `/start`（歡迎訊息）和 `/help`（指令說明）移入 CommandRouter，LINE 和 Telegram 共用
- LINE `FollowEvent`（加好友）觸發歡迎訊息，告知使用者如何綁定 CTOS 帳號
- `/help` 自動列出所有已註冊且該平台可用的指令，不再寫死內容
- 新增指令啟用/停用開關（設定檔或環境變數控制），停用的指令不會被 CommandRouter 匹配
- 移除 Telegram handler 中寫死的 `/start`、`/help` 處理邏輯

## Capabilities

### New Capabilities
- `bot-command-toggle`: 指令啟用/停用開關機制，支援透過設定檔或環境變數控制每個指令的啟用狀態

### Modified Capabilities
- `bot-slash-commands`: 新增 `/start` 和 `/help` 指令定義、自動列出指令清單、指令啟用/停用支援
- `line-bot`: LINE FollowEvent 發送歡迎訊息

## Impact

- `backend/src/ching_tech_os/services/bot/command_handlers.py` — 新增 `/start`、`/help` handler 註冊
- `backend/src/ching_tech_os/services/bot/commands.py` — CommandRouter 加入 `enabled` 欄位和過濾邏輯
- `backend/src/ching_tech_os/services/bot_telegram/handler.py` — 移除寫死的 `/start`、`/help`、`HELP_MESSAGE`、`START_MESSAGE`
- `backend/src/ching_tech_os/api/linebot_router.py` — `process_follow_event` 加發歡迎訊息
- `backend/src/ching_tech_os/config.py` — 新增指令開關設定項
