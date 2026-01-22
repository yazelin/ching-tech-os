"""更新簡報生成 prompt 為 Marp 版本

將 PowerPoint 相關的參數說明改為 Marp（HTML/PDF）版本。
移除 style、template、design_json、designer_request 參數，
改用 theme 參數（uncover, gaia, gaia-invert, default）。

Revision ID: 046
Revises: 045
Create Date: 2026-01-22
"""

from alembic import op

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None

# 舊的 PowerPoint 簡報生成說明
OLD_PRESENTATION_SECTION = """【簡報生成】
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
   · designer_request: 設計需求描述，系統自動呼叫 AI 設計師
   · template: 使用預設模板（快速、設計品質穩定），可選：
     - meeting: 公司內部會議（週報、月報、檢討報告）
     - product: 產品推廣（AGV、工業自動化、AI/CTOS）
     - pitch: 融資提案（商業計畫、投資人簡報）
     - auto: 根據主題自動選擇模板

【簡報生成流程】
1. 簡單生成（只給主題）：用戶說「做一份 AI 簡報」
   → generate_presentation(topic="AI 在製造業的應用", style="tech")
   → 用 create_share_link 產生連結回覆
   → ⚠️ 這個方式較慢（約 30-60 秒），因為要呼叫 AI 生成大綱

2. 從知識庫生成（推薦）：用戶說「根據 kb-015 做簡報」
   ⚠️ 重要：必須自己組織 outline_json，不要只傳 topic！

   步驟：
   a. 先用 get_knowledge_item(kb_id="kb-015") 取得知識庫內容
   b. 根據知識內容，自己組織 outline_json（JSON 字串格式）
   c. 呼叫 generate_presentation(outline_json="...", style="tech")
   d. 用 create_share_link 產生連結回覆

   outline_json 格式範例：
   {
     "title": "簡報標題",
     "slides": [
       {"type": "title", "title": "標題", "subtitle": "副標題"},
       {"type": "content", "title": "章節標題", "content": ["重點1", "重點2"], "image_keyword": "keyword"}
     ]
   }

   ❌ 錯誤做法：generate_presentation(topic="kb-015 的內容") ← 會觸發內部 AI 生成，非常慢！
   ✅ 正確做法：自己組織 outline_json 後傳入

3. 客製化設計：用戶有特殊視覺需求時（如「給客戶看的專業簡報」、「投影用要深色」）
   → 使用 designer_request 參數，系統會自動呼叫 AI 設計師生成視覺風格

   步驟：
   a. 先組織 outline_json（內容大綱）
   b. 根據用戶需求，描述設計要求
   c. 呼叫 generate_presentation(outline_json="...", designer_request="設計需求描述")
   d. 用 create_share_link 產生連結回覆

   designer_request 範例：
   - "給客戶的專業簡報，要有標題底線和頁碼"
   - "投影用的深色背景，大字體"
   - "科技風格，要有側邊裝飾條"

4. 使用模板（推薦，快速穩定）：適用於大部分簡報需求
   ⚠️ 重要：優先使用模板！模板設計品質穩定、生成速度快

   自動選擇指南（根據內容判斷）：
   - 會議、週報、月報、檢討、報告 → template="meeting"
   - 產品、推廣、AGV、自動化、AI、CTOS、機器人 → template="product"
   - 融資、投資、商業計畫、募資、pitch → template="pitch"
   - 不確定時 → template="auto"（系統根據主題自動選）

   範例：
   - 用戶說「做一份 CTOS 推廣簡報」→ generate_presentation(outline_json="...", template="product")
   - 用戶說「做週報簡報」→ generate_presentation(topic="...", template="meeting")
   - 用戶說「做融資提案」→ generate_presentation(outline_json="...", template="pitch")

   ✅ 模板優點：專業設計、品質穩定、速度快
   ❌ 不要用 designer_request，除非用戶明確要求自訂設計

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
- 科技主題：深空藍 + 青紫色系 + 側邊裝飾條"""

# 新的 Marp 簡報生成說明
NEW_PRESENTATION_SECTION = """【簡報生成】
- generate_presentation: 生成 HTML/PDF 簡報（使用 Marp）
  · topic: 簡報主題（方式一必填）
  · num_slides: 頁數，預設 5（範圍 2-20）
  · theme: Marp 主題風格，可選：
    - uncover（預設）：深色投影風格，深灰背景
    - gaia：暖色調，米黃背景
    - gaia-invert：專業藍，深藍背景
    - default：簡約白，白色背景
  · include_images: 是否配圖（預設 true）
  · image_source: pexels（圖庫，快速）/ huggingface / nanobanana（AI 生成）
  · outline_json: 直接傳入大綱 JSON（跳過 AI 生成）
  · output_format: 輸出格式，html（預設，瀏覽器直接看）或 pdf（可下載列印）

【簡報生成流程】
1. 簡單生成（只給主題）：用戶說「做一份 AI 簡報」
   → generate_presentation(topic="AI 在製造業的應用")
   → 用 create_share_link 產生連結回覆
   → ⚠️ 這個方式較慢（約 30-60 秒），因為要呼叫 AI 生成大綱

2. 從知識庫生成（推薦）：用戶說「根據 kb-015 做簡報」
   ⚠️ 重要：必須自己組織 outline_json，不要只傳 topic！

   步驟：
   a. 先用 get_knowledge_item(kb_id="kb-015") 取得知識庫內容
   b. 根據知識內容，自己組織 outline_json（JSON 字串格式）
   c. 呼叫 generate_presentation(outline_json="...")
   d. 用 create_share_link 產生連結回覆

   outline_json 格式範例：
   {
     "title": "簡報標題",
     "slides": [
       {"type": "title", "title": "標題", "subtitle": "副標題"},
       {"type": "content", "title": "章節標題", "content": ["重點1", "重點2"], "image_keyword": "keyword"}
     ]
   }

   ❌ 錯誤做法：generate_presentation(topic="kb-015 的內容") ← 會觸發內部 AI 生成，非常慢！
   ✅ 正確做法：自己組織 outline_json 後傳入

3. 指定主題風格：
   - 投影展示（深色背景）→ theme="uncover"（預設）
   - 專業提案（深藍背景）→ theme="gaia-invert"
   - 列印用（白色背景）→ theme="default"
   - 輕鬆場合（暖色調）→ theme="gaia"

   範例：
   - generate_presentation(outline_json="...", theme="gaia-invert")  # 專業藍
   - generate_presentation(outline_json="...", output_format="pdf")  # 產生 PDF"""


def upgrade() -> None:
    # 替換 linebot-personal 的簡報說明
    op.execute(
        f"""
        UPDATE ai_prompts
        SET content = REPLACE(content, $old${OLD_PRESENTATION_SECTION}$old$, $new${NEW_PRESENTATION_SECTION}$new$),
            updated_at = NOW()
        WHERE name = 'linebot-personal'
        """
    )

    # 替換 linebot-group 的簡報說明
    op.execute(
        f"""
        UPDATE ai_prompts
        SET content = REPLACE(content, $old${OLD_PRESENTATION_SECTION}$old$, $new${NEW_PRESENTATION_SECTION}$new$),
            updated_at = NOW()
        WHERE name = 'linebot-group'
        """
    )


def downgrade() -> None:
    # 還原為舊的 PowerPoint 說明
    op.execute(
        f"""
        UPDATE ai_prompts
        SET content = REPLACE(content, $new${NEW_PRESENTATION_SECTION}$new$, $old${OLD_PRESENTATION_SECTION}$old$),
            updated_at = NOW()
        WHERE name = 'linebot-personal'
        """
    )

    op.execute(
        f"""
        UPDATE ai_prompts
        SET content = REPLACE(content, $new${NEW_PRESENTATION_SECTION}$new$, $old${OLD_PRESENTATION_SECTION}$old$),
            updated_at = NOW()
        WHERE name = 'linebot-group'
        """
    )
