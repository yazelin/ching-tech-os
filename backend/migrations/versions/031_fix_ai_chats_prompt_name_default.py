"""修正 ai_chats.prompt_name 的欄位預設值

欄位預設值是 'default'，但 ai_agents 沒有叫 'default' 的 agent（seed 裡是
'web-chat-default'）。經 ChatCreate（Pydantic）建立的對話不受影響，因為
Pydantic 層的預設值已與 api/ai.py 的退回值對齊；這裡修的是繞過 Pydantic
直接寫入資料庫時會踩到的欄位層級預設值，一併把既有殘留資料改過來。

Revision ID: 031
"""

from alembic import op
import sqlalchemy as sa

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "ai_chats",
        "prompt_name",
        server_default="web-chat-default",
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE ai_chats SET prompt_name = 'web-chat-default' WHERE prompt_name = 'default'"
        )
    )


def downgrade() -> None:
    op.alter_column(
        "ai_chats",
        "prompt_name",
        server_default="default",
    )
