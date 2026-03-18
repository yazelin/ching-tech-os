"""bot_groups 新增 voice_auto_trigger 欄位

群組語音訊息自動觸發 AI 開關（預設開啟）。
開啟時，群組中的語音訊息會自動觸發 AI 處理（無需 @機器人）；
關閉時，語音僅轉錄存入對話歷史，使用者需另外 @機器人才會觸發 AI。

Revision ID: 016
"""

from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bot_groups",
        sa.Column(
            "voice_auto_trigger",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("bot_groups", "voice_auto_trigger")
