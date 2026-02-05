## Why

原有的專案管理、物料管理、廠商管理功能過於簡單，無法滿足實際業務需求。ERPNext 是功能完整的 ERP 系統，已部署並可透過 MCP 整合。我們決定將這三大模組的資料與功能遷移至 ERPNext，利用其成熟的功能取代自行開發的簡易版本。

## What Changes

### 資料遷移
- **BREAKING**: 將 `projects` 資料轉移至 ERPNext Project
- **BREAKING**: 將 `inventory_items` 資料轉移至 ERPNext Item
- **BREAKING**: 將 `vendors` 資料轉移至 ERPNext Supplier
- 轉移相關的子資料（里程碑、成員、會議、進出貨記錄、訂購記錄等）

### MCP 工具調整
- **BREAKING**: 移除 CTOS 的專案管理 MCP 工具（16 個），改用 ERPNext MCP
- **BREAKING**: 移除 CTOS 的物料管理 MCP 工具（7 個），改用 ERPNext MCP
- **BREAKING**: 移除 CTOS 的廠商管理 MCP 工具（3 個），改用 ERPNext MCP
- 更新 AI Agent 的 prompt，引導使用 ERPNext MCP 工具

### 前端調整
- 移除專案管理、物料管理、廠商管理 3 個應用程式
- 新增 1 個「ERPNext」應用程式 icon，點擊後開新視窗連至 `http://ct.erp`
- 保留知識庫、檔案管理等其他功能不變

### 資料庫清理
- 保留原資料表作為備份（標記為 deprecated）
- 或在確認轉移成功後移除

## Capabilities

### New Capabilities
- `erpnext-data-migration`: 資料遷移腳本與驗證機制，將 CTOS 資料轉換並匯入 ERPNext
- `erpnext-mcp-integration`: ERPNext MCP 工具整合，包含 prompt 調整與工具對應
- `erpnext-file-upload`: 擴充 ERPNext MCP，加入檔案上傳工具（用於專案附件等）

### Modified Capabilities
- `project-management`: 移除前端應用程式與相關 API
- `inventory-management`: 移除前端應用程式與相關 API
- `mcp-tools`: 移除專案/物料/廠商相關工具（26 個），更新 prompt 引導使用 ERPNext
- `web-desktop`: 移除 3 個 app icon，新增 ERPNext app（外連 http://ct.erp）

## Impact

### 程式碼
- `backend/src/ching_tech_os/services/mcp_server.py` - 移除 26 個 MCP 工具
- `backend/src/ching_tech_os/services/bot/agents.py` - 更新 prompt
- `backend/src/ching_tech_os/api/` - 移除或標記 deprecated 的 API endpoints
- `frontend/js/project-manager.js` - 移除
- `frontend/js/inventory-manager.js` - 移除
- `frontend/js/desktop.js` - 移除 3 個 app，新增 ERPNext app（開新視窗至 http://ct.erp）

### 資料庫
- `projects`, `project_*` 相關資料表 - 資料轉移後標記 deprecated
- `inventory_items`, `inventory_*` 相關資料表 - 資料轉移後標記 deprecated
- `vendors` 資料表 - 資料轉移後標記 deprecated

### 相依性
- Line Bot AI Agent 需要更新 prompt 以使用 ERPNext MCP
- 專案關聯的功能（如發包交貨、附件、連結）需決定保留或遷移

### ERPNext DocType 對應

| CTOS 資料表 | ERPNext DocType | 說明 |
|-------------|-----------------|------|
| `projects` | **Project** | 專案主檔 |
| `project_members` | **Project.users[]** | Project 的子表 |
| `project_meetings` | **Event** | 行事曆事件，透過 `reference_doctype=Project` 關聯 |
| `project_milestones` | **Task** | 任務/里程碑，透過 `project` 欄位關聯 |
| `project_attachments` | **File** | 透過 `attached_to_doctype=Project` 關聯 |
| `project_links` | **Comment** | 在 Project 上的註解 |
| `project_delivery_schedules` | **Purchase Order** | 採購單 |
| `inventory_items` | **Item** | 物料主檔 |
| `inventory_transactions` | **Stock Entry** | 庫存異動 |
| `inventory_orders` | **Purchase Order** | 採購單 |
| `vendors` | **Supplier** | 供應商 |

### 欄位對應明細

#### 專案 (projects → Project)
| CTOS 欄位 | ERPNext 欄位 |
|-----------|--------------|
| name | project_name |
| description | notes |
| status | status (Open/Completed/Cancelled) |
| start_date | expected_start_date |
| end_date | expected_end_date |

#### 物料 (inventory_items → Item)
| CTOS 欄位 | ERPNext 欄位 |
|-----------|--------------|
| name | item_name |
| model | item_code |
| specification | description |
| category | item_group |
| unit | stock_uom |
| min_stock | safety_stock |
| storage_location | default_warehouse (在 item_defaults 子表) |

#### 廠商 (vendors → Supplier)
| CTOS 欄位 | ERPNext 欄位 |
|-----------|--------------|
| name | supplier_name |
| contact_person | 透過 Contact DocType 關聯 |
| phone, email | 透過 Contact DocType 關聯 |
| address | 透過 Address DocType 關聯 |

#### 會議 (project_meetings → Event)
| CTOS 欄位 | ERPNext 欄位 |
|-----------|--------------|
| title | subject |
| meeting_date | starts_on |
| location | location (custom field 或 description) |
| content | description |
| project_id | reference_doctype=Project, reference_name=專案ID |

#### 附件 (project_attachments → File)
| CTOS 欄位 | ERPNext 欄位 |
|-----------|--------------|
| filename | file_name |
| file_path | file_url |
| project_id | attached_to_doctype=Project, attached_to_name=專案ID |

## 設計決策

| 議題 | 決策 |
|------|------|
| 發包/交貨流程 | 使用 ERPNext Purchase Order 標準流程 |
| 檔案上傳 | 擴充 ERPNext MCP 加入檔案上傳工具 |
| 專案連結管理 | 使用 ERPNext Comment |
| 庫存管理 | 使用 ERPNext 標準流程（完整庫存估值、批次、序號） |

## MCP 工具對應

### 要移除的 CTOS 工具 → ERPNext MCP 對應

#### 專案管理
| CTOS 工具 | ERPNext MCP 對應 |
|-----------|------------------|
| `query_project` | `list_documents(doctype="Project")` |
| `create_project` | `create_document(doctype="Project")` |
| `update_project` | `update_document(doctype="Project")` |
| `add_project_member` | `update_document(doctype="Project")` 更新 users 子表 |
| `update_project_member` | `update_document(doctype="Project")` |
| `get_project_members` | `get_document(doctype="Project")` 讀取 users |
| `add_project_milestone` | `create_document(doctype="Task")` |
| `update_milestone` | `update_document(doctype="Task")` |
| `get_project_milestones` | `list_documents(doctype="Task", filters={"project": "..."})` |
| `add_project_meeting` | `create_document(doctype="Event")` |
| `update_project_meeting` | `update_document(doctype="Event")` |
| `get_project_meetings` | `list_documents(doctype="Event", filters={"reference_doctype": "Project"})` |
| `add_project_link` | `create_document(doctype="Comment")` |
| `update_project_link` | `update_document(doctype="Comment")` |
| `get_project_links` | `list_documents(doctype="Comment")` |
| `delete_project_link` | `delete_document(doctype="Comment")` |
| `add_project_attachment` | `upload_file` (新增工具) |
| `get_project_attachments` | `list_documents(doctype="File", filters={"attached_to_doctype": "Project"})` |
| `update_project_attachment` | `update_document(doctype="File")` |
| `delete_project_attachment` | `delete_document(doctype="File")` |
| `add_delivery_schedule` | `create_document(doctype="Purchase Order")` |
| `update_delivery_schedule` | `update_document(doctype="Purchase Order")` |
| `get_delivery_schedules` | `list_documents(doctype="Purchase Order")` |

#### 廠商管理
| CTOS 工具 | ERPNext MCP 對應 |
|-----------|------------------|
| `query_vendors` | `list_documents(doctype="Supplier")` |
| `add_vendor` | `create_document(doctype="Supplier")` |
| `update_vendor` | `update_document(doctype="Supplier")` |

#### 物料管理
| CTOS 工具 | ERPNext MCP 對應 |
|-----------|------------------|
| `query_inventory` | `list_documents(doctype="Item")` + `get_stock_balance()` |
| `add_inventory_item` | `create_document(doctype="Item")` |
| `update_inventory_item` | `update_document(doctype="Item")` |
| `record_inventory_in` | `create_document(doctype="Stock Entry", data={"stock_entry_type": "Material Receipt"})` |
| `record_inventory_out` | `create_document(doctype="Stock Entry", data={"stock_entry_type": "Material Issue"})` |
| `adjust_inventory` | `create_document(doctype="Stock Entry", data={"stock_entry_type": "Material Transfer"})` |
| `query_project_inventory` | `list_documents(doctype="Item")` 配合專案 filter |
| `add_inventory_order` | `create_document(doctype="Purchase Order")` |
| `update_inventory_order` | `update_document(doctype="Purchase Order")` |
| `get_inventory_orders` | `list_documents(doctype="Purchase Order")` |

### ERPNext MCP 新增工具

| 工具 | 用途 |
|------|------|
| `upload_file` | 上傳檔案並附加到指定 DocType |

### ERPNext 權限需求

API Key 用戶需要以下角色：
- **Projects User** / **Projects Manager** - 專案、任務、事件
- **Stock User** / **Stock Manager** - 物料、庫存異動
- **Purchase User** / **Purchase Manager** - 採購單、供應商
