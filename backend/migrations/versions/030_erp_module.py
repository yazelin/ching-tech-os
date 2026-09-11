"""往來與物料模組：parties / items / warehouses / stock / purchase / audit

取代 ERPNext 的自建類 ERP（規格 docs/superpowers/specs/2026-09-12-ai-native-erp-design.md
第二節）。供應商與客戶合併成一張 parties；庫存是簡化分類帳（stock_movements 累計
stock_balances），不做成本與批號；採購單只做開單與收貨。

模糊解析靠 pg_trgm：parties.name／short_name 與 items.name 建 gin trgm 索引，
aliases text[] 建 gin 索引。extension 在 upgrade 建立，downgrade **不** drop
（其他資料庫物件可能也在用）。

Revision ID: 030
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _created_by() -> sa.Column:
    return sa.Column(
        "created_by",
        sa.Integer(),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    ]


def _deleted_at() -> sa.Column:
    """主檔的軟刪除欄位；非空的主檔不進清單也不進模糊解析"""
    return sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True)


def upgrade() -> None:
    # 模糊比對用；已存在就不動
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── 往來對象（vendor-management）────────────────────────────
    op.create_table(
        "parties",
        _uuid_pk(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=True),
        # 模糊比對用的別名（「鴻佰」「鴻佰科技」），gin 索引
        sa.Column(
            "aliases",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        # 同一家公司可以同時是供應商與客戶，只有一筆 party
        sa.Column(
            "is_supplier", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "is_customer", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("tax_id", sa.Text(), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("payment_terms", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # ERPNext 的 Supplier／Customer name，匯入對照用（scripts/erpnext_import.py 的冪等 key）
        sa.Column("source_ref", sa.Text(), nullable=True),
        _created_by(),
        *_timestamps(),
        _deleted_at(),
    )
    op.create_index(
        "idx_parties_name_trgm",
        "parties",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index(
        "idx_parties_short_name_trgm",
        "parties",
        ["short_name"],
        postgresql_using="gin",
        postgresql_ops={"short_name": "gin_trgm_ops"},
    )
    op.create_index(
        "idx_parties_aliases", "parties", ["aliases"], postgresql_using="gin"
    )
    # 統編是精確命中的捷徑（解析器優先用它）
    op.create_index("idx_parties_tax_id", "parties", ["tax_id"])

    op.create_table(
        "party_contacts",
        _uuid_pk(),
        sa.Column(
            "party_id",
            UUID(as_uuid=True),
            sa.ForeignKey("parties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("mobile", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column(
            "is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        _created_by(),
        *_timestamps(),
    )
    op.create_index("idx_party_contacts_party_id", "party_contacts", ["party_id"])
    op.create_index(
        "idx_party_contacts_name_trgm",
        "party_contacts",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    # 電話是精確命中（名片上的號碼直接對到既有 party）
    op.create_index("idx_party_contacts_phone", "party_contacts", ["phone"])
    op.create_index("idx_party_contacts_mobile", "party_contacts", ["mobile"])

    op.create_table(
        "party_addresses",
        _uuid_pk(),
        sa.Column(
            "party_id",
            UUID(as_uuid=True),
            sa.ForeignKey("parties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # 公司／工廠／收貨
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column(
            "is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        _created_by(),
        *_timestamps(),
    )
    op.create_index("idx_party_addresses_party_id", "party_addresses", ["party_id"])

    # ── 物料與庫存（inventory-management）───────────────────────
    op.create_table(
        "items",
        _uuid_pk(),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("spec", sa.Text(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("item_group", sa.Text(), nullable=True),
        sa.Column(
            "default_supplier_id",
            UUID(as_uuid=True),
            sa.ForeignKey("parties.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("purchase_price", sa.Numeric(14, 4), nullable=True),
        sa.Column("lead_days", sa.Integer(), nullable=True),
        sa.Column(
            "aliases",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_ref", sa.Text(), nullable=True),
        _created_by(),
        *_timestamps(),
        _deleted_at(),
        # 料號唯一（含軟刪除的，避免刪掉又建同號後庫存對不起來）
        sa.UniqueConstraint("code", name="uq_items_code"),
    )
    op.create_index(
        "idx_items_name_trgm",
        "items",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index("idx_items_aliases", "items", ["aliases"], postgresql_using="gin")

    op.create_table(
        "warehouses",
        _uuid_pk(),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        _created_by(),
        *_timestamps(),
        _deleted_at(),
        sa.UniqueConstraint("code", name="uq_warehouses_code"),
    )

    op.create_table(
        "stock_balances",
        _uuid_pk(),
        sa.Column(
            "item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "qty", sa.Numeric(18, 4), nullable=False, server_default=sa.text("0")
        ),
        _created_by(),
        *_timestamps(),
        # adjust_stock 的 ON CONFLICT 靠這個 unique
        sa.UniqueConstraint(
            "item_id", "warehouse_id", name="uq_stock_balances_item_warehouse"
        ),
    )

    op.create_table(
        "stock_movements",
        _uuid_pk(),
        sa.Column(
            "item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("qty_delta", sa.Numeric(18, 4), nullable=False),
        # receipt / issue / adjust / transfer_in / transfer_out / import
        sa.Column("reason", sa.Text(), nullable=False),
        # 來源單據（採購收貨是 purchase_order）
        sa.Column("ref_type", sa.Text(), nullable=True),
        sa.Column("ref_id", UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        _created_by(),
        *_timestamps(),
    )
    op.create_index(
        "idx_stock_movements_item_created",
        "stock_movements",
        ["item_id", "created_at"],
    )

    # ── 採購（inventory-management）──────────────────────────────
    op.create_table(
        "purchase_orders",
        _uuid_pk(),
        # PO-YYYYMM-NNN，由 service 在同一交易內產生
        sa.Column("po_no", sa.Text(), nullable=False),
        sa.Column(
            "supplier_id",
            UUID(as_uuid=True),
            sa.ForeignKey("parties.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # draft / ordered / partial / received / cancelled
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("order_date", sa.Date(), nullable=True),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        _created_by(),
        *_timestamps(),
        sa.UniqueConstraint("po_no", name="uq_purchase_orders_po_no"),
    )
    op.create_index(
        "idx_purchase_orders_supplier_id", "purchase_orders", ["supplier_id"]
    )
    op.create_index("idx_purchase_orders_status", "purchase_orders", ["status"])
    op.create_index("idx_purchase_orders_project_id", "purchase_orders", ["project_id"])

    op.create_table(
        "purchase_order_lines",
        _uuid_pk(),
        sa.Column(
            "po_id",
            UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=True),
        sa.Column(
            "received_qty",
            sa.Numeric(18, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        _created_by(),
        *_timestamps(),
        # 已收量不可能超過訂購量；service 也擋，這裡是最後一道（併發收貨時才看得到差別）
        sa.CheckConstraint(
            "received_qty <= qty", name="ck_purchase_order_lines_received_qty"
        ),
    )
    op.create_index("idx_purchase_order_lines_po_id", "purchase_order_lines", ["po_id"])

    # ── 稽核 ────────────────────────────────────────────────────
    op.create_table(
        "erp_audit",
        _uuid_pk(),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("diff", JSONB(), nullable=True),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # mcp / rest
        sa.Column("via", sa.Text(), nullable=False, server_default="mcp"),
        sa.Column("agent_name", sa.Text(), nullable=True),
        _created_by(),
        *_timestamps(),
    )
    op.create_index("idx_erp_audit_entity", "erp_audit", ["entity_type", "entity_id"])


def downgrade() -> None:
    # 反序 drop；pg_trgm extension 保留不 drop
    op.drop_index("idx_erp_audit_entity", table_name="erp_audit")
    op.drop_table("erp_audit")

    op.drop_index("idx_purchase_order_lines_po_id", table_name="purchase_order_lines")
    op.drop_table("purchase_order_lines")

    op.drop_index("idx_purchase_orders_project_id", table_name="purchase_orders")
    op.drop_index("idx_purchase_orders_status", table_name="purchase_orders")
    op.drop_index("idx_purchase_orders_supplier_id", table_name="purchase_orders")
    op.drop_table("purchase_orders")

    op.drop_index("idx_stock_movements_item_created", table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_table("stock_balances")
    op.drop_table("warehouses")

    op.drop_index("idx_items_aliases", table_name="items")
    op.drop_index("idx_items_name_trgm", table_name="items")
    op.drop_table("items")

    op.drop_index("idx_party_addresses_party_id", table_name="party_addresses")
    op.drop_table("party_addresses")

    op.drop_index("idx_party_contacts_mobile", table_name="party_contacts")
    op.drop_index("idx_party_contacts_phone", table_name="party_contacts")
    op.drop_index("idx_party_contacts_name_trgm", table_name="party_contacts")
    op.drop_index("idx_party_contacts_party_id", table_name="party_contacts")
    op.drop_table("party_contacts")

    op.drop_index("idx_parties_tax_id", table_name="parties")
    op.drop_index("idx_parties_aliases", table_name="parties")
    op.drop_index("idx_parties_short_name_trgm", table_name="parties")
    op.drop_index("idx_parties_name_trgm", table_name="parties")
    op.drop_table("parties")
