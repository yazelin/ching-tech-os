"""bot_users 新增黑名單欄位

新增 is_blocked、blocked_at、blocked_reason 欄位，
支援手動封鎖/解封未綁定用戶。

Revision ID: 021
"""

from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bot_users",
        sa.Column("is_blocked", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "bot_users",
        sa.Column("blocked_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "bot_users",
        sa.Column("blocked_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bot_users", "blocked_reason")
    op.drop_column("bot_users", "blocked_at")
    op.drop_column("bot_users", "is_blocked")
