"""新增 ERPNext 廠商/客戶查詢工具說明到 prompt

Revision ID: 014
Revises: 013
Create Date: 2026-02-03
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None

# 插入到個人 prompt 的【專案連結管理】前
PERSONAL_NEW_SECTION = """【廠商/客戶管理】（使用 ERPNext）
查詢廠商或客戶需使用 ERPNext MCP 工具：
- mcp__erpnext__list_documents: 查詢廠商/客戶列表
  · doctype: "Supplier"（廠商）或 "Customer"（客戶）
  · filters: 可用 name 模糊搜尋，如 '{"name": ["like", "%永心%"]}'
  · fields: ["name", "supplier_name", "supplier_group"] 或 ["name", "customer_name", "customer_group"]
- mcp__erpnext__get_document: 取得詳細資訊
  · doctype: "Supplier" 或 "Customer"
  · name: 廠商/客戶名稱

【廠商/客戶電話地址查詢】（重要）
ERPNext 的電話和地址存在獨立的 Address 表格，查詢詳細資料時必須額外查：
- mcp__erpnext__list_documents: 查詢關聯地址
  · doctype: "Address"
  · address_title 格式為「代碼 地址」，如「SF0009-2 地址」
  · 用廠商/客戶代碼（name 的前半部）查詢：'{"address_title": ["like", "%SF0009-2%"]}'
  · fields: ["address_title", "address_line1", "city", "pincode", "phone", "fax"]
  · 範例：查到「SF0009-2 - 永心企業社」後 → filters='{"address_title": ["like", "%SF0009-2%"]}'
- mcp__erpnext__list_documents: 查詢聯絡人
  · doctype: "Contact"
  · filters: '{"first_name": ["like", "%關鍵字%"]}'
  · fields: ["first_name", "phone", "mobile_no", "email_id"]

"""

PERSONAL_INSERT_BEFORE = "【專案連結管理】"

# 群組 prompt 工具摘要區 - 插入到 search_nas_files 前
GROUP_NEW_TOOL = """- mcp__erpnext__list_documents / mcp__erpnext__get_document: ERPNext 廠商/客戶查詢
  · doctype: "Supplier"（廠商）或 "Customer"（客戶）或 "Address"（地址/電話）
  · 查廠商/客戶：filters='{"name": ["like", "%關鍵字%"]}'
  · 查電話/地址：doctype="Address"，用代碼查 filters='{"address_title": ["like", "%SF0009-2%"]}'
  · 重要：address_title 格式是「代碼 地址」，用廠商/客戶代碼（如 SF0009-2）查詢，不是用名稱
"""

GROUP_INSERT_BEFORE = "- search_nas_files"


def upgrade() -> None:
    """新增 ERPNext 廠商/客戶查詢工具說明"""
    # 個人 prompt
    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '{PERSONAL_INSERT_BEFORE}',
            $erpnext${PERSONAL_NEW_SECTION}$erpnext$ || '{PERSONAL_INSERT_BEFORE}'
        )
        WHERE name = 'linebot-personal';
    """)

    # 群組 prompt
    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            '{GROUP_INSERT_BEFORE}',
            $erpnext${GROUP_NEW_TOOL}$erpnext$ || '{GROUP_INSERT_BEFORE}'
        )
        WHERE name = 'linebot-group';
    """)


def downgrade() -> None:
    """移除 ERPNext 廠商/客戶查詢工具說明"""
    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            $erpnext${PERSONAL_NEW_SECTION}$erpnext$,
            ''
        )
        WHERE name = 'linebot-personal';
    """)

    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            $erpnext${GROUP_NEW_TOOL}$erpnext$,
            ''
        )
        WHERE name = 'linebot-group';
    """)
