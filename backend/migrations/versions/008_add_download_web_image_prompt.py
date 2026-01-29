"""新增 download_web_image 工具說明到 prompt

Revision ID: 008
Revises: 007
Create Date: 2026-01-30
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

# 插入到個人 prompt 的【AI 文件/簡報生成】前
PERSONAL_NEW_SECTION = """【網路圖片下載與傳送】
- download_web_image: 下載網路圖片並傳送給用戶
  · url: 圖片的完整 URL（支援 jpg、jpeg、png、gif、webp）
  · 用於將 WebSearch/WebFetch 找到的參考圖片傳送給用戶
  · 建議不超過 4 張
  · 回傳 [FILE_MESSAGE:...] 標記，原封不動包含在回覆中即可

【網路圖片使用情境】
1. 用戶說「找貓咪的參考圖片」
   → 先用 WebSearch 搜尋相關圖片
   → 從搜尋結果中找到圖片 URL
   → 用 download_web_image(url="https://...jpg") 下載並傳送
2. 用戶說「找一些裝潢風格的照片給我看」
   → WebSearch 搜尋，找到圖片 URL
   → 多次呼叫 download_web_image 傳送（建議 2-4 張）

"""

PERSONAL_INSERT_BEFORE = "【AI 文件/簡報生成】"

# 群組 prompt 工具摘要區 - 插入到 convert_pdf_to_images 前
GROUP_NEW_TOOL = """- download_web_image: 下載網路圖片並傳送（用 WebSearch 找到圖片 URL 後呼叫，建議不超過 4 張）
"""

GROUP_INSERT_BEFORE = "- convert_pdf_to_images"


def upgrade() -> None:
    """新增 download_web_image 工具說明"""
    # 個人 prompt
    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '{PERSONAL_INSERT_BEFORE}',
            '{PERSONAL_NEW_SECTION}{PERSONAL_INSERT_BEFORE}'
        )
        WHERE name = 'linebot-personal';
    """)

    # 群組 prompt
    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '{GROUP_INSERT_BEFORE}',
            '{GROUP_NEW_TOOL}{GROUP_INSERT_BEFORE}'
        )
        WHERE name = 'linebot-group';
    """)


def downgrade() -> None:
    """移除 download_web_image 工具說明"""
    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '{PERSONAL_NEW_SECTION}',
            ''
        )
        WHERE name = 'linebot-personal';
    """)

    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '{GROUP_NEW_TOOL}',
            ''
        )
        WHERE name = 'linebot-group';
    """)
