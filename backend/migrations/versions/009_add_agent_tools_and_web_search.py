"""add agent tools column and web search agent

Revision ID: 009
Revises: 008
Create Date: 2025-12-22

為 Agent 新增 tools 欄位，並建立網路搜尋 Agent
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 為 ai_agents 新增 tools 欄位（JSONB 陣列）
    op.execute("""
        ALTER TABLE ai_agents
        ADD COLUMN IF NOT EXISTS tools JSONB DEFAULT '[]'::jsonb
    """)
    op.execute("COMMENT ON COLUMN ai_agents.tools IS '允許使用的工具列表，如 [\"WebSearch\", \"WebFetch\"]'")

    # 新增網路搜尋 Prompt
    op.execute("""
        INSERT INTO ai_prompts (name, display_name, category, content, description)
        VALUES (
            'web-search',
            '網路搜尋助手',
            'task',
            '你是一個網路搜尋助手。你的任務是：

1. 根據使用者的查詢，使用 WebSearch 工具搜尋最新的相關資訊
2. 分析搜尋結果，篩選出最相關、最有價值的內容
3. 以清晰、結構化的方式總結搜尋結果

回應格式：
## 搜尋主題
[使用者查詢的主題]

## 搜尋結果摘要
[3-5 個重點摘要]

## 詳細內容
[針對每個重要結果的詳細說明]

## 資料來源
[列出參考的網站連結]

注意事項：
- 優先呈現最新的資訊
- 如果搜尋結果有矛盾，請指出不同來源的說法
- 對於時效性資訊，請標註資料的日期
- 使用繁體中文回應',
            '使用 WebSearch 工具搜尋網路資訊並總結回報'
        )
        ON CONFLICT (name) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            content = EXCLUDED.content,
            description = EXCLUDED.description,
            updated_at = NOW()
    """)

    # 新增網路搜尋 Agent
    op.execute("""
        INSERT INTO ai_agents (name, display_name, model, is_active, tools)
        SELECT
            'web-search',
            '網路搜尋',
            'claude-sonnet',
            true,
            '["WebSearch"]'::jsonb
        WHERE NOT EXISTS (SELECT 1 FROM ai_agents WHERE name = 'web-search')
    """)

    # 關聯 Agent 和 Prompt
    op.execute("""
        UPDATE ai_agents
        SET system_prompt_id = (SELECT id FROM ai_prompts WHERE name = 'web-search')
        WHERE name = 'web-search'
    """)


def downgrade() -> None:
    # 移除 Agent
    op.execute("DELETE FROM ai_agents WHERE name = 'web-search'")

    # 移除 Prompt
    op.execute("DELETE FROM ai_prompts WHERE name = 'web-search'")

    # 移除 tools 欄位
    op.execute("ALTER TABLE ai_agents DROP COLUMN IF EXISTS tools")
