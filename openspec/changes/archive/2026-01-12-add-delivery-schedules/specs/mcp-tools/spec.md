# mcp-tools Spec Delta

## ADDED Requirements

### Requirement: 發包/交貨管理 MCP 工具
MCP Server SHALL 提供發包/交貨管理工具，讓 AI 助手可以協助使用者管理專案發包期程。

#### Scenario: add_delivery_schedule 工具
- **GIVEN** AI 收到使用者關於新增發包記錄的請求
- **WHEN** AI 呼叫 `add_delivery_schedule` 工具
- **THEN** 工具參數包含：
  - `project_id`：專案 UUID（必填）
  - `vendor`：廠商名稱（必填）
  - `item`：料件名稱（必填）
  - `quantity`：數量與單位（選填，如「2 台」）
  - `order_date`：發包日期（選填，格式 YYYY-MM-DD）
  - `expected_delivery_date`：預計交貨日（選填，格式 YYYY-MM-DD）
  - `status`：狀態（選填，預設 pending）
  - `notes`：備註（選填）
- **AND** 系統建立發包記錄
- **AND** 返回「已新增發包記錄：{廠商} - {料件}」

#### Scenario: update_delivery_schedule 工具
- **GIVEN** AI 收到使用者關於更新發包狀態的請求
- **WHEN** AI 呼叫 `update_delivery_schedule` 工具
- **THEN** 工具參數包含：
  - `project_id`：專案 UUID（必填）
  - `delivery_id`：發包記錄 UUID（選填，直接指定）
  - `vendor`：廠商名稱（選填，用於匹配）
  - `item`：料件名稱（選填，用於匹配）
  - `new_status`：新狀態（選填）
  - `actual_delivery_date`：實際到貨日（選填，格式 YYYY-MM-DD）
  - `expected_delivery_date`：更新預計交貨日（選填）
  - `new_notes`：更新備註（選填）
- **WHEN** 透過 vendor + item 匹配找到唯一記錄
- **THEN** 更新該記錄並返回成功訊息
- **WHEN** 找到多筆匹配記錄
- **THEN** 返回錯誤，列出所有匹配項目請使用者選擇
- **WHEN** 找不到匹配記錄
- **THEN** 返回錯誤，提示無此發包記錄

#### Scenario: get_delivery_schedules 工具
- **GIVEN** AI 收到使用者關於查詢發包狀態的請求
- **WHEN** AI 呼叫 `get_delivery_schedules` 工具
- **THEN** 工具參數包含：
  - `project_id`：專案 UUID（必填）
  - `status`：狀態過濾（選填）
  - `vendor`：廠商過濾（選填）
  - `limit`：最大數量（選填，預設 20）
- **AND** 系統返回格式化的發包列表

---

### Requirement: Line Bot System Prompt 更新
Line Bot 的 system prompt SHALL 說明發包/交貨管理工具的用途。

#### Scenario: Prompt 包含工具說明
- **WHEN** Line Bot AI 收到 system prompt
- **THEN** prompt 包含以下工具說明：
  - `add_delivery_schedule`：新增發包/交貨記錄
  - `update_delivery_schedule`：更新發包狀態或到貨日期
  - `get_delivery_schedules`：查詢發包列表
- **AND** prompt 說明四種狀態的意義：
  - `pending`：待發包
  - `ordered`：已發包
  - `delivered`：已到貨
  - `completed`：已完成

#### Scenario: AI 正確使用工具
- **GIVEN** 使用者說「A 公司的水切爐已經到貨了」
- **WHEN** AI 處理此訊息
- **THEN** AI 應呼叫 `update_delivery_schedule` 工具
- **AND** 設定 `vendor` 為 "A 公司"
- **AND** 設定 `item` 為 "水切爐"
- **AND** 設定 `new_status` 為 "delivered"
- **AND** 設定 `actual_delivery_date` 為當天日期
