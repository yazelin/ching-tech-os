---
name: project
description: 專案管理（ERPNext）
allowed-tools: mcp__erpnext__list_documents mcp__erpnext__get_document mcp__erpnext__create_document
  mcp__erpnext__update_document mcp__erpnext__delete_document mcp__erpnext__submit_document
  mcp__erpnext__cancel_document mcp__erpnext__run_report mcp__erpnext__get_count mcp__erpnext__get_list_with_summary
  mcp__erpnext__run_method mcp__erpnext__search_link mcp__erpnext__list_doctypes mcp__erpnext__get_doctype_meta
  mcp__erpnext__make_mapped_doc mcp__erpnext__upload_file mcp__erpnext__upload_file_from_url
  mcp__erpnext__list_files mcp__erpnext__download_file mcp__erpnext__get_file_url
metadata:
  ctos:
    requires_app: project-management
    mcp_servers: erpnext
---

【專案管理】（使用 ERPNext）
專案管理功能已遷移至 ERPNext 系統，請使用 ERPNext MCP 工具操作：

【查詢專案】
- mcp__erpnext__list_documents: 查詢專案列表
  · doctype: "Project"
  · fields: ["name", "project_name", "status", "expected_start_date", "expected_end_date"]
  · filters: 可依狀態過濾，如 '{"status": "Open"}'
- mcp__erpnext__get_document: 取得專案詳情
  · doctype: "Project"
  · name: 專案名稱

【任務管理】（對應原本的里程碑）
- mcp__erpnext__list_documents: 查詢專案任務
  · doctype: "Task"
  · filters: '{"project": "專案名稱"}'
- mcp__erpnext__create_document: 新增任務
  · doctype: "Task"
  · data: {"subject": "任務名稱", "project": "專案名稱", "status": "Open"}

【專案操作範例】
1. 查詢所有進行中的專案：
   mcp__erpnext__list_documents(doctype="Project", filters='{"status":"Open"}')
2. 查詢特定專案的任務：
   mcp__erpnext__list_documents(doctype="Task", filters='{"project":"專案名稱"}')
3. 更新任務狀態為完成：
   mcp__erpnext__update_document(doctype="Task", name="TASK-00001", data='{"status":"Completed"}')

【直接操作 ERPNext】
若需要更複雜的操作，請直接在 ERPNext 系統操作：http://ct.erp
