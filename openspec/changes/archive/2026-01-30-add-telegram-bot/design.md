## Context

系統已完成多平台重構，`bot/adapter.py` 定義了三個 Protocol：
- `BotAdapter`（必要）：send_text、send_image、send_file、send_messages
- `EditableMessageAdapter`（可選）：edit_message、delete_message
- `ProgressNotifier`（可選）：send_progress、update_progress、finish_progress

資料庫表格已重命名為 `bot_*` 且包含 `platform_type` 欄位，但欄位名仍有殘留的 `line_*` 需要修正。

參考專案 `~/SDD/telegram-bot/` 已驗證 `python-telegram-bot` 22.x + Claude CLI 整合可行。

## Goals / Non-Goals

**Goals:**
- 實作與 Line Bot 功能對等的 Telegram Bot
- 1 個 CTOS 用戶可同時綁定多個平台（Line + Telegram 各自獨立）
- 各平台訊息完全隔離（從哪來回哪去、歷史不混）
- 利用 Telegram 原生能力（訊息編輯、進度通知、原生檔案發送）
- 共用 AI 核心、Agent 管理、資料庫結構
- 測試覆蓋確保穩定性

**Non-Goals:**
- Telegram inline mode
- Telegram payment 整合
- 管理介面大規模重寫（僅擴展篩選功能）
- 多租戶 Telegram independent bot mode（第一版用 shared mode）

## Decisions

### D1: Webhook 模式整合到 FastAPI

使用 `python-telegram-bot` 22.x 的 webhook 模式，整合到現有的 FastAPI 應用程式。

**原因：**
- 系統已有公開 HTTPS URL（`ching-tech.ddns.net`）+ nginx
- 與 Line Bot 統一架構（都是接收 POST webhook）
- 資源效率高、即時回應
- 生產環境最佳實踐

**整合方式：**
```python
# FastAPI 啟動時初始化 Telegram Application（不啟動 polling）
telegram_app = Application.builder().token(TOKEN).build()
await telegram_app.initialize()
await telegram_app.bot.set_webhook(url=WEBHOOK_URL, secret_token=SECRET)

# Webhook route 接收 Update，手動餵給 telegram_app 處理
@router.post("/api/bot/telegram/webhook")
async def telegram_webhook(request: Request):
    # 驗證 X-Telegram-Bot-Api-Secret-Token header
    update = Update.de_json(await request.json(), telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}
```

**設定項（vs Line Bot）：**
| | Line Bot | Telegram Bot |
|---|---|---|
| 認證 | `LINE_CHANNEL_SECRET` + `LINE_CHANNEL_ACCESS_TOKEN` | `TELEGRAM_BOT_TOKEN`（一個搞定） |
| Webhook 驗證 | X-Line-Signature（HMAC-SHA256） | X-Telegram-Bot-Api-Secret-Token（自訂 secret） |
| Webhook URL | Line Developer Console 設定 | 程式啟動時呼叫 `set_webhook` API 註冊 |
| 額外設定 | `line_bot_trigger_names`（群組 @ 觸發名稱） | 不需要（Telegram 用 @username 天然支援） |

**替代方案：**
- Polling 模式：測試專案用此方案，但需要額外管理背景 process 生命週期，不適合生產
- `aiogram`：更輕量但生態系較小

### D2: 不新增平行表，共用 `bot_*` 表格

**原因：**
- 兩個平台的資料結構相同（群組、用戶、訊息、檔案）
- `platform_type` 欄位已能區分
- 避免資料同步和 N+1 表格問題

**需要修正的欄位名（殘留的 line_*）：**

| 表格 | 舊欄位名 | 新欄位名 |
|---|---|---|
| `bot_users` | `line_user_id` | `platform_user_id` |
| `bot_groups` | `line_group_id` | `platform_group_id` |
| `bot_messages` | `line_user_id` | `bot_user_id` |
| `bot_messages` | `line_group_id` | `bot_group_id` |
| `bot_binding_codes` | `used_by_line_user_id` | `used_by_bot_user_id` |
| `bot_user_memories` | `line_user_id` | `bot_user_id` |
| `bot_files` | `line_message_id`（若有） | `bot_message_id` |
| `bot_files` | `line_group_id`（若有） | `bot_group_id` |

**索引修正：**
- `idx_line_users_tenant_line_user_unique (tenant_id, line_user_id)` → `(tenant_id, platform_type, platform_user_id)` — 加入 platform_type 確保唯一性跨平台正確
- 同理 `bot_groups` 的唯一索引也要包含 `platform_type`
- 新增 `platform_type` 查詢用索引

### D3: 多平台綁定設計

**核心概念：1 個 CTOS 用戶 ↔ 多個 bot_user（每平台一個）**

```
users (CTOS)           bot_users
┌──────────┐           ┌─────────────────────────────────┐
│ id: 1    │◄──────────│ id: aaa, platform: line,    user_id: 1 │
│ name: CT │◄──────────│ id: bbb, platform: telegram, user_id: 1 │
└──────────┘           └─────────────────────────────────┘
```

- `bot_users.user_id` → `users.id`：多對一（同一個 CTOS 用戶可有多筆 bot_user）
- 綁定流程不變：CTOS 產生驗證碼 → 在對應平台私訊 Bot → 建立該平台的 bot_user 並設定 user_id
- `bot_binding_codes` 不需要 platform_type（驗證碼本身是平台無關的，由接收端決定建哪個平台的 bot_user）

**歷史記錄隔離：**
```
Line user (bot_user: aaa) → bot_messages (bot_user_id: aaa)
Telegram user (bot_user: bbb) → bot_messages (bot_user_id: bbb)
```
不同平台的 bot_user 是不同記錄，所以訊息天然隔離。

### D4: 共享 AI 處理協調器

從 `linebot_ai.py` 抽取平台無關邏輯到 `bot/processor.py`：

```
任何平台 webhook → Handler → 建構 BotContext + BotMessage
                          → bot/processor.py：
                             1. 存取控制檢查
                             2. 組合 system prompt（Agent + 權限 + 記憶）
                             3. 組合對話歷史
                             4. 呼叫 Claude CLI
                             5. 解析回應（FILE_MESSAGE、nanobanana 圖片）
                             6. 回傳 BotResponse
                          → Adapter 發送結果
```

Line 和 Telegram 各自負責：
- Webhook 驗證、事件解析
- BotMessage/BotContext 建構
- 透過各自 Adapter 發送結果
- 平台特定功能（Line 的 reply_token、Telegram 的進度通知）

### D5: 進度通知

Telegram 的 `edit_message_text` 可即時更新訊息（測試專案已驗證）：
1. AI 開始 → `send_progress("🤖 處理中...")`
2. Tool 開始 → `update_progress("🔧 搜尋中...")`
3. Tool 完成 → `update_progress("✅ 搜尋完成")`
4. AI 完成 → `finish_progress()`（刪除通知訊息）→ 發送最終結果

核心處理邏輯用 `isinstance(adapter, ProgressNotifier)` 判斷是否啟用。
Line 不支援此 Protocol，所以 Line Bot 行為不變。

### D6: 檔案儲存路徑

```
NAS:   {ctos_mount_path}/linebot/files/telegram/groups/{group_id}/{date}/{msg_id}_{filename}
暫存:  /tmp/telegram-images/{msg_id}.jpg
       /tmp/telegram-files/{msg_id}_{filename}
```

## Risks / Trade-offs

- **風險**：欄位重命名是 breaking change，所有引用舊欄位名的程式碼都要更新
  - 緩解：migration 加入向後相容（DO alias 或一次性全改）、回歸測試覆蓋
- **風險**：`python-telegram-bot` webhook 模式需要手動整合到 FastAPI
  - 緩解：有官方文件和社群範例，測試專案已驗證 library 可用
- **風險**：Telegram API rate limit（每秒 30 則 / 群組每分鐘 20 則）
  - 緩解：初期使用者量不大，後續再加 rate limiting
- **風險**：AI 處理核心抽取可能影響 Line Bot
  - 緩解：先寫回歸測試再重構

## Migration Plan

1. Phase 0: 資料庫欄位重命名 + 回歸測試（先做，減少後續風險）
2. Phase 1: 基礎架構（Adapter + Webhook + 基本文字收發）
3. Phase 2: AI 處理整合（共享核心 + 進度通知）
4. Phase 3: 完整功能（圖片/檔案、綁定、記憶、存取控制）
5. Phase 4: 前端管理擴展
6. Phase 5: 測試與文件

## Open Questions

1. Telegram Bot 是否需要支援多租戶 independent mode？→ 第一版先 shared mode
2. 是否需要 Telegram inline query 支援？→ Non-goal
3. Telegram 群組中的 @ 觸發：Telegram 天然支援 @username，不需要像 Line 一樣配置觸發名稱列表
