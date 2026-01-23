"""修正 ai_prompts 和 ai_agents 唯一約束為多租戶模式

原本的唯一約束只在 name 欄位，多租戶模式需要改為 (name, tenant_id) 組合唯一。

Revision ID: 056
Revises: 055
Create Date: 2025-01-20
"""

from alembic import op

# revision identifiers
revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === ai_prompts 表 ===
    # 移除舊的唯一約束
    op.drop_constraint("ai_prompts_name_key", "ai_prompts", type_="unique")

    # 建立新的組合唯一約束 (name, tenant_id)
    op.create_unique_constraint(
        "ai_prompts_name_tenant_id_key",
        "ai_prompts",
        ["name", "tenant_id"]
    )

    # === ai_agents 表 ===
    # 移除舊的唯一約束
    op.drop_constraint("ai_agents_name_key", "ai_agents", type_="unique")

    # 建立新的組合唯一約束 (name, tenant_id)
    op.create_unique_constraint(
        "ai_agents_name_tenant_id_key",
        "ai_agents",
        ["name", "tenant_id"]
    )


def downgrade() -> None:
    # === ai_agents 表 ===
    op.drop_constraint("ai_agents_name_tenant_id_key", "ai_agents", type_="unique")
    op.create_unique_constraint("ai_agents_name_key", "ai_agents", ["name"])

    # === ai_prompts 表 ===
    op.drop_constraint("ai_prompts_name_tenant_id_key", "ai_prompts", type_="unique")
    op.create_unique_constraint("ai_prompts_name_key", "ai_prompts", ["name"])
