"""更新杰膚美 Agent：jfmskin-full 改用 skill script 架構

- jfmskin-full：更新 prompt 為診所內部助理語氣，移除舊 HIS query 工具
- jfmskin-edu：新增叫號查詢 script 提示

Revision ID: 015
"""

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None

# jfmskin-full 新 prompt（對內助理）
JFMSKIN_FULL_PROMPT = """\
你是杰膚美皮膚科的內部 AI 助理，服務對象為診所的醫護人員與行政人員。

你可以使用以下工具：

【HIS 系統查詢】（透過 run_skill_script 呼叫）
- 看診進度：run_skill_script(skill="clinic-info", script="queue_status")
  · 查詢各診間目前看到幾號、還有幾位等候
- 門診統計：run_skill_script(skill="his-integration", script="visit_stats", input='{"period":"this_month"}')
  · period: this_week / last_week / this_month / last_month / last_30d（預設）
  · doctor_name: 指定醫師（可選）
- 藥品消耗：run_skill_script(skill="his-integration", script="drug_usage", input='{"days":30}')
  · days: 查詢天數（預設 30）
  · drug_code: 藥品代碼（可選，查特定藥品）
  · start_date / end_date: 自訂日期範圍 YYYY-MM-DD（可選）
- 預約紀錄查詢：run_skill_script(skill="his-integration", script="appointment_list", input='{"days":7}')
  · days: 查詢天數（預設 7）
  · doctor_name: 指定醫師（可選）
  · date_str: 指定日期 YYYY-MM-DD（可選）
- 手動預約統計（查詢歷史紀錄）：run_skill_script(skill="his-integration", script="manual_booking_stats", input='{"days":30}')
  · days: 查詢天數（預設 30）

【衛教知識庫】
- search_knowledge: 搜尋知識庫
- get_knowledge_item: 取得知識庫文件完整內容
- search_nas_files: 搜尋 NAS 檔案（含衛教文件）
- read_document: 讀取文件內容

【醫師資訊參考】
柯人玄（院長）、周哲毅、程昭瑞、廖憶如、蕭伯舟、鄭日鈞、羅揚清、吳若薇、陳宥伶、馮寶慧、劉芳綺、吳明聰

【回應原則】
- 使用繁體中文
- 語氣簡潔直接，適合內部溝通
- 醫療資料僅供內部參考，不對外公開
- 病患個資僅顯示必要欄位，遵循最小權限原則
- 統計數據如有異常值需主動提醒
- 系統僅提供查詢功能，無法代為掛號、預約或修改 HIS 資料

格式規則（極重要，必須遵守）：
- 絕對禁止使用任何 Markdown 格式
- 禁止：### 標題、**粗體**、*斜體*、`程式碼`、[連結](url)、- 列表
- 只能使用純文字、emoji、全形標點符號
- 列表用「・」或數字編號
- 分隔用空行，不要用分隔線"""

# jfmskin-edu 叫號查詢追加段落
JFMSKIN_EDU_QUEUE_ADDITION = """

【看診進度查詢】
當病患詢問「看到幾號了」、「還要等多久」等問題時：
- 使用 run_skill_script(skill="clinic-info", script="queue_status") 查詢
- 回報各診間目前的看診進度
- 用親切的語氣告知等候狀況"""


def upgrade():
    conn = op.get_bind()

    # 1. 更新 jfmskin-full prompt
    conn.execute(
        __import__("sqlalchemy").text(
            """UPDATE ai_prompts SET content = :content, updated_at = now()
               WHERE id = (SELECT system_prompt_id FROM ai_agents WHERE name = 'jfmskin-full')"""
        ),
        {"content": JFMSKIN_FULL_PROMPT},
    )

    # 2. 更新 jfmskin-full tools、display_name、description
    conn.execute(
        __import__("sqlalchemy").text(
            """UPDATE ai_agents
               SET tools = :tools,
                   display_name = '杰膚美內部助理（CTHIS）',
                   description = '杰膚美診所內部 AI 助理，含 HIS 系統查詢',
                   updated_at = now()
               WHERE name = 'jfmskin-full'"""
        ),
        {"tools": '["search_knowledge", "search_nas_files", "read_document"]'},
    )

    # 3. 設定 jfmskin-full 為可切換（user_selectable）
    conn.execute(
        __import__("sqlalchemy").text(
            """UPDATE ai_agents
               SET settings = COALESCE(settings, '{}'::jsonb) || '{"user_selectable": "true"}'::jsonb,
                   updated_at = now()
               WHERE name = 'jfmskin-full'"""
        ),
    )

    # 4. 在 jfmskin-edu prompt 追加叫號查詢段落
    conn.execute(
        __import__("sqlalchemy").text(
            """UPDATE ai_prompts SET content = content || :addition, updated_at = now()
               WHERE id = (SELECT system_prompt_id FROM ai_agents WHERE name = 'jfmskin-edu')"""
        ),
        {"addition": JFMSKIN_EDU_QUEUE_ADDITION},
    )


def downgrade():
    pass
