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
| 媒體下載 | 從網路下載影片/音訊檔案到 NAS |
| 逐字稿轉錄 | 將影片/音訊轉錄為逐字稿文字 |
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
| 指令 | 共用 CommandRouter：`/start`、`/help`、`/reset`、`/debug`、`/agent` | 共用 CommandRouter：`/start`、`/help`、`/reset`、`/debug`、`/agent` |
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

LINE 和 Telegram 共用 `CommandRouter` 框架（`services/bot/commands.py`），所有指令統一定義在 `services/bot/command_handlers.py`。

| 指令 | 說明 | 別名 | 可用範圍 | 權限 |
|------|------|------|----------|------|
| `/start` | 歡迎訊息（功能介紹 + 帳號綁定步驟） | - | 私訊 | 不需綁定 |
| `/help` | 動態列出所有已註冊的可用指令 | `/說明` | 私訊 | 不需綁定 |
| `/reset` | 重置對話歷史 | `/新對話`、`/清除對話`、`/忘記` 等 | 私訊 | 不需綁定 |
| `/debug` | 管理員系統診斷（AI 分析 logs） | `/診斷`、`/diag` | 私訊 | 需綁定 + 管理員 |
| `/agent` | 切換對話使用的 AI Agent | `/切換助理` | 私訊 + 群組 | 需綁定 + 管理員 |

> **指令開關**：可透過環境變數 `BOT_CMD_DISABLED`（逗號分隔）停用特定指令，如 `BOT_CMD_DISABLED=debug,start`。
> **Agent 切換**：詳見 [linebot.md Agent 切換章節](linebot.md#agent-切換agent-指令)。

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
- 未綁定用戶行為由 `BOT_UNBOUND_USER_POLICY` 控制：`reject`（預設，回覆綁定提示）或 `restricted`（受限模式 AI 對話，有頻率限制）
- 受限模式的歡迎訊息、綁定提示、頻率限制訊息等可透過 `bot-restricted` Agent 的 `settings` 自訂，詳見 [Line Bot 文件 - 受限模式設定](linebot.md#受限模式設定)

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

# Local Bot API Server（可選，突破 20MB 下載限制，支援 2GB 檔案接收）
TELEGRAM_API_ID=your_api_id                        # 從 https://my.telegram.org 取得
TELEGRAM_API_HASH=your_api_hash                    # 從 https://my.telegram.org 取得
TELEGRAM_LOCAL_API_URL=http://localhost:8081        # Local API Server URL
TELEGRAM_LOCAL_API_DATA_DIR=/tmp/telegram-bot-api   # Local API 資料目錄

# Bot 多模式平台設定（LINE/Telegram 共用）
BOT_UNBOUND_USER_POLICY=reject                     # reject | restricted
BOT_RESTRICTED_MODEL=haiku                         # 受限模式使用的 AI 模型
BOT_DEBUG_MODEL=sonnet                             # /debug 指令使用的模型
BOT_CMD_DISABLED=                                  # 停用指令（逗號分隔，如 debug,start）
BOT_RATE_LIMIT_ENABLED=true                        # 受限模式頻率限制開關
BOT_RATE_LIMIT_HOURLY=20                           # 每小時上限（未綁定用戶）
BOT_RATE_LIMIT_DAILY=50                            # 每日上限（未綁定用戶）
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

### Local Bot API Server（可選）

Telegram Bot API 預設限制 `getFile` 只能下載 20MB 以內的檔案。透過自架 [Local Bot API Server](https://github.com/tdlib/telegram-bot-api)，可將限制提升至 **2GB**，且檔案直接存在本機檔案系統。

**啟動方式：**

1. 到 [my.telegram.org](https://my.telegram.org) 取得 `api_id` 和 `api_hash`（免費，一個帳號一組，可多台共用）
2. 在 `.env` 設定 `TELEGRAM_API_ID`、`TELEGRAM_API_HASH`、`TELEGRAM_LOCAL_API_URL`、`TELEGRAM_LOCAL_API_DATA_DIR`
3. systemd 服務啟動時會自動偵測 `TELEGRAM_LOCAL_API_URL`，有設定才啟動 Local API container

**架構差異：**

```
# 預設模式（20MB 限制）
使用者 → Telegram 雲端 → api.telegram.org → 後端

# Local API 模式（2GB 限制）
使用者 → Telegram 雲端 → 自架 Local API Server → 後端（直接讀本機檔案）
```

**注意事項：**
- `api_id`/`api_hash` 綁定 Telegram 帳號，可多台主機共用
- 同一個 Bot Token 只能被一個 polling 實例使用
- Local API 的資料目錄需設定 ACL 讓後端服務可讀取（systemd service 會自動處理）
- 不設定 `TELEGRAM_LOCAL_API_URL` 時，程式碼完全走原路徑，無任何影響

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
