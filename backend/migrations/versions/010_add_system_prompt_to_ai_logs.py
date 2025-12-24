"""為 ai_logs 添加 system_prompt 欄位

Revision ID: 010
Revises: 009
Create Date: 2024-01-01
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加 system_prompt 欄位到 ai_logs 表"""
    # 為 ai_logs 添加 system_prompt 欄位（記錄實際使用的 system prompt 內容）
    op.add_column(
        "ai_logs",
        sa.Column("system_prompt", sa.Text(), nullable=True, comment="實際使用的 system prompt 內容"),
    )


def downgrade() -> None:
    """移除 system_prompt 欄位"""
    op.drop_column("ai_logs", "system_prompt")
