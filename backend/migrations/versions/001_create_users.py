"""create users table

Revision ID: 001
Revises:
Create Date: 2024-12-10

對應現有的 users 表結構（來自 docker/init.sql）
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("preferences", JSONB, server_default="{}", nullable=False),
        sa.Column(
            "created_at", sa.DateTime, server_default=sa.text("NOW()"), nullable=True
        ),
        sa.Column("last_login_at", sa.DateTime, nullable=True),
    )
    op.create_index("idx_users_username", "users", ["username"])

    # Add comments
    op.execute(
        "COMMENT ON TABLE users IS '使用者表：記錄曾經透過 NAS 認證登入的使用者'"
    )
    op.execute("COMMENT ON COLUMN users.username IS 'NAS 帳號'")
    op.execute("COMMENT ON COLUMN users.display_name IS '顯示名稱（可選）'")
    op.execute(
        "COMMENT ON COLUMN users.preferences IS '使用者偏好設定（JSONB），包含 theme 等設定'"
    )
    op.execute("COMMENT ON COLUMN users.created_at IS '首次登入時間'")
    op.execute("COMMENT ON COLUMN users.last_login_at IS '最後登入時間'")


def downgrade() -> None:
    op.drop_index("idx_users_username")
    op.drop_table("users")
