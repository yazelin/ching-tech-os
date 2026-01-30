"""更新 search_nas_files 工具說明：搜尋範圍擴展至線路圖

Revision ID: 009
Revises: 008
Create Date: 2026-01-30
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

# 舊文字（個人 prompt 和群組 prompt 中都有）
OLD_SECTION = "【NAS 專案檔案】\n- search_nas_files: 搜尋 NAS 共享檔案（用於搜尋專案資料夾中的檔案）"
NEW_SECTION = "【NAS 共用檔案】\n- search_nas_files: 搜尋 NAS 共享檔案（搜尋範圍包含：專案資料、線路圖）"

# 群組 prompt 的摘要區
OLD_GROUP_TOOL = "- search_nas_files: 搜尋 NAS 專案檔案（keywords 用逗號分隔，file_types 過濾類型）"
NEW_GROUP_TOOL = "- search_nas_files: 搜尋 NAS 共用檔案（專案資料+線路圖，keywords 用逗號分隔，file_types 過濾類型）"


def _replace_prompt(name: str, old_text: str, new_text: str) -> None:
    """使用參數化查詢安全地替換 prompt 內容"""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE ai_prompts SET content = REPLACE(content, :old, :new) WHERE name = :name"
        ),
        {"old": old_text, "new": new_text, "name": name},
    )


def upgrade() -> None:
    """更新 search_nas_files 工具說明"""
    # 個人 prompt
    _replace_prompt("linebot-personal", OLD_SECTION, NEW_SECTION)
    # 群組 prompt（詳細區段）
    _replace_prompt("linebot-group", OLD_SECTION, NEW_SECTION)
    # 群組 prompt（摘要區）
    _replace_prompt("linebot-group", OLD_GROUP_TOOL, NEW_GROUP_TOOL)


def downgrade() -> None:
    """還原 search_nas_files 工具說明"""
    _replace_prompt("linebot-personal", NEW_SECTION, OLD_SECTION)
    _replace_prompt("linebot-group", NEW_SECTION, OLD_SECTION)
    _replace_prompt("linebot-group", NEW_GROUP_TOOL, OLD_GROUP_TOOL)
