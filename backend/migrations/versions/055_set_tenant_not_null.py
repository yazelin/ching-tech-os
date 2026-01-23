"""設定 tenant_id 欄位的 NOT NULL 約束

Revision ID: 055
Revises: 054
Create Date: 2026-01-20

此 migration 應在確認所有現有資料都已遷移到預設租戶後執行。
執行前請確認：
1. 所有 tenant_id IS NULL 的記錄都已更新
2. 應用程式已更新為在新增記錄時自動帶入 tenant_id

注意：
- ai_agents 和 ai_prompts 的 tenant_id 保持 nullable（NULL 表示全域）
- 分區表（ai_logs, messages, login_records）不支援外鍵，但仍設定 NOT NULL
"""

from alembic import op

# revision identifiers
revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None

# 需要設定 NOT NULL 的表（排除允許 NULL 的表）
TABLES_REQUIRE_NOT_NULL = [
    # users
    "users",
    # projects
    "projects",
    "project_members",
    "project_meetings",
    "project_milestones",
    "project_delivery_schedules",
    "project_links",
    "project_attachments",
    # ai（ai_agents 和 ai_prompts 允許 NULL）
    "ai_chats",
    "ai_logs",  # 分區表
    # line
    "line_groups",
    "line_users",
    "line_messages",
    "line_files",
    "line_binding_codes",
    # inventory
    "inventory_items",
    "inventory_transactions",
    "vendors",
    # misc
    "public_share_links",
    "messages",  # 分區表
    "login_records",  # 分區表
]


def upgrade() -> None:
    """設定 NOT NULL 約束前先驗證資料"""
    from alembic import context
    from sqlalchemy import text

    # 取得連線執行驗證
    connection = context.get_context().connection

    # 驗證每個表是否有未遷移的資料
    errors = []
    for table in TABLES_REQUIRE_NOT_NULL:
        result = connection.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NULL")
        )
        null_count = result.scalar()
        if null_count > 0:
            errors.append(f"  - {table}: {null_count} 筆資料的 tenant_id 為 NULL")

    if errors:
        error_msg = (
            "無法設定 NOT NULL 約束，以下資料表有未遷移的資料：\n"
            + "\n".join(errors)
            + "\n\n請先執行資料遷移腳本將這些記錄遷移到正確的租戶。"
        )
        raise Exception(error_msg)

    # 驗證通過，設定 NOT NULL 約束
    for table in TABLES_REQUIRE_NOT_NULL:
        op.alter_column(
            table,
            "tenant_id",
            nullable=False
        )


def downgrade() -> None:
    # 移除 NOT NULL 約束（還原為 nullable）
    for table in TABLES_REQUIRE_NOT_NULL:
        op.alter_column(
            table,
            "tenant_id",
            nullable=True
        )
