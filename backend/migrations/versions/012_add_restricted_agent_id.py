"""新增 bot_groups 和 bot_users 的 restricted_agent_id 欄位

用於 /agent restricted 指令，讓管理員設定未綁定用戶使用的 AI Agent。
與 active_agent_id 對稱：
- active_agent_id: 已綁定用戶的 Agent 偏好
- restricted_agent_id: 未綁定用戶（受限模式）的 Agent 偏好

NULL = 使用預設 bot-restricted Agent。

Revision ID: 012
"""

import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # bot_groups 新增 restricted_agent_id
    op.add_column(
        "bot_groups",
        sa.Column(
            "restricted_agent_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_bot_groups_restricted_agent_id",
        "bot_groups",
        "ai_agents",
        ["restricted_agent_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # bot_users 新增 restricted_agent_id
    op.add_column(
        "bot_users",
        sa.Column(
            "restricted_agent_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_bot_users_restricted_agent_id",
        "bot_users",
        "ai_agents",
        ["restricted_agent_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_bot_users_restricted_agent_id", "bot_users", type_="foreignkey"
    )
    op.drop_column("bot_users", "restricted_agent_id")
    op.drop_constraint(
        "fk_bot_groups_restricted_agent_id", "bot_groups", type_="foreignkey"
    )
    op.drop_column("bot_groups", "restricted_agent_id")
