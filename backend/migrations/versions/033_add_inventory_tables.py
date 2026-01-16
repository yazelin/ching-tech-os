"""新增物料管理資料表

Revision ID: 033
Revises: 032
Create Date: 2026-01-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 建立物料主檔資料表
    op.create_table(
        "inventory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False, comment="物料名稱"),
        sa.Column("specification", sa.String(500), nullable=True, comment="規格"),
        sa.Column("unit", sa.String(50), nullable=True, comment="單位（如：個、台、公斤）"),
        sa.Column("category", sa.String(100), nullable=True, comment="類別"),
        sa.Column("default_vendor", sa.String(200), nullable=True, comment="預設廠商"),
        sa.Column("min_stock", sa.Numeric(15, 3), nullable=True, server_default="0", comment="最低庫存量"),
        sa.Column("current_stock", sa.Numeric(15, 3), nullable=False, server_default="0", comment="目前庫存"),
        sa.Column("notes", sa.Text, nullable=True, comment="備註"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True, comment="建立者"),
    )

    # 建立物料名稱索引（唯一性）
    op.create_index("idx_inventory_items_name", "inventory_items", ["name"], unique=True)

    # 建立類別索引
    op.create_index("idx_inventory_items_category", "inventory_items", ["category"])

    # 建立進出貨記錄資料表
    op.create_table(
        "inventory_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, comment="物料 ID"),
        sa.Column("type", sa.String(10), nullable=False, comment="類型：in（進貨）/ out（出貨）"),
        sa.Column("quantity", sa.Numeric(15, 3), nullable=False, comment="數量"),
        sa.Column("transaction_date", sa.Date, nullable=False, server_default=sa.text("CURRENT_DATE"), comment="進出貨日期"),
        sa.Column("vendor", sa.String(200), nullable=True, comment="廠商"),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, comment="關聯專案"),
        sa.Column("notes", sa.Text, nullable=True, comment="備註"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True, comment="建立者"),
    )

    # 建立物料 ID 索引
    op.create_index("idx_inventory_transactions_item_id", "inventory_transactions", ["item_id"])

    # 建立專案 ID 索引
    op.create_index("idx_inventory_transactions_project_id", "inventory_transactions", ["project_id"])

    # 建立日期索引
    op.create_index("idx_inventory_transactions_date", "inventory_transactions", ["transaction_date"])

    # 建立類型索引
    op.create_index("idx_inventory_transactions_type", "inventory_transactions", ["type"])

    # 建立觸發器：自動更新 inventory_items 的 updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_inventory_items_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trigger_inventory_items_updated_at
        BEFORE UPDATE ON inventory_items
        FOR EACH ROW
        EXECUTE FUNCTION update_inventory_items_updated_at();
    """)

    # 建立觸發器：自動更新 current_stock
    op.execute("""
        CREATE OR REPLACE FUNCTION update_inventory_current_stock()
        RETURNS TRIGGER AS $$
        DECLARE
            new_stock NUMERIC(15, 3);
        BEGIN
            -- 計算新庫存
            IF TG_OP = 'DELETE' THEN
                SELECT COALESCE(
                    SUM(CASE WHEN type = 'in' THEN quantity ELSE -quantity END),
                    0
                ) INTO new_stock
                FROM inventory_transactions
                WHERE item_id = OLD.item_id;

                UPDATE inventory_items SET current_stock = new_stock WHERE id = OLD.item_id;
                RETURN OLD;
            ELSE
                SELECT COALESCE(
                    SUM(CASE WHEN type = 'in' THEN quantity ELSE -quantity END),
                    0
                ) INTO new_stock
                FROM inventory_transactions
                WHERE item_id = NEW.item_id;

                UPDATE inventory_items SET current_stock = new_stock WHERE id = NEW.item_id;
                RETURN NEW;
            END IF;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trigger_update_inventory_stock
        AFTER INSERT OR UPDATE OR DELETE ON inventory_transactions
        FOR EACH ROW
        EXECUTE FUNCTION update_inventory_current_stock();
    """)


def downgrade() -> None:
    # 刪除觸發器
    op.execute("DROP TRIGGER IF EXISTS trigger_update_inventory_stock ON inventory_transactions")
    op.execute("DROP FUNCTION IF EXISTS update_inventory_current_stock()")
    op.execute("DROP TRIGGER IF EXISTS trigger_inventory_items_updated_at ON inventory_items")
    op.execute("DROP FUNCTION IF EXISTS update_inventory_items_updated_at()")

    # 刪除索引
    op.drop_index("idx_inventory_transactions_type")
    op.drop_index("idx_inventory_transactions_date")
    op.drop_index("idx_inventory_transactions_project_id")
    op.drop_index("idx_inventory_transactions_item_id")
    op.drop_index("idx_inventory_items_category")
    op.drop_index("idx_inventory_items_name")

    # 刪除資料表
    op.drop_table("inventory_transactions")
    op.drop_table("inventory_items")
