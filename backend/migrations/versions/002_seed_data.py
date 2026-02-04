"""初始種子資料

載入預設租戶、AI prompts 和 agents 等初始資料。

Revision ID: 002
Revises: 001
Create Date: 2025-01-23
"""
from alembic import op
import os

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    raw_conn = connection.connection.dbapi_connection
    cur = raw_conn.cursor()
    base_path = os.path.dirname(__file__)

    # 載入種子資料（預設租戶、prompts、agents）
    seed_path = os.path.join(base_path, 'seed_data.sql')
    with open(seed_path, 'r', encoding='utf-8') as f:
        seed_sql = f.read()
    cur.execute(seed_sql)


def downgrade() -> None:
    # 種子資料的 downgrade 會清空相關表格
    # 但在生產環境中不應該執行
    raise NotImplementedError("種子資料 migration 不支援 downgrade")
