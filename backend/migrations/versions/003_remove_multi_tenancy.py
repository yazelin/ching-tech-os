"""移除多租戶架構

將系統從多租戶改為單一租戶模式：
1. 刪除非 chingtech 租戶的資料
2. 新增 bot_settings 表
3. 移除所有表的 tenant_id 欄位
4. 刪除 tenants 和 tenant_admins 表
5. 更新 users.role 欄位值

Revision ID: 003
Revises: 002
Create Date: 2025-02-05
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

# chingtech 租戶 UUID
CHINGTECH_TENANT_ID = 'fe530f72-f9f5-434c-ba0b-8bc2d6485ca3'


def upgrade() -> None:
    connection = op.get_bind()

    # ============================================================
    # Phase 1: 刪除非 chingtech 租戶的資料
    # ============================================================
    print("Phase 1: 刪除非 chingtech 租戶資料...")

    # 按外鍵依賴順序刪除（只列出有 tenant_id 的表）
    tables_with_tenant_id = [
        'bot_files',
        'bot_messages',
        'bot_binding_codes',
        'bot_groups',
        'bot_users',
        'ai_chats',
        'ai_prompts',
        'ai_agents',
        'public_share_links',
        'users',
    ]

    for table in tables_with_tenant_id:
        result = connection.execute(sa.text(f"""
            DELETE FROM {table} WHERE tenant_id != :tid
        """), {'tid': CHINGTECH_TENANT_ID})
        print(f"  {table}: deleted {result.rowcount} rows")

    # 分區表
    for table in ['ai_logs', 'messages', 'login_records']:
        try:
            result = connection.execute(sa.text(f"""
                DELETE FROM {table} WHERE tenant_id != :tid
            """), {'tid': CHINGTECH_TENANT_ID})
            print(f"  {table}: deleted {result.rowcount} rows")
        except Exception as e:
            print(f"  {table}: skipped ({e})")

    # ============================================================
    # Phase 2: 新增 bot_settings 表
    # ============================================================
    print("Phase 2: 新增 bot_settings 表...")

    connection.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS bot_settings (
            id SERIAL PRIMARY KEY,
            platform VARCHAR(20) NOT NULL,
            key VARCHAR(100) NOT NULL,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_bot_settings_platform_key UNIQUE (platform, key)
        )
    """))

    # ============================================================
    # Phase 3: 更新 users.role 欄位值
    # ============================================================
    print("Phase 3: 更新 users.role...")

    connection.execute(sa.text("""
        UPDATE users SET role = 'admin' WHERE role = 'platform_admin'
    """))
    connection.execute(sa.text("""
        UPDATE users SET role = 'admin' WHERE role = 'tenant_admin'
    """))

    # ============================================================
    # Phase 4: 移除外鍵約束和唯一約束
    # ============================================================
    print("Phase 4: 移除外鍵約束...")

    constraints_to_drop = [
        ('users', 'fk_users_tenant_id'),
        ('ai_agents', 'fk_ai_agents_tenant_id'),
        ('ai_chats', 'fk_ai_chats_tenant_id'),
        ('ai_prompts', 'fk_ai_prompts_tenant_id'),
        ('bot_groups', 'fk_bot_groups_tenant_id'),
        ('bot_users', 'fk_bot_users_tenant_id'),
        ('bot_messages', 'fk_bot_messages_tenant_id'),
        ('bot_files', 'fk_bot_files_tenant_id'),
        ('bot_binding_codes', 'fk_bot_binding_codes_tenant_id'),
        ('public_share_links', 'fk_public_share_links_tenant_id'),
        # 唯一約束（也是 constraint）
        ('ai_agents', 'ai_agents_name_tenant_id_key'),
        ('ai_prompts', 'ai_prompts_name_tenant_id_key'),
    ]

    for table, constraint in constraints_to_drop:
        try:
            connection.execute(sa.text(f"""
                ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}
            """))
            print(f"  Dropped constraint {constraint}")
        except Exception as e:
            print(f"  Could not drop constraint {constraint}: {e}")

    # ============================================================
    # Phase 5: 移除包含 tenant_id 的索引
    # ============================================================
    print("Phase 5: 移除 tenant_id 索引...")

    indexes_to_drop = [
        'idx_users_tenant_id',
        'idx_users_tenant_username',
        'idx_users_tenant_email',
        'idx_ai_agents_tenant_id',
        'idx_ai_chats_tenant_id',
        'idx_ai_chats_tenant_user',
        'idx_ai_prompts_tenant_id',
        'idx_bot_groups_tenant_id',
        'idx_bot_groups_tenant_platform_unique',
        'idx_bot_users_tenant_id',
        'idx_bot_users_tenant_platform_unique',
        'idx_bot_users_tenant_platform',
        'idx_bot_messages_tenant_id',
        'idx_bot_messages_tenant_group',
        'idx_bot_files_tenant_id',
        'idx_bot_binding_codes_tenant_id',
        'idx_public_share_links_tenant_id',
        # 分區表索引
        'idx_ai_logs_tenant_id',
        'idx_ai_logs_tenant_created',
        'idx_messages_tenant_id',
        'idx_messages_tenant_created',
        'idx_login_records_tenant_id',
    ]

    for idx in indexes_to_drop:
        try:
            connection.execute(sa.text(f"DROP INDEX IF EXISTS {idx}"))
            print(f"  Dropped index {idx}")
        except Exception as e:
            print(f"  Could not drop index {idx}: {e}")

    # ============================================================
    # Phase 6: 移除 tenant_id 欄位
    # ============================================================
    print("Phase 6: 移除 tenant_id 欄位...")

    tables_to_remove_tenant_id = [
        'users',
        'ai_agents',
        'ai_chats',
        'ai_prompts',
        'bot_groups',
        'bot_users',
        'bot_messages',
        'bot_files',
        'bot_binding_codes',
        'public_share_links',
    ]

    for table in tables_to_remove_tenant_id:
        try:
            connection.execute(sa.text(f"""
                ALTER TABLE {table} DROP COLUMN IF EXISTS tenant_id
            """))
            print(f"  Dropped tenant_id from {table}")
        except Exception as e:
            print(f"  Could not drop tenant_id from {table}: {e}")

    # ============================================================
    # Phase 7: 重建必要的索引（不含 tenant_id）
    # ============================================================
    print("Phase 7: 重建索引...")

    new_indexes = [
        ('idx_ai_agents_name', 'ai_agents', 'name', True),
        ('idx_ai_prompts_name', 'ai_prompts', 'name', True),
        ('idx_bot_groups_platform_unique', 'bot_groups', 'platform_type, platform_group_id', True),
        ('idx_bot_users_platform_unique', 'bot_users', 'platform_type, platform_user_id', True),
        ('idx_bot_messages_group', 'bot_messages', 'bot_group_id, created_at', False),
        ('idx_users_username', 'users', 'username', True),
    ]

    for idx_name, table, columns, is_unique in new_indexes:
        try:
            unique_str = "UNIQUE" if is_unique else ""
            connection.execute(sa.text(f"""
                CREATE {unique_str} INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})
            """))
            print(f"  Created index {idx_name}")
        except Exception as e:
            print(f"  Could not create index {idx_name}: {e}")

    # ============================================================
    # Phase 8: 刪除 tenant_admins 表
    # ============================================================
    print("Phase 8: 刪除 tenant_admins 表...")

    connection.execute(sa.text("DROP TABLE IF EXISTS tenant_admins"))

    # ============================================================
    # Phase 9: 刪除 tenants 表
    # ============================================================
    print("Phase 9: 刪除 tenants 表...")

    connection.execute(sa.text("DROP TABLE IF EXISTS tenants"))

    print("Migration 完成！")


def downgrade() -> None:
    # 這是破壞性變更，不支援 downgrade
    raise NotImplementedError("這是破壞性 migration，無法 downgrade。請從備份還原。")
