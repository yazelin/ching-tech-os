"""重命名殘留的 line_* 欄位名為平台無關名稱

將所有 bot_* 表格中殘留的 line_user_id / line_group_id 欄位
重命名為 platform_user_id / platform_group_id / bot_user_id / bot_group_id，
並修正索引和約束名稱，加入 platform_type 到唯一索引。

欄位重命名對照：
  bot_users.line_user_id → platform_user_id
  bot_groups.line_group_id → platform_group_id
  bot_messages.line_user_id → bot_user_id
  bot_messages.line_group_id → bot_group_id
  bot_binding_codes.used_by_line_user_id → used_by_bot_user_id
  bot_user_memories.line_user_id → bot_user_id
  bot_group_memories.line_group_id → bot_group_id

Revision ID: 007
Revises: 006
Create Date: 2026-01-29
"""

from alembic import op
from sqlalchemy import text

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

# ============================================================
# 欄位重命名對照表：(表格, 舊欄位, 新欄位)
# ============================================================
COLUMN_RENAMES = [
    ("bot_users", "line_user_id", "platform_user_id"),
    ("bot_groups", "line_group_id", "platform_group_id"),
    ("bot_messages", "line_user_id", "bot_user_id"),
    ("bot_messages", "line_group_id", "bot_group_id"),
    ("bot_binding_codes", "used_by_line_user_id", "used_by_bot_user_id"),
    ("bot_user_memories", "line_user_id", "bot_user_id"),
    ("bot_group_memories", "line_group_id", "bot_group_id"),
]

# ============================================================
# 索引重命名對照表：(舊名, 新名)
# ============================================================
INDEX_RENAMES = [
    # bot_users
    ("idx_line_users_line_user_id", "idx_bot_users_platform_user_id"),
    ("idx_line_users_tenant_id", "idx_bot_users_tenant_id"),
    ("idx_line_users_tenant_line_user", "idx_bot_users_tenant_platform"),
    ("idx_line_users_user_id", "idx_bot_users_user_id"),
    # bot_groups
    ("idx_line_groups_line_group_id", "idx_bot_groups_platform_group_id"),
    ("idx_line_groups_project_id", "idx_bot_groups_project_id"),
    ("idx_line_groups_tenant_id", "idx_bot_groups_tenant_id"),
    # bot_messages
    ("idx_line_messages_created_at", "idx_bot_messages_created_at"),
    ("idx_line_messages_line_group_id", "idx_bot_messages_bot_group_id"),
    ("idx_line_messages_line_user_id", "idx_bot_messages_bot_user_id"),
    ("idx_line_messages_message_type", "idx_bot_messages_message_type"),
    ("idx_line_messages_tenant_group", "idx_bot_messages_tenant_group"),
    ("idx_line_messages_tenant_id", "idx_bot_messages_tenant_id"),
    # bot_files
    ("idx_line_files_file_type", "idx_bot_files_file_type"),
    ("idx_line_files_message_id", "idx_bot_files_message_id"),
    ("idx_line_files_tenant_id", "idx_bot_files_tenant_id"),
    # bot_binding_codes
    ("idx_line_binding_codes_tenant_id", "idx_bot_binding_codes_tenant_id"),
    # bot_user_memories
    ("idx_line_user_memories_active", "idx_bot_user_memories_active"),
    ("idx_line_user_memories_user_id", "idx_bot_user_memories_bot_user_id"),
    # bot_group_memories
    ("idx_line_group_memories_active", "idx_bot_group_memories_active"),
    ("idx_line_group_memories_group_id", "idx_bot_group_memories_bot_group_id"),
]

# ============================================================
# 約束重命名：(表格, 舊約束名, 新約束名)
# ============================================================
CONSTRAINT_RENAMES = [
    # FK 約束
    ("bot_messages", "bot_messages_line_user_id_fkey", "bot_messages_bot_user_id_fkey"),
    ("bot_messages", "bot_messages_line_group_id_fkey", "bot_messages_bot_group_id_fkey"),
    ("bot_binding_codes", "bot_binding_codes_used_by_line_user_id_fkey", "bot_binding_codes_used_by_bot_user_id_fkey"),
    ("bot_user_memories", "bot_user_memories_line_user_id_fkey", "bot_user_memories_bot_user_id_fkey"),
    ("bot_group_memories", "bot_group_memories_line_group_id_fkey", "bot_group_memories_bot_group_id_fkey"),
    # FK 約束（殘留 line_ 前綴）
    ("bot_users", "fk_line_users_tenant_id", "fk_bot_users_tenant_id"),
    ("bot_groups", "fk_line_groups_tenant_id", "fk_bot_groups_tenant_id"),
    ("bot_messages", "fk_line_messages_file_id", "fk_bot_messages_file_id"),
    ("bot_messages", "fk_line_messages_tenant_id", "fk_bot_messages_tenant_id"),
    ("bot_files", "fk_line_files_tenant_id", "fk_bot_files_tenant_id"),
    ("bot_binding_codes", "fk_line_binding_codes_tenant_id", "fk_bot_binding_codes_tenant_id"),
]


def upgrade() -> None:
    conn = op.get_bind()

    # ---- 1. 重命名欄位 ----
    for table, old_col, new_col in COLUMN_RENAMES:
        op.execute(f'ALTER TABLE {table} RENAME COLUMN "{old_col}" TO "{new_col}"')

    # ---- 2. 重命名索引 ----
    for old_name, new_name in INDEX_RENAMES:
        # 先檢查索引是否存在
        exists = conn.execute(text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :name"
        ), {"name": old_name}).fetchone()
        if exists:
            op.execute(f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"')

    # ---- 3. 重命名約束 ----
    for table, old_name, new_name in CONSTRAINT_RENAMES:
        exists = conn.execute(text(
            "SELECT 1 FROM pg_constraint WHERE conname = :name"
        ), {"name": old_name}).fetchone()
        if exists:
            op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT "{old_name}" TO "{new_name}"')

    # ---- 4. 修正唯一索引：加入 platform_type ----

    # bot_users：舊的 (tenant_id, line_user_id) → (tenant_id, platform_type, platform_user_id)
    exists = conn.execute(text(
        "SELECT 1 FROM pg_indexes WHERE indexname = 'idx_line_users_tenant_line_user_unique'"
    )).fetchone()
    if exists:
        op.execute('DROP INDEX "idx_line_users_tenant_line_user_unique"')
    op.execute(
        'CREATE UNIQUE INDEX "idx_bot_users_tenant_platform_unique" '
        'ON bot_users (tenant_id, platform_type, platform_user_id)'
    )

    # bot_groups：舊的 (line_group_id) → (tenant_id, platform_type, platform_group_id)
    exists = conn.execute(text(
        "SELECT 1 FROM pg_constraint WHERE conname = 'bot_groups_line_group_id_key'"
    )).fetchone()
    if exists:
        op.execute('ALTER TABLE bot_groups DROP CONSTRAINT "bot_groups_line_group_id_key"')
    op.execute(
        'CREATE UNIQUE INDEX "idx_bot_groups_tenant_platform_unique" '
        'ON bot_groups (tenant_id, platform_type, platform_group_id)'
    )

    # ---- 5. 新增 platform_type 查詢用索引 ----
    op.execute(
        'CREATE INDEX IF NOT EXISTS "idx_bot_users_platform_type" '
        'ON bot_users (platform_type)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "idx_bot_groups_platform_type" '
        'ON bot_groups (platform_type)'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "idx_bot_messages_platform_type" '
        'ON bot_messages (platform_type)'
    )


def downgrade() -> None:
    conn = op.get_bind()

    # ---- 5. 移除 platform_type 索引 ----
    op.execute('DROP INDEX IF EXISTS "idx_bot_messages_platform_type"')
    op.execute('DROP INDEX IF EXISTS "idx_bot_groups_platform_type"')
    op.execute('DROP INDEX IF EXISTS "idx_bot_users_platform_type"')

    # ---- 4. 還原唯一索引 ----
    op.execute('DROP INDEX IF EXISTS "idx_bot_groups_tenant_platform_unique"')
    op.execute(
        'ALTER TABLE bot_groups ADD CONSTRAINT "bot_groups_line_group_id_key" '
        'UNIQUE (platform_group_id)'  # 注意：此處仍使用新欄位名，欄位將在最後一步還原
    )

    op.execute('DROP INDEX IF EXISTS "idx_bot_users_tenant_platform_unique"')
    op.execute(
        'CREATE UNIQUE INDEX "idx_line_users_tenant_line_user_unique" '
        'ON bot_users (tenant_id, platform_user_id)'  # 注意：此處仍使用新欄位名，欄位將在最後一步還原
    )

    # ---- 3. 還原約束名稱 ----
    for table, old_name, new_name in CONSTRAINT_RENAMES:
        exists = conn.execute(text(
            "SELECT 1 FROM pg_constraint WHERE conname = :name"
        ), {"name": new_name}).fetchone()
        if exists:
            op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT "{new_name}" TO "{old_name}"')

    # ---- 2. 還原索引名稱 ----
    for old_name, new_name in INDEX_RENAMES:
        exists = conn.execute(text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :name"
        ), {"name": new_name}).fetchone()
        if exists:
            op.execute(f'ALTER INDEX "{new_name}" RENAME TO "{old_name}"')

    # ---- 1. 還原欄位名稱 ----
    for table, old_col, new_col in COLUMN_RENAMES:
        op.execute(f'ALTER TABLE {table} RENAME COLUMN "{new_col}" TO "{old_col}"')
