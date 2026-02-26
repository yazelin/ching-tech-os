## 1. SlashCommand 資料結構擴充

- [x] 1.1 `SlashCommand` 新增 `description: str = ""` 欄位（`bot/commands.py`）
- [x] 1.2 `SlashCommand` 新增 `enabled: bool = True` 欄位（`bot/commands.py`）
- [x] 1.3 `CommandRouter.parse()` 加入 `enabled` 過濾：匹配到 `enabled=False` 的指令時回傳 None

## 2. 指令啟用/停用開關

- [x] 2.1 `config.py` 新增 `bot_cmd_disabled: list[str]` 設定項，讀取 `BOT_CMD_DISABLED` 環境變數（逗號分隔，大小寫不敏感）
- [x] 2.2 `register_builtin_commands()` 讀取 `settings.bot_cmd_disabled`，將對應指令設為 `enabled=False`

## 3. /start 和 /help 指令實作

- [x] 3.1 `command_handlers.py` 新增 `get_welcome_message()` 函式，回傳歡迎訊息文字（含功能介紹、綁定步驟、/help 提示）
- [x] 3.2 `command_handlers.py` 新增 `_handle_start()` handler，呼叫 `get_welcome_message()` 回傳歡迎訊息
- [x] 3.3 `command_handlers.py` 新增 `_handle_help()` handler，遍歷 `router._commands` 動態生成指令列表（根據平台、角色過濾，管理員指令標註）
- [x] 3.4 `register_builtin_commands()` 註冊 `/start`（`private_only=True`, `require_bound=False`）和 `/help`（`private_only=True`, `require_bound=False`）
- [x] 3.5 所有現有指令（`/reset`、`/debug`）補上 `description` 欄位

## 4. 移除 Telegram 寫死邏輯

- [x] 4.1 移除 `bot_telegram/handler.py` 中的 `START_MESSAGE` 和 `HELP_MESSAGE` 常數
- [x] 4.2 移除 `handler.py` 中 `/start` 和 `/help` 的 if 區塊

## 5. LINE FollowEvent 歡迎訊息

- [x] 5.1 `linebot_router.py` 的 `process_follow_event()` 呼叫 `get_welcome_message()` 取得歡迎訊息
- [x] 5.2 使用 LINE push message API 發送歡迎訊息給新加好友的用戶

## 6. 測試

- [x] 6.1 測試 `CommandRouter.parse()` 跳過 `enabled=False` 的指令
- [x] 6.2 測試 `_handle_help()` 根據角色過濾指令列表（管理員 vs 一般用戶）
- [x] 6.3 測試 `BOT_CMD_DISABLED` 設定項正確解析
- [x] 6.4 測試 `/start` 和 `/help` 在 LINE 和 Telegram 回覆一致
- [x] 6.5 驗證 Telegram 移除寫死邏輯後 `/start`、`/help` 仍正常運作
