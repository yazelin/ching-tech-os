"""新增廠商主檔資料表與關聯

Revision ID: 034
Revises: 033
Create Date: 2026-01-16

廠商主檔功能：
- 建立 vendors 資料表（含 ERP 編號對照）
- project_delivery_schedules 新增 vendor_id、item_id 外鍵
- inventory_items 新增 default_vendor_id 外鍵
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 建立廠商主檔資料表
    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("erp_code", sa.String(50), nullable=True, unique=True, comment="ERP 系統廠商編號"),
        sa.Column("name", sa.String(200), nullable=False, comment="廠商名稱"),
        sa.Column("short_name", sa.String(100), nullable=True, comment="簡稱"),
        sa.Column("contact_person", sa.String(100), nullable=True, comment="聯絡人"),
        sa.Column("phone", sa.String(50), nullable=True, comment="電話"),
        sa.Column("fax", sa.String(50), nullable=True, comment="傳真"),
        sa.Column("email", sa.String(200), nullable=True, comment="Email"),
        sa.Column("address", sa.Text, nullable=True, comment="地址"),
        sa.Column("tax_id", sa.String(20), nullable=True, comment="統一編號"),
        sa.Column("payment_terms", sa.String(200), nullable=True, comment="付款條件"),
        sa.Column("notes", sa.Text, nullable=True, comment="備註"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true", comment="是否啟用"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True, comment="建立者"),
    )

    # 建立廠商名稱索引
    op.create_index("idx_vendors_name", "vendors", ["name"])

    # 建立 ERP 編號索引（唯一性已由 column 定義）
    op.create_index("idx_vendors_erp_code", "vendors", ["erp_code"])

    # 建立啟用狀態索引
    op.create_index("idx_vendors_is_active", "vendors", ["is_active"])

    # 建立觸發器：自動更新 vendors 的 updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_vendors_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trigger_vendors_updated_at
        BEFORE UPDATE ON vendors
        FOR EACH ROW
        EXECUTE FUNCTION update_vendors_updated_at();
    """)

    # project_delivery_schedules 新增 vendor_id 外鍵
    op.add_column(
        "project_delivery_schedules",
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=True, comment="關聯廠商 ID")
    )
    op.create_foreign_key(
        "fk_delivery_schedules_vendor",
        "project_delivery_schedules", "vendors",
        ["vendor_id"], ["id"],
        ondelete="SET NULL"
    )
    op.create_index("idx_delivery_schedules_vendor_id", "project_delivery_schedules", ["vendor_id"])

    # project_delivery_schedules 新增 item_id 外鍵
    op.add_column(
        "project_delivery_schedules",
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=True, comment="關聯物料 ID")
    )
    op.create_foreign_key(
        "fk_delivery_schedules_item",
        "project_delivery_schedules", "inventory_items",
        ["item_id"], ["id"],
        ondelete="SET NULL"
    )
    op.create_index("idx_delivery_schedules_item_id", "project_delivery_schedules", ["item_id"])

    # inventory_items 新增 default_vendor_id 外鍵
    op.add_column(
        "inventory_items",
        sa.Column("default_vendor_id", postgresql.UUID(as_uuid=True), nullable=True, comment="預設廠商 ID")
    )
    op.create_foreign_key(
        "fk_inventory_items_default_vendor",
        "inventory_items", "vendors",
        ["default_vendor_id"], ["id"],
        ondelete="SET NULL"
    )
    op.create_index("idx_inventory_items_default_vendor_id", "inventory_items", ["default_vendor_id"])


def downgrade() -> None:
    # 刪除 inventory_items 的外鍵和欄位
    op.drop_index("idx_inventory_items_default_vendor_id")
    op.drop_constraint("fk_inventory_items_default_vendor", "inventory_items", type_="foreignkey")
    op.drop_column("inventory_items", "default_vendor_id")

    # 刪除 project_delivery_schedules 的 item_id 外鍵和欄位
    op.drop_index("idx_delivery_schedules_item_id")
    op.drop_constraint("fk_delivery_schedules_item", "project_delivery_schedules", type_="foreignkey")
    op.drop_column("project_delivery_schedules", "item_id")

    # 刪除 project_delivery_schedules 的 vendor_id 外鍵和欄位
    op.drop_index("idx_delivery_schedules_vendor_id")
    op.drop_constraint("fk_delivery_schedules_vendor", "project_delivery_schedules", type_="foreignkey")
    op.drop_column("project_delivery_schedules", "vendor_id")

    # 刪除觸發器和函數
    op.execute("DROP TRIGGER IF EXISTS trigger_vendors_updated_at ON vendors")
    op.execute("DROP FUNCTION IF EXISTS update_vendors_updated_at()")

    # 刪除索引
    op.drop_index("idx_vendors_is_active")
    op.drop_index("idx_vendors_erp_code")
    op.drop_index("idx_vendors_name")

    # 刪除 vendors 資料表
    op.drop_table("vendors")
