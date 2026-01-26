"""更新 LineBot Agent Prompt 支援文件/簡報生成

新增工具說明：
- generate_presentation: 產生 MD2PPT 格式簡報
- generate_document: 產生 MD2DOC 格式文件

Revision ID: 003
Revises: 002
Create Date: 2025-01-26
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 從 linebot_agents.py 導入最新的 prompt
    from ching_tech_os.services.linebot_agents import (
        LINEBOT_PERSONAL_PROMPT,
        LINEBOT_GROUP_PROMPT,
        AGENT_LINEBOT_PERSONAL,
        AGENT_LINEBOT_GROUP,
    )

    # 更新 linebot-personal prompt
    op.execute(
        f"""
        UPDATE ai_prompts
        SET content = $prompt${LINEBOT_PERSONAL_PROMPT}$prompt$,
            updated_at = NOW()
        WHERE name = '{AGENT_LINEBOT_PERSONAL}'
        """
    )

    # 更新 linebot-group prompt
    op.execute(
        f"""
        UPDATE ai_prompts
        SET content = $prompt${LINEBOT_GROUP_PROMPT}$prompt$,
            updated_at = NOW()
        WHERE name = '{AGENT_LINEBOT_GROUP}'
        """
    )


def downgrade() -> None:
    # 降級時不做任何動作，因為無法還原到舊版本內容
    # 如果需要還原，可以手動修改 linebot_agents.py 並再次執行 migration
    pass
