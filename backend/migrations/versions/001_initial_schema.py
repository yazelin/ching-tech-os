"""初始資料庫結構 - 多租戶架構 baseline

這是完全重建後的初始 migration，包含完整的多租戶架構。
從 database.sql 匯入的結構，作為新環境的起點。

Revision ID: 001
Revises:
Create Date: 2025-01-23
"""
from alembic import op
from sqlalchemy import text
import os

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    base_path = os.path.dirname(__file__)

    # 1. 執行 schema SQL（建立表格結構）
    schema_path = os.path.join(base_path, 'clean_schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    connection.execute(text(schema_sql))

    # 2. 建立當月和下月的分區
    connection.execute(text("SELECT create_ai_logs_partition()"))
    connection.execute(text("SELECT create_next_month_partitions()"))

    # 3. 載入種子資料（預設租戶、prompts、agents）
    seed_path = os.path.join(base_path, 'seed_data.sql')
    with open(seed_path, 'r', encoding='utf-8') as f:
        seed_sql = f.read()
    connection.execute(text(seed_sql))


def downgrade() -> None:
    # 完整的 downgrade 需要刪除所有表格
    # 這是 baseline，不應該被 downgrade
    raise NotImplementedError("這是初始 migration，無法 downgrade")
