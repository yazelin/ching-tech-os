"""更新圖片生成 prompt，新增模型資訊說明

Revision ID: 004
Revises: 003
Create Date: 2026-01-28
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


# 要插入的新區塊內容
NEW_SECTION = """
【圖片生成模型資訊】
nanobanana 回應會包含模型資訊，請根據以下欄位告知用戶：
- modelUsed: 實際使用的模型（gemini-3-pro-image-preview 或 gemini-2.5-flash-image）
- usedFallback: 是否使用了備用模型（true/false）
- primaryModel: 原本預設的模型
- fallbackReason: 切換備用模型的原因（例如：timeout after 60s、API 503: overloaded）

回覆時的說明方式：
- gemini-3-pro-image-preview（usedFallback=false）→ 不用特別說明（預設高品質模型）
- gemini-2.5-flash-image（usedFallback=true）→ 在回覆中說明原因，例如：
  · 若 fallbackReason 包含 "timeout" → 「（Pro 模型超時，改用快速模式）」
  · 若 fallbackReason 包含 "overloaded" 或 "503" → 「（Pro 模型忙碌中，改用快速模式）」
  · 其他原因 → 「（快速模式）」
- 若系統 fallback 到 FLUX → 會自動加上「（使用備用服務）」

範例回覆：
- Pro 模型成功：「圖片畫好了！👇」
- Pro 超時改用 Flash：「圖片畫好了！（Pro 模型超時，改用快速模式）👇」
- Pro 忙碌改用 Flash：「圖片畫好了！（Pro 模型忙碌中，改用快速模式）👇」
"""

# 插入位置的標記
INSERT_BEFORE = "【AI 文件/簡報生成】"


def upgrade() -> None:
    """新增【圖片生成模型資訊】區塊到 linebot-personal prompt"""
    # 使用 SQL 進行字串替換
    # 在【圖片發送流程】區塊後、【AI 文件/簡報生成】區塊前插入新區塊
    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '{INSERT_BEFORE}',
            '{NEW_SECTION}
{INSERT_BEFORE}'
        )
        WHERE name IN ('linebot-personal', 'linebot-group');
    """)


def downgrade() -> None:
    """移除【圖片生成模型資訊】區塊"""
    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '{NEW_SECTION}
',
            ''
        )
        WHERE name IN ('linebot-personal', 'linebot-group');
    """)
