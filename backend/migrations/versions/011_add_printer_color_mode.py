"""新增 printer color_mode 參數說明

Revision ID: 011
Revises: 010
Create Date: 2026-02-02
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None

OLD_TEXT = "· orientation: 方向（可選，portrait/landscape）"
NEW_TEXT = "· orientation: 方向（可選，portrait/landscape）\n  · color_mode: 色彩模式（可選，gray/color，預設 gray。除非用戶要求彩色列印，否則一律用 gray）"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE ai_prompts SET content = REPLACE(content, :old, :new) WHERE name = :name"
        ),
        {"old": OLD_TEXT, "new": NEW_TEXT, "name": "linebot-personal"},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE ai_prompts SET content = REPLACE(content, :old, :new) WHERE name = :name"
        ),
        {"old": NEW_TEXT, "new": OLD_TEXT, "name": "linebot-personal"},
    )
