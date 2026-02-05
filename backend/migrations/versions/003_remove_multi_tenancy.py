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

    # 刪除其他租戶的資料（按外鍵依賴順序）
    tables_with_tenant_id = [
        'bot_files',
        'bot_messages',
        'bot_binding_codes',
        'bot_group_memories',
        'bot_user_memories',
        'bot_groups',
        'bot_users',
        'ai_chats',
        'ai_prompts',
        'ai_agents',
        'public_share_links',
        'password_reset_tokens',
        'users',
    ]

    for table in tables_with_tenant_id:
        try:
            connection.execute(sa.text(f"""
                DELETE FROM {table} WHERE tenant_id != :tid
            """), {'tid': CHINGTECH_TENANT_ID})
        except Exception as e:
            # 某些表可能沒有 tenant_id 欄位，跳過
            print(f"Skipping {table}: {e}")

    # 分區表需要特殊處理
    try:
        connection.execute(sa.text("""
            DELETE FROM ai_logs WHERE tenant_id != :tid
        """), {'tid': CHINGTECH_TENANT_ID})
    except Exception:
        pass

    try:
        connection.execute(sa.text("""
            DELETE FROM messages WHERE tenant_id != :tid
        """), {'tid': CHINGTECH_TENANT_ID})
    except Exception:
        pass

    try:
        connection.execute(sa.text("""
            DELETE FROM login_records WHERE tenant_id != :tid
        """), {'tid': CHINGTECH_TENANT_ID})
    except Exception:
        pass

    # ============================================================
    # Phase 2: 新增 bot_settings 表
    # ============================================================

    op.create_table(
        'bot_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('platform', sa.String(20), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('platform', 'key', name='uq_bot_settings_platform_key')
    )

    # ============================================================
    # Phase 3: 更新 users.role 欄位值
    # ============================================================

    # platform_admin -> admin
    connection.execute(sa.text("""
        UPDATE users SET role = 'admin' WHERE role = 'platform_admin'
    """))

    # tenant_admin -> admin
    connection.execute(sa.text("""
        UPDATE users SET role = 'admin' WHERE role = 'tenant_admin'
    """))

    # ============================================================
    # Phase 4: 移除 tenant_id 外鍵約束
    # ============================================================

    fk_constraints = [
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
    ]

    for table, constraint in fk_constraints:
        try:
            op.drop_constraint(constraint, table, type_='foreignkey')
        except Exception as e:
            print(f"Could not drop FK {constraint}: {e}")

    # ============================================================
    # Phase 5: 刪除包含 tenant_id 的索引
    # ============================================================

    indexes_to_drop = [
        ('users', 'idx_users_tenant_id'),
        ('users', 'idx_users_tenant_username'),
        ('users', 'idx_users_tenant_email'),
        ('ai_agents', 'idx_ai_agents_tenant_id'),
        ('ai_agents', 'ai_agents_name_tenant_id_key'),
        ('ai_chats', 'idx_ai_chats_tenant_id'),
        ('ai_chats', 'idx_ai_chats_tenant_user'),
        ('ai_prompts', 'idx_ai_prompts_tenant_id'),
        ('ai_prompts', 'ai_prompts_name_tenant_id_key'),
        ('bot_groups', 'idx_bot_groups_tenant_id'),
        ('bot_groups', 'idx_bot_groups_tenant_platform_unique'),
        ('bot_users', 'idx_bot_users_tenant_id'),
        ('bot_users', 'idx_bot_users_tenant_platform_unique'),
        ('bot_users', 'idx_bot_users_tenant_platform'),
        ('bot_messages', 'idx_bot_messages_tenant_id'),
        ('bot_messages', 'idx_bot_messages_tenant_group'),
        ('bot_files', 'idx_bot_files_tenant_id'),
        ('bot_binding_codes', 'idx_bot_binding_codes_tenant_id'),
        ('public_share_links', 'idx_public_share_links_tenant_id'),
    ]

    for table, idx in indexes_to_drop:
        try:
            op.drop_index(idx, table_name=table)
        except Exception as e:
            print(f"Could not drop index {idx}: {e}")

    # ============================================================
    # Phase 6: 移除 tenant_id 欄位
    # ============================================================

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
            op.drop_column(table, 'tenant_id')
        except Exception as e:
            print(f"Could not drop tenant_id from {table}: {e}")

    # ============================================================
    # Phase 7: 重建必要的索引（不含 tenant_id）
    # ============================================================

    op.create_index('idx_ai_agents_name', 'ai_agents', ['name'], unique=True)
    op.create_index('idx_ai_prompts_name', 'ai_prompts', ['name'], unique=True)
    op.create_index('idx_bot_groups_platform_unique', 'bot_groups', ['platform_type', 'platform_group_id'], unique=True)
    op.create_index('idx_bot_users_platform_unique', 'bot_users', ['platform_type', 'platform_user_id'], unique=True)
    op.create_index('idx_bot_messages_group', 'bot_messages', ['bot_group_id', 'created_at'])
    op.create_index('idx_users_username', 'users', ['username'], unique=True)

    # ============================================================
    # Phase 8: 刪除 tenant_admins 表
    # ============================================================

    op.drop_table('tenant_admins')

    # ============================================================
    # Phase 9: 刪除 tenants 表
    # ============================================================

    op.drop_table('tenants')

    # ============================================================
    # Phase 10: 處理分區表（ai_logs, messages, login_records）
    # 分區表的 tenant_id 欄位保留，但不再使用
    # 因為重建分區表太複雜，這裡只刪除相關索引
    # ============================================================

    # 刪除主表的 tenant_id 索引
    partition_indexes = [
        ('ai_logs', 'idx_ai_logs_tenant_id'),
        ('ai_logs', 'idx_ai_logs_tenant_created'),
        ('messages', 'idx_messages_tenant_id'),
        ('messages', 'idx_messages_tenant_created'),
        ('login_records', 'idx_login_records_tenant_id'),
    ]

    for table, idx in partition_indexes:
        try:
            op.drop_index(idx, table_name=table)
        except Exception as e:
            print(f"Could not drop partition index {idx}: {e}")


def downgrade() -> None:
    # 這是破壞性變更，不支援 downgrade
    raise NotImplementedError("這是破壞性 migration，無法 downgrade。請從備份還原。")
