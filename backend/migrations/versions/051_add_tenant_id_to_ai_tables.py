"""為 AI 相關表新增 tenant_id 欄位

Revision ID: 051
Revises: 050
Create Date: 2026-01-20

影響表格：
- ai_agents（支援 NULL 表示全域 Agent）
- ai_chats
- ai_logs（分區表）
- ai_prompts（支援 NULL 表示全域 Prompt）
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "051"
down_revision = "050"
branch_labels = None
depends_on = None

# 預設租戶 UUID
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    # === ai_agents ===
    # tenant_id 為 NULL 表示全域 Agent，可被所有租戶使用
    op.add_column(
        "ai_agents",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,  # NULL = 全域
            comment="租戶 ID（NULL 表示全域 Agent）"
        )
    )
    op.create_foreign_key(
        "fk_ai_agents_tenant_id",
        "ai_agents",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE"
    )
    op.create_index("idx_ai_agents_tenant_id", "ai_agents", ["tenant_id"])

    # === ai_prompts ===
    # tenant_id 為 NULL 表示全域 Prompt，可被所有租戶使用
    op.add_column(
        "ai_prompts",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,  # NULL = 全域
            comment="租戶 ID（NULL 表示全域 Prompt）"
        )
    )
    op.create_foreign_key(
        "fk_ai_prompts_tenant_id",
        "ai_prompts",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE"
    )
    op.create_index("idx_ai_prompts_tenant_id", "ai_prompts", ["tenant_id"])

    # === ai_chats ===
    op.add_column(
        "ai_chats",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="租戶 ID"
        )
    )
    # 將現有 ai_chats 指派到預設租戶
    op.execute(f"""
        UPDATE ai_chats SET tenant_id = '{DEFAULT_TENANT_ID}'::uuid WHERE tenant_id IS NULL;
    """)
    op.create_foreign_key(
        "fk_ai_chats_tenant_id",
        "ai_chats",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE"
    )
    op.create_index("idx_ai_chats_tenant_id", "ai_chats", ["tenant_id"])
    op.create_index("idx_ai_chats_tenant_user", "ai_chats", ["tenant_id", "user_id"])

    # === ai_logs（分區表）===
    # 分區表需要對主表和所有分區同時操作
    # 新增欄位到分區表會自動傳播到所有分區
    op.add_column(
        "ai_logs",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="租戶 ID"
        )
    )

    # 更新所有現有分區的資料
    # 注意：直接更新主表會自動路由到對應分區
    op.execute(f"""
        UPDATE ai_logs SET tenant_id = '{DEFAULT_TENANT_ID}'::uuid WHERE tenant_id IS NULL;
    """)

    # 為分區表建立索引（會自動傳播到所有分區）
    op.create_index("idx_ai_logs_tenant_id", "ai_logs", ["tenant_id"])
    op.create_index("idx_ai_logs_tenant_created", "ai_logs", ["tenant_id", "created_at"])

    # 注意：分區表不支援外鍵約束，這是 PostgreSQL 的限制
    # 資料完整性將在應用層保證


def downgrade() -> None:
    # === ai_logs ===
    op.drop_index("idx_ai_logs_tenant_created", table_name="ai_logs")
    op.drop_index("idx_ai_logs_tenant_id", table_name="ai_logs")
    op.drop_column("ai_logs", "tenant_id")

    # === ai_chats ===
    op.drop_index("idx_ai_chats_tenant_user", table_name="ai_chats")
    op.drop_index("idx_ai_chats_tenant_id", table_name="ai_chats")
    op.drop_constraint("fk_ai_chats_tenant_id", "ai_chats", type_="foreignkey")
    op.drop_column("ai_chats", "tenant_id")

    # === ai_prompts ===
    op.drop_index("idx_ai_prompts_tenant_id", table_name="ai_prompts")
    op.drop_constraint("fk_ai_prompts_tenant_id", "ai_prompts", type_="foreignkey")
    op.drop_column("ai_prompts", "tenant_id")

    # === ai_agents ===
    op.drop_index("idx_ai_agents_tenant_id", table_name="ai_agents")
    op.drop_constraint("fk_ai_agents_tenant_id", "ai_agents", type_="foreignkey")
    op.drop_column("ai_agents", "tenant_id")
