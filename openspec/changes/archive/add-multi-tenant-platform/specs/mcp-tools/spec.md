# MCP Tools Specification - Multi-Tenant Changes

## MODIFIED Requirements

### Requirement: MCP Tool Parameters
所有 MCP 工具 SHALL 支援租戶識別參數：
- **ctos_tenant_id: 租戶 UUID（新增參數）**
- ctos_user_id: 用戶 ID（現有參數）
- 若未提供 ctos_tenant_id，使用預設租戶

#### Scenario: 工具呼叫帶租戶
- **WHEN** AI Agent 呼叫 MCP 工具
- **AND** 提供 ctos_tenant_id 參數
- **THEN** 工具僅存取該租戶的資料

#### Scenario: 工具呼叫無租戶（向後相容）
- **WHEN** AI Agent 呼叫 MCP 工具
- **AND** 未提供 ctos_tenant_id
- **THEN** 使用預設租戶 ID
- **AND** 功能正常運作

### Requirement: Project Query Tools
專案查詢工具 SHALL 支援租戶隔離：
- query_project: 查詢專案時加入 tenant_id 過濾
- create_project: 建立專案時自動帶入 tenant_id
- update_project: 更新專案時驗證 tenant_id

#### Scenario: 查詢專案
- **WHEN** 呼叫 query_project
- **AND** 提供 ctos_tenant_id
- **THEN** 僅回傳該租戶的專案
- **AND** 跨租戶專案 ID 回傳「專案不存在」

### Requirement: Knowledge Tools
知識庫工具 SHALL 支援租戶隔離：
- search_knowledge: 搜尋範圍限定於租戶
- add_note: 筆記儲存於租戶目錄
- get_knowledge_item: 驗證知識項目屬於租戶

#### Scenario: 搜尋知識庫
- **WHEN** 呼叫 search_knowledge
- **AND** 提供 ctos_tenant_id
- **THEN** 僅搜尋該租戶的知識項目
- **AND** 不顯示其他租戶的知識

### Requirement: NAS File Tools
NAS 檔案工具 SHALL 支援租戶路徑隔離：
- search_nas_files: 搜尋限定於租戶目錄
- get_nas_file_info: 驗證檔案路徑屬於租戶
- send_nas_file: 發送前驗證租戶權限
- prepare_file_message: 路徑轉換加入租戶前綴

#### Scenario: 搜尋 NAS 檔案
- **WHEN** 呼叫 search_nas_files
- **AND** 提供 ctos_tenant_id
- **THEN** 搜尋範圍限定於 /mnt/nas/ctos/tenants/{tenant_id}/

#### Scenario: 存取跨租戶檔案
- **WHEN** 嘗試存取其他租戶的檔案路徑
- **THEN** 回傳「檔案不存在」
- **AND** 不洩漏檔案真實存在狀態

### Requirement: Inventory Tools
庫存工具 SHALL 支援租戶隔離：
- query_inventory: 查詢限定於租戶
- add_inventory_item: 自動帶入 tenant_id
- record_inventory_in/out: 驗證物料屬於租戶

#### Scenario: 查詢庫存
- **WHEN** 呼叫 query_inventory
- **AND** 提供 ctos_tenant_id
- **THEN** 僅回傳該租戶的庫存項目

### Requirement: Vendor Tools
廠商工具 SHALL 支援租戶隔離：
- query_vendors: 查詢限定於租戶
- add_vendor: 自動帶入 tenant_id
- update_vendor: 驗證廠商屬於租戶

#### Scenario: 查詢廠商
- **WHEN** 呼叫 query_vendors
- **AND** 提供 ctos_tenant_id
- **THEN** 僅回傳該租戶的廠商資料

## ADDED Requirements

### Requirement: Tenant Context in MCP Prompt
MCP Server 的 Agent Prompt SHALL 包含租戶上下文說明：
- 說明 ctos_tenant_id 參數用途
- 指示 AI 在呼叫工具時傳遞租戶 ID
- 強調資料隔離的重要性

#### Scenario: Prompt 更新
- **WHEN** 部署多租戶版本
- **THEN** linebot_agents.py 的 prompt 包含租戶參數說明
- **AND** AI 自動傳遞 ctos_tenant_id

### Requirement: Tenant Validation in Tools
所有 MCP 工具 SHALL 在執行前驗證租戶：
- 驗證 ctos_tenant_id 對應的租戶存在且 active
- 驗證用戶屬於該租戶
- 驗證失敗時回傳錯誤訊息

#### Scenario: 租戶驗證失敗
- **WHEN** 提供無效的 ctos_tenant_id
- **THEN** 工具回傳「租戶驗證失敗」
- **AND** 不執行任何資料操作
