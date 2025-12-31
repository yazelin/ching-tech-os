"""add conversation_reset_at to line_users

Revision ID: 014
Revises: 013
Create Date: 2025-12-31

新增對話重置時間欄位，用於「忘記對話」功能。
查詢對話歷史時，只取這個時間之後的訊息。
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 新增對話重置時間欄位
    op.execute("""
        ALTER TABLE line_users
        ADD COLUMN IF NOT EXISTS conversation_reset_at TIMESTAMPTZ
    """)
    op.execute("""
        COMMENT ON COLUMN line_users.conversation_reset_at IS
        '對話重置時間，查詢歷史時只取這個時間之後的訊息'
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE line_users
        DROP COLUMN IF EXISTS conversation_reset_at
    """)
