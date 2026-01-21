"""建立 password_reset_tokens 表

Revision ID: 047
Revises: 046
Create Date: 2026-01-21

用於 Email 密碼重設的 token 管理
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(64), unique=True, nullable=False, comment="重設 token（隨機字串）"),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False, comment="過期時間"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True, comment="使用時間（已使用則不為 NULL）"),
        comment="密碼重設 Token"
    )

    # 建立索引
    op.create_index("idx_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("idx_password_reset_tokens_token", "password_reset_tokens", ["token"])
    op.create_index("idx_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_password_reset_tokens_expires_at", table_name="password_reset_tokens")
    op.drop_index("idx_password_reset_tokens_token", table_name="password_reset_tokens")
    op.drop_index("idx_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
