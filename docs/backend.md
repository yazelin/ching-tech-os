# 後端開發指南

使用 FastAPI + NAS SMB 認證的後端服務。

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
uv run uvicorn ching_tech_os.main:socket_app --host 0.0.0.0 --port 8089 --reload
```

服務將在 http://localhost:8089 啟動。

## API 文件

啟動後端後，訪問：
- Swagger UI: http://localhost:8089/docs
- ReDoc: http://localhost:8089/redoc

## 主要 API

### 認證

| 方法 | 端點 | 說明 |
|------|------|------|
| POST | `/api/auth/login` | 登入（NAS SMB 認證） |
| POST | `/api/auth/logout` | 登出 |

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

### 租戶管理（多租戶模式）

詳細說明請參考 [多租戶架構](multi-tenant.md)。

#### 租戶自助 API

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/tenant/info` | 取得租戶資訊 |
| GET | `/api/tenant/usage` | 取得使用量統計 |
| PUT | `/api/tenant/settings` | 更新租戶設定 |
| GET | `/api/tenant/admins` | 列出租戶管理員 |
| POST | `/api/tenant/admins` | 新增租戶管理員 |
| DELETE | `/api/tenant/admins/{user_id}` | 移除租戶管理員 |
| POST | `/api/tenant/export` | 匯出租戶資料（ZIP） |
| POST | `/api/tenant/import` | 匯入租戶資料 |
| GET | `/api/tenant/validate` | 驗證資料完整性 |

#### 平台管理 API（平台管理員）

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/admin/tenants` | 列出所有租戶 |
| POST | `/api/admin/tenants` | 建立新租戶 |
| GET | `/api/admin/tenants/{id}` | 取得租戶詳情 |
| PATCH | `/api/admin/tenants/{id}` | 更新租戶 |
| DELETE | `/api/admin/tenants/{id}` | 刪除租戶 |
| GET | `/api/admin/tenants/{id}/admins` | 列出租戶管理員 |
| POST | `/api/admin/tenants/{id}/admins` | 新增租戶管理員 |
| DELETE | `/api/admin/tenants/{id}/admins/{user_id}` | 移除租戶管理員 |

### 終端機 (WebSocket)

| 端點 | 說明 |
|------|------|
| `ws://host/terminal/{session_id}` | PTY shell session |

## 環境變數

可透過環境變數覆蓋預設設定（前綴 `CHING_TECH_`）：

| 變數 | 預設值 | 說明 |
|------|--------|------|
| CHING_TECH_NAS_HOST | 192.168.11.50 | NAS 主機位址 |
| CHING_TECH_DB_HOST | localhost | 資料庫主機 |
| CHING_TECH_DB_PORT | 5432 | 資料庫埠號 |
| CHING_TECH_DB_USER | ching_tech | 資料庫使用者 |
| CHING_TECH_DB_PASSWORD | REMOVED_PASSWORD | 資料庫密碼 |
| CHING_TECH_SESSION_TTL_HOURS | 8 | Session 有效時間（小時）|
| MULTI_TENANT_MODE | false | 是否啟用多租戶模式 |
| DEFAULT_TENANT_ID | 00000000-0000-0000-0000-000000000000 | 預設租戶 UUID |

## 專案結構

```
backend/
├── pyproject.toml
├── alembic.ini
├── migrations/
│   └── versions/         # Migration 檔案
├── src/ching_tech_os/
│   ├── main.py           # FastAPI 入口（含 Socket.IO）
│   ├── config.py         # 設定檔
│   ├── database.py       # 資料庫連線
│   ├── mcp_cli.py        # MCP CLI 入口
│   ├── api/
│   │   ├── auth.py         # 認證 API
│   │   ├── nas.py          # NAS 操作 API
│   │   ├── knowledge.py    # 知識庫 API
│   │   ├── ai_router.py    # AI 對話 API
│   │   ├── ai_management.py # AI 管理 API (Prompts/Agents/Logs)
│   │   ├── linebot_router.py # Line Bot API
│   │   ├── inventory.py    # 物料/庫存 API
│   │   ├── vendor.py       # 廠商主檔 API
│   │   ├── tenant.py       # 租戶自助 API
│   │   └── admin/
│   │       └── tenants.py  # 平台管理 API
│   ├── services/
│   │   ├── session.py      # Session 管理
│   │   ├── smb.py          # SMB 連線服務
│   │   ├── user.py         # 使用者服務
│   │   ├── terminal.py     # 終端機服務
│   │   ├── claude_agent.py # Claude API 服務
│   │   ├── ai_chat.py      # AI 對話服務
│   │   ├── ai_manager.py   # AI 管理服務 (Prompts/Agents/Logs)
│   │   ├── linebot.py      # Line Bot 服務
│   │   ├── linebot_ai.py   # Line Bot AI 處理
│   │   ├── mcp_server.py   # MCP Server（FastMCP）
│   │   ├── inventory.py    # 物料/庫存服務
│   │   ├── vendor.py       # 廠商主檔服務
│   │   ├── tenant.py       # 租戶服務
│   │   └── tenant_data.py  # 租戶資料匯出/匯入
│   └── models/
│       ├── auth.py         # 認證模型
│       ├── nas.py          # NAS 模型
│       ├── ai.py           # AI 相關模型
│       ├── linebot.py      # Line Bot 模型
│       ├── inventory.py    # 物料/庫存模型
│       ├── vendor.py       # 廠商主檔模型
│       └── tenant.py       # 租戶模型
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
