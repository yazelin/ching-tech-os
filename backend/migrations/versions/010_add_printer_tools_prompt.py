"""新增列印工具說明到 AI Agent prompt

Revision ID: 010
Revises: 009
Create Date: 2026-02-02
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None

# 在「文件/簡報回覆格式」之前插入列印工具說明
ANCHOR_TEXT = "【文件/簡報回覆格式】"

PRINTER_SECTION = """【列印功能】
列印分兩步驟，先轉換路徑再列印：

步驟 1 - 準備檔案：
- prepare_print_file: 將虛擬路徑轉換為絕對路徑，Office 文件自動轉 PDF
  · file_path: 檔案路徑（必填，虛擬路徑如 ctos://... 或絕對路徑）
  · ctos_tenant_id: 租戶 ID（必傳，從【對話識別】取得）
  · 回傳可列印的絕對路徑

步驟 2 - 實際列印（printer-mcp 工具）：
- mcp__printer__print_file: 將檔案送至印表機
  · file_path: 步驟 1 回傳的絕對路徑（必填）
  · printer: 印表機名稱（可選）
  · copies: 份數（可選，預設 1）
  · page_size: 紙張大小（可選，A4/A3/Letter 等）
  · orientation: 方向（可選，portrait/landscape）
- mcp__printer__list_printers: 查詢可用印表機
- mcp__printer__printer_status: 查詢印表機狀態

⚠️ 重要：虛擬路徑（ctos://、shared://）必須先經過 prepare_print_file 轉換！

【列印使用情境】
- 用戶說「把報告印出來」→ 先找到檔案 → prepare_print_file → mcp__printer__print_file
- 用戶說「印 3 份 A3」→ prepare_print_file → mcp__printer__print_file(copies=3, page_size="A3")
- 用戶說「有哪些印表機」→ mcp__printer__list_printers

"""


def _insert_before(name: str, anchor: str, new_text: str) -> None:
    """在指定錨點文字之前插入新內容"""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE ai_prompts SET content = REPLACE(content, :anchor, :new || :anchor) WHERE name = :name"
        ),
        {"anchor": anchor, "new": new_text, "name": name},
    )


def _remove_section(name: str, text: str) -> None:
    """移除指定內容"""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE ai_prompts SET content = REPLACE(content, :text, '') WHERE name = :name"
        ),
        {"text": text, "name": name},
    )


def upgrade() -> None:
    """新增列印工具說明"""
    _insert_before("linebot-personal", ANCHOR_TEXT, PRINTER_SECTION)


def downgrade() -> None:
    """移除列印工具說明"""
    _remove_section("linebot-personal", PRINTER_SECTION)
