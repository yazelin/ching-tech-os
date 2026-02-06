"""移除分區表的 tenant_id 欄位

移除 ai_logs、login_records、messages 分區表中的 tenant_id 欄位。
這些表在 003 migration 中被遺漏。

Revision ID: 004
Revises: 003
Create Date: 2026-02-06
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    # 取得所有含 tenant_id 的分區表
    result = connection.execute(sa.text("""
        SELECT table_name FROM information_schema.columns
        WHERE column_name = 'tenant_id'
          AND table_schema = 'public'
        ORDER BY table_name
    """))
    tables = [row[0] for row in result]

    if not tables:
        print("沒有需要處理的表")
        return

    print(f"需要移除 tenant_id 的表: {tables}")

    for table in tables:
        try:
            # 先移除相關的索引
            idx_result = connection.execute(sa.text(f"""
                SELECT indexname FROM pg_indexes
                WHERE tablename = '{table}'
                  AND indexdef LIKE '%tenant_id%'
            """))
            for idx_row in idx_result:
                idx_name = idx_row[0]
                print(f"  移除索引 {idx_name} from {table}")
                connection.execute(sa.text(f"DROP INDEX IF EXISTS {idx_name}"))

            # 移除 tenant_id 欄位
            print(f"  移除 {table}.tenant_id")
            connection.execute(sa.text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS tenant_id"))
        except Exception as e:
            print(f"  警告：處理 {table} 時發生錯誤: {e}")

    print("分區表 tenant_id 移除完成")


def downgrade() -> None:
    # 不支援回滾
    pass
