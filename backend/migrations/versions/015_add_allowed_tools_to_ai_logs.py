"""為 ai_logs 添加 allowed_tools 欄位

Revision ID: 015
Revises: 014
Create Date: 2026-01-05
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加 allowed_tools 欄位到 ai_logs 表"""
    op.add_column(
        "ai_logs",
        sa.Column(
            "allowed_tools",
            sa.JSON(),
            nullable=True,
            comment="允許使用的工具列表",
        ),
    )


def downgrade() -> None:
    """移除 allowed_tools 欄位"""
    op.drop_column("ai_logs", "allowed_tools")
