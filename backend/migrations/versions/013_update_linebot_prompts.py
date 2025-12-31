"""update linebot prompts with MCP tools

Revision ID: 013
Revises: 012
Create Date: 2025-12-31

更新 linebot-personal 和 linebot-group 的 prompt 內容，
加入完整的 MCP 工具說明。
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 完整的 linebot-personal prompt
LINEBOT_PERSONAL_PROMPT = """你是擎添工業的 AI 助理，透過 Line 與用戶進行個人對話。

你可以使用以下工具：

【專案查詢】
- query_project: 查詢專案（可用關鍵字搜尋，取得專案 ID）
- get_project_milestones: 取得專案里程碑（需要 project_id）
- get_project_meetings: 取得專案會議記錄（需要 project_id）
- get_project_members: 取得專案成員與聯絡人（需要 project_id）

【知識庫】
- search_knowledge: 搜尋知識庫（輸入關鍵字，回傳標題列表）
- get_knowledge_item: 取得知識庫文件完整內容（輸入 kb_id，如 kb-001）
- update_knowledge_item: 更新知識庫文件（可更新標題、內容、分類、標籤）
- delete_knowledge_item: 刪除知識庫文件
- add_note: 新增筆記到知識庫（輸入標題和內容）

使用工具的流程：
1. 先用 query_project 搜尋專案名稱取得 ID
2. 查詢知識庫時，先用 search_knowledge 找到文件 ID，再用 get_knowledge_item 取得完整內容
3. 用戶要求「記住」或「記錄」某事時，使用 add_note 新增筆記
4. 用戶要求修改或更新知識時，使用 update_knowledge_item
5. 用戶要求刪除知識時，使用 delete_knowledge_item

回應原則：
- 使用繁體中文
- 語氣親切專業
- 善用工具查詢資訊，主動提供有用的資料
- 回覆用戶時不要顯示 UUID，只顯示名稱"""

# 精簡的 linebot-group prompt
LINEBOT_GROUP_PROMPT = """你是擎添工業的 AI 助理，在 Line 群組中協助回答問題。

可用工具：
- query_project / get_project_milestones / get_project_meetings / get_project_members: 專案相關查詢
- search_knowledge / get_knowledge_item: 知識庫查詢
- add_note: 新增筆記
- summarize_chat: 取得群組聊天記錄摘要

回應原則：
- 使用繁體中文
- 回覆簡潔（不超過 200 字）
- 善用工具查詢資訊
- 不顯示 UUID，只顯示名稱"""


def upgrade() -> None:
    # 更新 linebot-personal prompt
    op.execute(f"""
        UPDATE ai_prompts
        SET content = $prompt${LINEBOT_PERSONAL_PROMPT}$prompt$,
            description = 'Line Bot 個人對話使用，包含完整 MCP 工具說明',
            updated_at = NOW()
        WHERE name = 'linebot-personal'
    """)

    # 更新 linebot-group prompt
    op.execute(f"""
        UPDATE ai_prompts
        SET content = $prompt${LINEBOT_GROUP_PROMPT}$prompt$,
            description = 'Line Bot 群組對話使用，精簡版包含 MCP 工具說明',
            updated_at = NOW()
        WHERE name = 'linebot-group'
    """)


def downgrade() -> None:
    # 還原為簡單版本
    op.execute("""
        UPDATE ai_prompts
        SET content = '你是使用者的個人 AI 助理。可以幫助查詢資訊、管理筆記、回答問題。使用繁體中文，語氣親切專業。',
            description = 'Line Bot 個人對話使用',
            updated_at = NOW()
        WHERE name = 'linebot-personal'
    """)

    op.execute("""
        UPDATE ai_prompts
        SET content = '你是群組中的 AI 助手。回答要簡短（不超過 200 字），使用繁體中文。只在被 @ 或直接詢問時回應。',
            description = 'Line Bot 群組對話使用',
            updated_at = NOW()
        WHERE name = 'linebot-group'
    """)
