## Context

目前三個具 start/check 模式的背景 skill（research-skill、media-downloader、media-transcription）在完成後只更新 `status.json`，由使用者主動呼叫 `check-*` 指令才能取得結果。

各平台推送能力現況：
- Line：`bot_line/messaging.py` 已有 `push_text()` / `push_messages()`，透過 Line Push API 傳送
- Telegram：`bot_telegram/adapter.py` 已有 `send_text()` / `send_messages()`，透過 Telegram Bot API 傳送
- 設定儲存：`bot_settings` 表（platform + key + value），已用於儲存憑證

背景 skill 的運作方式：Claude CLI 呼叫 start script → 立即回傳 job_id → 在子行程中執行實際工作，結果寫入 `status.json`。子行程結束時無法直接存取 FastAPI / MCP。

## Goals / Non-Goals

**Goals:**
- 背景任務完成後，可依平台設定決定是否主動推送結果給發起者
- Line 預設關閉、Telegram 預設開啟；可由管理員在前端切換
- 三個 skill 統一整合同一套推送機制
- 未啟用時行為完全不變（向下相容）

**Non-Goals:**
- 不支援排程推送或延遲推送
- 不處理推送失敗的重試（失敗靜默 log，不影響主流程）
- 不推送非 start/check 模式的一般 AI 回覆

## Decisions

### 1. 呼叫者上下文（caller context）的傳遞

**決策**：start script 接受 `caller_context` 欄位作為輸入，寫入 `status.json`；背景子行程完成時讀取此欄位決定推送對象。

```json
// status.json 新增欄位
{
  "caller_context": {
    "platform": "line",          // "line" | "telegram"
    "platform_user_id": "Uxxx",  // Line user ID 或 Telegram chat_id
    "is_group": false,
    "group_id": "Cxxx"           // 群組對話時填入，個人對話為 null
  }
}
```

**替代方案考慮**：由 check-* script 主動推送（被棄用）— check-* 是用戶手動呼叫的，只有用戶問了才執行，無法達到主動推送目的。

### 2. 推送觸發點

**決策**：背景子行程在寫入 `status: "completed"` 後，呼叫 FastAPI 內部端點 `POST /api/internal/proactive-push` 觸發推送。

```
[背景子行程] 完成 → 寫入 status.json (completed) → POST /api/internal/proactive-push {job_id, skill}
[FastAPI] → 讀 status.json caller_context → 檢查 bot_settings → 呼叫 push_text()
```

**替代方案考慮**：子行程直接呼叫 push API（被棄用）— 需要在子行程中載入完整 DB 連線與 Line/Telegram client，耦合度高且環境依賴複雜。

### 3. 推送服務設計

**決策**：新增 `services/proactive_push_service.py`，提供統一介面：

```python
async def notify_job_complete(
    platform: str,
    platform_user_id: str,
    is_group: bool,
    group_id: str | None,
    message: str,
) -> None
```

內部依 platform 分派：
- `"line"` → 讀取 `bot_settings` key `proactive_push_enabled`，若啟用呼叫 `push_text()`
- `"telegram"` → 讀取 `bot_settings` key `proactive_push_enabled`，若未明確設為 false 則呼叫 `send_text()`

### 4. bot_settings 儲存格式

**決策**：沿用現有 `bot_settings` 表，新增兩筆記錄：

| platform | key | value（預設） |
|---|---|---|
| `line` | `proactive_push_enabled` | `"false"` |
| `telegram` | `proactive_push_enabled` | `"true"` |

管理員透過既有 `PUT /api/admin/bot-settings/{platform}` 更新（擴充支援此 key）。

### 5. caller_context 的傳入方式

**決策**：由 AI（Claude CLI）在呼叫 start script 時自動附帶 `caller_context`。AI 的 system prompt 中已有 `platform_type`、`bot_user_id`、`group_id` 等上下文，可直接傳入。

- `linebot_agents.py` 組合 AI prompt 時注入 caller_context 說明
- AI 在呼叫 `start-research` / `download-video` / `transcribe` 時帶入此欄位

## Risks / Trade-offs

- **子行程呼叫 FastAPI**：若 FastAPI 服務未啟動或重啟中，推送呼叫會失敗 → 靜默 log，任務結果不受影響，使用者仍可手動 check
- **AI 忘記帶 caller_context**：推送將靜默跳過（caller_context 為 optional）→ 行為等同未啟用
- **Line Push API 費用**：Line 預設關閉，降低意外啟用風險

## Migration Plan

1. 新增 `proactive_push_service.py`
2. 新增 `/api/internal/proactive-push` 端點（僅限 localhost）
3. 三個 start script 新增 `caller_context` 欄位支援（不影響現有呼叫）
4. 三個背景子行程完成時呼叫內部端點
5. `bot_settings` migration：新增預設值記錄
6. 前端 Bot 設定頁面新增主動推送開關
7. 更新 AI system prompt，說明 `caller_context` 欄位

## Open Questions

- 推送訊息格式：直接轉發 skill 的結果摘要，還是固定格式通知？（建議：各 skill 自行組裝摘要訊息傳入 notify 函式）
- Telegram 的 `platform_user_id` 是 user chat_id 還是 group chat_id？（群組時應使用 group chat_id）
