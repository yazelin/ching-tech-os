"""add user_id to project_members

Revision ID: 021
Revises: 020
Create Date: 2026-01-07

專案成員關聯 CTOS 用戶 - 用於權限控制
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "021"
down_revision: str | None = "020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 新增 user_id 欄位到 project_members
    op.execute("""
        ALTER TABLE project_members
        ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
    """)

    # 建立索引
    op.execute("CREATE INDEX IF NOT EXISTS idx_project_members_user_id ON project_members(user_id)")

    # 註解
    op.execute("COMMENT ON COLUMN project_members.user_id IS '關聯的 CTOS 用戶 ID，用於權限控制'")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_project_members_user_id")
    op.execute("ALTER TABLE project_members DROP COLUMN IF EXISTS user_id")
