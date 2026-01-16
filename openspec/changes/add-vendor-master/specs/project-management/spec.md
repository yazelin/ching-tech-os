## ADDED Requirements

### Requirement: 廠商主檔管理
專案管理 SHALL 支援管理廠商主檔，包含 ERP 編號對照與完整聯絡資訊。

#### Scenario: 廠商列表顯示
- **WHEN** 使用者開啟廠商管理介面
- **THEN** 顯示廠商列表
- **AND** 每筆廠商顯示：ERP 編號、名稱、簡稱、聯絡人、電話、狀態

#### Scenario: 搜尋廠商
- **WHEN** 使用者在搜尋框輸入關鍵字
- **THEN** 系統依名稱、簡稱、ERP 編號篩選廠商
- **AND** 即時更新列表

#### Scenario: 新增廠商
- **WHEN** 使用者點擊「新增廠商」按鈕
- **THEN** 顯示廠商編輯表單
- **AND** 表單包含：ERP 編號、名稱（必填）、簡稱、聯絡人、電話、傳真、Email、地址、統一編號、付款條件、備註

#### Scenario: ERP 編號唯一性
- **WHEN** 使用者輸入已存在的 ERP 編號
- **THEN** 系統顯示錯誤訊息
- **AND** 阻止儲存

#### Scenario: 編輯廠商
- **WHEN** 使用者點擊廠商的編輯按鈕
- **THEN** 顯示廠商編輯表單
- **AND** 可修改所有廠商資訊

#### Scenario: 停用廠商
- **WHEN** 使用者點擊廠商的停用按鈕
- **THEN** 系統顯示確認對話框
- **WHEN** 使用者確認
- **THEN** 將廠商標記為停用（不刪除）
- **AND** 停用的廠商不會出現在選擇清單中

---

### Requirement: 廠商主檔 API
後端 SHALL 提供 RESTful API 供前端操作廠商主檔。

#### Scenario: 廠商列表 API
- **WHEN** 前端請求 `GET /api/vendors?q={keyword}&active={bool}`
- **THEN** 後端返回符合條件的廠商列表
- **AND** 每筆廠商包含 id、erp_code、name、short_name、contact_person、phone、is_active

#### Scenario: 廠商詳情 API
- **WHEN** 前端請求 `GET /api/vendors/{id}`
- **THEN** 後端返回廠商完整資料

#### Scenario: 新增廠商 API
- **WHEN** 前端請求 `POST /api/vendors`
- **THEN** 後端建立新廠商記錄
- **AND** 返回新廠商的完整資料
- **WHEN** ERP 編號已存在
- **THEN** 返回 409 Conflict 錯誤

#### Scenario: 更新廠商 API
- **WHEN** 前端請求 `PUT /api/vendors/{id}`
- **THEN** 後端更新廠商記錄
- **AND** 更新 `updated_at` 時間戳

#### Scenario: 停用廠商 API
- **WHEN** 前端請求 `DELETE /api/vendors/{id}`
- **THEN** 後端將廠商標記為停用（`is_active=false`）
- **AND** 不刪除實體資料

---

### Requirement: 廠商主檔資料庫儲存
專案管理 SHALL 使用 PostgreSQL 資料庫儲存廠商主檔資料。

#### Scenario: 廠商資料表結構
- **WHEN** 系統儲存廠商
- **THEN** 廠商資料存於 `vendors` 資料表
- **AND** 包含欄位：id、erp_code（唯一）、name、short_name、contact_person、phone、fax、email、address、tax_id、payment_terms、notes、is_active、created_at、updated_at、created_by

#### Scenario: ERP 編號索引
- **WHEN** 查詢廠商 by ERP 編號
- **THEN** 使用 `erp_code` 唯一索引快速查詢

---

### Requirement: 廠商 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以操作廠商主檔。

#### Scenario: AI 查詢廠商
- **WHEN** AI 呼叫 `query_vendors` 工具
- **AND** 提供 keyword 或 erp_code 參數
- **THEN** 系統返回匹配的廠商列表

#### Scenario: AI 新增廠商
- **WHEN** AI 呼叫 `add_vendor` 工具
- **AND** 提供 name 參數（必填）
- **THEN** 系統建立新廠商記錄
- **AND** 返回建立成功訊息與廠商 ID

#### Scenario: AI 更新廠商
- **WHEN** AI 呼叫 `update_vendor` 工具
- **AND** 提供 vendor_id 和要更新的欄位
- **THEN** 系統更新廠商記錄
- **AND** 返回更新成功訊息

---

## MODIFIED Requirements

### Requirement: 專案發包/交貨管理
專案管理 SHALL 支援管理專案的發包與交貨期程，追蹤廠商、料件、發包日期及交貨狀態。發包記錄可選擇性關聯到廠商主檔與物料主檔。

#### Scenario: 顯示發包/交貨標籤頁
- **WHEN** 使用者選擇一個專案
- **THEN** 標籤頁導航列新增「發包/交貨」選項
- **AND** 標籤頁排列順序為：概覽、成員、會議、附件、連結、發包/交貨

#### Scenario: 顯示發包列表
- **WHEN** 使用者切換到「發包/交貨」標籤頁
- **THEN** 顯示該專案的發包記錄列表
- **AND** 列表欄位包含：廠商、料件、數量、發包日、預計交貨、實際到貨、狀態
- **AND** 已關聯廠商主檔的記錄顯示廠商名稱（來自主檔）
- **AND** 已關聯物料主檔的記錄顯示物料名稱（來自主檔）
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
- **AND** 廠商欄位為 combo box，可選擇已存在的廠商或手動輸入
- **AND** 料件欄位為 combo box，可選擇已存在的物料或手動輸入
- **AND** 表單包含：廠商（必填）、料件（必填）、數量、發包日、預計交貨日、狀態、備註

#### Scenario: 廠商選擇行為
- **WHEN** 使用者從下拉選單選擇廠商
- **THEN** 系統設定 `vendor_id` 並自動填入廠商名稱到 `vendor` 欄位
- **WHEN** 使用者手動輸入廠商名稱
- **THEN** 系統只設定 `vendor` 欄位，`vendor_id` 為 NULL

#### Scenario: 料件選擇行為
- **WHEN** 使用者從下拉選單選擇物料
- **THEN** 系統設定 `item_id` 並自動填入物料名稱到 `item` 欄位
- **WHEN** 使用者手動輸入料件名稱
- **THEN** 系統只設定 `item` 欄位，`item_id` 為 NULL

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

### Requirement: 發包/交貨資料庫儲存
專案管理 SHALL 使用 PostgreSQL 資料庫儲存發包/交貨資料，支援廠商與物料關聯。

#### Scenario: 發包資料表
- **WHEN** 系統儲存發包記錄
- **THEN** 發包資料存於 `project_delivery_schedules` 資料表
- **AND** 包含欄位：id、project_id、vendor、vendor_id（FK）、item、item_id（FK）、quantity、order_date、expected_delivery_date、actual_delivery_date、status、notes、created_at、updated_at、created_by

#### Scenario: 廠商關聯
- **WHEN** 發包記錄關聯廠商主檔
- **THEN** `vendor_id` 外鍵指向 `vendors.id`
- **WHEN** 廠商被停用
- **THEN** 發包記錄的 `vendor_id` 保持不變（ON DELETE SET NULL）

#### Scenario: 物料關聯
- **WHEN** 發包記錄關聯物料主檔
- **THEN** `item_id` 外鍵指向 `inventory_items.id`
- **WHEN** 物料被刪除
- **THEN** 發包記錄的 `item_id` 設為 NULL（ON DELETE SET NULL）

#### Scenario: 級聯刪除
- **WHEN** 刪除專案
- **THEN** 同時刪除所有關聯的發包記錄

---

### Requirement: 發包/交貨 MCP 工具
MCP Server SHALL 提供工具讓 AI 可以操作發包/交貨記錄，支援廠商與物料關聯。

#### Scenario: AI 新增發包記錄
- **WHEN** AI 呼叫 `add_delivery_schedule` 工具
- **AND** 提供 project_id、vendor（或 vendor_id）、item（或 item_id）參數
- **THEN** 系統建立新發包記錄
- **WHEN** 提供 vendor_id
- **THEN** 系統自動查詢廠商名稱填入 `vendor` 欄位
- **WHEN** 提供 item_id
- **THEN** 系統自動查詢物料名稱填入 `item` 欄位
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
- **AND** 列表包含關聯的廠商與物料資訊
- **AND** 列表格式化為易讀文字
