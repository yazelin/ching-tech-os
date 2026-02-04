"""新增 get_supplier_details / get_customer_details 工具說明（支援別名搜尋）

Revision ID: 015
Revises: 014
Create Date: 2026-02-03
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None

# 舊的廠商/客戶工具說明（要被替換的）
OLD_GROUP_TOOL = """- mcp__erpnext__list_documents / mcp__erpnext__get_document: ERPNext 廠商/客戶查詢
  · doctype: "Supplier"（廠商）或 "Customer"（客戶）或 "Address"（地址/電話）
  · 查廠商/客戶：filters='{"name": ["like", "%關鍵字%"]}'
  · 查電話/地址：doctype="Address"，用代碼查 filters='{"address_title": ["like", "%SF0009-2%"]}'
  · 重要：address_title 格式是「代碼 地址」，用廠商/客戶代碼（如 SF0009-2）查詢，不是用名稱
"""

# 新的廠商/客戶工具說明（支援別名搜尋）
NEW_GROUP_TOOL = """- mcp__erpnext__get_supplier_details: 查詢廠商完整資料（⭐首選，支援別名）
  · keyword: 關鍵字搜尋（支援別名，如「健保局」、「104人力銀行」）
  · 回傳：名稱、地址、電話、傳真、聯絡人
- mcp__erpnext__get_customer_details: 查詢客戶完整資料（⭐首選，支援別名）
  · keyword: 關鍵字搜尋（支援別名）
  · 回傳：名稱、地址、電話、傳真、聯絡人
- mcp__erpnext__list_documents: 進階查詢（需更精細控制時使用）
  · doctype: "Supplier"/"Customer"/"Address"
"""

# 舊的個人 prompt 廠商/客戶區塊
OLD_PERSONAL_SECTION = """【廠商/客戶管理】（使用 ERPNext）
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

# 新的個人 prompt 廠商/客戶區塊
NEW_PERSONAL_SECTION = """【廠商/客戶管理】（使用 ERPNext）
⭐ 首選工具（一次取得完整資料，支援別名搜尋）：
- mcp__erpnext__get_supplier_details: 查詢廠商完整資料
  · keyword: 關鍵字搜尋（支援別名，如「健保局」、「104人力銀行」）
  · 回傳：名稱、地址、電話、傳真、聯絡人
- mcp__erpnext__get_customer_details: 查詢客戶完整資料
  · keyword: 關鍵字搜尋（支援別名）
  · 回傳：名稱、地址、電話、傳真、聯絡人

進階查詢（需要更精細控制時使用）：
- mcp__erpnext__list_documents: 查詢廠商/客戶列表
  · doctype: "Supplier"（廠商）或 "Customer"（客戶）
  · filters: 可用 name 模糊搜尋，如 '{"name": ["like", "%永心%"]}'
- mcp__erpnext__get_document: 取得單一文件詳細資訊

"""


def upgrade() -> None:
    """更新 prompt 加入 get_supplier_details / get_customer_details 工具"""
    # 更新群組 prompt
    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            $old${OLD_GROUP_TOOL}$old$,
            $new${NEW_GROUP_TOOL}$new$
        )
        WHERE name = 'linebot-group';
    """)

    # 更新個人 prompt
    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            $old${OLD_PERSONAL_SECTION}$old$,
            $new${NEW_PERSONAL_SECTION}$new$
        )
        WHERE name = 'linebot-personal';
    """)


def downgrade() -> None:
    """還原為舊版 prompt"""
    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            $new${NEW_GROUP_TOOL}$new$,
            $old${OLD_GROUP_TOOL}$old$
        )
        WHERE name = 'linebot-group';
    """)

    op.execute(f"""
        UPDATE ai_prompts
        SET content = REPLACE(
            content,
            $new${NEW_PERSONAL_SECTION}$new$,
            $old${OLD_PERSONAL_SECTION}$old$
        )
        WHERE name = 'linebot-personal';
    """)
