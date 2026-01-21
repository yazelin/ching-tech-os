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
    # 先確認沒有 NULL 值
    for table in TABLES_REQUIRE_NOT_NULL:
        # 如果有 NULL 值，這個 migration 會失敗，這是預期行為
        # 表示需要先執行資料遷移
        pass

    # 設定 NOT NULL 約束
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
