"""新增記憶管理工具說明到 linebot prompt

讓 linebot 能透過對話管理自訂記憶。

Revision ID: 045
Revises: 044
Create Date: 2026-01-22
"""

from alembic import op

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None

# 記憶管理工具說明區塊
MEMORY_TOOLS_SECTION = """

【記憶管理】
系統支援自訂記憶功能，記憶會在每次對話時自動套用。

MCP 工具：
· add_memory(content, title?, line_group_id?, line_user_id?): 新增記憶
  - content: 記憶內容（必填）
  - title: 標題（可選，若未提供系統會自動產生）
  - 使用 line_group_id（群組對話）或 line_user_id（個人對話）
· get_memories(line_group_id?, line_user_id?): 查詢記憶列表
· update_memory(memory_id, title?, content?, is_active?): 更新記憶
· delete_memory(memory_id): 刪除記憶

使用時機：
1. 用戶說「記住 XXX」或「以後 XXX」→ 使用 add_memory
   例：「記住列出專案進度時，客戶新增的項目要標記 ⭐客戶新增」
   → add_memory(content="列出專案進度時，客戶新增的項目要標記 ⭐客戶新增")

2. 用戶說「列出記憶」或「我設定了什麼」→ 使用 get_memories

3. 用戶說「修改記憶 XXX」或「把 XXX 改成 YYY」
   → 先用 get_memories 查詢，找到後用 update_memory 更新

4. 用戶說「忘記 XXX」或「不要再 XXX」
   → 先用 get_memories 查詢，找到後用 delete_memory 刪除

注意事項：
- 群組記憶適用於該群組的所有對話
- 個人記憶只適用於用戶的私人對話
- 記憶會自動加入到系統提示中，不需要特別處理
- 判斷新增或修改時，可以自動決定合適的標題
"""


def upgrade() -> None:
    # 在 prompt 末尾添加記憶管理說明
    # 使用字串串接方式，在 prompt 末尾（【簡報生成流程】之後）添加
    op.execute(
        """
        UPDATE ai_prompts
        SET content = content || $section$"""
        + MEMORY_TOOLS_SECTION
        + """$section$,
            updated_at = NOW()
        WHERE name IN ('linebot-personal', 'linebot-group')
        """
    )


def downgrade() -> None:
    # 移除記憶管理說明
    op.execute(
        """
        UPDATE ai_prompts
        SET content = REPLACE(content, $section$"""
        + MEMORY_TOOLS_SECTION
        + """$section$, ''),
            updated_at = NOW()
        WHERE name IN ('linebot-personal', 'linebot-group')
        """
    )
