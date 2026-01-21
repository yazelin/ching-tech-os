"""擴展 public_share_links.resource_id 欄位長度

NAS 路徑可能超過 100 字元，增加到 500 字元

Revision ID: 037
Revises: 036
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 將 resource_id 從 VARCHAR(100) 擴展到 VARCHAR(500)
    op.alter_column(
        "public_share_links",
        "resource_id",
        type_=sa.VARCHAR(500),
        existing_type=sa.VARCHAR(100),
        existing_nullable=False,
    )


def downgrade() -> None:
    # 還原為 VARCHAR(100)
    op.alter_column(
        "public_share_links",
        "resource_id",
        type_=sa.VARCHAR(100),
        existing_type=sa.VARCHAR(500),
        existing_nullable=False,
    )
