# mcp-tools Spec Delta

## MODIFIED Requirements

### Requirement: 物料新增 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以新增物料。

#### Scenario: AI 新增物料
- **WHEN** AI 呼叫 `add_inventory_item` 工具
- **AND** 提供 name 參數（必填）
- **AND** 可選提供 model、specification、unit、category、default_vendor、storage_location、min_stock、notes 參數
- **THEN** 系統建立新物料記錄
- **AND** 初始庫存設為 0
- **AND** 返回建立成功訊息與物料 ID

#### Scenario: 物料名稱重複檢查
- **WHEN** AI 呼叫 `add_inventory_item` 工具
- **AND** 已存在相同名稱的物料
- **THEN** 系統返回錯誤訊息
- **AND** 提示使用不同名稱或更新現有物料

---

### Requirement: 物料查詢 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以查詢物料與庫存。

#### Scenario: AI 查詢物料列表
- **WHEN** AI 呼叫 `query_inventory` 工具
- **AND** 提供 keyword 參數（可選）
- **THEN** 系統返回匹配的物料列表
- **AND** 每個物料顯示名稱、型號、規格、存放庫位、目前庫存、單位

#### Scenario: AI 查詢單一物料詳情
- **WHEN** AI 呼叫 `query_inventory` 工具
- **AND** 提供 item_id 參數
- **THEN** 系統返回該物料的完整資訊
- **AND** 包含型號、存放庫位、近期進出貨記錄摘要

#### Scenario: 查詢庫存不足物料
- **WHEN** AI 呼叫 `query_inventory` 工具
- **AND** 提供 low_stock=true 參數
- **THEN** 系統返回庫存低於最低庫存量的物料列表

---

### Requirement: 物料管理 Line Bot Prompt
Line Bot 助理 SHALL 包含物料管理功能的使用說明。

#### Scenario: Prompt 包含物料管理工具
- **WHEN** Line Bot 收到物料相關訊息
- **THEN** AI 可識別並使用物料管理工具
- **AND** Prompt 說明包含：
  - query_inventory: 查詢物料/庫存
  - add_inventory_item: 新增物料（支援型號、存放庫位）
  - record_inventory_in: 記錄進貨
  - record_inventory_out: 記錄出貨
  - adjust_inventory: 庫存調整
  - add_inventory_order: 新增訂購記錄
  - update_inventory_order: 更新訂購記錄
  - get_inventory_orders: 查詢訂購記錄

#### Scenario: 物料管理對話範例
- **WHEN** 使用者說「查詢螺絲的庫存」
- **THEN** AI 呼叫 `query_inventory` 並返回結果（包含型號、庫位）
- **WHEN** 使用者說「新增物料 M8 不鏽鋼螺絲，型號 SS304-M8x20，存放在 A-1-3」
- **THEN** AI 呼叫 `add_inventory_item` 並設定 model 和 storage_location
- **WHEN** 使用者說「訂購 M8 螺絲 500 個，預計下週三交貨」
- **THEN** AI 呼叫 `add_inventory_order` 建立訂購記錄

---

## ADDED Requirements

### Requirement: 訂購記錄新增 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以新增物料訂購記錄。

#### Scenario: AI 新增訂購記錄（依物料 ID）
- **WHEN** AI 呼叫 `add_inventory_order` 工具
- **AND** 提供 item_id 和 order_quantity 參數（必填）
- **AND** 可選提供 order_date、expected_delivery_date、vendor、project_id、project_name、notes 參數
- **THEN** 系統建立訂購記錄
- **AND** 狀態預設為 pending
- **AND** 返回建立成功訊息

#### Scenario: AI 新增訂購記錄（依物料名稱）
- **WHEN** AI 呼叫 `add_inventory_order` 工具
- **AND** 提供 item_name 和 order_quantity 參數
- **THEN** 系統搜尋匹配的物料
- **WHEN** 找到唯一匹配
- **THEN** 建立訂購記錄
- **WHEN** 找到多個匹配
- **THEN** 返回候選清單請使用者確認

#### Scenario: 訂購關聯專案
- **WHEN** AI 呼叫 `add_inventory_order` 工具
- **AND** 提供 project_id 或 project_name 參數
- **THEN** 系統將此訂購記錄關聯到指定專案

---

### Requirement: 訂購記錄更新 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以更新物料訂購記錄。

#### Scenario: AI 更新訂購狀態
- **WHEN** AI 呼叫 `update_inventory_order` 工具
- **AND** 提供 order_id 和 status 參數
- **THEN** 系統更新訂購記錄狀態
- **AND** 返回更新成功訊息

#### Scenario: AI 更新訂購資訊
- **WHEN** AI 呼叫 `update_inventory_order` 工具
- **AND** 提供 order_id 參數
- **AND** 可選提供 order_quantity、order_date、expected_delivery_date、actual_delivery_date、vendor、project_id、notes 參數
- **THEN** 系統更新訂購記錄對應欄位
- **AND** 返回更新成功訊息

#### Scenario: 設定交貨完成
- **WHEN** AI 呼叫 `update_inventory_order` 工具
- **AND** 設定 status="delivered" 和 actual_delivery_date
- **THEN** 系統更新訂購記錄為已交貨
- **AND** 返回成功訊息並提示可建立進貨記錄

#### Scenario: 訂購記錄不存在
- **WHEN** AI 呼叫 `update_inventory_order` 工具
- **AND** order_id 不存在
- **THEN** 系統返回錯誤訊息「訂購記錄不存在」

---

### Requirement: 訂購記錄查詢 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以查詢物料訂購記錄。

#### Scenario: AI 查詢物料訂購記錄
- **WHEN** AI 呼叫 `get_inventory_orders` 工具
- **AND** 提供 item_id 或 item_name 參數
- **THEN** 系統返回該物料的訂購記錄列表
- **AND** 每筆記錄顯示訂購數量、下單日期、預計交貨日、狀態、廠商、關聯專案

#### Scenario: 依狀態過濾訂購記錄
- **WHEN** AI 呼叫 `get_inventory_orders` 工具
- **AND** 提供 status 參數（pending/ordered/delivered/cancelled）
- **THEN** 系統返回指定狀態的訂購記錄

#### Scenario: 查詢待交貨訂購
- **WHEN** AI 呼叫 `get_inventory_orders` 工具
- **AND** 提供 status="ordered" 參數
- **THEN** 系統返回所有已下單但尚未交貨的訂購記錄
- **AND** 方便追蹤待交貨項目
