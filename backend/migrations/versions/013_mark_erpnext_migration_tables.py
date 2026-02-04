"""標記已遷移至 ERPNext 的資料表

專案管理、物料管理、廠商管理功能已遷移至 ERPNext。
此 migration 在相關資料表加上 COMMENT 說明資料已遷移，不再使用。

⚠️ 注意：此 migration 不刪除資料，僅加上標記註解。
正式移除資料表前，請確認已完成所有資料遷移和驗證。

Revision ID: 013
Revises: 012
Create Date: 2026-02-03
"""

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None

# 已遷移至 ERPNext 的資料表
DEPRECATED_TABLES = {
    "projects": "DEPRECATED: 已遷移至 ERPNext Project DocType",
    "project_members": "DEPRECATED: 已遷移至 ERPNext（成員資訊存於 Project Comment）",
    "project_milestones": "DEPRECATED: 已遷移至 ERPNext Task DocType",
    "project_meetings": "DEPRECATED: 已遷移至 ERPNext Event DocType",
    "project_attachments": "DEPRECATED: 已遷移至 ERPNext（附件資訊存於 Project Comment）",
    "project_links": "DEPRECATED: 已遷移至 ERPNext（連結資訊存於 Project Comment）",
    "project_delivery_schedules": "DEPRECATED: 已遷移至 ERPNext Purchase Order DocType",
    "vendors": "DEPRECATED: 已遷移至 ERPNext Supplier DocType",
    "inventory_items": "DEPRECATED: 已遷移至 ERPNext Item DocType",
    "inventory_transactions": "DEPRECATED: 已遷移至 ERPNext Stock Entry DocType",
    "inventory_orders": "DEPRECATED: 已遷移至 ERPNext Purchase Order DocType",
}


def upgrade() -> None:
    # 為每個資料表加上 COMMENT
    for table, comment in DEPRECATED_TABLES.items():
        op.execute(f"COMMENT ON TABLE {table} IS '{comment}'")


def downgrade() -> None:
    # 移除 COMMENT
    for table in DEPRECATED_TABLES:
        op.execute(f"COMMENT ON TABLE {table} IS NULL")
