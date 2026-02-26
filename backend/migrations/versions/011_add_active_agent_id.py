"""新增 bot_users 和 bot_groups 的 active_agent_id 欄位

用於 /agent 指令切換對話使用的 AI Agent。

Revision ID: 011
"""

from alembic import op
import sqlalchemy as sa


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # bot_users 新增 active_agent_id
    op.add_column(
        "bot_users",
        sa.Column(
            "active_agent_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_bot_users_active_agent_id",
        "bot_users",
        "ai_agents",
        ["active_agent_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # bot_groups 新增 active_agent_id
    op.add_column(
        "bot_groups",
        sa.Column(
            "active_agent_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_bot_groups_active_agent_id",
        "bot_groups",
        "ai_agents",
        ["active_agent_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_bot_groups_active_agent_id", "bot_groups", type_="foreignkey")
    op.drop_column("bot_groups", "active_agent_id")
    op.drop_constraint("fk_bot_users_active_agent_id", "bot_users", type_="foreignkey")
    op.drop_column("bot_users", "active_agent_id")
