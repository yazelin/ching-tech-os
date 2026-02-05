## REMOVED Requirements

### Requirement: 專案查詢工具
**Reason**: 改用 ERPNext MCP 的 list_documents(doctype="Project")
**Migration**: AI Agent prompt 更新引導使用 ERPNext MCP

包含以下工具：
- query_project
- create_project
- update_project

### Requirement: 專案成員工具
**Reason**: 改用 ERPNext MCP 更新 Project.users 子表
**Migration**: 使用 update_document(doctype="Project") 更新 users

包含以下工具：
- add_project_member
- update_project_member
- get_project_members

### Requirement: 專案里程碑工具
**Reason**: 改用 ERPNext MCP 的 Task DocType
**Migration**: 使用 create_document/list_documents(doctype="Task")

包含以下工具：
- add_project_milestone
- update_milestone
- get_project_milestones

### Requirement: 專案會議工具
**Reason**: 改用 ERPNext MCP 的 Event DocType
**Migration**: 使用 create_document/list_documents(doctype="Event")

包含以下工具：
- add_project_meeting
- update_project_meeting
- get_project_meetings

### Requirement: 專案連結工具
**Reason**: 改用 ERPNext MCP 的 Comment DocType
**Migration**: 使用 create_document/list_documents(doctype="Comment")

包含以下工具：
- add_project_link
- update_project_link
- get_project_links
- delete_project_link

### Requirement: 專案附件工具
**Reason**: 改用 ERPNext MCP 的 File DocType 和 upload_file 工具
**Migration**: 使用 upload_file 和 list_documents(doctype="File")

包含以下工具：
- add_project_attachment
- update_project_attachment
- get_project_attachments
- delete_project_attachment

### Requirement: 專案發包交貨工具
**Reason**: 改用 ERPNext MCP 的 Purchase Order DocType
**Migration**: 使用 create_document/list_documents(doctype="Purchase Order")

包含以下工具：
- add_delivery_schedule
- update_delivery_schedule
- get_delivery_schedules

### Requirement: 廠商管理工具
**Reason**: 改用 ERPNext MCP 的 Supplier DocType
**Migration**: 使用 create_document/list_documents(doctype="Supplier")

包含以下工具：
- query_vendors
- add_vendor
- update_vendor

### Requirement: 物料管理工具
**Reason**: 改用 ERPNext MCP 的 Item DocType
**Migration**: 使用 create_document/list_documents(doctype="Item")

包含以下工具：
- query_inventory
- add_inventory_item
- update_inventory_item
- query_project_inventory

### Requirement: 庫存異動工具
**Reason**: 改用 ERPNext MCP 的 Stock Entry DocType
**Migration**: 使用 create_document(doctype="Stock Entry")

包含以下工具：
- record_inventory_in
- record_inventory_out
- adjust_inventory

### Requirement: 訂購記錄工具
**Reason**: 改用 ERPNext MCP 的 Purchase Order DocType
**Migration**: 使用 create_document/list_documents(doctype="Purchase Order")

包含以下工具：
- add_inventory_order
- update_inventory_order
- get_inventory_orders
