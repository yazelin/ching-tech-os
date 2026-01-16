## ADDED Requirements

### Requirement: 廠商查詢工具
MCP Server SHALL 提供 `query_vendors` 工具讓 AI 可以查詢廠商主檔。

#### Scenario: 依關鍵字查詢廠商
- **WHEN** AI 呼叫 `query_vendors` 工具
- **AND** 提供 keyword 參數
- **THEN** 系統依廠商名稱、簡稱、ERP 編號搜尋
- **AND** 返回匹配的廠商列表

#### Scenario: 依 ERP 編號查詢廠商
- **WHEN** AI 呼叫 `query_vendors` 工具
- **AND** 提供 erp_code 參數
- **THEN** 系統依 ERP 編號精確查詢
- **AND** 返回匹配的廠商資料

#### Scenario: 廠商查詢結果格式
- **WHEN** 查詢成功
- **THEN** 返回廠商列表
- **AND** 每筆包含：id、erp_code、name、short_name、contact_person、phone

---

### Requirement: 廠商新增工具
MCP Server SHALL 提供 `add_vendor` 工具讓 AI 可以新增廠商。

#### Scenario: 新增廠商
- **WHEN** AI 呼叫 `add_vendor` 工具
- **AND** 提供 name 參數（必填）
- **THEN** 系統建立新廠商記錄
- **AND** 返回建立成功訊息與廠商 ID

#### Scenario: 新增廠商含 ERP 編號
- **WHEN** AI 呼叫 `add_vendor` 工具
- **AND** 提供 name 和 erp_code 參數
- **THEN** 系統建立新廠商記錄
- **WHEN** erp_code 已存在
- **THEN** 返回錯誤訊息

#### Scenario: 新增廠商含聯絡資訊
- **WHEN** AI 呼叫 `add_vendor` 工具
- **AND** 提供 contact_person、phone、email、address 等參數
- **THEN** 系統建立包含完整聯絡資訊的廠商記錄

---

### Requirement: 廠商更新工具
MCP Server SHALL 提供 `update_vendor` 工具讓 AI 可以更新廠商資訊。

#### Scenario: 更新廠商資訊
- **WHEN** AI 呼叫 `update_vendor` 工具
- **AND** 提供 vendor_id 和要更新的欄位
- **THEN** 系統更新廠商記錄
- **AND** 返回更新成功訊息

#### Scenario: 找不到廠商
- **WHEN** AI 呼叫 `update_vendor` 工具
- **AND** 提供的 vendor_id 不存在
- **THEN** 返回錯誤訊息

---

## MODIFIED Requirements

### Requirement: 發包記錄新增工具
MCP Server SHALL 提供 `add_delivery_schedule` 工具讓 AI 可以新增發包記錄，支援廠商與物料關聯。

#### Scenario: AI 新增發包記錄（基本）
- **WHEN** AI 呼叫 `add_delivery_schedule` 工具
- **AND** 提供 project_id、vendor、item 參數
- **THEN** 系統建立新發包記錄
- **AND** 返回建立成功訊息

#### Scenario: AI 新增發包記錄（關聯廠商）
- **WHEN** AI 呼叫 `add_delivery_schedule` 工具
- **AND** 提供 project_id、vendor_id、item 參數
- **THEN** 系統查詢 vendor_id 對應的廠商名稱
- **AND** 自動填入 vendor 欄位
- **AND** 建立發包記錄

#### Scenario: AI 新增發包記錄（關聯物料）
- **WHEN** AI 呼叫 `add_delivery_schedule` 工具
- **AND** 提供 project_id、vendor、item_id 參數
- **THEN** 系統查詢 item_id 對應的物料名稱
- **AND** 自動填入 item 欄位
- **AND** 建立發包記錄

#### Scenario: 廠商不存在
- **WHEN** AI 呼叫 `add_delivery_schedule` 工具
- **AND** 提供的 vendor_id 不存在
- **THEN** 返回錯誤訊息

#### Scenario: 物料不存在
- **WHEN** AI 呼叫 `add_delivery_schedule` 工具
- **AND** 提供的 item_id 不存在
- **THEN** 返回錯誤訊息

---

### Requirement: 發包記錄查詢工具
MCP Server SHALL 提供 `get_delivery_schedules` 工具讓 AI 可以查詢發包記錄，包含廠商與物料關聯資訊。

#### Scenario: 查詢發包記錄
- **WHEN** AI 呼叫 `get_delivery_schedules` 工具
- **AND** 提供 project_id 參數
- **THEN** 系統返回該專案的發包記錄列表
- **AND** 列表包含關聯的廠商名稱（若有 vendor_id）
- **AND** 列表包含關聯的物料名稱（若有 item_id）
- **AND** 列表格式化為易讀文字
