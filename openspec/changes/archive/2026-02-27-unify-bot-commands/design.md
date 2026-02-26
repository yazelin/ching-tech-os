## Context

目前 LINE 和 Telegram 的指令處理分為兩層：
1. **CommandRouter**（`bot/commands.py`）— 統一的指令路由框架，LINE 和 Telegram 共用，目前只註冊了 `/reset` 和 `/debug`
2. **平台專屬 handler** — Telegram 在 `handler.py` 中寫死了 `/start` 和 `/help`（`START_MESSAGE`、`HELP_MESSAGE` 常數），LINE 完全沒有這兩個指令

LINE 的 `FollowEvent`（加好友）只在 `linebot_router.py` 中建帳號，沒有發送歡迎訊息。

設定方面，`config.py` 已有 `BOT_*` 系列環境變數（`BOT_UNBOUND_USER_POLICY`、`BOT_DEBUG_MODEL` 等）。

## Goals / Non-Goals

**Goals:**
- `/start` 和 `/help` 統一到 CommandRouter，兩平台行為一致
- `/help` 動態列出已註冊指令（不再寫死內容），根據平台和使用者角色過濾
- LINE FollowEvent 發送歡迎訊息（與 `/start` 同內容）
- 每個指令可透過環境變數獨立啟用/停用
- 移除 Telegram handler 中的寫死邏輯

**Non-Goals:**
- 不做 Web UI 管理介面（指令開關透過環境變數控制）
- 不做動態新增指令（指令仍然在程式碼中註冊）
- 不做指令使用統計或 audit log

## Decisions

### D1: 指令開關用環境變數，而非 DB

**選擇**: `BOT_CMD_DISABLED=debug,start` 環境變數（逗號分隔的停用指令清單）

**替代方案**:
- DB 欄位控制 — 需要 migration + 管理 UI，過重
- 每個指令一個環境變數（`BOT_CMD_DEBUG_ENABLED=false`）— 指令多了環境變數會爆炸

**理由**: 一個環境變數管全部，簡單直覺。大部分情況只需要停用少數指令，用黑名單比白名單合理。

### D2: SlashCommand 加 `enabled` 欄位 + Router 層過濾

**選擇**: `SlashCommand` 新增 `enabled: bool = True`，`register_builtin_commands()` 讀取 `BOT_CMD_DISABLED` 設定值，符合的指令設 `enabled=False`。`CommandRouter.parse()` 跳過 `enabled=False` 的指令。

**替代方案**:
- 不註冊停用的指令 — 行為一樣但 `/help` 沒辦法顯示「此指令已停用」的資訊
- `dispatch()` 層過濾 — parse 已匹配成功但 dispatch 拒絕執行，語意不清楚

**理由**: parse 層過濾最乾淨，停用的指令等於不存在，會 fallback 到 AI 或被忽略。

### D3: /help 動態生成內容

**選擇**: `/help` handler 遍歷 `router._commands` 中已啟用的指令（去重 alias），根據 `ctx.platform_type` 過濾，組裝說明文字。

**格式範例**:
```
CTOS Bot 使用說明

直接傳送文字即可與 AI 對話
在群組中 @Bot 或回覆 Bot 訊息即可觸發

指令列表
/start — 歡迎訊息
/reset — 重置對話（別名：/新對話、/清除對話）
/debug — 系統診斷（管理員）

帳號綁定
發送 6 位數驗證碼完成綁定
```

管理員專用指令會標註「（管理員）」，`private_only` 指令標註「（僅限私聊）」。非管理員看不到 `require_admin=True` 的指令。

### D4: /start 訊息內容共用於 FollowEvent

**選擇**: `/start` handler 回傳歡迎訊息文字，LINE `process_follow_event` 也呼叫同一個函式取得訊息內容，透過 push message 發送。

**替代方案**:
- FollowEvent 直接呼叫 CommandRouter.dispatch — FollowEvent 沒有 text 訊息，語意不對
- 共用常數 — 跟現在 Telegram 的問題一樣，寫死在兩個地方

**理由**: 一個函式產生歡迎訊息，不管從 `/start` 指令還是 FollowEvent 觸發都一致。

### D5: SlashCommand 加 `description` 欄位

**選擇**: `SlashCommand` 新增 `description: str = ""`，`/help` 用此欄位生成指令說明。

**理由**: 指令名稱不夠描述功能，description 讓 `/help` 的輸出有意義。

## Risks / Trade-offs

- **[LINE push message 配額]** → LINE FollowEvent 用 push message 發送歡迎訊息會消耗推送配額。不過 FollowEvent 只觸發一次（加好友時），量很少。
- **[/help 內容長度]** → 指令多了 `/help` 輸出會變長。→ 短期指令數量可控（< 10），不需分頁。
- **[環境變數需要重啟]** → `BOT_CMD_DISABLED` 改了要重啟服務才生效。→ 可接受，跟其他 `BOT_*` 設定一致。

## Open Questions

（無）
