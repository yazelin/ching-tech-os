"""create ai_chats table

Revision ID: 002
Revises: 001
Create Date: 2024-12-10

新增 AI 對話資料表，用於持久化儲存對話記錄
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_chats",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("title", sa.String(100), server_default="新對話", nullable=False),
        sa.Column("model", sa.String(50), server_default="claude-sonnet", nullable=False),
        sa.Column(
            "prompt_name", sa.String(50), server_default="default", nullable=False
        ),
        sa.Column("messages", JSONB, server_default="[]", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("idx_ai_chats_user_id", "ai_chats", ["user_id"])
    op.create_index(
        "idx_ai_chats_updated_at", "ai_chats", [sa.text("updated_at DESC")]
    )

    # Add comments
    op.execute("COMMENT ON TABLE ai_chats IS 'AI 對話記錄表'")
    op.execute("COMMENT ON COLUMN ai_chats.id IS '對話 UUID'")
    op.execute("COMMENT ON COLUMN ai_chats.user_id IS '使用者 ID（關聯 users 表）'")
    op.execute("COMMENT ON COLUMN ai_chats.title IS '對話標題'")
    op.execute("COMMENT ON COLUMN ai_chats.model IS 'AI 模型名稱'")
    op.execute(
        "COMMENT ON COLUMN ai_chats.prompt_name IS 'System Prompt 名稱（對應 data/prompts/*.md）'"
    )
    op.execute(
        "COMMENT ON COLUMN ai_chats.messages IS '對話訊息 JSONB 陣列 [{role, content, timestamp}]'"
    )
    op.execute("COMMENT ON COLUMN ai_chats.created_at IS '建立時間'")
    op.execute("COMMENT ON COLUMN ai_chats.updated_at IS '最後更新時間'")


def downgrade() -> None:
    op.drop_index("idx_ai_chats_updated_at")
    op.drop_index("idx_ai_chats_user_id")
    op.drop_table("ai_chats")
