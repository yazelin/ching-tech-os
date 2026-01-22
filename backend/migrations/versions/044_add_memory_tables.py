"""新增 Line Bot 記憶資料表

Revision ID: 044
Revises: 042
Create Date: 2026-01-22

新增群組記憶和個人記憶資料表，支援自訂 prompt 記憶功能
"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "044"
down_revision: str | None = "042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 群組記憶表
    op.execute("""
        CREATE TABLE IF NOT EXISTS line_group_memories (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            line_group_id UUID NOT NULL REFERENCES line_groups(id) ON DELETE CASCADE,
            title VARCHAR(128) NOT NULL,
            content TEXT NOT NULL,
            is_active BOOLEAN DEFAULT true,
            created_by UUID REFERENCES line_users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_group_memories_group_id ON line_group_memories(line_group_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_group_memories_active ON line_group_memories(line_group_id, is_active)")
    op.execute("COMMENT ON TABLE line_group_memories IS 'Line 群組自訂記憶（會加入 AI prompt）'")
    op.execute("COMMENT ON COLUMN line_group_memories.title IS '記憶標題（方便識別）'")
    op.execute("COMMENT ON COLUMN line_group_memories.content IS '記憶內容（會加入 prompt）'")
    op.execute("COMMENT ON COLUMN line_group_memories.is_active IS '是否啟用'")
    op.execute("COMMENT ON COLUMN line_group_memories.created_by IS '建立者（Line 用戶）'")

    # 個人記憶表
    op.execute("""
        CREATE TABLE IF NOT EXISTS line_user_memories (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            line_user_id UUID NOT NULL REFERENCES line_users(id) ON DELETE CASCADE,
            title VARCHAR(128) NOT NULL,
            content TEXT NOT NULL,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_user_memories_user_id ON line_user_memories(line_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_line_user_memories_active ON line_user_memories(line_user_id, is_active)")
    op.execute("COMMENT ON TABLE line_user_memories IS 'Line 個人自訂記憶（會加入 AI prompt）'")
    op.execute("COMMENT ON COLUMN line_user_memories.title IS '記憶標題（方便識別）'")
    op.execute("COMMENT ON COLUMN line_user_memories.content IS '記憶內容（會加入 prompt）'")
    op.execute("COMMENT ON COLUMN line_user_memories.is_active IS '是否啟用'")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS line_user_memories CASCADE")
    op.execute("DROP TABLE IF EXISTS line_group_memories CASCADE")
