# Ching Tech OS Backend

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

### 3. 啟動後端服務

```bash
cd backend
uv run uvicorn ching_tech_os.main:app --host 0.0.0.0 --port 8088 --reload
```

服務將在 http://localhost:8088 啟動。

## API 文件

啟動後端後，訪問：
- Swagger UI: http://localhost:8088/docs
- ReDoc: http://localhost:8088/redoc

## 主要 API

### 認證

- `POST /api/auth/login` - 登入（NAS SMB 認證）
- `POST /api/auth/logout` - 登出

### NAS 操作

- `GET /api/nas/shares` - 列出共享資料夾
- `GET /api/nas/browse?path=/share_name` - 瀏覽資料夾

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
├── src/ching_tech_os/
│   ├── main.py          # FastAPI 入口
│   ├── config.py        # 設定檔
│   ├── database.py      # 資料庫連線
│   ├── api/
│   │   ├── auth.py      # 認證 API
│   │   └── nas.py       # NAS 操作 API
│   ├── services/
│   │   ├── session.py   # Session 管理
│   │   ├── smb.py       # SMB 連線服務
│   │   └── user.py      # 使用者服務
│   └── models/
│       ├── auth.py      # 認證模型
│       └── nas.py       # NAS 模型
└── tests/

docker/
├── docker-compose.yml   # PostgreSQL 容器
├── init.sql             # 資料庫初始化
└── .env                 # 環境變數
```
