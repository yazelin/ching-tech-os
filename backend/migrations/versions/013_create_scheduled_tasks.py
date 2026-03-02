"""新增 scheduled_tasks 資料表

儲存動態排程定義，支援 Agent 執行和 Skill Script 呼叫兩種模式。
排程觸發由 APScheduler 管理，定義持久化到資料庫。

Revision ID: 013
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("trigger_type", sa.String(16), nullable=False),
        sa.Column("trigger_config", JSONB, nullable=False),
        sa.Column("executor_type", sa.String(16), nullable=False),
        sa.Column("executor_config", JSONB, nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", sa.Integer, nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_success", sa.Boolean, nullable=True),
        sa.Column("last_run_error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # FK 到 users 表
    op.create_foreign_key(
        "fk_scheduled_tasks_created_by",
        "scheduled_tasks",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    # 加速啟動時載入啟用排程
    op.create_index(
        "ix_scheduled_tasks_is_enabled",
        "scheduled_tasks",
        ["is_enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_scheduled_tasks_is_enabled", table_name="scheduled_tasks")
    op.drop_constraint(
        "fk_scheduled_tasks_created_by", "scheduled_tasks", type_="foreignkey"
    )
    op.drop_table("scheduled_tasks")
