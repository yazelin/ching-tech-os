# project-management Spec Delta

## ADDED Requirements

### Requirement: 專案發包/交貨管理
專案管理 SHALL 支援管理專案的發包與交貨期程，追蹤廠商、料件、發包日期及交貨狀態。

#### Scenario: 顯示發包/交貨標籤頁
- **WHEN** 使用者選擇一個專案
- **THEN** 標籤頁導航列新增「發包/交貨」選項
- **AND** 標籤頁排列順序為：概覽、成員、會議、附件、連結、發包/交貨

#### Scenario: 顯示發包列表
- **WHEN** 使用者切換到「發包/交貨」標籤頁
- **THEN** 顯示該專案的發包記錄列表
- **AND** 列表欄位包含：廠商、料件、數量、發包日、預計交貨、實際到貨、狀態
- **AND** 每筆記錄有編輯和刪除按鈕

#### Scenario: 狀態顏色標示
- **WHEN** 發包狀態為「待發包」（pending）
- **THEN** 狀態標籤顯示灰色
- **WHEN** 發包狀態為「已發包」（ordered）
- **THEN** 狀態標籤顯示藍色
- **WHEN** 發包狀態為「已到貨」（delivered）
- **THEN** 狀態標籤顯示橙色
- **WHEN** 發包狀態為「已完成」（completed）
- **THEN** 狀態標籤顯示綠色

#### Scenario: 新增發包記錄
- **WHEN** 使用者點擊「新增發包」按鈕
- **THEN** 顯示發包編輯表單
- **AND** 表單包含：廠商（必填）、料件（必填）、數量、發包日、預計交貨日、狀態、備註

#### Scenario: 編輯發包記錄
- **WHEN** 使用者點擊發包項目的編輯按鈕
- **THEN** 顯示發包編輯表單
- **AND** 表單額外包含「實際到貨日」欄位
- **AND** 可修改所有發包資訊

#### Scenario: 刪除發包記錄
- **WHEN** 使用者點擊發包項目的刪除按鈕
- **THEN** 系統顯示確認對話框
- **WHEN** 使用者確認
- **THEN** 從專案移除該發包記錄

---

### Requirement: 發包/交貨 API
後端 SHALL 提供 RESTful API 供前端操作發包/交貨記錄。

#### Scenario: 發包列表 API
- **WHEN** 前端請求 `GET /api/projects/{id}/deliveries`
- **THEN** 後端返回該專案的發包記錄列表
- **AND** 每筆記錄包含 id、廠商、料件、數量、發包日、預計交貨日、實際到貨日、狀態、備註

#### Scenario: 新增發包 API
- **WHEN** 前端請求 `POST /api/projects/{id}/deliveries`
- **THEN** 後端建立新發包記錄
- **AND** 返回新記錄的完整資料

#### Scenario: 更新發包 API
- **WHEN** 前端請求 `PUT /api/projects/{id}/deliveries/{did}`
- **THEN** 後端更新發包記錄
- **AND** 更新 `updated_at` 時間戳

#### Scenario: 刪除發包 API
- **WHEN** 前端請求 `DELETE /api/projects/{id}/deliveries/{did}`
- **THEN** 後端刪除發包記錄
- **AND** 返回成功狀態

---

### Requirement: 發包/交貨資料庫儲存
專案管理 SHALL 使用 PostgreSQL 資料庫儲存發包/交貨資料。

#### Scenario: 發包資料表
- **WHEN** 系統儲存發包記錄
- **THEN** 發包資料存於 `project_delivery_schedules` 資料表
- **AND** 包含欄位：id、project_id、vendor、item、quantity、order_date、expected_delivery_date、actual_delivery_date、status、notes、created_at、updated_at、created_by

#### Scenario: 級聯刪除
- **WHEN** 刪除專案
- **THEN** 同時刪除所有關聯的發包記錄

---

### Requirement: 發包/交貨 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以操作發包/交貨記錄。

#### Scenario: AI 新增發包記錄
- **WHEN** AI 呼叫 `add_delivery_schedule` 工具
- **AND** 提供 project_id、vendor、item 參數
- **THEN** 系統建立新發包記錄
- **AND** 返回建立成功訊息

#### Scenario: AI 更新發包狀態
- **WHEN** AI 呼叫 `update_delivery_schedule` 工具
- **AND** 提供 project_id、vendor、item 用於匹配
- **AND** 提供 new_status 為目標狀態
- **THEN** 系統找到匹配的發包記錄並更新狀態
- **WHEN** 找不到匹配記錄
- **THEN** 返回錯誤訊息，列出可能的匹配項目

#### Scenario: AI 查詢發包列表
- **WHEN** AI 呼叫 `get_delivery_schedules` 工具
- **AND** 提供 project_id 參數
- **THEN** 系統返回該專案的發包記錄列表
- **AND** 列表格式化為易讀文字
