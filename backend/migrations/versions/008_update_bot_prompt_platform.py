"""更新 Bot Agent Prompt，加入 Telegram 平台說明

原本 prompt 只提到 Line，導致 AI 透過 Telegram 回應時不知道自己也支援 Telegram。

Revision ID: 008
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '你是擎添工業的 AI 助理，透過 Line 與用戶進行個人對話。',
            '你是擎添工業的 AI 助理，透過 Line 或 Telegram 與用戶進行個人對話。'
        )
        WHERE name = 'linebot-personal'
    """)
    op.execute("""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '你是擎添工業的 AI 助理，在 Line 群組中協助回答問題。',
            '你是擎添工業的 AI 助理，在 Line 或 Telegram 群組中協助回答問題。'
        )
        WHERE name = 'linebot-group'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '你是擎添工業的 AI 助理，透過 Line 或 Telegram 與用戶進行個人對話。',
            '你是擎添工業的 AI 助理，透過 Line 與用戶進行個人對話。'
        )
        WHERE name = 'linebot-personal'
    """)
    op.execute("""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '你是擎添工業的 AI 助理，在 Line 或 Telegram 群組中協助回答問題。',
            '你是擎添工業的 AI 助理，在 Line 群組中協助回答問題。'
        )
        WHERE name = 'linebot-group'
    """)
