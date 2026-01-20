"""為其他表新增 tenant_id 欄位

Revision ID: 043
Revises: 042
Create Date: 2026-01-20

影響表格：
- public_share_links
- messages（分區表）
- login_records（分區表）
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None

# 預設租戶 UUID
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    # === public_share_links ===
    op.add_column(
        "public_share_links",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="租戶 ID"
        )
    )
    op.execute(f"""
        UPDATE public_share_links SET tenant_id = '{DEFAULT_TENANT_ID}'::uuid WHERE tenant_id IS NULL;
    """)
    op.create_foreign_key(
        "fk_public_share_links_tenant_id",
        "public_share_links",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE"
    )
    op.create_index("idx_public_share_links_tenant_id", "public_share_links", ["tenant_id"])

    # === messages（分區表）===
    # 分區表新增欄位會自動傳播到所有分區
    op.add_column(
        "messages",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="租戶 ID"
        )
    )
    op.execute(f"""
        UPDATE messages SET tenant_id = '{DEFAULT_TENANT_ID}'::uuid WHERE tenant_id IS NULL;
    """)
    # 分區表不支援外鍵約束
    op.create_index("idx_messages_tenant_id", "messages", ["tenant_id"])
    op.create_index("idx_messages_tenant_created", "messages", ["tenant_id", "created_at"])

    # === login_records（分區表）===
    op.add_column(
        "login_records",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="租戶 ID"
        )
    )
    op.execute(f"""
        UPDATE login_records SET tenant_id = '{DEFAULT_TENANT_ID}'::uuid WHERE tenant_id IS NULL;
    """)
    # 分區表不支援外鍵約束
    op.create_index("idx_login_records_tenant_id", "login_records", ["tenant_id"])


def downgrade() -> None:
    # === login_records ===
    op.drop_index("idx_login_records_tenant_id", table_name="login_records")
    op.drop_column("login_records", "tenant_id")

    # === messages ===
    op.drop_index("idx_messages_tenant_created", table_name="messages")
    op.drop_index("idx_messages_tenant_id", table_name="messages")
    op.drop_column("messages", "tenant_id")

    # === public_share_links ===
    op.drop_index("idx_public_share_links_tenant_id", table_name="public_share_links")
    op.drop_constraint("fk_public_share_links_tenant_id", "public_share_links", type_="foreignkey")
    op.drop_column("public_share_links", "tenant_id")
