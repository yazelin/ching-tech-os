# inventory-management Spec Delta

## MODIFIED Requirements

### Requirement: 物料主檔 CRUD 操作
物料管理 SHALL 支援物料主檔的新增、讀取、更新、刪除操作。

#### Scenario: 新增物料
- **WHEN** 使用者點擊「新增物料」按鈕
- **THEN** 顯示物料編輯表單
- **AND** 表單包含名稱（必填）、型號、規格、單位、類別、預設廠商、存放庫位、最低庫存量、備註

#### Scenario: 編輯物料
- **WHEN** 使用者在檢視物料時點擊「編輯」按鈕
- **THEN** 切換至編輯模式
- **AND** 可修改物料所有欄位（包含型號、存放庫位）

#### Scenario: 儲存物料
- **WHEN** 使用者在編輯模式點擊「儲存」按鈕
- **THEN** 系統更新物料資料
- **AND** 顯示儲存成功通知

#### Scenario: 刪除物料
- **WHEN** 使用者點擊「刪除」按鈕
- **THEN** 系統顯示確認對話框
- **WHEN** 使用者確認刪除
- **THEN** 從系統移除該物料及所有進出貨記錄與訂購記錄

---

### Requirement: 物料管理視窗佈局
物料管理應用程式 SHALL 提供雙欄式介面佈局與標籤頁切換。

#### Scenario: 顯示完整介面佈局
- **WHEN** 物料管理應用程式視窗開啟
- **THEN** 視窗內顯示上方工具列、左側物料列表、右側物料詳情面板

#### Scenario: 上方工具列
- **WHEN** 物料管理視窗開啟
- **THEN** 工具列顯示搜尋框、類別過濾下拉選單、新增物料按鈕

#### Scenario: 左側物料列表
- **WHEN** 使用者載入物料管理
- **THEN** 左側顯示物料列表
- **AND** 每個物料顯示名稱、型號、規格、目前庫存、單位、存放庫位

#### Scenario: 右側詳情面板
- **WHEN** 使用者選擇一個物料
- **THEN** 右側顯示標籤頁導航列
- **AND** 標籤頁包含：概覽、進出貨記錄、訂購記錄

---

### Requirement: 物料管理 API
後端 SHALL 提供 RESTful API 供前端操作物料管理。

#### Scenario: 物料列表 API
- **WHEN** 前端請求 `GET /api/inventory/items?q={keyword}&category={category}`
- **THEN** 後端返回符合條件的物料列表
- **AND** 每個物料包含 id、名稱、型號、規格、單位、類別、存放庫位、目前庫存、最低庫存量、更新時間

#### Scenario: 物料詳情 API
- **WHEN** 前端請求 `GET /api/inventory/items/{id}`
- **THEN** 後端返回物料完整資料（包含型號、存放庫位）

#### Scenario: 新增物料 API
- **WHEN** 前端請求 `POST /api/inventory/items`
- **AND** 請求包含 name、model（選填）、specification（選填）、unit（選填）、category（選填）、default_vendor（選填）、storage_location（選填）、min_stock（選填）、notes（選填）
- **THEN** 後端建立新物料記錄
- **AND** 返回新物料的完整資料

#### Scenario: 更新物料 API
- **WHEN** 前端請求 `PUT /api/inventory/items/{id}`
- **THEN** 後端更新物料記錄（包含型號、存放庫位）
- **AND** 更新 `updated_at` 時間戳

#### Scenario: 刪除物料 API
- **WHEN** 前端請求 `DELETE /api/inventory/items/{id}`
- **THEN** 後端刪除物料記錄及所有進出貨記錄與訂購記錄
- **AND** 返回成功狀態

#### Scenario: 進出貨記錄列表 API
- **WHEN** 前端請求 `GET /api/inventory/items/{id}/transactions`
- **THEN** 後端返回該物料的進出貨記錄列表

#### Scenario: 新增進出貨記錄 API
- **WHEN** 前端請求 `POST /api/inventory/items/{id}/transactions`
- **THEN** 後端建立新進出貨記錄
- **AND** 自動更新物料庫存數量
- **AND** 返回新記錄的完整資料

#### Scenario: 刪除進出貨記錄 API
- **WHEN** 前端請求 `DELETE /api/inventory/transactions/{tid}`
- **THEN** 後端刪除進出貨記錄
- **AND** 自動更新物料庫存數量
- **AND** 返回成功狀態

---

### Requirement: 物料管理資料庫儲存
物料管理 SHALL 使用 PostgreSQL 資料庫儲存物料資料。

#### Scenario: 物料主檔資料表
- **WHEN** 系統儲存物料
- **THEN** 物料資料存於 `inventory_items` 資料表
- **AND** 包含欄位：id（UUID）、name、model、specification、unit、category、default_vendor、storage_location、min_stock、current_stock、notes、created_at、updated_at、created_by

#### Scenario: 進出貨記錄資料表
- **WHEN** 系統儲存進出貨記錄
- **THEN** 進出貨資料存於 `inventory_transactions` 資料表
- **AND** 包含欄位：id（UUID）、item_id（外鍵）、type（in/out）、quantity、transaction_date、vendor、project_id（可選外鍵）、notes、created_at、created_by

#### Scenario: 訂購記錄資料表
- **WHEN** 系統儲存訂購記錄
- **THEN** 訂購資料存於 `inventory_orders` 資料表
- **AND** 包含欄位：id（UUID）、item_id（外鍵）、order_quantity、order_date、expected_delivery_date、actual_delivery_date、status、vendor、project_id（可選外鍵）、notes、created_at、updated_at、created_by

#### Scenario: 級聯刪除
- **WHEN** 刪除物料
- **THEN** 同時刪除所有關聯的進出貨記錄與訂購記錄

---

## ADDED Requirements

### Requirement: 訂購記錄管理
物料管理 SHALL 支援記錄物料的訂購狀態。

#### Scenario: 顯示訂購記錄列表
- **WHEN** 使用者切換到「訂購記錄」標籤頁
- **THEN** 顯示該物料的訂購記錄列表
- **AND** 按下單日期降序排列
- **AND** 每筆記錄顯示訂購數量、下單日期、預計交貨日、實際交貨日、狀態、廠商、關聯專案、備註

#### Scenario: 訂購狀態顏色標示
- **WHEN** 狀態為「待下單」（pending）
- **THEN** 狀態標籤顯示灰色
- **WHEN** 狀態為「已下單」（ordered）
- **THEN** 狀態標籤顯示藍色
- **WHEN** 狀態為「已交貨」（delivered）
- **THEN** 狀態標籤顯示綠色
- **WHEN** 狀態為「已取消」（cancelled）
- **THEN** 狀態標籤顯示紅色

#### Scenario: 新增訂購記錄
- **WHEN** 使用者在訂購記錄標籤頁點擊「新增訂購」按鈕
- **THEN** 顯示訂購編輯表單
- **AND** 表單包含訂購數量（必填）、下單日期、預計交貨日、廠商、關聯專案（下拉選單）、備註
- **AND** 狀態預設為「pending」

#### Scenario: 編輯訂購記錄
- **WHEN** 使用者點擊訂購記錄的編輯按鈕
- **THEN** 顯示訂購編輯表單
- **AND** 可修改所有欄位包含狀態、實際交貨日

#### Scenario: 刪除訂購記錄
- **WHEN** 使用者點擊訂購記錄的刪除按鈕
- **THEN** 系統顯示確認對話框
- **WHEN** 使用者確認
- **THEN** 從系統移除該記錄

#### Scenario: 專案關聯選擇器
- **WHEN** 使用者編輯訂購記錄
- **THEN** 可選擇關聯到現有專案（下拉選單）
- **AND** 可選擇「不關聯專案」

---

### Requirement: 訂購記錄 API
後端 SHALL 提供 RESTful API 供前端操作訂購記錄。

#### Scenario: 訂購記錄列表 API
- **WHEN** 前端請求 `GET /api/inventory/items/{id}/orders`
- **THEN** 後端返回該物料的訂購記錄列表

#### Scenario: 新增訂購記錄 API
- **WHEN** 前端請求 `POST /api/inventory/items/{id}/orders`
- **AND** 請求包含 order_quantity（必填）、order_date、expected_delivery_date、vendor、project_id、notes
- **THEN** 後端建立訂購記錄
- **AND** 返回新記錄的完整資料

#### Scenario: 更新訂購記錄 API
- **WHEN** 前端請求 `PUT /api/inventory/orders/{order_id}`
- **THEN** 後端更新訂購記錄
- **AND** 更新 `updated_at` 時間戳
- **AND** 返回更新後的記錄

#### Scenario: 刪除訂購記錄 API
- **WHEN** 前端請求 `DELETE /api/inventory/orders/{order_id}`
- **THEN** 後端刪除訂購記錄
- **AND** 返回成功狀態
