"""更新 Line Bot prompts 加入簡報生成工具說明

Revision ID: 040
Revises: 039
Create Date: 2026-01-22
"""

from alembic import op

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None

# 簡報生成工具說明（會附加到現有 prompt）
PRESENTATION_TOOLS_SECTION = """
【簡報生成】
- generate_presentation: 生成 PowerPoint 簡報
  · topic: 簡報主題（方式一必填）
  · num_slides: 頁數，預設 5（範圍 2-20）
  · style: 預設風格，可選：
    - professional（專業）：客戶提案、正式報告
    - casual（休閒）：內部分享、教育訓練
    - creative（創意）：創意提案、品牌展示
    - minimal（極簡）：技術文件、學術報告
    - dark（深色）：投影展示、晚間活動
    - tech（科技）：科技新創、產品發布
    - nature（自然）：環保、健康主題
    - warm（溫暖）：激勵演講、活動推廣
    - elegant（優雅）：奢華品牌、高端提案
  · include_images: 是否配圖（預設 true）
  · image_source: pexels（圖庫，快速）/ huggingface / nanobanana（AI 生成）
  · outline_json: 直接傳入大綱 JSON（跳過 AI 生成）
  · design_json: 傳入設計規格（覆蓋 style，見下方說明）

【簡報生成流程】
1. 簡單生成：用戶說「做一份 AI 簡報」
   → generate_presentation(topic="AI 在製造業的應用", style="tech")
   → 用 create_share_link 產生連結回覆

2. 從知識庫生成：用戶說「根據 kb-015 做簡報」
   → get_knowledge_item 取得內容
   → 根據內容組織 outline_json
   → generate_presentation(outline_json=...)

3. 客製化設計：用戶說「做一份給客戶的專業簡報，要有底線裝飾」
   → 你可以自己設計 design_json，或請系統呼叫設計師 AI
   → generate_presentation(design_json=...)

【design_json 結構】（進階用法）
當用戶有特殊視覺需求時，可傳入 design_json：
{
  "design": {
    "colors": {
      "background": "#F7FAFC",
      "title": "#03256C",
      "subtitle": "#1768AC",
      "text": "#2D3748",
      "bullet": "#1768AC",
      "accent": "#1768AC"
    },
    "typography": {
      "title_font": "Noto Sans TC",
      "title_size": 44,
      "title_bold": true,
      "body_font": "Noto Sans TC",
      "body_size": 20
    },
    "layout": {
      "title_align": "left",
      "image_position": "right",
      "image_size": "medium"
    },
    "decorations": {
      "title_underline": true,
      "title_underline_color": "#1768AC",
      "accent_bar_left": false,
      "page_number": true
    }
  },
  "slides": [
    {"type": "title", "title": "標題", "subtitle": "副標題"},
    {"type": "content", "title": "第一章", "content": ["重點1", "重點2"], "image_keyword": "technology"}
  ]
}

【設計建議】
- 客戶提案：淺色背景 + 標題底線 + 頁碼
- 內部分享：輕鬆配色，可省略裝飾
- 投影展示：深色背景 + 大字體
- 科技主題：深空藍 + 青紫色系 + 側邊裝飾條
"""


def upgrade() -> None:
    # 更新 linebot-personal prompt，附加簡報工具說明
    op.execute(
        f"""
        UPDATE ai_prompts
        SET content = content || $section${PRESENTATION_TOOLS_SECTION}$section$,
            updated_at = NOW()
        WHERE name = 'linebot-personal'
        """
    )

    # 更新 linebot-group prompt，附加簡報工具說明
    op.execute(
        f"""
        UPDATE ai_prompts
        SET content = content || $section${PRESENTATION_TOOLS_SECTION}$section$,
            updated_at = NOW()
        WHERE name = 'linebot-group'
        """
    )


def downgrade() -> None:
    # 移除附加的簡報工具說明（從最後一個 【簡報生成】 開始刪除）
    op.execute(
        """
        UPDATE ai_prompts
        SET content = SUBSTRING(content FROM 1 FOR POSITION('【簡報生成】' IN content) - 1),
            updated_at = NOW()
        WHERE name = 'linebot-personal'
          AND content LIKE '%【簡報生成】%'
        """
    )

    op.execute(
        """
        UPDATE ai_prompts
        SET content = SUBSTRING(content FROM 1 FOR POSITION('【簡報生成】' IN content) - 1),
            updated_at = NOW()
        WHERE name = 'linebot-group'
          AND content LIKE '%【簡報生成】%'
        """
    )
