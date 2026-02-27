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
│       ├── 001_initial_schema.py              # 初始資料庫結構
│       ├── 002_seed_data.py                   # 種子資料
│       ├── 003_remove_multi_tenancy.py        # 移除多租戶架構
│       ├── 004_remove_tenant_id_partitioned_tables.py  # 移除分區表 tenant_id
│       ├── 005_sessions_table.py              # 建立 sessions 表
│       ├── 006_add_username_unique_constraint.py  # username 唯一約束
│       ├── 007_seed_admin_user.py             # 預設管理員帳號
│       ├── 008_update_bot_prompt_platform.py  # Bot Prompt 加入 Telegram 平台說明
│       ├── 009_add_bot_usage_tracking.py      # 未綁定用戶使用量追蹤表
│       ├── 010_add_bot_restricted_settings.py # bot-restricted Agent 預設 settings
│       ├── 011_add_active_agent_id.py         # bot_users/bot_groups 新增 active_agent_id
│       └── 012_add_restricted_agent_id.py     # bot_users/bot_groups 新增 restricted_agent_id
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

儲存系統使用者，支援 CTOS 本地密碼認證與 NAS SMB 認證。

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,    -- 帳號名稱
    display_name VARCHAR(100),                -- 顯示名稱
    password_hash VARCHAR(255),               -- 密碼 bcrypt hash（NULL 表示 NAS 認證）
    email VARCHAR(255),                       -- 電子郵件
    role VARCHAR(50) NOT NULL DEFAULT 'user', -- 角色（admin / user）
    preferences JSONB NOT NULL DEFAULT '{}',  -- 偏好設定（theme、permissions 等）
    is_active BOOLEAN NOT NULL DEFAULT TRUE,  -- 帳號是否啟用
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,  -- 強制變更密碼
    password_changed_at TIMESTAMPTZ,          -- 最後密碼變更時間
    created_at TIMESTAMPTZ DEFAULT NOW(),     -- 建立時間
    last_login_at TIMESTAMPTZ                 -- 最後登入時間
);

CREATE INDEX idx_users_username ON users(username);
```

**認證方式判定**：
- `password_hash` 有值 → CTOS 本地密碼認證
- `password_hash` 為 NULL → NAS SMB 認證

**預設管理員**（migration 007）：
- 帳號 `ct`，密碼 `36274806`（bcrypt hash）
- `role = 'admin'`、`must_change_password = True`

### sessions 表

儲存持久化 Session（migration 005）。

```sql
CREATE TABLE sessions (
    token VARCHAR(100) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    username VARCHAR(100) NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
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

### bot_settings 表

儲存 Bot 平台憑證（AES-256-GCM 加密）。

```sql
CREATE TABLE bot_settings (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,     -- 平台（line / telegram）
    key VARCHAR(100) NOT NULL,          -- 設定鍵名
    value TEXT,                         -- 加密後的值（Base64）
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_bot_settings_platform_key UNIQUE (platform, key)
);
```

**支援的鍵值**：

| 平台 | Key | 說明 |
|------|-----|------|
| line | `channel_secret` | Channel Secret（加密） |
| line | `channel_access_token` | Channel Access Token（加密） |
| telegram | `bot_token` | Bot Token（加密） |
| telegram | `webhook_secret` | Webhook Secret（加密） |
| telegram | `admin_chat_id` | 管理員 Chat ID |

### bot_usage_tracking 表

追蹤未綁定用戶的訊息使用量，用於受限模式頻率限制（migration 009）。

```sql
CREATE TABLE bot_usage_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_user_id UUID NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
    period_type VARCHAR(10) NOT NULL,   -- 'hourly' 或 'daily'
    period_key VARCHAR(20) NOT NULL,    -- 如 '2026-02-27-14'、'2026-02-27'
    message_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(bot_user_id, period_type, period_key)
);
```

### ai_agents.settings JSONB（bot-restricted）

`ai_agents` 表的 `settings` JSONB 欄位用於儲存 Agent 的可自訂設定。`bot-restricted` Agent 使用此欄位存放面向用戶的文字模板（migration 010）：

| Key | 說明 |
|-----|------|
| `welcome_message` | `/start` 指令與加好友歡迎訊息 |
| `binding_prompt` | `reject` 模式拒絕時的綁定提示 |
| `rate_limit_hourly_msg` | 每小時頻率超限訊息（支援 `{limit}`、`{count}` 變數） |
| `rate_limit_daily_msg` | 每日頻率超限訊息（支援 `{limit}`、`{count}` 變數） |
| `disclaimer` | 附加在受限模式 AI 回應後的免責聲明 |
| `error_message` | AI 處理失敗時的錯誤訊息 |

> Migration 010 使用 JSONB merge（`defaults || COALESCE(settings, '{}')`）寫入預設值，已存在的 key 不會被覆蓋。

> **v0.3.0 變更**：移除多租戶架構（`tenants`、`tenant_admins` 表），所有資料表的 `tenant_id` 欄位已移除。使用者角色簡化為 `admin` / `user`。
>
> **v0.3.1 變更**：新增 CTOS 本地密碼認證（users 表新增 `password_hash`、`must_change_password`、`password_changed_at`、`is_active`、`email`、`role` 欄位）。建立 sessions 表支援持久化 Session。新增預設管理員帳號 migration。

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
