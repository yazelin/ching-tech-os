# Telegram Bot 整合

> **注意**：Telegram Bot 與 Line Bot 共用相同的 `bot_*` 資料表（`bot_messages`、`bot_groups`、`bot_users`、`bot_files`），
> 透過 `platform_type = 'telegram'` 欄位區分平台。

Telegram Bot 整合功能，實現 Telegram 訊息儲存、AI 助理回應、帳號綁定與群組管理。

## 架構

```
Telegram Platform
     │
     ▼ Polling（getUpdates long polling）
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI                                                         │
│  ┌─────────────────┐    ┌─────────────────────────────────────┐ │
│  │ bot_telegram/    │    │ linebot_ai.py（共用 AI 處理）       │ │
│  │ polling.py       │───▶│ - build_system_prompt               │ │
│  │ - getUpdates     │    │ - get_conversation_context          │ │
│  └─────────────────┘    │ - log_linebot_ai_call               │ │
│         │                └──────────────┬──────────────────────┘ │
│         ▼                              ▼                         │
│  ┌─────────────────┐    ┌─────────────────────────────────────┐ │
│  │ bot_telegram/    │    │ mcp_server.py                       │ │
│  │ - handler.py     │    │ - 專案管理、知識庫、NAS 搜尋       │ │
│  │ - adapter.py     │    │ - AI 圖片生成、分享連結等           │ │
│  │ - media.py       │    └─────────────────────────────────────┘ │
│  └─────────────────┘                                             │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────┐    ┌─────────────┐                             │
│  │ PostgreSQL  │    │ NAS 檔案    │                             │
│  │ bot_*       │    │ 附件儲存    │                             │
│  └─────────────┘    └─────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

## 功能總覽

| 功能 | 說明 |
|------|------|
| 訊息儲存 | 自動儲存所有群組/私訊到資料庫 |
| 檔案儲存 | 圖片、檔案自動下載到 NAS |
| AI 對話 | 私訊/群組對話支援 AI 助理（與 Line Bot 共用 Agent） |
| 自訂記憶 | 群組/個人可設定自訂記憶 |
| AI 圖片生成 | 根據文字描述生成圖片、編輯圖片 |
| 文件讀取 | 支援讀取 Word、Excel、PowerPoint、PDF 文件內容 |
| 專案管理 | 透過對話建立專案、新增成員和里程碑 |
| 知識庫 | 透過對話新增筆記、搜尋知識、管理附件 |
| NAS 檔案搜尋 | 搜尋並發送 NAS 共享檔案 |
| 公開分享 | 建立知識庫/專案/檔案的公開連結 |
| 帳號綁定 | 6 位數驗證碼綁定 CTOS 帳號 |
| 回覆引用 | 回覆訊息時自動帶入被回覆的內容（含圖片和檔案） |

## 與 Line Bot 的差異

| 項目 | Line Bot | Telegram Bot |
|------|----------|-------------|
| 訊息接收 | Webhook | Polling（getUpdates） |
| 多租戶 | 支援獨立 Bot / 共用 Bot | 目前使用預設租戶 |
| 群組觸發 | @Bot mention / 回覆 Bot | @Bot mention / 回覆 Bot |
| 群組 Mention 回覆 | 支援（TextMessageV2） | 不支援（Telegram 無此機制） |
| 進度通知 | 透過新訊息 | 透過 edit_message_text 原地更新 |
| 指令 | `/新對話`、`/reset` | `/start`、`/help`、`/reset`、`/新對話` |
| 資料庫表 | `bot_*`（platform_type='line'） | `bot_*`（platform_type='telegram'） |

## API 端點

### 訊息接收模式：Polling

目前使用 **polling（getUpdates）** 模式主動從 Telegram API 拉取訊息，不受伺服器 IP 變動影響。
Polling 在 FastAPI lifespan 啟動時以背景 `asyncio.Task` 執行，關閉時自動停止。

> **備註**：舊的 webhook endpoint（`POST /api/bot/telegram/webhook`）程式碼仍保留，
> 如需切回可在 `main.py` lifespan 改回呼叫 `setup_telegram_webhook()` 並啟用排程健康檢查。

### 管理 API

Telegram Bot 的群組、用戶、訊息管理共用 Line Bot 的 API 端點，透過 `platform_type` 參數篩選：

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/bot/groups?platform_type=telegram` | 列表 Telegram 群組 |
| GET | `/api/bot/users?platform_type=telegram` | 列表 Telegram 用戶 |
| GET | `/api/bot/messages?platform_type=telegram` | 列表 Telegram 訊息 |

## 指令

| 指令 | 說明 | 可用範圍 |
|------|------|----------|
| `/start` | 顯示歡迎訊息和綁定步驟 | 私訊 |
| `/help` | 顯示使用說明 | 私訊 |
| `/reset` | 重置對話記錄 | 私訊 |
| `/新對話` | 重置對話記錄（中文別名） | 私訊 |

## 帳號綁定

Telegram 帳號綁定流程與 Line Bot 相同：

1. 用戶登入 CTOS 系統
2. 進入 Bot 管理頁面
3. 點擊「綁定帳號」產生 6 位數驗證碼
4. 在 Telegram 私訊 Bot 發送驗證碼
5. 系統驗證後將 `bot_users.user_id` 連結到 CTOS 帳號

## 群組使用

### 觸發條件

- **@Bot mention**：在群組中 @Bot 名稱觸發 AI 回覆
- **回覆 Bot 訊息**：回覆 Bot 之前發的訊息觸發 AI 回覆
- **圖片/檔案**：需回覆 Bot 訊息才觸發處理

### 存取控制

- 群組需要在前端管理介面開啟 `allow_ai_response` 才會回覆
- 用戶需要綁定 CTOS 帳號才能使用 AI 功能
- 未綁定用戶在群組中靜默忽略，私訊會回覆綁定提示

## 檔案儲存

Telegram Bot 收到的檔案會自動下載並儲存到 NAS：

```
NAS/{ctos_mount_path}/linebot/files/
├── telegram/
│   ├── groups/{chat_id}/
│   │   ├── images/{date}/{filename}
│   │   └── files/{date}/{filename}
│   └── users/{chat_id}/
│       ├── images/{date}/{filename}
│       └── files/{date}/{filename}
```

## 設定

### 環境變數

```bash
# Telegram Bot 設定
TELEGRAM_BOT_TOKEN=your_telegram_bot_token        # 從 @BotFather 取得
TELEGRAM_WEBHOOK_SECRET=your_webhook_secret        # 自訂字串，用於驗證 webhook
TELEGRAM_ADMIN_CHAT_ID=your_admin_chat_id          # 管理員 Telegram ID（啟動通知）
```

### BotFather 設定步驟

1. 在 Telegram 搜尋 `@BotFather`
2. 發送 `/newbot` 建立新 Bot
3. 設定 Bot 名稱和 username
4. 取得 Bot Token
5. 發送 `/setprivacy` 將 privacy mode 設為 `Disable`（允許 Bot 接收群組訊息）
6. 將 Bot 加入群組

### Polling 模式

應用程式啟動時自動以 long polling 模式拉取 Telegram 訊息，不需要 public URL 或 Nginx 代理。
啟動時會自動刪除既有 webhook 設定（polling 與 webhook 不能同時使用）。

## 程式碼結構

```
backend/src/ching_tech_os/
├── api/
│   └── telegram_router.py          # Telegram Webhook API
├── services/
│   └── bot_telegram/
│       ├── __init__.py
│       ├── adapter.py              # TelegramBotAdapter（發送訊息、編輯訊息）
│       ├── handler.py              # 事件處理（文字、圖片、檔案、指令）
│       ├── media.py                # 媒體下載與 NAS 儲存
│       └── polling.py              # Polling 迴圈（getUpdates long polling）
```

## MCP 工具

Telegram Bot 使用與 Line Bot 完全相同的 MCP 工具集。完整列表請參考 [docs/linebot.md](linebot.md#mcp-工具)。
