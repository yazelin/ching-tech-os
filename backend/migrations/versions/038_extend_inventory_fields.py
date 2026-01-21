"""擴充物料主檔欄位並新增訂購記錄資料表

Revision ID: 038
Revises: 037
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 物料主檔新增欄位
    op.add_column(
        "inventory_items",
        sa.Column("model", sa.String(200), nullable=True, comment="型號"),
    )
    op.add_column(
        "inventory_items",
        sa.Column("storage_location", sa.String(200), nullable=True, comment="存放庫位"),
    )

    # 建立訂購記錄資料表
    op.create_table(
        "inventory_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, comment="物料 ID"),
        sa.Column("order_quantity", sa.Numeric(15, 3), nullable=False, comment="訂購數量"),
        sa.Column("order_date", sa.Date, nullable=True, comment="下單日期"),
        sa.Column("expected_delivery_date", sa.Date, nullable=True, comment="預計交貨日期"),
        sa.Column("actual_delivery_date", sa.Date, nullable=True, comment="實際交貨日期"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", comment="狀態：pending/ordered/delivered/cancelled"),
        sa.Column("vendor", sa.String(200), nullable=True, comment="訂購廠商"),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, comment="關聯專案"),
        sa.Column("notes", sa.Text, nullable=True, comment="備註"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True, comment="建立者"),
    )

    # 建立索引
    op.create_index("idx_inventory_orders_item_id", "inventory_orders", ["item_id"])
    op.create_index("idx_inventory_orders_project_id", "inventory_orders", ["project_id"])
    op.create_index("idx_inventory_orders_status", "inventory_orders", ["status"])
    op.create_index("idx_inventory_orders_order_date", "inventory_orders", ["order_date"])

    # 建立觸發器：自動更新 inventory_orders 的 updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_inventory_orders_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trigger_inventory_orders_updated_at
        BEFORE UPDATE ON inventory_orders
        FOR EACH ROW
        EXECUTE FUNCTION update_inventory_orders_updated_at();
    """)


def downgrade() -> None:
    # 刪除觸發器
    op.execute("DROP TRIGGER IF EXISTS trigger_inventory_orders_updated_at ON inventory_orders")
    op.execute("DROP FUNCTION IF EXISTS update_inventory_orders_updated_at()")

    # 刪除索引
    op.drop_index("idx_inventory_orders_order_date", table_name="inventory_orders")
    op.drop_index("idx_inventory_orders_status", table_name="inventory_orders")
    op.drop_index("idx_inventory_orders_project_id", table_name="inventory_orders")
    op.drop_index("idx_inventory_orders_item_id", table_name="inventory_orders")

    # 刪除訂購記錄資料表
    op.drop_table("inventory_orders")

    # 移除物料主檔新增欄位
    op.drop_column("inventory_items", "storage_location")
    op.drop_column("inventory_items", "model")
