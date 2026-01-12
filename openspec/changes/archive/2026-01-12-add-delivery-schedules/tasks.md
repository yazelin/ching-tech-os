# Tasks: add-delivery-schedules

## Phase 1: 資料庫與後端基礎

- [x] **T1.1** 建立 Alembic migration `025_create_delivery_schedules.py`
  - 建立 `project_delivery_schedules` 資料表
  - 欄位：id, project_id, vendor, item, quantity, order_date, expected_delivery_date, actual_delivery_date, status, notes, created_at, updated_at, created_by
  - 索引：project_id, status, vendor

- [x] **T1.2** 新增 Pydantic models 到 `models/project.py`
  - `DeliveryScheduleBase`
  - `DeliveryScheduleCreate`
  - `DeliveryScheduleUpdate`
  - `DeliveryScheduleResponse`

- [x] **T1.3** 新增 API endpoints 到 `api/projects.py`
  - `GET /api/projects/{id}/deliveries` - 列表
  - `POST /api/projects/{id}/deliveries` - 新增
  - `PUT /api/projects/{id}/deliveries/{did}` - 更新
  - `DELETE /api/projects/{id}/deliveries/{did}` - 刪除

- [x] **T1.4** 執行 migration 驗證資料表建立成功

## Phase 2: MCP 工具

- [x] **T2.1** 新增 `add_delivery_schedule` MCP 工具
  - 參數：project_id, vendor, item, quantity, order_date, expected_delivery_date, status, notes
  - 驗證專案存在
  - 返回新建記錄摘要

- [x] **T2.2** 新增 `update_delivery_schedule` MCP 工具
  - 支援 delivery_id 直接指定
  - 支援 project_id + vendor + item 模糊匹配
  - 可更新：status, actual_delivery_date, expected_delivery_date, notes
  - 找不到時返回錯誤訊息

- [x] **T2.3** 新增 `get_delivery_schedules` MCP 工具
  - 參數：project_id, status, vendor, limit
  - 返回格式化的發包列表

- [x] **T2.4** 更新 Line Bot prompt（程式碼內）
  - 在 `linebot_agents.py` 中說明三個新工具的用途
  - 說明狀態值意義（pending/ordered/delivered/completed）

- [x] **T2.5** 建立 migration 更新資料庫內的 prompt

## Phase 3: 前端 UI

- [x] **T3.1** 新增「發包/交貨」標籤頁到標籤列
  - 更新 TABS 定義
  - 新增 `truck-delivery` 圖示（如需要）

- [x] **T3.2** 實作發包列表渲染 `renderDeliveriesTab()`
  - 表格顯示：廠商、料件、數量、發包日、預計交貨、實際到貨、狀態、操作
  - 狀態顏色標籤

- [x] **T3.3** 實作新增發包表單
  - 欄位：廠商、料件、數量、發包日、預計交貨日、狀態、備註
  - 狀態下拉選單

- [x] **T3.4** 實作編輯發包表單
  - 可編輯所有欄位
  - 新增「實際到貨日」欄位

- [x] **T3.5** 實作刪除確認
  - 刪除前顯示確認對話框

- [x] **T3.6** 新增 CSS 樣式
  - 表格樣式
  - 狀態標籤顏色
  - 表單樣式

## Phase 4: 驗證

- [x] **T4.1** 前端功能驗證
  - 新增發包記錄
  - 編輯發包記錄
  - 刪除發包記錄
  - 狀態篩選

- [x] **T4.2** MCP 工具驗證
  - 透過 AI 新增發包記錄
  - 透過 AI 更新狀態（例如：「A 廠商的水切爐已到貨」）
  - 透過 AI 查詢發包列表

- [x] **T4.3** 整合測試
  - 前端與後端 API 整合
  - Line Bot 對話測試

## Dependencies

- T1.1 → T1.2, T1.3, T1.4
- T1.2, T1.3 → T2.1, T2.2, T2.3
- T2.4 → T2.5
- T1.3 → T3.2, T3.3, T3.4, T3.5
- T3.1 ~ T3.6 可並行
- T4.* 依賴所有前置任務

## Parallelizable Work

Phase 2 和 Phase 3 可以並行進行：
- 後端 MCP 工具開發（T2.1-T2.5）
- 前端 UI 開發（T3.1-T3.6）
