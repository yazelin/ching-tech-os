"""create messages table with partitioning

Revision ID: 003
Revises: 002
Create Date: 2025-12-11

訊息中心 - 訊息表（使用 RANGE 分區按月分區）
"""

from collections.abc import Sequence
from datetime import datetime, timedelta

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 建立分區父表
    op.execute("""
        CREATE TABLE messages (
            id BIGSERIAL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            -- 分類
            severity VARCHAR(20) NOT NULL,
            source VARCHAR(20) NOT NULL,
            category VARCHAR(50),

            -- 內容
            title VARCHAR(200) NOT NULL,
            content TEXT,
            metadata JSONB,

            -- 關聯
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            session_id VARCHAR(100),

            -- 已讀狀態
            is_read BOOLEAN DEFAULT FALSE,

            -- 分區鍵
            partition_date DATE NOT NULL DEFAULT CURRENT_DATE,

            PRIMARY KEY (id, partition_date)
        ) PARTITION BY RANGE (partition_date)
    """)

    # 建立索引
    op.execute("CREATE INDEX idx_messages_created_at ON messages (created_at DESC)")
    op.execute("CREATE INDEX idx_messages_severity ON messages (severity)")
    op.execute("CREATE INDEX idx_messages_source ON messages (source)")
    op.execute("CREATE INDEX idx_messages_user_id ON messages (user_id)")
    op.execute("CREATE INDEX idx_messages_category ON messages (category)")
    op.execute("CREATE INDEX idx_messages_is_read ON messages (is_read) WHERE is_read = FALSE")

    # 建立當月和下兩個月的分區
    now = datetime.now()
    for i in range(3):
        month = now.replace(day=1) + timedelta(days=32 * i)
        month = month.replace(day=1)
        next_month = month + timedelta(days=32)
        next_month = next_month.replace(day=1)

        partition_name = f"messages_{month.strftime('%Y_%m')}"
        op.execute(f"""
            CREATE TABLE {partition_name} PARTITION OF messages
            FOR VALUES FROM ('{month.strftime('%Y-%m-%d')}') TO ('{next_month.strftime('%Y-%m-%d')}')
        """)

    # 建立預設分區（處理未來資料）
    op.execute("""
        CREATE TABLE messages_default PARTITION OF messages DEFAULT
    """)

    # 加入註解
    op.execute("COMMENT ON TABLE messages IS '訊息中心 - 訊息表（分區表）'")
    op.execute("COMMENT ON COLUMN messages.severity IS '嚴重程度: debug/info/warning/error/critical'")
    op.execute("COMMENT ON COLUMN messages.source IS '來源: system/security/app/user'")
    op.execute("COMMENT ON COLUMN messages.category IS '細分類: auth/file-manager/ai-assistant 等'")
    op.execute("COMMENT ON COLUMN messages.metadata IS '結構化附加資料 (JSONB)'")
    op.execute("COMMENT ON COLUMN messages.is_read IS '是否已讀'")
    op.execute("COMMENT ON COLUMN messages.partition_date IS '分區鍵（日期）'")

    # 建立 CHECK 約束確保有效的 severity 和 source
    op.execute("""
        ALTER TABLE messages ADD CONSTRAINT chk_messages_severity
        CHECK (severity IN ('debug', 'info', 'warning', 'error', 'critical'))
    """)
    op.execute("""
        ALTER TABLE messages ADD CONSTRAINT chk_messages_source
        CHECK (source IN ('system', 'security', 'app', 'user'))
    """)


def downgrade() -> None:
    # 刪除所有分區和主表
    op.execute("DROP TABLE IF EXISTS messages CASCADE")
