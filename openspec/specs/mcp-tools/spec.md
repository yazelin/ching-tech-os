# mcp-tools Specification

## Purpose
MCP Server 提供 AI 可使用的工具，包括檔案操作、知識庫、分享連結等功能。

> **Note**: 專案管理、物料管理、廠商管理相關的 36 個 MCP 工具已於 2026-02 遷移至 ERPNext MCP Server。
> 詳見 `erpnext-mcp-integration` 規格。

## Requirements

### Requirement: 搜尋 NAS 共享檔案 MCP 工具
MCP Server SHALL 提供 `search_nas_files` 工具搜尋多個 NAS 共享掛載點中的檔案。

#### Scenario: 搜尋範圍包含多來源
- **GIVEN** 系統掛載了 projects 和 circuits 兩個共享區
- **WHEN** 呼叫 `search_nas_files(keywords="layout")`
- **THEN** 系統同時搜尋 `/mnt/nas/projects` 和 `/mnt/nas/circuits`
- **AND** 結果路徑帶來源前綴（如 `shared://projects/...`、`shared://circuits/...`）

#### Scenario: 結果路徑格式
- **GIVEN** 在 circuits 掛載點找到檔案 `線路圖A/xxx.dwg`
- **WHEN** 搜尋結果回傳
- **THEN** 路徑為 `shared://circuits/線路圖A/xxx.dwg`

#### Scenario: 單一來源不可用
- **GIVEN** circuits 掛載點不存在或未掛載
- **WHEN** 呼叫 `search_nas_files`
- **THEN** 系統跳過該來源，僅搜尋可用的掛載點
- **AND** 不回傳錯誤

#### Scenario: 安全限制
- **GIVEN** 搜尋範圍限定於已設定的掛載點（唯讀掛載）
- **WHEN** AI 嘗試搜尋其他路徑
- **THEN** 系統拒絕並回傳錯誤

---

### Requirement: 取得 NAS 檔案資訊 MCP 工具
MCP Server SHALL 提供 `get_nas_file_info` 工具讓 AI 助手取得特定檔案的詳細資訊。

#### Scenario: 取得檔案詳細資訊
- **GIVEN** AI 已透過搜尋找到檔案路徑
- **WHEN** 呼叫 `get_nas_file_info(file_path="...")`
- **THEN** 回傳檔案大小、修改時間、完整路徑

#### Scenario: 檔案不存在
- **WHEN** 呼叫 `get_nas_file_info` 且檔案不存在
- **THEN** 回傳錯誤訊息「檔案不存在」

#### Scenario: 路徑超出允許範圍
- **WHEN** 呼叫 `get_nas_file_info` 且路徑不在允許的掛載點下
- **THEN** 回傳錯誤訊息「不允許存取此路徑」

---

### Requirement: 分享連結 MCP 工具
MCP Server SHALL 提供 `create_share_link` 工具建立暫時分享連結。

#### Scenario: 為 NAS 檔案建立分享連結
- **GIVEN** AI 找到 NAS 檔案
- **WHEN** 呼叫 `create_share_link(resource_type="nas_file", ...)`
- **THEN** 系統建立公開分享連結
- **AND** 回傳包含下載 URL 的連結資訊

---

### Requirement: 準備檔案訊息 MCP 工具
MCP Server SHALL 提供 `prepare_file_message` 工具讓 AI 準備要發送的檔案訊息。

#### Scenario: 準備小圖片訊息
- **GIVEN** AI 找到 NAS 上的圖片檔案（jpg/png/gif/webp）
- **AND** 檔案大小 < 10MB
- **WHEN** 呼叫 `prepare_file_message(file_path="...")`
- **THEN** 系統產生 24 小時有效的分享連結
- **AND** 回傳包含 `[FILE_MESSAGE:{"type":"image",...}]` 的訊息

#### Scenario: 準備大檔案訊息
- **GIVEN** AI 找到 NAS 上的檔案
- **AND** 檔案不是圖片或大小 >= 10MB
- **WHEN** 呼叫 `prepare_file_message(file_path="...")`
- **THEN** 系統產生 24 小時有效的分享連結
- **AND** 回傳包含 `[FILE_MESSAGE:{"type":"file",...}]` 的訊息

---

### Requirement: PDF 轉圖片 MCP 工具
MCP Server SHALL 提供 `convert_pdf_to_images` 工具讓 AI 將 PDF 檔案轉換為圖片。

#### Scenario: 查詢 PDF 頁數（不轉換）
- **GIVEN** AI 需要先知道 PDF 有幾頁
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", pages="0")`
- **THEN** 系統只回傳 PDF 頁數資訊，不進行轉換

#### Scenario: 指定頁面範圍轉換
- **GIVEN** AI 需要轉換特定頁面
- **WHEN** 呼叫 `convert_pdf_to_images(pdf_path="...", pages="1-3")`
- **THEN** 系統只轉換第 1、2、3 頁
- **AND** 回傳轉換的圖片路徑列表

#### Scenario: PDF 轉換工具參數
- **WHEN** AI 呼叫 `convert_pdf_to_images` 工具
- **THEN** 工具接受以下參數：
  - `pdf_path`：PDF 檔案路徑（必填）
  - `pages`：要轉換的頁面（"0"=查詢頁數、"1"=第1頁、"1-3"=範圍、"all"=全部）
  - `output_format`：輸出格式（"png" 或 "jpg"）
  - `dpi`：解析度（72-600，預設 150）
  - `max_pages`：最大頁數限制（預設 20）

---

### Requirement: 記憶管理 MCP 工具
MCP Server SHALL 提供記憶管理工具，讓 AI 可以在對話中管理記憶。

#### Scenario: add_memory 新增記憶
- **WHEN** AI 呼叫 `add_memory` 工具
- **AND** 提供 content 參數
- **AND** 提供 line_group_id（群組對話）或 line_user_id（個人對話）
- **THEN** 系統建立新的記憶
- **AND** 回傳成功訊息和記憶 ID

#### Scenario: get_memories 查詢記憶
- **WHEN** AI 呼叫 `get_memories` 工具
- **AND** 提供 line_group_id 或 line_user_id
- **THEN** 系統回傳該群組或用戶的所有記憶列表

#### Scenario: update_memory 更新記憶
- **WHEN** AI 呼叫 `update_memory` 工具
- **AND** 提供 memory_id 參數
- **THEN** 系統更新該記憶
- **AND** 回傳成功訊息

#### Scenario: delete_memory 刪除記憶
- **WHEN** AI 呼叫 `delete_memory` 工具
- **AND** 提供 memory_id 參數
- **THEN** 系統刪除該記憶
- **AND** 回傳成功訊息

---

### Requirement: Generate Presentation Tool
系統 SHALL 提供 MCP Tool 讓 AI Agent 產生簡報內容。

#### Scenario: 產生簡報
- **GIVEN** LineBot AI 判斷用戶需要產生簡報
- **WHEN** 呼叫 `generate_presentation` tool 並傳入用戶提供的內容
- **THEN** 使用專門的 MD2PPT Agent prompt 產生符合格式的內容
- **AND** 自動建立帶密碼的分享連結
- **AND** 回傳分享連結 URL 和存取密碼

---

### Requirement: Generate Document Tool
系統 SHALL 提供 MCP Tool 讓 AI Agent 產生文件內容。

#### Scenario: 產生文件
- **GIVEN** LineBot AI 判斷用戶需要產生文件
- **WHEN** 呼叫 `generate_document` tool 並傳入用戶提供的內容
- **THEN** 使用專門的 MD2DOC Agent prompt 產生符合格式的內容
- **AND** 自動建立帶密碼的分享連結
- **AND** 回傳分享連結 URL 和存取密碼

---

## Archived Requirements (Migrated to ERPNext)

以下工具已遷移至 ERPNext MCP Server，保留作為歷史參考：

### 專案管理工具 [DEPRECATED]
- query_project → `list_documents(doctype="Project")`
- create_project → `create_document(doctype="Project")`
- update_project → `update_document(doctype="Project")`
- add_project_member → `update_document(doctype="Project")` (更新 users 子表)
- update_project_member
- get_project_members
- add_project_milestone → `create_document(doctype="Task")`
- update_milestone → `update_document(doctype="Task")`
- get_project_milestones → `list_documents(doctype="Task")`
- add_project_meeting → `create_document(doctype="Event")`
- update_project_meeting → `update_document(doctype="Event")`
- get_project_meetings → `list_documents(doctype="Event")`
- add_project_link → `create_document(doctype="Comment")`
- update_project_link
- get_project_links
- delete_project_link
- add_project_attachment → `upload_file`
- update_project_attachment
- get_project_attachments → `list_documents(doctype="File")`
- delete_project_attachment
- add_delivery_schedule → `create_document(doctype="Purchase Order")`
- update_delivery_schedule
- get_delivery_schedules

### 廠商管理工具 [DEPRECATED]
- query_vendors → `list_documents(doctype="Supplier")`
- add_vendor → `create_document(doctype="Supplier")`
- update_vendor → `update_document(doctype="Supplier")`

### 物料管理工具 [DEPRECATED]
- query_inventory → `list_documents(doctype="Item")`
- add_inventory_item → `create_document(doctype="Item")`
- update_inventory_item → `update_document(doctype="Item")`
- query_project_inventory
- record_inventory_in → `create_document(doctype="Stock Entry")`
- record_inventory_out → `create_document(doctype="Stock Entry")`
- adjust_inventory → `create_document(doctype="Stock Entry")`
- add_inventory_order → `create_document(doctype="Purchase Order")`
- update_inventory_order → `update_document(doctype="Purchase Order")`
- get_inventory_orders → `list_documents(doctype="Purchase Order")`
