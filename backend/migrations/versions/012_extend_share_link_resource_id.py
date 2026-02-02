"""擴展 public_share_links.resource_id 欄位長度

NAS 中文路徑容易超過 100 字元限制，導致建立分享連結失敗。

Revision ID: 012
Revises: 011
Create Date: 2026-02-02
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "public_share_links",
        "resource_id",
        type_=sa.String(500),
        existing_type=sa.String(100),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "public_share_links",
        "resource_id",
        type_=sa.String(100),
        existing_type=sa.String(500),
        existing_nullable=False,
    )
