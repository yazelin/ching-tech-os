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
| GET | `/api/ai/conversations` | 列表對話 |
| POST | `/api/ai/conversations` | 新增對話 |
| GET | `/api/ai/conversations/{id}` | 取得對話 |
| DELETE | `/api/ai/conversations/{id}` | 刪除對話 |
| POST | `/api/ai/conversations/{id}/messages` | 發送訊息 |

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
│   ├── api/
│   │   ├── auth.py       # 認證 API
│   │   ├── nas.py        # NAS 操作 API
│   │   ├── knowledge.py  # 知識庫 API
│   │   └── ai.py         # AI 對話 API
│   ├── services/
│   │   ├── session.py    # Session 管理
│   │   ├── smb.py        # SMB 連線服務
│   │   ├── user.py       # 使用者服務
│   │   ├── terminal.py   # 終端機服務
│   │   └── ai_agent.py   # AI Agent 服務
│   └── models/
│       ├── auth.py       # 認證模型
│       ├── nas.py        # NAS 模型
│       └── ai.py         # AI 對話模型
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
