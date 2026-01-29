"""新增 query_project_inventory 工具說明到 prompt

Revision ID: 006
Revises: 005
Create Date: 2026-01-29
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

# 新增的工具說明（插入到個人 prompt 的【訂購記錄管理】前）
PERSONAL_NEW_TOOL = """- query_project_inventory: 查詢專案物料進出貨狀態（哪些到貨、哪些沒到）
  · project_id 或 project_name: 專案識別（擇一提供）

"""

PERSONAL_INSERT_BEFORE = "【訂購記錄管理】"

# 群組 prompt 插入到 add_inventory_order 前
GROUP_NEW_TOOL = """- query_project_inventory: 查詢專案物料進出貨狀態（project_id 或 project_name 擇一）
"""

GROUP_INSERT_BEFORE = "- add_inventory_order"


def upgrade() -> None:
    """新增 query_project_inventory 工具說明"""
    # 個人 prompt
    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '{PERSONAL_INSERT_BEFORE}',
            '{PERSONAL_NEW_TOOL}{PERSONAL_INSERT_BEFORE}'
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
    """移除 query_project_inventory 工具說明"""
    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '{PERSONAL_NEW_TOOL}{PERSONAL_INSERT_BEFORE}',
            '{PERSONAL_INSERT_BEFORE}'
        )
        WHERE name = 'linebot-personal';
    """)

    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '{GROUP_NEW_TOOL}{GROUP_INSERT_BEFORE}',
            '{GROUP_INSERT_BEFORE}'
        )
        WHERE name = 'linebot-group';
    """)
