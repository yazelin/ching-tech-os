"""重命名 line_* 表格為 bot_* 並統一時間欄位格式

1. 將 line_* 表格重命名為 bot_*，加入 platform_type 欄位（預設 'line'）
2. 將所有 timestamp without time zone 欄位統一為 timestamp with time zone

Revision ID: 005
Revises: 004
Create Date: 2026-01-29
"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

# ============================================================
# 需要重命名的表格：line_* → bot_*
# ============================================================
LINE_TO_BOT_TABLES = [
    "line_groups",
    "line_users",
    "line_messages",
    "line_files",
    "line_binding_codes",
    "line_group_memories",
    "line_user_memories",
]

# ============================================================
# 需要修正的 timestamp 欄位（without → with time zone）
# ============================================================
TIMESTAMP_FIXES = [
    ("project_attachments", "uploaded_at"),
    ("project_delivery_schedules", "created_at"),
    ("project_delivery_schedules", "updated_at"),
    ("project_links", "created_at"),
    ("project_meetings", "created_at"),
    ("project_meetings", "updated_at"),
    ("project_members", "created_at"),
    ("project_milestones", "created_at"),
    ("project_milestones", "updated_at"),
    ("projects", "created_at"),
    ("projects", "updated_at"),
    ("users", "created_at"),
    ("users", "last_login_at"),
]


def _rename_db_objects(conn, from_prefix, to_prefix):
    """重命名 index、sequence、constraint"""
    # Index
    rows = conn.execute(text(
        "SELECT indexname FROM pg_indexes "
        f"WHERE schemaname = 'public' AND indexname LIKE '{from_prefix}%'"
    )).fetchall()
    for (name,) in rows:
        new_name = name.replace(from_prefix, to_prefix, 1)
        op.execute(f'ALTER INDEX IF EXISTS "{name}" RENAME TO "{new_name}"')

    # Sequence
    rows = conn.execute(text(
        "SELECT sequencename FROM pg_sequences "
        f"WHERE schemaname = 'public' AND sequencename LIKE '{from_prefix}%'"
    )).fetchall()
    for (name,) in rows:
        new_name = name.replace(from_prefix, to_prefix, 1)
        op.execute(f'ALTER SEQUENCE IF EXISTS "{name}" RENAME TO "{new_name}"')

    # Constraint（需要知道表名才能 rename）
    rows = conn.execute(text(
        "SELECT c.conname, t.relname "
        "FROM pg_constraint c "
        "JOIN pg_class t ON c.conrelid = t.oid "
        f"WHERE c.conname LIKE '{from_prefix}%'"
    )).fetchall()
    for con_name, table_name in rows:
        new_con_name = con_name.replace(from_prefix, to_prefix, 1)
        op.execute(
            f'ALTER TABLE "{table_name}" '
            f'RENAME CONSTRAINT "{con_name}" TO "{new_con_name}"'
        )


def upgrade() -> None:
    conn = op.get_bind()

    # ---- Part 1: 重命名 line_* → bot_* ----
    for old_name in LINE_TO_BOT_TABLES:
        new_name = old_name.replace("line_", "bot_", 1)
        op.rename_table(old_name, new_name)

    # 重命名相關的 index、sequence、constraint
    _rename_db_objects(conn, "line_", "bot_")

    # 為主要表格加入 platform_type 欄位
    for table in ["bot_groups", "bot_users", "bot_messages", "bot_files", "bot_binding_codes"]:
        op.execute(
            f"ALTER TABLE {table} "
            f"ADD COLUMN IF NOT EXISTS platform_type VARCHAR(20) "
            f"NOT NULL DEFAULT 'line'"
        )

    # ---- Part 2: 統一 timestamp 格式 ----
    for table, column in TIMESTAMP_FIXES:
        op.execute(
            f"ALTER TABLE {table} "
            f"ALTER COLUMN {column} TYPE timestamp with time zone "
            f"USING {column} AT TIME ZONE 'Asia/Taipei'"
        )


def downgrade() -> None:
    conn = op.get_bind()

    # ---- Part 2 回滾: timestamp with → without ----
    for table, column in TIMESTAMP_FIXES:
        op.execute(
            f"ALTER TABLE {table} "
            f"ALTER COLUMN {column} TYPE timestamp without time zone"
        )

    # ---- Part 1 回滾: 移除 platform_type ----
    for table in ["bot_groups", "bot_users", "bot_messages", "bot_files", "bot_binding_codes"]:
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS platform_type")

    # 重命名 bot_* → line_*
    for old_name in LINE_TO_BOT_TABLES:
        new_name = old_name.replace("line_", "bot_", 1)
        op.rename_table(new_name, old_name)

    # 重命名相關的 index、sequence、constraint
    _rename_db_objects(conn, "bot_", "line_")
