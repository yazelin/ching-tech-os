# Design: add-backend-nas-auth

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   FastAPI       │────▶│   NAS           │
│   (Browser)     │◀────│   Backend       │◀────│   192.168.11.50 │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   PostgreSQL    │
                        │   (Docker)      │
                        │   [未來使用]     │
                        └─────────────────┘
```

## Project Structure

```
backend/
├── pyproject.toml          # uv 專案設定
├── src/
│   └── ching_tech_os/
│       ├── __init__.py
│       ├── main.py         # FastAPI 應用程式入口
│       ├── config.py       # 設定檔 (NAS IP, DB 連線等)
│       ├── api/
│       │   ├── __init__.py
│       │   ├── auth.py     # 登入/登出 API
│       │   └── nas.py      # NAS 操作 API
│       ├── services/
│       │   ├── __init__.py
│       │   ├── session.py  # Session 管理
│       │   └── smb.py      # SMB 連線服務
│       └── models/
│           ├── __init__.py
│           └── auth.py     # Pydantic models
└── tests/
    └── ...

docker/
├── docker-compose.yml      # PostgreSQL + 未來服務
└── .env.example            # 環境變數範例
```

## API Design

### POST /api/auth/login
登入並建立 session。

**Request:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response (200):**
```json
{
  "success": true,
  "token": "session-uuid",
  "username": "string"
}
```

**Response (401):**
```json
{
  "success": false,
  "error": "認證失敗：帳號或密碼錯誤"
}
```

### POST /api/auth/logout
登出並清除 session。

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true
}
```

### GET /api/nas/shares
列出 NAS 上的共享資料夾。

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "shares": [
    {"name": "公用資料夾", "type": "disk"},
    {"name": "home", "type": "disk"}
  ]
}
```

### GET /api/nas/browse?path=/share_name/folder
瀏覽指定資料夾內容。

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "path": "/公用資料夾",
  "items": [
    {"name": "文件", "type": "directory", "modified": "2024-01-01T00:00:00"},
    {"name": "readme.txt", "type": "file", "size": 1024, "modified": "2024-01-01T00:00:00"}
  ]
}
```

## Session Management

```python
# 記憶體儲存結構
sessions: dict[str, SessionData] = {}

@dataclass
class SessionData:
    username: str
    password: str  # SMB 操作需要
    nas_host: str
    created_at: datetime
    expires_at: datetime  # 預設 8 小時
```

### Session 清理策略
- 背景任務每 10 分鐘清理過期 session
- 登出時立即刪除
- Server 重啟時全部清空

## Security Considerations

1. **密碼傳輸**：前端到後端使用 HTTPS（開發環境可用 HTTP）
2. **密碼儲存**：僅存於記憶體，不寫入檔案或資料庫
3. **Token 安全**：使用 UUID4，足夠隨機
4. **日誌安全**：不記錄密碼內容
5. **CORS**：限制允許的來源

## Database Schema

### users 表
記錄曾經登入過的使用者，供後續功能關聯使用。

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,  -- NAS 帳號
    display_name VARCHAR(100),              -- 顯示名稱（可選）
    created_at TIMESTAMP DEFAULT NOW(),     -- 首次登入時間
    last_login_at TIMESTAMP                 -- 最後登入時間
);

CREATE INDEX idx_users_username ON users(username);
```

**說明：**
- 密碼不儲存，認證走 NAS SMB
- 第一次登入成功時自動建立記錄
- 每次登入更新 `last_login_at`

## Docker Compose Configuration

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ching_tech
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ching_tech_os
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

## Dependencies (pyproject.toml)

```toml
[project]
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "python-socketio>=5.10.0",
    "smbprotocol>=1.12.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "httpx>=0.26.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
]
```

## Error Handling

| Error Code | Situation | Response |
|------------|-----------|----------|
| 401 | Token 無效/過期 | `{"error": "未授權，請重新登入"}` |
| 401 | NAS 認證失敗 | `{"error": "帳號或密碼錯誤"}` |
| 503 | NAS 無法連線 | `{"error": "無法連線至檔案伺服器"}` |
| 403 | 無權限存取 | `{"error": "無權限存取此資料夾"}` |
