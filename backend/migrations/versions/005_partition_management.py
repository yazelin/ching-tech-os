"""create partition management functions

Revision ID: 005
Revises: 004
Create Date: 2025-12-11

自動分區管理函式 - 建立新分區、刪除過期分區
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 建立自動建立下個月分區的函式
    op.execute("""
        CREATE OR REPLACE FUNCTION create_next_month_partitions()
        RETURNS void AS $$
        DECLARE
            next_month_start DATE;
            next_month_end DATE;
            partition_name TEXT;
        BEGIN
            -- 計算下個月的起始和結束日期
            next_month_start := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')::DATE;
            next_month_end := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '2 months')::DATE;

            -- 建立 messages 分區（如果不存在）
            partition_name := 'messages_' || TO_CHAR(next_month_start, 'YYYY_MM');
            IF NOT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = partition_name
            ) THEN
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF messages FOR VALUES FROM (%L) TO (%L)',
                    partition_name, next_month_start, next_month_end
                );
                RAISE NOTICE 'Created partition: %', partition_name;
            END IF;

            -- 建立 login_records 分區（如果不存在）
            partition_name := 'login_records_' || TO_CHAR(next_month_start, 'YYYY_MM');
            IF NOT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = partition_name
            ) THEN
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF login_records FOR VALUES FROM (%L) TO (%L)',
                    partition_name, next_month_start, next_month_end
                );
                RAISE NOTICE 'Created partition: %', partition_name;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 建立刪除過期分區的函式（保留 1 年）
    op.execute("""
        CREATE OR REPLACE FUNCTION drop_old_partitions(retention_months INTEGER DEFAULT 12)
        RETURNS void AS $$
        DECLARE
            cutoff_date DATE;
            rec RECORD;
        BEGIN
            cutoff_date := DATE_TRUNC('month', CURRENT_DATE - (retention_months || ' months')::INTERVAL)::DATE;

            -- 刪除過期的 messages 分區
            FOR rec IN
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename ~ '^messages_[0-9]{4}_[0-9]{2}$'
            LOOP
                -- 從分區名稱解析日期
                IF TO_DATE(SUBSTRING(rec.tablename FROM 10), 'YYYY_MM') < cutoff_date THEN
                    EXECUTE format('DROP TABLE IF EXISTS %I', rec.tablename);
                    RAISE NOTICE 'Dropped partition: %', rec.tablename;
                END IF;
            END LOOP;

            -- 刪除過期的 login_records 分區
            FOR rec IN
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename ~ '^login_records_[0-9]{4}_[0-9]{2}$'
            LOOP
                -- 從分區名稱解析日期
                IF TO_DATE(SUBSTRING(rec.tablename FROM 15), 'YYYY_MM') < cutoff_date THEN
                    EXECUTE format('DROP TABLE IF EXISTS %I', rec.tablename);
                    RAISE NOTICE 'Dropped partition: %', rec.tablename;
                END IF;
            END LOOP;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 建立統計分區資訊的函式
    op.execute("""
        CREATE OR REPLACE FUNCTION get_partition_stats()
        RETURNS TABLE (
            table_name TEXT,
            partition_name TEXT,
            row_count BIGINT,
            size_bytes BIGINT
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                p.parent::TEXT as table_name,
                c.relname::TEXT as partition_name,
                pg_stat_get_live_tuples(c.oid) as row_count,
                pg_total_relation_size(c.oid) as size_bytes
            FROM pg_inherits i
            JOIN pg_class c ON c.oid = i.inhrelid
            JOIN (
                SELECT 'messages'::regclass::oid as parent
                UNION ALL
                SELECT 'login_records'::regclass::oid as parent
            ) p ON p.parent = i.inhparent
            ORDER BY c.relname;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 加入函式註解
    op.execute("""
        COMMENT ON FUNCTION create_next_month_partitions() IS
        '自動建立下個月的分區（messages 和 login_records）'
    """)
    op.execute("""
        COMMENT ON FUNCTION drop_old_partitions(INTEGER) IS
        '刪除超過保留期限的分區，預設保留 12 個月'
    """)
    op.execute("""
        COMMENT ON FUNCTION get_partition_stats() IS
        '取得分區統計資訊（列數、大小）'
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS create_next_month_partitions()")
    op.execute("DROP FUNCTION IF EXISTS drop_old_partitions(INTEGER)")
    op.execute("DROP FUNCTION IF EXISTS get_partition_stats()")
