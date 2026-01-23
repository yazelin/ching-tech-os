"""為專案相關表新增 tenant_id 欄位

Revision ID: 050
Revises: 049
Create Date: 2026-01-20

影響表格：
- projects
- project_members
- project_meetings
- project_milestones
- project_delivery_schedules
- project_links
- project_attachments
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None

# 預設租戶 UUID
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"

# 專案相關表清單
PROJECT_TABLES = [
    "projects",
    "project_members",
    "project_meetings",
    "project_milestones",
    "project_delivery_schedules",
    "project_links",
    "project_attachments",
]


def upgrade() -> None:
    # 為所有專案相關表新增 tenant_id 欄位
    for table in PROJECT_TABLES:
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
    for table in PROJECT_TABLES:
        op.execute(f"""
            UPDATE {table} SET tenant_id = '{DEFAULT_TENANT_ID}'::uuid WHERE tenant_id IS NULL;
        """)

    # 為所有表建立外鍵約束
    for table in PROJECT_TABLES:
        op.create_foreign_key(
            f"fk_{table}_tenant_id",
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE"
        )

    # 為 projects 表建立索引
    op.create_index("idx_projects_tenant_id", "projects", ["tenant_id"])
    op.create_index("idx_projects_tenant_status", "projects", ["tenant_id", "status"])

    # 為子表建立複合索引（tenant_id + 主表外鍵）
    op.create_index("idx_project_members_tenant_project", "project_members", ["tenant_id", "project_id"])
    op.create_index("idx_project_meetings_tenant_project", "project_meetings", ["tenant_id", "project_id"])
    op.create_index("idx_project_milestones_tenant_project", "project_milestones", ["tenant_id", "project_id"])
    op.create_index("idx_project_delivery_schedules_tenant_project", "project_delivery_schedules", ["tenant_id", "project_id"])
    op.create_index("idx_project_links_tenant_project", "project_links", ["tenant_id", "project_id"])
    op.create_index("idx_project_attachments_tenant_project", "project_attachments", ["tenant_id", "project_id"])


def downgrade() -> None:
    # 刪除子表的複合索引
    op.drop_index("idx_project_attachments_tenant_project", table_name="project_attachments")
    op.drop_index("idx_project_links_tenant_project", table_name="project_links")
    op.drop_index("idx_project_delivery_schedules_tenant_project", table_name="project_delivery_schedules")
    op.drop_index("idx_project_milestones_tenant_project", table_name="project_milestones")
    op.drop_index("idx_project_meetings_tenant_project", table_name="project_meetings")
    op.drop_index("idx_project_members_tenant_project", table_name="project_members")

    # 刪除 projects 表索引
    op.drop_index("idx_projects_tenant_status", table_name="projects")
    op.drop_index("idx_projects_tenant_id", table_name="projects")

    # 刪除外鍵約束
    for table in PROJECT_TABLES:
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")

    # 刪除 tenant_id 欄位
    for table in PROJECT_TABLES:
        op.drop_column(table, "tenant_id")
