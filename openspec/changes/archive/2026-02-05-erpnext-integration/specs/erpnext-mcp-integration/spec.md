## ADDED Requirements

### Requirement: AI Agent Prompt 更新
系統 SHALL 更新 AI Agent prompt 引導使用 ERPNext MCP 工具。

#### Scenario: 移除 CTOS 工具說明
- **WHEN** 更新 AI Agent prompt
- **THEN** 移除專案管理、物料管理、廠商管理的 CTOS 工具說明
- **AND** 包含 query_project、query_inventory、query_vendors 等 33 個工具

#### Scenario: 新增 ERPNext 操作指引
- **WHEN** 更新 AI Agent prompt
- **THEN** 新增 ERPNext DocType 說明：
  - Project（專案）
  - Item（物料）
  - Supplier（廠商）
  - Task（任務/里程碑）
  - Event（會議/事件）
  - Stock Entry（庫存異動）
  - Purchase Order（採購單）

#### Scenario: 提供操作範例
- **WHEN** AI Agent 需要操作專案
- **THEN** prompt 包含 ERPNext MCP 工具使用範例：
  - 查詢專案：`list_documents(doctype="Project")`
  - 建立專案：`create_document(doctype="Project", data=...)`
  - 查詢庫存：`get_stock_balance(item_code=...)`

---

### Requirement: 權限群組對應
系統 SHALL 定義 CTOS 權限群組與 ERPNext 工具的對應關係。

#### Scenario: 專案管理權限
- **WHEN** 用戶有 project-management 權限群組
- **THEN** AI Agent 可使用 ERPNext Project、Task、Event 相關工具

#### Scenario: 物料管理權限
- **WHEN** 用戶有 inventory-management 權限群組
- **THEN** AI Agent 可使用 ERPNext Item、Stock Entry 相關工具

#### Scenario: 廠商管理權限
- **WHEN** 用戶有 vendor-management 權限群組
- **THEN** AI Agent 可使用 ERPNext Supplier、Purchase Order 相關工具

---

### Requirement: 錯誤處理指引
AI Agent prompt SHALL 包含 ERPNext API 錯誤的處理指引。

#### Scenario: 權限不足
- **WHEN** ERPNext 回傳 403 Forbidden
- **THEN** AI Agent 應告知用戶需要聯繫管理員設定權限

#### Scenario: 資料驗證失敗
- **WHEN** ERPNext 回傳 ValidationError
- **THEN** AI Agent 應解析錯誤訊息並告知用戶缺少哪些必填欄位

#### Scenario: 文件不存在
- **WHEN** ERPNext 回傳 DoesNotExistError
- **THEN** AI Agent 應提示用戶確認文件名稱或先建立文件
