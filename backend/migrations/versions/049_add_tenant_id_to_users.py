"""為 users 表新增 tenant_id 欄位

Revision ID: 049
Revises: 048
Create Date: 2026-01-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None

# 預設租戶 UUID
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    # 為 users 表新增 tenant_id 欄位（初始為 nullable，後續 migration 設為 NOT NULL）
    op.add_column(
        "users",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="租戶 ID"
        )
    )

    # 將現有用戶指派到預設租戶
    op.execute(f"""
        UPDATE users SET tenant_id = '{DEFAULT_TENANT_ID}'::uuid WHERE tenant_id IS NULL;
    """)

    # 建立外鍵約束
    op.create_foreign_key(
        "fk_users_tenant_id",
        "users",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE"
    )

    # 建立索引
    op.create_index("idx_users_tenant_id", "users", ["tenant_id"])

    # 建立複合索引（租戶內用戶名唯一）
    # 注意：需要先刪除舊的唯一約束
    op.drop_constraint("users_username_key", "users", type_="unique")
    op.create_index("idx_users_tenant_username", "users", ["tenant_id", "username"], unique=True)

    # 修正 tenant_admins 表的 user_id 類型（users.id 是 integer，不是 UUID）
    # 先刪除舊的 user_id 欄位
    op.drop_index("idx_tenant_admins_tenant_user", table_name="tenant_admins")
    op.drop_column("tenant_admins", "user_id")

    # 新增正確類型的 user_id 欄位
    op.add_column(
        "tenant_admins",
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="用戶 ID"
        )
    )

    # 重新建立複合唯一索引
    op.create_index("idx_tenant_admins_tenant_user", "tenant_admins", ["tenant_id", "user_id"], unique=True)

    # 為 users 表新增 role 欄位（用於區分平台管理員和一般用戶）
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(50),
            nullable=False,
            server_default="user",
            comment="角色：user, tenant_admin, platform_admin"
        )
    )


def downgrade() -> None:
    # 刪除 role 欄位
    op.drop_column("users", "role")

    # 還原 tenant_admins 表的 user_id 為 UUID
    op.drop_index("idx_tenant_admins_tenant_user", table_name="tenant_admins")
    op.drop_column("tenant_admins", "user_id")
    op.add_column(
        "tenant_admins",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False)
    )
    op.create_index("idx_tenant_admins_tenant_user", "tenant_admins", ["tenant_id", "user_id"], unique=True)

    # 還原 users 表的唯一約束
    op.drop_index("idx_users_tenant_username", table_name="users")
    op.create_unique_constraint("users_username_key", "users", ["username"])

    # 刪除索引
    op.drop_index("idx_users_tenant_id", table_name="users")

    # 刪除外鍵
    op.drop_constraint("fk_users_tenant_id", "users", type_="foreignkey")

    # 刪除 tenant_id 欄位
    op.drop_column("users", "tenant_id")
