"""語音模組獨立化

- users 表新增 voice_settings JSONB 欄位
- bot_groups 表新增 voice_settings JSONB 欄位
- ai_agents 表新增 voice_settings JSONB 欄位（bot_agents 視圖同步）
- 更新 linebot-personal 和 linebot-group 的 prompt（新增語音工具說明）

Revision ID: 017
"""

from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


# 語音工具 prompt 片段
VOICE_TOOL_PROMPT = """
【語音回覆】
- text_to_speech: 將文字轉換為語音訊息回覆使用者
  · text: 要轉語音的文字（上限 500 字）
  · 使用者用語音訊息發問時（含 [語音訊息] 前綴），優先語音回覆
  · 可自訂語音內容（摘要、口語化），不一定要唸完整回覆
  · 回覆主要是圖片/檔案/程式碼時不需要語音
"""


def upgrade() -> None:
    # 1. users 表新增 voice_settings JSONB 欄位
    op.add_column(
        "users",
        sa.Column("voice_settings", sa.JSON(), nullable=True),
    )

    # 2. bot_groups 表新增 voice_settings JSONB 欄位
    op.add_column(
        "bot_groups",
        sa.Column("voice_settings", sa.JSON(), nullable=True),
    )

    # 3. ai_agents 表新增 voice_settings JSONB 欄位
    op.add_column(
        "ai_agents",
        sa.Column("voice_settings", sa.JSON(), nullable=True),
    )

    # 4. 更新 linebot-personal prompt（在【AI 文件/簡報生成】之前插入語音工具說明）
    op.execute(
        f"""
        UPDATE ai_prompts SET content = content || '{VOICE_TOOL_PROMPT}'
        WHERE id = (SELECT system_prompt_id FROM ai_agents WHERE name = 'linebot-personal')
        AND content NOT LIKE '%text_to_speech%'
        """
    )

    # 5. 更新 linebot-group prompt
    op.execute(
        f"""
        UPDATE ai_prompts SET content = content || '{VOICE_TOOL_PROMPT}'
        WHERE id = (SELECT system_prompt_id FROM ai_agents WHERE name = 'linebot-group')
        AND content NOT LIKE '%text_to_speech%'
        """
    )


def downgrade() -> None:
    op.drop_column("ai_agents", "voice_settings")
    op.drop_column("bot_groups", "voice_settings")
    op.drop_column("users", "voice_settings")
