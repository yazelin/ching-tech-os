"""為 Line Bot 相關表新增 tenant_id 欄位

Revision ID: 041
Revises: 040
Create Date: 2026-01-20

影響表格：
- line_groups（群組綁定租戶的核心）
- line_users
- line_messages
- line_files
- line_binding_codes
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None

# 預設租戶 UUID
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"

# Line 相關表清單
LINE_TABLES = [
    "line_groups",
    "line_users",
    "line_messages",
    "line_files",
    "line_binding_codes",
]


def upgrade() -> None:
    # 為所有 Line 相關表新增 tenant_id 欄位
    for table in LINE_TABLES:
        op.add_column(
            table,
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
                comment="租戶 ID"
            )
        )

    # 將現有資料指派到預設租戶
    for table in LINE_TABLES:
        op.execute(f"""
            UPDATE {table} SET tenant_id = '{DEFAULT_TENANT_ID}'::uuid WHERE tenant_id IS NULL;
        """)

    # 為所有表建立外鍵約束
    for table in LINE_TABLES:
        op.create_foreign_key(
            f"fk_{table}_tenant_id",
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE"
        )

    # === line_groups 索引 ===
    # 這是最重要的表，用於識別群組屬於哪個租戶
    op.create_index("idx_line_groups_tenant_id", "line_groups", ["tenant_id"])

    # === line_users 索引 ===
    # 同一 Line 用戶可能在不同租戶的群組中
    op.create_index("idx_line_users_tenant_id", "line_users", ["tenant_id"])
    op.create_index("idx_line_users_tenant_line_user", "line_users", ["tenant_id", "line_user_id"])

    # === line_messages 索引 ===
    op.create_index("idx_line_messages_tenant_id", "line_messages", ["tenant_id"])
    op.create_index("idx_line_messages_tenant_group", "line_messages", ["tenant_id", "line_group_id"])

    # === line_files 索引 ===
    op.create_index("idx_line_files_tenant_id", "line_files", ["tenant_id"])

    # === line_binding_codes 索引 ===
    op.create_index("idx_line_binding_codes_tenant_id", "line_binding_codes", ["tenant_id"])


def downgrade() -> None:
    # 刪除索引
    op.drop_index("idx_line_binding_codes_tenant_id", table_name="line_binding_codes")
    op.drop_index("idx_line_files_tenant_id", table_name="line_files")
    op.drop_index("idx_line_messages_tenant_group", table_name="line_messages")
    op.drop_index("idx_line_messages_tenant_id", table_name="line_messages")
    op.drop_index("idx_line_users_tenant_line_user", table_name="line_users")
    op.drop_index("idx_line_users_tenant_id", table_name="line_users")
    op.drop_index("idx_line_groups_tenant_id", table_name="line_groups")

    # 刪除外鍵約束
    for table in LINE_TABLES:
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")

    # 刪除 tenant_id 欄位
    for table in LINE_TABLES:
        op.drop_column(table, "tenant_id")
