# Proposal: add-telegram-progress-notify

## Problem

Telegram Bot 的 AI 處理期間（通常需要 10-60 秒），用戶完全看不到任何進度資訊。
`TelegramBotAdapter` 已實作 `ProgressNotifier` protocol（`send_progress`、`update_progress`、`finish_progress`），
但 `handler.py` 在呼叫 `call_claude()` 時完全沒有使用。

參考專案 `~/SDD/telegram-bot` 已驗證此模式可行：
送出進度訊息 → 用 `edit_message` 原地更新 tool 狀態 → 完成後刪除通知。

## Solution

1. 為 `claude_agent.py` 的 `call_claude()` 新增 `on_tool_start` / `on_tool_end` callback 參數
2. 將現有的「收集全部 stdout 再解析」改為「即時串流解析 + 觸發 callback」
3. 在 `handler.py` 的 `_handle_text_with_ai()` 中接入 adapter 的 ProgressNotifier

## Scope

- **Modified**: `claude_agent.py` — 新增 callback 機制
- **Modified**: `bot_telegram/handler.py` — 接入進度通知
- **Spec delta**: `bot-platform` — 強化 ProgressNotifier 使用場景

## Out of scope

- Line Bot 進度通知（Line 不支援 edit_message）
- Web AI 助手進度通知（另案處理）
