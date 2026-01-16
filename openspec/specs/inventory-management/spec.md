# inventory-management Specification

## Purpose
TBD - created by archiving change add-inventory-management. Update Purpose after archive.
## Requirements
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
- **AND** 每個物料顯示名稱、規格、目前庫存、單位

#### Scenario: 右側詳情面板
- **WHEN** 使用者選擇一個物料
- **THEN** 右側顯示標籤頁導航列
- **AND** 標籤頁包含：概覽、進出貨記錄

---

### Requirement: 物料主檔 CRUD 操作
物料管理 SHALL 支援物料主檔的新增、讀取、更新、刪除操作。

#### Scenario: 新增物料
- **WHEN** 使用者點擊「新增物料」按鈕
- **THEN** 顯示物料編輯表單
- **AND** 表單包含名稱（必填）、規格、單位、類別、預設廠商、最低庫存量、備註

#### Scenario: 編輯物料
- **WHEN** 使用者在檢視物料時點擊「編輯」按鈕
- **THEN** 切換至編輯模式
- **AND** 可修改物料所有欄位

#### Scenario: 儲存物料
- **WHEN** 使用者在編輯模式點擊「儲存」按鈕
- **THEN** 系統更新物料資料
- **AND** 顯示儲存成功通知

#### Scenario: 刪除物料
- **WHEN** 使用者點擊「刪除」按鈕
- **THEN** 系統顯示確認對話框
- **WHEN** 使用者確認刪除
- **THEN** 從系統移除該物料及所有進出貨記錄

---

### Requirement: 進出貨記錄管理
物料管理 SHALL 支援記錄物料的進貨與出貨。

#### Scenario: 顯示進出貨記錄列表
- **WHEN** 使用者切換到「進出貨記錄」標籤頁
- **THEN** 顯示該物料的進出貨記錄列表
- **AND** 按日期降序排列
- **AND** 每筆記錄顯示日期、類型（進貨/出貨）、數量、廠商、關聯專案、備註

#### Scenario: 進出貨類型顏色標示
- **WHEN** 記錄類型為「進貨」（in）
- **THEN** 類型標籤顯示綠色，數量前顯示「+」
- **WHEN** 記錄類型為「出貨」（out）
- **THEN** 類型標籤顯示紅色，數量前顯示「-」

#### Scenario: 新增進貨記錄
- **WHEN** 使用者點擊「進貨」按鈕
- **THEN** 顯示進貨編輯表單
- **AND** 表單包含數量（必填）、日期（預設今日）、廠商、關聯專案（下拉選單）、備註
- **AND** 類型自動設為「in」

#### Scenario: 新增出貨記錄
- **WHEN** 使用者點擊「出貨」按鈕
- **THEN** 顯示出貨編輯表單
- **AND** 表單包含數量（必填）、日期（預設今日）、關聯專案（下拉選單）、備註
- **AND** 類型自動設為「out」

#### Scenario: 專案關聯選擇器
- **WHEN** 使用者編輯進出貨記錄
- **THEN** 可選擇關聯到現有專案（下拉選單）
- **AND** 可選擇「不關聯專案」

#### Scenario: 刪除進出貨記錄
- **WHEN** 使用者點擊進出貨記錄的刪除按鈕
- **THEN** 系統顯示確認對話框
- **WHEN** 使用者確認
- **THEN** 從系統移除該記錄
- **AND** 自動更新物料庫存數量

---

### Requirement: 庫存計算
物料管理 SHALL 自動計算並顯示物料的目前庫存。

#### Scenario: 庫存自動計算
- **WHEN** 新增或刪除進出貨記錄
- **THEN** 系統自動重新計算該物料的庫存數量
- **AND** 庫存 = 所有進貨數量總和 - 所有出貨數量總和

#### Scenario: 庫存警示
- **WHEN** 物料庫存低於設定的最低庫存量
- **THEN** 物料列表中該物料顯示警示圖示（紅色）
- **AND** 概覽頁面顯示「庫存不足」警告

#### Scenario: 庫存為零或負數警示
- **WHEN** 物料庫存為 0 或負數
- **THEN** 物料列表中該物料以紅色顯示庫存數量

---

### Requirement: 物料搜尋與過濾
物料管理 SHALL 支援搜尋與過濾物料列表。

#### Scenario: 關鍵字搜尋
- **WHEN** 使用者在搜尋框輸入關鍵字
- **THEN** 系統過濾顯示名稱或規格包含關鍵字的物料
- **AND** 搜尋使用 300ms 防抖

#### Scenario: 類別過濾
- **WHEN** 使用者選擇類別過濾
- **THEN** 系統只顯示該類別的物料

#### Scenario: 庫存警示過濾
- **WHEN** 使用者選擇「庫存不足」過濾
- **THEN** 系統只顯示庫存低於最低庫存量的物料

---

### Requirement: 物料管理 API
後端 SHALL 提供 RESTful API 供前端操作物料管理。

#### Scenario: 物料列表 API
- **WHEN** 前端請求 `GET /api/inventory/items?q={keyword}&category={category}`
- **THEN** 後端返回符合條件的物料列表
- **AND** 每個物料包含 id、名稱、規格、單位、類別、目前庫存、最低庫存量、更新時間

#### Scenario: 物料詳情 API
- **WHEN** 前端請求 `GET /api/inventory/items/{id}`
- **THEN** 後端返回物料完整資料

#### Scenario: 新增物料 API
- **WHEN** 前端請求 `POST /api/inventory/items`
- **THEN** 後端建立新物料記錄
- **AND** 返回新物料的完整資料

#### Scenario: 更新物料 API
- **WHEN** 前端請求 `PUT /api/inventory/items/{id}`
- **THEN** 後端更新物料記錄
- **AND** 更新 `updated_at` 時間戳

#### Scenario: 刪除物料 API
- **WHEN** 前端請求 `DELETE /api/inventory/items/{id}`
- **THEN** 後端刪除物料記錄及所有進出貨記錄
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
- **AND** 包含欄位：id（UUID）、name、specification、unit、category、default_vendor、min_stock、current_stock、notes、created_at、updated_at、created_by

#### Scenario: 進出貨記錄資料表
- **WHEN** 系統儲存進出貨記錄
- **THEN** 進出貨資料存於 `inventory_transactions` 資料表
- **AND** 包含欄位：id（UUID）、item_id（外鍵）、type（in/out）、quantity、transaction_date、vendor、project_id（可選外鍵）、notes、created_at、created_by

#### Scenario: 級聯刪除
- **WHEN** 刪除物料
- **THEN** 同時刪除所有關聯的進出貨記錄

---

### Requirement: 物料管理 CSS 設計系統
物料管理 SHALL 使用全域 CSS 變數確保設計一致性。

#### Scenario: 使用全域色彩變數
- **WHEN** 定義物料管理 UI 樣式
- **THEN** 使用 `main.css` 定義的全域色彩變數
- **AND** 保持與其他應用（如專案管理）視覺風格一致

#### Scenario: 進出貨類型樣式
- **WHEN** 顯示進貨記錄
- **THEN** 使用 `--color-success` 變數
- **WHEN** 顯示出貨記錄
- **THEN** 使用 `--color-error` 變數

