"""為庫存管理相關表新增 tenant_id 欄位

Revision ID: 053
Revises: 052
Create Date: 2026-01-20

影響表格：
- inventory_items
- inventory_transactions
- vendors
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None

# 預設租戶 UUID
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"

# 庫存相關表清單
INVENTORY_TABLES = [
    "inventory_items",
    "inventory_transactions",
    "vendors",
]


def upgrade() -> None:
    # 為所有庫存相關表新增 tenant_id 欄位
    for table in INVENTORY_TABLES:
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
    for table in INVENTORY_TABLES:
        op.execute(f"""
            UPDATE {table} SET tenant_id = '{DEFAULT_TENANT_ID}'::uuid WHERE tenant_id IS NULL;
        """)

    # 為所有表建立外鍵約束
    for table in INVENTORY_TABLES:
        op.create_foreign_key(
            f"fk_{table}_tenant_id",
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE"
        )

    # === inventory_items 索引 ===
    op.create_index("idx_inventory_items_tenant_id", "inventory_items", ["tenant_id"])
    # 修改物料名稱唯一性為租戶內唯一
    op.drop_index("idx_inventory_items_name", table_name="inventory_items")
    op.create_index("idx_inventory_items_tenant_name", "inventory_items", ["tenant_id", "name"], unique=True)

    # === inventory_transactions 索引 ===
    op.create_index("idx_inventory_transactions_tenant_id", "inventory_transactions", ["tenant_id"])
    op.create_index("idx_inventory_transactions_tenant_item", "inventory_transactions", ["tenant_id", "item_id"])

    # === vendors 索引 ===
    op.create_index("idx_vendors_tenant_id", "vendors", ["tenant_id"])
    # 修改 ERP 編號唯一性為租戶內唯一（如果有的話）
    # 先檢查是否有 erp_code 的唯一索引
    op.execute("""
        DROP INDEX IF EXISTS idx_vendors_erp_code;
    """)
    op.create_index("idx_vendors_tenant_erp_code", "vendors", ["tenant_id", "erp_code"], unique=False)


def downgrade() -> None:
    # === vendors ===
    op.drop_index("idx_vendors_tenant_erp_code", table_name="vendors")
    op.drop_index("idx_vendors_tenant_id", table_name="vendors")

    # === inventory_transactions ===
    op.drop_index("idx_inventory_transactions_tenant_item", table_name="inventory_transactions")
    op.drop_index("idx_inventory_transactions_tenant_id", table_name="inventory_transactions")

    # === inventory_items ===
    op.drop_index("idx_inventory_items_tenant_name", table_name="inventory_items")
    op.create_index("idx_inventory_items_name", "inventory_items", ["name"], unique=True)
    op.drop_index("idx_inventory_items_tenant_id", table_name="inventory_items")

    # 刪除外鍵約束
    for table in INVENTORY_TABLES:
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")

    # 刪除 tenant_id 欄位
    for table in INVENTORY_TABLES:
        op.drop_column(table, "tenant_id")
