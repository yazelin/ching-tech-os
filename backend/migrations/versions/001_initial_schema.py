"""初始資料庫結構 - 多租戶架構

建立完整的資料庫表格結構和函數。
從 clean_schema.sql 匯入，作為新環境的起點。

Revision ID: 001
Revises:
Create Date: 2025-01-23
"""
from alembic import op
import os

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    raw_conn = connection.connection.dbapi_connection
    cur = raw_conn.cursor()
    base_path = os.path.dirname(__file__)

    # 1. 執行 schema SQL（建立表格結構）
    #    使用 raw dbapi cursor 避免 SQLAlchemy text() 對 % 符號的處理問題
    #    （PL/pgSQL 函式中使用 FORMAT('%I', ...) 等語法）
    schema_path = os.path.join(base_path, 'clean_schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    cur.execute(schema_sql)

    # 2. 還原 search_path（clean_schema.sql 會將它設為空）
    cur.execute("SET search_path = public")

    # 3. 建立當月和下月的分區
    cur.execute("SELECT create_ai_logs_partition()")
    cur.execute("SELECT create_next_month_partitions()")


def downgrade() -> None:
    # 完整的 downgrade 需要刪除所有表格
    # 這是 baseline，不應該被 downgrade
    raise NotImplementedError("這是初始 migration，無法 downgrade")
