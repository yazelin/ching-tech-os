"""建立租戶（Tenant）相關資料表

Revision ID: 037
Revises: 036
Create Date: 2026-01-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None

# 預設租戶 UUID（用於單租戶模式和現有資料遷移）
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    # 建立租戶主表
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), nullable=False, unique=True, comment="租戶代碼（用於登入識別）"),
        sa.Column("name", sa.String(200), nullable=False, comment="租戶名稱"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", comment="狀態：active, suspended, trial"),
        sa.Column("plan", sa.String(50), nullable=False, server_default="trial", comment="方案：trial, basic, pro, enterprise"),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"), comment="租戶設定"),
        sa.Column("storage_quota_mb", sa.BigInteger, nullable=False, server_default="5120", comment="儲存配額 (MB)"),
        sa.Column("storage_used_mb", sa.BigInteger, nullable=False, server_default="0", comment="已使用儲存 (MB)"),
        sa.Column("trial_ends_at", sa.TIMESTAMP(timezone=True), nullable=True, comment="試用期結束時間"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    # 建立租戶代碼索引（用於快速查詢）
    op.create_index("idx_tenants_code", "tenants", ["code"], unique=True)

    # 建立租戶狀態索引
    op.create_index("idx_tenants_status", "tenants", ["status"])

    # 建立觸發器：自動更新 tenants 的 updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_tenants_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trigger_tenants_updated_at
        BEFORE UPDATE ON tenants
        FOR EACH ROW
        EXECUTE FUNCTION update_tenants_updated_at();
    """)

    # 建立預設租戶（用於單租戶模式和現有資料遷移）
    op.execute(f"""
        INSERT INTO tenants (id, code, name, status, plan, storage_quota_mb)
        VALUES (
            '{DEFAULT_TENANT_ID}'::uuid,
            'default',
            '預設租戶',
            'active',
            'enterprise',
            102400  -- 100GB
        )
        ON CONFLICT (id) DO NOTHING;
    """)

    # 建立租戶管理員關聯表
    # 注意：此表的 user_id 外鍵將在 users 表新增 tenant_id 後再建立
    op.create_table(
        "tenant_admins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, comment="租戶 ID"),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, comment="用戶 ID（稍後建立外鍵）"),
        sa.Column("role", sa.String(50), nullable=False, server_default="admin", comment="角色：admin, owner"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    # 建立複合唯一索引（一個用戶在一個租戶只能有一個角色）
    op.create_index("idx_tenant_admins_tenant_user", "tenant_admins", ["tenant_id", "user_id"], unique=True)


def downgrade() -> None:
    # 刪除租戶管理員表
    op.drop_index("idx_tenant_admins_tenant_user", table_name="tenant_admins")
    op.drop_table("tenant_admins")

    # 刪除觸發器和函數
    op.execute("DROP TRIGGER IF EXISTS trigger_tenants_updated_at ON tenants")
    op.execute("DROP FUNCTION IF EXISTS update_tenants_updated_at()")

    # 刪除索引
    op.drop_index("idx_tenants_status", table_name="tenants")
    op.drop_index("idx_tenants_code", table_name="tenants")

    # 刪除租戶表
    op.drop_table("tenants")
