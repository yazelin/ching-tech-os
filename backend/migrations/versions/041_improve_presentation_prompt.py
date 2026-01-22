"""改進簡報生成 prompt，明確指示從知識庫生成時必須自己組織 outline_json

問題：當用戶說「用 kb-015 做簡報」時，AI 沒有正確傳入 outline_json，
導致 generate_presentation 內部調用 Claude CLI 生成大綱（嵌套調用），
每次需要約 120 秒，多次重試導致超時。

解決：改進 prompt，提供詳細的 outline_json 格式範例和警告。

Revision ID: 041
Revises: 040
Create Date: 2026-01-22
"""

from alembic import op

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None

# 舊的簡報生成流程說明（要被替換）
OLD_SECTION = """【簡報生成流程】
1. 簡單生成：用戶說「做一份 AI 簡報」
   → generate_presentation(topic="AI 在製造業的應用", style="tech")
   → 用 create_share_link 產生連結回覆

2. 從知識庫生成：用戶說「根據 kb-015 做簡報」
   → get_knowledge_item 取得內容
   → 根據內容組織 outline_json
   → generate_presentation(outline_json=...)

3. 客製化設計：用戶說「做一份給客戶的專業簡報，要有底線裝飾」
   → 你可以自己設計 design_json，或請系統呼叫設計師 AI
   → generate_presentation(design_json=...)"""

# 新的簡報生成流程說明（更詳細）
NEW_SECTION = """【簡報生成流程】
1. 簡單生成（只給主題）：用戶說「做一份 AI 簡報」
   → generate_presentation(topic="AI 在製造業的應用", style="tech")
   → 用 create_share_link 產生連結回覆
   → ⚠️ 這個方式較慢（約 30-60 秒），因為要呼叫 AI 生成大綱

2. 從知識庫生成（推薦）：用戶說「根據 kb-015 做簡報」或「用知識庫做簡報」
   ⚠️ 重要：必須自己組織 outline_json，不要只傳 topic！

   步驟：
   a. 先用 get_knowledge_item(kb_id="kb-015") 取得知識庫內容
   b. 根據知識內容，自己組織 outline_json（JSON 字串格式）
   c. 呼叫 generate_presentation(outline_json="...", style="tech")
   d. 用 create_share_link 產生連結回覆

   outline_json 格式範例：
   {
     "title": "CTOS 系統介紹",
     "slides": [
       {"type": "title", "title": "CTOS 系統介紹", "subtitle": "擎添工業智慧助理"},
       {"type": "content", "title": "系統特色", "content": ["AI 驅動的專案管理", "知識庫整合", "Line Bot 對話介面"], "image_keyword": "AI technology"},
       {"type": "content", "title": "核心功能", "content": ["專案追蹤", "物料管理", "文件分享"], "image_keyword": "business management"},
       {"type": "content", "title": "適用場景", "content": ["製造業", "專案團隊", "跨部門協作"], "image_keyword": "manufacturing team"},
       {"type": "content", "title": "聯絡我們", "content": ["官網：xxx", "Email：xxx"], "image_keyword": "contact us"}
     ]
   }

   ❌ 錯誤做法：generate_presentation(topic="kb-015 的內容") ← 會觸發內部 AI 生成，非常慢！
   ✅ 正確做法：自己組織 outline_json 後傳入

3. 客製化設計：用戶說「做一份給客戶的專業簡報，要有底線裝飾」
   → 你可以自己設計 design_json，或請系統呼叫設計師 AI
   → generate_presentation(design_json=...)"""


def upgrade() -> None:
    # 替換 linebot-personal 的簡報生成流程說明
    op.execute(
        f"""
        UPDATE ai_prompts
        SET content = REPLACE(content, $old${OLD_SECTION}$old$, $new${NEW_SECTION}$new$),
            updated_at = NOW()
        WHERE name = 'linebot-personal'
        """
    )

    # 替換 linebot-group 的簡報生成流程說明
    op.execute(
        f"""
        UPDATE ai_prompts
        SET content = REPLACE(content, $old${OLD_SECTION}$old$, $new${NEW_SECTION}$new$),
            updated_at = NOW()
        WHERE name = 'linebot-group'
        """
    )


def downgrade() -> None:
    # 還原為舊的說明
    op.execute(
        f"""
        UPDATE ai_prompts
        SET content = REPLACE(content, $new${NEW_SECTION}$new$, $old${OLD_SECTION}$old$),
            updated_at = NOW()
        WHERE name = 'linebot-personal'
        """
    )

    op.execute(
        f"""
        UPDATE ai_prompts
        SET content = REPLACE(content, $new${NEW_SECTION}$new$, $old${OLD_SECTION}$old$),
            updated_at = NOW()
        WHERE name = 'linebot-group'
        """
    )
