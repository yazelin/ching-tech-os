# erpnext-data-migration Specification

## Purpose
CTOS 資料遷移至 ERPNext 的規格，包含廠商、物料、專案資料的遷移腳本與驗證機制。

## Requirements

### Requirement: 廠商資料遷移
系統 SHALL 提供腳本將 CTOS vendors 資料遷移至 ERPNext Supplier。

#### Scenario: 遷移廠商基本資料
- **WHEN** 執行遷移腳本
- **THEN** CTOS vendors 的 name 對應到 Supplier.supplier_name
- **AND** 在 ERPNext 建立 Supplier 記錄
- **AND** 記錄 ID 映射（CTOS UUID → ERPNext Supplier name）

#### Scenario: 遷移廠商聯絡資訊
- **WHEN** CTOS vendor 有 contact_person、phone、email
- **THEN** 在 ERPNext 建立對應的 Contact 記錄
- **AND** 關聯到 Supplier（links）

---

### Requirement: 物料資料遷移
系統 SHALL 提供腳本將 CTOS inventory_items 資料遷移至 ERPNext Item。

#### Scenario: 遷移物料主檔
- **WHEN** 執行遷移腳本
- **THEN** 欄位對應如下：
  - name → item_name
  - model → item_code（若為空則用 name）
  - specification → description
  - category → item_group
  - unit → stock_uom
  - min_stock → safety_stock
- **AND** 在 ERPNext 建立 Item 記錄

#### Scenario: 設定預設倉庫
- **WHEN** CTOS item 有 storage_location
- **THEN** 在 Item.item_defaults 子表設定 default_warehouse

#### Scenario: 建立期初庫存
- **WHEN** CTOS item 有 current_stock > 0
- **THEN** 在 ERPNext 建立 Stock Entry（Material Receipt）
- **AND** 數量等於 current_stock
- **AND** 設定合理的估值金額

---

### Requirement: 專案資料遷移
系統 SHALL 提供腳本將 CTOS projects 資料遷移至 ERPNext Project。

#### Scenario: 遷移專案主檔
- **WHEN** 執行遷移腳本
- **THEN** 欄位對應如下：
  - name → project_name
  - description → notes
  - status → status（Open/Completed/Cancelled）
  - start_date → expected_start_date
  - end_date → expected_end_date
- **AND** 在 ERPNext 建立 Project 記錄

#### Scenario: 遷移專案成員
- **WHEN** CTOS project 有 project_members
- **THEN** 更新 Project.users 子表
- **AND** 成員 email 對應到 ERPNext User

#### Scenario: 遷移專案里程碑
- **WHEN** CTOS project 有 project_milestones
- **THEN** 在 ERPNext 建立 Task 記錄
- **AND** 設定 Task.project 關聯到對應專案
- **AND** milestone_type 對應到 Task.subject 前綴

#### Scenario: 遷移專案會議
- **WHEN** CTOS project 有 project_meetings
- **THEN** 在 ERPNext 建立 Event 記錄
- **AND** 設定 Event.reference_doctype = "Project"
- **AND** 設定 Event.reference_name = 專案名稱

#### Scenario: 遷移專案附件（小型）
- **WHEN** CTOS project_attachment 檔案大小 < 1MB
- **THEN** 使用 upload_file 上傳到 ERPNext
- **AND** 設定 attached_to_doctype = "Project"

#### Scenario: 遷移專案附件（大型 NAS）
- **WHEN** CTOS project_attachment 使用 NAS 儲存
- **THEN** 在 ERPNext 建立 Comment
- **AND** Comment 內容包含 NAS 路徑連結

#### Scenario: 遷移專案連結
- **WHEN** CTOS project 有 project_links
- **THEN** 在 ERPNext 建立 Comment 記錄
- **AND** Comment 內容包含連結 URL 和描述

---

### Requirement: 遷移腳本執行模式
系統 SHALL 支援 dry-run 模式驗證遷移邏輯。

#### Scenario: Dry-run 模式
- **WHEN** 執行遷移腳本帶 --dry-run 參數
- **THEN** 只輸出將要執行的操作
- **AND** 不實際寫入 ERPNext

#### Scenario: 正式執行
- **WHEN** 執行遷移腳本不帶 --dry-run
- **THEN** 執行實際遷移
- **AND** 輸出遷移結果統計

#### Scenario: 遷移日誌
- **WHEN** 遷移執行（無論 dry-run 或正式）
- **THEN** 輸出每筆資料的處理結果
- **AND** 錯誤時顯示詳細原因

---

### Requirement: ID 映射保存
系統 SHALL 保存 CTOS 與 ERPNext 的 ID 對應關係。

#### Scenario: 保存映射表
- **WHEN** 遷移完成
- **THEN** 將 ID 映射表保存為 JSON 檔案
- **AND** 檔案路徑為 data/migration/id_mapping.json

#### Scenario: 映射表格式
- **WHEN** 查看映射表
- **THEN** 格式為：
  ```json
  {
    "vendors": {"ctos-uuid-1": "supplier-name-1"},
    "items": {"ctos-uuid-2": "item-code-2"},
    "projects": {"ctos-uuid-3": "PROJ-0001"}
  }
  ```

---

### Requirement: 遷移驗證
系統 SHALL 提供驗證機制確認遷移正確性。

#### Scenario: 筆數比對
- **WHEN** 遷移完成後執行驗證
- **THEN** 比對 CTOS 與 ERPNext 的記錄筆數
- **AND** 輸出比對結果

#### Scenario: 抽樣驗證
- **WHEN** 執行驗證帶 --sample 參數
- **THEN** 隨機抽取 N 筆資料
- **AND** 比對關鍵欄位內容
