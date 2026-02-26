"""為 bot-restricted Agent 的 settings 欄位寫入預設值

使用 JSONB merge（||）方式，已有的 key 不會被覆蓋。

Revision ID: 010
"""

import json

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None

# 預設值：與 linebot_agents.py DEFAULT_BOT_MODE_AGENTS 一致
_DEFAULT_SETTINGS = {
    "welcome_message": (
        "歡迎使用 CTOS Bot！\n\n"
        "我是 Ching Tech OS 的 AI 助手，可以幫你：\n"
        "• 回答問題和對話\n"
        "• 管理專案和筆記\n"
        "• 生成和編輯圖片\n\n"
        "首次使用請先綁定帳號：\n"
        "1. 登入 CTOS 系統\n"
        "2. 進入 Bot 管理頁面\n"
        "3. 點擊「綁定帳號」產生驗證碼\n"
        "4. 將 6 位數驗證碼發送給我\n\n"
        "輸入 /help 查看更多功能"
    ),
    "binding_prompt": "",
    "rate_limit_hourly_msg": "",
    "rate_limit_daily_msg": "",
    "disclaimer": "",
    "error_message": "",
}


def upgrade() -> None:
    defaults_json = json.dumps(_DEFAULT_SETTINGS)
    # 用預設值 || 現有值的方式 merge：
    # 已有的 key 會覆蓋預設值，未設定的 key 則使用預設值
    op.execute(
        f"""
        UPDATE ai_agents
        SET settings = '{defaults_json}'::jsonb || COALESCE(settings, '{{}}'::jsonb),
            updated_at = NOW()
        WHERE name = 'bot-restricted'
        """
    )


def downgrade() -> None:
    # 移除 6 個 settings key（恢復為空或原狀態）
    op.execute(
        """
        UPDATE ai_agents
        SET settings = settings
            - 'welcome_message'
            - 'binding_prompt'
            - 'rate_limit_hourly_msg'
            - 'rate_limit_daily_msg'
            - 'disclaimer'
            - 'error_message',
            updated_at = NOW()
        WHERE name = 'bot-restricted'
          AND settings IS NOT NULL
        """
    )
