# 資料庫設計與 Migration 管理

## 概覽

ChingTech OS 使用 PostgreSQL 作為資料庫，透過 Alembic 管理 schema migration。

```
backend/
├── alembic.ini                 # Alembic 設定檔
├── migrations/
│   ├── env.py                  # 環境設定（整合 config.py）
│   ├── script.py.mako          # Migration 檔案範本
│   └── versions/
│       ├── 001_create_users.py
│       └── 002_create_ai_chats.py
```

## 資料庫連線設定

設定位於 `backend/src/ching_tech_os/config.py`：

```python
# 同步連線（Alembic/SQLAlchemy 用）
database_url = "postgresql+psycopg://user:pass@host:port/db"

# 非同步連線（asyncpg 用）
async_database_url = "postgresql+asyncpg://user:pass@host:port/db"
```

環境變數前綴：`CHING_TECH_`，例如：
- `CHING_TECH_DB_HOST`
- `CHING_TECH_DB_PORT`
- `CHING_TECH_DB_USER`
- `CHING_TECH_DB_PASSWORD`
- `CHING_TECH_DB_NAME`

## 資料表設計

### users 表

儲存透過 NAS 認證登入的使用者。

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,  -- NAS 帳號
    display_name VARCHAR(100),               -- 顯示名稱
    created_at TIMESTAMP DEFAULT NOW(),      -- 首次登入時間
    last_login_at TIMESTAMP                  -- 最後登入時間
);

CREATE INDEX idx_users_username ON users(username);
```

### ai_chats 表

儲存 AI 對話記錄。

```sql
CREATE TABLE ai_chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER REFERENCES users(id),
    title VARCHAR(100) DEFAULT '新對話',
    model VARCHAR(50) DEFAULT 'claude-sonnet',
    prompt_name VARCHAR(50) DEFAULT 'default',  -- 對應 data/prompts/{name}.md
    messages JSONB DEFAULT '[]',                 -- 對話訊息陣列
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ai_chats_user_id ON ai_chats(user_id);
CREATE INDEX idx_ai_chats_updated_at ON ai_chats(updated_at DESC);
```

#### messages JSONB 結構

```json
[
  {
    "role": "user",
    "content": "你好",
    "timestamp": 1702345678
  },
  {
    "role": "assistant",
    "content": "你好！有什麼可以幫助你的？",
    "timestamp": 1702345680
  },
  {
    "role": "system",
    "content": "[對話摘要] ...",
    "timestamp": 1702345700,
    "is_summary": true
  }
]
```

## Alembic 常用指令

```bash
cd backend

# 查看目前版本
uv run alembic current

# 升級到最新版本
uv run alembic upgrade head

# 回滾一個版本
uv run alembic downgrade -1

# 回滾到特定版本
uv run alembic downgrade 001

# 查看 migration 歷史
uv run alembic history

# 建立新 migration
uv run alembic revision -m "add_new_table"

# 標記某版本為已套用（不實際執行）
uv run alembic stamp 001
```

## 建立新 Migration

### 1. 建立 migration 檔案

```bash
uv run alembic revision -m "create_xxx_table"
```

會在 `migrations/versions/` 產生檔案，例如：
`abc123def456_create_xxx_table.py`

### 2. 編輯 migration 檔案

```python
"""create xxx table

Revision ID: abc123def456
Revises: 002
Create Date: 2024-12-10
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'xxx',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('idx_xxx_name', 'xxx', ['name'])


def downgrade() -> None:
    op.drop_index('idx_xxx_name')
    op.drop_table('xxx')
```

### 3. 執行 migration

```bash
uv run alembic upgrade head
```

## 時間欄位建議

| 類型 | 用途 | 說明 |
|------|------|------|
| `TIMESTAMP` | 本地時間 | 不含時區資訊 |
| `TIMESTAMPTZ` | UTC 時間 | 含時區資訊，推薦使用 |

建議統一使用 `TIMESTAMPTZ`，PostgreSQL 會自動轉換時區。

SQLAlchemy 寫法：
```python
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
```

## asyncpg 與 JSONB

asyncpg 回傳的 JSONB 是字串，需要手動解析：

```python
import json

async def get_chat(chat_id: UUID) -> dict:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM ai_chats WHERE id = $1", chat_id
        )
        if row:
            result = dict(row)
            result["messages"] = json.loads(result["messages"])
            return result
```

## 開發流程

### 本地開發

1. 啟動 PostgreSQL：
   ```bash
   cd docker && docker compose up -d
   ```

2. 執行 migration：
   ```bash
   cd backend && uv run alembic upgrade head
   ```

3. 啟動後端：
   ```bash
   ./scripts/start.sh dev
   ```

### 部署到新環境

1. 設定環境變數（或使用 `.env` 檔案）
2. 執行 `alembic upgrade head`
3. 啟動服務

### 已存在的資料庫

如果資料庫已有表格（例如從 init.sql 建立），需要標記已套用的 migration：

```bash
# 標記 001 為已套用（users 表已存在）
uv run alembic stamp 001

# 然後執行剩餘的 migration
uv run alembic upgrade head
```

## 資料庫備份

```bash
# 備份
pg_dump -h localhost -U ching_tech -d ching_tech_os > backup.sql

# 還原
psql -h localhost -U ching_tech -d ching_tech_os < backup.sql
```

## 相關檔案

- `backend/alembic.ini` - Alembic 設定
- `backend/migrations/env.py` - 環境設定
- `backend/src/ching_tech_os/config.py` - 連線設定
- `backend/src/ching_tech_os/database.py` - asyncpg 連線池
- `docker/docker-compose.yml` - PostgreSQL 容器設定
- `docker/init.sql` - 初始 schema（參考用，實際用 Alembic）
