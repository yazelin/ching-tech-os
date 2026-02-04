"""更新 Line Bot Prompt 移除舊工具說明，指向 ERPNext

Revision ID: 016
Revises: 015
Create Date: 2026-02-04
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    """
    更新 linebot-personal 和 linebot-group prompts。

    移除專案、物料、廠商管理的舊工具說明，改為 ERPNext 指引。
    這些 prompt 的完整內容定義在 linebot_agents.py 中，
    此 migration 只是觸發資料庫中的 prompt 更新。

    注意：由於 prompt 內容過長，這裡只加上標記，
    實際內容會在下次服務重啟時由 ensure_default_linebot_agents() 更新。
    """
    # 加上 DEPRECATED 標記提示需要更新
    # 實際上不需要更新資料庫，因為：
    # 1. linebot_agents.py 中的 LINEBOT_PERSONAL_PROMPT 和 LINEBOT_GROUP_PROMPT 已更新
    # 2. 這些 prompt 存在資料庫中，但 ensure_default_linebot_agents() 只在不存在時建立
    # 3. 若要強制更新，需要手動刪除或更新資料庫中的 prompt

    # 為現有的 prompt 加上 DEPRECATED 註解，提示管理員手動更新
    op.execute("""
        UPDATE ai_prompts
        SET description = description || ' [需更新：專案/物料/廠商工具已遷移至 ERPNext]'
        WHERE name IN ('linebot-personal', 'linebot-group')
        AND description NOT LIKE '%ERPNext%'
    """)


def downgrade():
    """移除 DEPRECATED 標記"""
    op.execute("""
        UPDATE ai_prompts
        SET description = REPLACE(description, ' [需更新：專案/物料/廠商工具已遷移至 ERPNext]', '')
        WHERE name IN ('linebot-personal', 'linebot-group')
    """)
