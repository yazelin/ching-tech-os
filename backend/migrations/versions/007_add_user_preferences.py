"""add user preferences column

Revision ID: 007
Revises: 006
Create Date: 2024-12-11

新增 users 表的 preferences JSONB 欄位，用於儲存使用者個人化設定。
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: str = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("preferences", JSONB, server_default="{}", nullable=False),
    )

    # Add comment
    op.execute(
        "COMMENT ON COLUMN users.preferences IS '使用者偏好設定（JSONB），包含 theme 等設定'"
    )


def downgrade() -> None:
    op.drop_column("users", "preferences")
