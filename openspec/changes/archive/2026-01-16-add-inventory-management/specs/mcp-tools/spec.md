## ADDED Requirements

### Requirement: 物料查詢 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以查詢物料與庫存。

#### Scenario: AI 查詢物料列表
- **WHEN** AI 呼叫 `query_inventory` 工具
- **AND** 提供 keyword 參數（可選）
- **THEN** 系統返回匹配的物料列表
- **AND** 每個物料顯示名稱、規格、目前庫存、單位

#### Scenario: AI 查詢單一物料詳情
- **WHEN** AI 呼叫 `query_inventory` 工具
- **AND** 提供 item_id 參數
- **THEN** 系統返回該物料的完整資訊
- **AND** 包含近期進出貨記錄摘要

#### Scenario: 查詢庫存不足物料
- **WHEN** AI 呼叫 `query_inventory` 工具
- **AND** 提供 low_stock=true 參數
- **THEN** 系統返回庫存低於最低庫存量的物料列表

---

### Requirement: 物料新增 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以新增物料。

#### Scenario: AI 新增物料
- **WHEN** AI 呼叫 `add_inventory_item` 工具
- **AND** 提供 name 參數（必填）
- **AND** 可選提供 specification、unit、category、default_vendor、min_stock、notes 參數
- **THEN** 系統建立新物料記錄
- **AND** 初始庫存設為 0
- **AND** 返回建立成功訊息與物料 ID

#### Scenario: 物料名稱重複檢查
- **WHEN** AI 呼叫 `add_inventory_item` 工具
- **AND** 已存在相同名稱的物料
- **THEN** 系統返回錯誤訊息
- **AND** 提示使用不同名稱或更新現有物料

---

### Requirement: 進貨記錄 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以記錄進貨。

#### Scenario: AI 記錄進貨（依物料 ID）
- **WHEN** AI 呼叫 `record_inventory_in` 工具
- **AND** 提供 item_id 和 quantity 參數（必填）
- **AND** 可選提供 vendor、project_id、transaction_date、notes 參數
- **THEN** 系統建立進貨記錄
- **AND** 自動增加該物料庫存
- **AND** 返回進貨成功訊息

#### Scenario: AI 記錄進貨（依物料名稱）
- **WHEN** AI 呼叫 `record_inventory_in` 工具
- **AND** 提供 item_name 和 quantity 參數（必填）
- **THEN** 系統搜尋匹配的物料
- **WHEN** 找到唯一匹配
- **THEN** 建立進貨記錄
- **WHEN** 找到多個匹配
- **THEN** 返回候選清單請使用者確認

#### Scenario: 進貨關聯專案
- **WHEN** AI 呼叫 `record_inventory_in` 工具
- **AND** 提供 project_id 或 project_name 參數
- **THEN** 系統將此進貨記錄關聯到指定專案

---

### Requirement: 出貨記錄 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以記錄出貨。

#### Scenario: AI 記錄出貨（依物料 ID）
- **WHEN** AI 呼叫 `record_inventory_out` 工具
- **AND** 提供 item_id 和 quantity 參數（必填）
- **AND** 可選提供 project_id、transaction_date、notes 參數
- **THEN** 系統建立出貨記錄
- **AND** 自動減少該物料庫存
- **AND** 返回出貨成功訊息

#### Scenario: AI 記錄出貨（依物料名稱）
- **WHEN** AI 呼叫 `record_inventory_out` 工具
- **AND** 提供 item_name 和 quantity 參數（必填）
- **THEN** 系統搜尋匹配的物料
- **WHEN** 找到唯一匹配
- **THEN** 建立出貨記錄
- **WHEN** 找到多個匹配
- **THEN** 返回候選清單請使用者確認

#### Scenario: 出貨庫存不足警告
- **WHEN** AI 呼叫 `record_inventory_out` 工具
- **AND** 出貨數量大於目前庫存
- **THEN** 系統返回警告訊息
- **AND** 仍允許建立記錄（允許負庫存）
- **AND** 提醒用戶庫存將變為負數

---

### Requirement: 庫存調整 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以調整庫存（盤點校正）。

#### Scenario: AI 調整庫存
- **WHEN** AI 呼叫 `adjust_inventory` 工具
- **AND** 提供 item_id 或 item_name 和 new_quantity 參數（必填）
- **AND** 提供 reason 參數（必填，如「盤點調整」、「損耗」）
- **THEN** 系統計算調整差額
- **AND** 建立對應的進貨或出貨記錄
- **AND** 記錄備註說明調整原因
- **AND** 返回調整成功訊息

#### Scenario: 庫存調整記錄
- **WHEN** 系統執行庫存調整
- **THEN** 若新數量 > 目前庫存，建立進貨記錄
- **THEN** 若新數量 < 目前庫存，建立出貨記錄
- **AND** 備註自動加上「[庫存調整] {reason}」前綴

---

### Requirement: 物料管理 Line Bot Prompt
Line Bot 助理 SHALL 包含物料管理功能的使用說明。

#### Scenario: Prompt 包含物料管理工具
- **WHEN** Line Bot 收到物料相關訊息
- **THEN** AI 可識別並使用物料管理工具
- **AND** Prompt 說明包含：
  - query_inventory: 查詢物料/庫存
  - add_inventory_item: 新增物料
  - record_inventory_in: 記錄進貨
  - record_inventory_out: 記錄出貨
  - adjust_inventory: 庫存調整

#### Scenario: 物料管理對話範例
- **WHEN** 使用者說「查詢螺絲的庫存」
- **THEN** AI 呼叫 `query_inventory` 並返回結果
- **WHEN** 使用者說「進貨 M8 螺絲 100 個」
- **THEN** AI 呼叫 `record_inventory_in` 建立記錄
- **WHEN** 使用者說「從倉庫領料 M8 螺絲 20 個給 XX 專案」
- **THEN** AI 呼叫 `record_inventory_out` 並關聯專案
