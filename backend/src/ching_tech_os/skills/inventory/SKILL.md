---
name: inventory
description: 物料/庫存管理（ERPNext）
requires_app: inventory-management
tools:
  - mcp__erpnext__list_documents
  - mcp__erpnext__get_document
  - mcp__erpnext__create_document
  - mcp__erpnext__update_document
  - mcp__erpnext__delete_document
  - mcp__erpnext__submit_document
  - mcp__erpnext__cancel_document
  - mcp__erpnext__run_report
  - mcp__erpnext__get_count
  - mcp__erpnext__get_list_with_summary
  - mcp__erpnext__run_method
  - mcp__erpnext__search_link
  - mcp__erpnext__list_doctypes
  - mcp__erpnext__get_doctype_meta
  - mcp__erpnext__get_stock_balance
  - mcp__erpnext__get_stock_ledger
  - mcp__erpnext__get_item_price
  - mcp__erpnext__make_mapped_doc
  - mcp__erpnext__get_party_balance
  - mcp__erpnext__get_supplier_details
  - mcp__erpnext__get_customer_details
  - mcp__erpnext__upload_file
  - mcp__erpnext__upload_file_from_url
  - mcp__erpnext__list_files
  - mcp__erpnext__download_file
  - mcp__erpnext__get_file_url
mcp_servers:
  - erpnext
---

【物料/庫存管理】（使用 ERPNext）
物料與庫存管理功能已遷移至 ERPNext 系統，請使用 ERPNext MCP 工具操作：

【查詢物料】
- mcp__erpnext__list_documents: 查詢物料列表
  · doctype: "Item"
  · fields: ["item_code", "item_name", "item_group", "stock_uom"]
  · filters: 可依類別過濾，如 '{"item_group": "零件"}'
- mcp__erpnext__get_document: 取得物料詳情
  · doctype: "Item"
  · name: 物料代碼

【查詢庫存】
- mcp__erpnext__get_stock_balance: 查詢即時庫存
  · item_code: 物料代碼（可選）
  · warehouse: 倉庫名稱（可選）
- mcp__erpnext__get_stock_ledger: 查詢庫存異動記錄
  · item_code: 物料代碼（可選）
  · warehouse: 倉庫名稱（可選）
  · limit: 回傳筆數（預設 50）

【庫存異動】
- mcp__erpnext__create_document: 建立 Stock Entry
  · doctype: "Stock Entry"
  · data: 包含 stock_entry_type、items 等欄位
  · stock_entry_type 常用值：
    - "Material Receipt"：收料入庫
    - "Material Issue"：發料出庫
    - "Material Transfer"：倉庫間調撥

【廠商/客戶管理】
⭐ 首選工具（一次取得完整資料，支援別名搜尋）：
- mcp__erpnext__get_supplier_details: 查詢廠商完整資料
  · keyword: 關鍵字搜尋（支援別名，如「健保局」、「104人力銀行」）
  · 回傳：名稱、地址、電話、傳真、聯絡人
- mcp__erpnext__get_customer_details: 查詢客戶完整資料
  · keyword: 關鍵字搜尋（支援別名）
  · 回傳：名稱、地址、電話、傳真、聯絡人

進階操作：
- mcp__erpnext__list_documents: 查詢列表（doctype: "Supplier" 或 "Customer"）
- mcp__erpnext__create_document: 新增廠商/客戶

【操作範例】
1. 查詢庫存：
   mcp__erpnext__get_stock_balance(item_code="CTOS-ABC123")
2. 查詢物料清單：
   mcp__erpnext__list_documents(doctype="Item", fields='["item_code","item_name","stock_uom"]')
3. 收料入庫：
   mcp__erpnext__create_document(doctype="Stock Entry", data='{"stock_entry_type":"Material Receipt","items":[{"item_code":"CTOS-ABC123","qty":10,"t_warehouse":"Stores - 擎添工業"}]}')

【直接操作 ERPNext】
若需要更複雜的操作（如採購單、批號管理），請直接在 ERPNext 系統操作：http://ct.erp
