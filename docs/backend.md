# 後端開發指南

使用 FastAPI + NAS SMB 認證的後端服務。

## 近期重點（2026-02）

- 引入 `modules.py` 模組 registry，透過 `ENABLED_MODULES` 做條件式路由 / MCP / 排程載入。
- 新增 `GET /api/config/apps`，前端可動態取得啟用 app 清單。
- Skill 系統支援 `contributes`（app / mcp_tools / scheduler）解析與註冊。
- Skills Hub 支援多來源（ClawHub + SkillHub），由 `SKILLHUB_ENABLED` 控制是否啟用 SkillHub。

## 需求

- Python 3.11+
- uv (Python 套件管理)
- Docker & Docker Compose
- 區網 NAS (192.168.11.50) 可連線

## 快速開始

### 1. 啟動 PostgreSQL

```bash
cd docker
docker compose up -d
```

### 2. 安裝依賴

```bash
cd backend
uv sync
```

### 3. 執行資料庫 Migration

```bash
cd backend
uv run alembic upgrade head
```

### 4. 啟動後端服務

```bash
cd backend
uv run uvicorn ching_tech_os.main:socket_app --host 0.0.0.0 --port 8088 --reload
```

服務將在 http://localhost:8088 啟動。

## API 文件

啟動後端後，訪問：
- Swagger UI: http://localhost:8088/docs
- ReDoc: http://localhost:8088/redoc

## 主要 API

### 認證

| 方法 | 端點 | 說明 |
|------|------|------|
| POST | `/api/auth/login` | 登入（CTOS 密碼優先，NAS SMB 備用） |
| POST | `/api/auth/logout` | 登出 |
| POST | `/api/auth/change-password` | 變更密碼（一般使用者自行變更） |

### 使用者

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/user/me` | 取得目前登入使用者資訊 |
| PATCH | `/api/user/me` | 更新目前登入使用者資訊 |
| GET | `/api/user/preferences` | 取得偏好設定 |
| PUT | `/api/user/preferences` | 更新偏好設定 |
| GET | `/api/user/list` | 取得使用者簡化列表（下拉選單用） |

### 管理員 - 使用者管理

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/admin/users` | 使用者列表（含認證方式） |
| POST | `/api/admin/users` | 建立使用者 |
| PATCH | `/api/admin/users/{user_id}` | 編輯使用者資訊 |
| PATCH | `/api/admin/users/{user_id}/permissions` | 更新使用者權限 |
| POST | `/api/admin/users/{user_id}/reset-password` | 重設密碼 |
| POST | `/api/admin/users/{user_id}/clear-password` | 清除密碼（恢復 NAS 認證） |
| PATCH | `/api/admin/users/{user_id}/status` | 停用/啟用帳號 |
| DELETE | `/api/admin/users/{user_id}` | 永久刪除使用者 |
| GET | `/api/admin/default-permissions` | 取得預設權限設定 |

### NAS 檔案操作

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/nas/shares` | 列出共享資料夾 |
| GET | `/api/nas/browse?path=/share_name` | 瀏覽資料夾 |
| POST | `/api/nas/upload` | 上傳檔案 |
| GET | `/api/nas/download` | 下載檔案 |
| DELETE | `/api/nas/delete` | 刪除檔案 |

### 知識庫

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/knowledge` | 搜尋/列表知識 |
| GET | `/api/knowledge/{id}` | 取得單一知識 |
| POST | `/api/knowledge` | 新增知識 |
| PUT | `/api/knowledge/{id}` | 更新知識 |
| DELETE | `/api/knowledge/{id}` | 刪除知識 |
| GET | `/api/knowledge/tags` | 取得所有標籤 |
| GET | `/api/knowledge/{id}/history` | 取得版本歷史 |

### AI 對話

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/ai/chats` | 列表對話 |
| POST | `/api/ai/chats` | 新增對話 |
| GET | `/api/ai/chats/{id}` | 取得對話 |
| DELETE | `/api/ai/chats/{id}` | 刪除對話 |
| PATCH | `/api/ai/chats/{id}` | 更新對話 |

### AI 管理

#### Prompts

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/ai/prompts` | 列表 Prompts（支援 category 過濾）|
| POST | `/api/ai/prompts` | 新增 Prompt |
| GET | `/api/ai/prompts/{id}` | 取得 Prompt 詳情 |
| PUT | `/api/ai/prompts/{id}` | 更新 Prompt |
| DELETE | `/api/ai/prompts/{id}` | 刪除 Prompt |

#### Agents

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/ai/agents` | 列表 Agents |
| POST | `/api/ai/agents` | 新增 Agent |
| GET | `/api/ai/agents/{id}` | 取得 Agent 詳情（含 Prompt）|
| GET | `/api/ai/agents/by-name/{name}` | 依名稱取得 Agent |
| PUT | `/api/ai/agents/{id}` | 更新 Agent |
| DELETE | `/api/ai/agents/{id}` | 刪除 Agent |
| POST | `/api/ai/test` | 測試 Agent |

#### AI Logs

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/ai/logs` | 列表 Logs（分頁、過濾）|
| GET | `/api/ai/logs/{id}` | 取得 Log 詳情 |
| GET | `/api/ai/logs/stats` | 取得統計資料 |

### Line Bot

#### Webhook

| 方法 | 端點 | 說明 |
|------|------|------|
| POST | `/api/bot/line/webhook` | Line Webhook 接收端點 |

#### 群組管理

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/bot/groups` | 列表群組 |
| GET | `/api/bot/groups/{id}` | 取得群組詳情 |
| POST | `/api/bot/groups/{id}/bind-project` | 綁定專案 |
| DELETE | `/api/bot/groups/{id}/bind-project` | 解除專案綁定 |
| GET | `/api/bot/groups/{id}/files` | 列出群組檔案 |

#### 用戶管理

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/bot/users` | 列表用戶 |
| GET | `/api/bot/users/{id}` | 取得用戶詳情 |

#### 訊息管理

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/bot/messages` | 列表訊息（支援過濾）|

#### 檔案管理

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/bot/files` | 列表檔案（支援過濾）|
| GET | `/api/bot/files/{id}` | 取得檔案詳情 |
| GET | `/api/bot/files/{id}/download` | 下載檔案 |

### 物料/庫存管理

#### 物料

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/inventory/items` | 列表物料（支援 keyword、category、low_stock 過濾） |
| GET | `/api/inventory/items/{id}` | 取得物料詳情（含進出貨記錄） |
| POST | `/api/inventory/items` | 新增物料 |
| PUT | `/api/inventory/items/{id}` | 更新物料 |
| DELETE | `/api/inventory/items/{id}` | 刪除物料 |
| GET | `/api/inventory/categories` | 取得物料類別列表 |
| GET | `/api/inventory/low-stock-count` | 取得庫存不足物料數量 |

#### 進出貨記錄

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/inventory/transactions` | 列表進出貨記錄（支援 item_id、type、project_id 過濾） |
| POST | `/api/inventory/transactions` | 新增進出貨記錄 |
| GET | `/api/inventory/transactions/{id}` | 取得記錄詳情 |
| DELETE | `/api/inventory/transactions/{id}` | 刪除記錄 |

### 廠商主檔

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/vendors` | 列表廠商（支援 keyword、category 過濾） |
| GET | `/api/vendors/{id}` | 取得廠商詳情 |
| POST | `/api/vendors` | 新增廠商 |
| PUT | `/api/vendors/{id}` | 更新廠商 |
| DELETE | `/api/vendors/{id}` | 刪除廠商 |
| GET | `/api/vendors/categories` | 取得廠商類別列表 |

### Bot 設定管理（管理員）

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/admin/bot-settings/{platform}` | 取得憑證狀態（遮罩顯示） |
| PUT | `/api/admin/bot-settings/{platform}` | 更新 Bot 憑證 |
| DELETE | `/api/admin/bot-settings/{platform}` | 清除憑證（回退至環境變數） |
| POST | `/api/admin/bot-settings/{platform}/test` | 測試連線 |

> `platform` 支援 `line` 和 `telegram`。憑證使用 AES-256-GCM 加密儲存，詳見 [安全機制](security.md)。

### Telegram Bot

| 方法 | 端點 | 說明 |
|------|------|------|
| POST | `/api/bot/telegram/webhook` | Telegram Webhook 接收端點 |

> Telegram 群組、用戶、訊息管理共用 Line Bot 的 `/api/bot/*` API，透過 `platform_type=telegram` 參數篩選。

### AI Skills

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/skills` | 列出可用 Skills（含 `has_module`） |
| GET | `/api/skills/{name}` | 取得 Skill 詳情（含 scripts / contributes） |
| GET | `/api/skills/{name}/meta` | 取得 Skill `_meta.json` |
| PUT | `/api/skills/{name}` | 更新 Skill metadata |
| DELETE | `/api/skills/{name}` | 移除 Skill |
| POST | `/api/skills/reload` | 重載 Skills |
| GET | `/api/skills/hub/sources` | 取得 Hub 來源列表 |
| POST | `/api/skills/hub/search` | 搜尋 Hub Skills |
| POST | `/api/skills/hub/inspect` | 預覽 Hub Skill |
| POST | `/api/skills/hub/install` | 安裝 Hub Skill |
| GET | `/api/skills/{name}/frontend/{file_path}` | 提供 Skill 前端靜態資源（含路徑防護） |
| GET | `/api/skills/{name}/files/{file_path}` | 讀取 Skill 檔案 |

### 公開配置

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/config/health` | 配置 API 健康檢查 |
| GET | `/api/config/apps` | 回傳啟用模組的桌面 app 清單 |

### 終端機 (WebSocket)

| 端點 | 說明 |
|------|------|
| `ws://host/terminal/{session_id}` | PTY shell session |

## 環境變數

可透過環境變數覆蓋預設設定：

| 變數 | 預設值 | 說明 |
|------|--------|------|
| NAS_HOST | 192.168.11.50 | NAS 主機位址 |
| DB_HOST | localhost | 資料庫主機 |
| DB_PORT | 5432 | 資料庫埠號 |
| DB_USER | ching_tech | 資料庫使用者 |
| DB_PASSWORD | （必填） | 資料庫密碼 |
| SESSION_TTL_HOURS | 8 | Session 有效時間（小時）|
| ENABLE_NAS_AUTH | True | 是否啟用 NAS SMB 認證 |
| BOT_SECRET_KEY | （無預設） | Bot 憑證加密金鑰（AES-256-GCM） |
| ENABLED_MODULES | `*` | 啟用模組清單（`*`=全開） |
| SKILLHUB_ENABLED | false | 是否啟用 SkillHub 來源 |
| SKILL_ROUTE_POLICY | script-first | Skills 路由策略（script-first / mcp-first） |
| SKILL_SCRIPT_FALLBACK_ENABLED | true | script 失敗且明確要求 fallback 時，是否回退到對應 MCP tool |

## 專案結構

```
backend/
├── pyproject.toml
├── alembic.ini
├── migrations/
│   └── versions/           # Migration 檔案（001-007）
├── src/ching_tech_os/
│   ├── main.py             # FastAPI 入口（含 Socket.IO）
│   ├── config.py           # 設定檔
│   ├── database.py         # 資料庫連線
│   ├── mcp_cli.py          # MCP CLI 入口
│   ├── api/
│   │   ├── auth.py           # 認證 API
│   │   ├── user.py           # 使用者管理 API（含管理員端點）
│   │   ├── nas.py            # NAS 操作 API
│   │   ├── knowledge.py      # 知識庫 API
│   │   ├── ai_router.py      # AI 對話 API
│   │   ├── ai_management.py  # AI 管理 API (Prompts/Agents/Logs)
│   │   ├── linebot_router.py # Line Bot API
│   │   ├── telegram_router.py # Telegram Bot API
│   │   ├── inventory.py      # 物料/庫存 API
│   │   ├── vendor.py         # 廠商主檔 API
│   │   ├── bot_settings.py   # Bot 設定管理 API
│   │   ├── skills.py         # AI Skills API
│   │   ├── share.py          # 公開分享 API
│   │   ├── messages.py       # 訊息中心 API
│   │   └── config_public.py  # 公開設定 API
│   ├── services/
│   │   ├── session.py        # Session 管理
│   │   ├── smb.py            # SMB 連線服務
│   │   ├── user.py           # 使用者服務（CRUD、密碼管理）
│   │   ├── password.py       # 密碼雜湊與驗證
│   │   ├── permissions.py    # 權限管理
│   │   ├── terminal.py       # 終端機服務
│   │   ├── claude_agent.py   # Claude API 服務
│   │   ├── ai_chat.py        # AI 對話服務
│   │   ├── ai_manager.py     # AI 管理服務
│   │   ├── linebot.py        # Line Bot 服務
│   │   ├── linebot_ai.py     # Line Bot AI 處理
│   │   ├── linebot_agents.py # Line Bot Agent 定義
│   │   ├── bot_telegram/     # Telegram Bot 服務
│   │   ├── mcp_server.py     # MCP Server（FastMCP）
│   │   ├── inventory.py      # 物料/庫存服務
│   │   ├── vendor.py         # 廠商主檔服務
│   │   ├── bot_settings.py   # Bot 憑證管理服務
│   │   ├── presentation.py   # 簡報生成服務
│   │   ├── share.py          # 分享服務
│   │   ├── document_reader.py # 文件讀取（Word/Excel/PDF）
│   │   └── scheduler.py      # 排程任務
│   ├── skills/               # AI Skills 系統
│   │   ├── base/               # 內建：基礎工具（script-first）
│   │   ├── file-manager/       # 內建：檔案管理（script-first）
│   │   ├── script_runner.py    # Skill 腳本運行器
│   │   ├── media-downloader/   # 影片/音訊下載
│   │   └── media-transcription/ # 逐字稿轉錄
│   ├── utils/
│   │   └── crypto.py         # AES-256-GCM 加密
│   └── models/
│       ├── auth.py           # 認證模型
│       ├── user.py           # 使用者模型（含管理員操作）
│       ├── nas.py            # NAS 模型
│       ├── ai.py             # AI 相關模型
│       ├── linebot.py        # Line Bot 模型
│       ├── inventory.py      # 物料/庫存模型
│       ├── vendor.py         # 廠商主檔模型
│       └── share.py          # 分享模型
└── tests/
```

## 資料庫 Migration

所有資料庫 schema 變更都必須透過 Alembic migration：

```bash
# 建立新 migration
cd backend
uv run alembic revision -m "description"

# 執行 migration
uv run alembic upgrade head

# 回滾 migration
uv run alembic downgrade -1
```

Migration 檔案命名格式：`00X_description.py`（遞增編號）
