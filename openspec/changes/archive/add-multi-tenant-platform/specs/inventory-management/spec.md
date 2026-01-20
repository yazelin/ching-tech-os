# Inventory Management Specification - Multi-Tenant Changes

## MODIFIED Requirements

### Requirement: Inventory Item Data Model
系統 SHALL 維護庫存項目資料模型：
- id: UUID 主鍵
- **tenant_id: UUID 租戶識別（必填）**
- name: 物料名稱
- specification: 規格
- unit: 單位
- category: 類別
- current_quantity: 目前數量
- min_stock: 最低庫存量
- default_vendor: 預設廠商
- created_by: 建立者

#### Scenario: 建立庫存項目
- **WHEN** 用戶建立新的庫存項目
- **THEN** 自動帶入當前 session 的 tenant_id
- **AND** 項目歸屬於該租戶

#### Scenario: 查詢庫存
- **WHEN** 用戶查詢庫存項目
- **THEN** 僅回傳當前租戶的項目
- **AND** 不顯示其他租戶的庫存

### Requirement: Inventory Transactions
系統 SHALL 記錄庫存異動交易：
- id: UUID 主鍵
- item_id: 物料 ID
- **tenant_id: UUID 租戶識別（必填）**
- transaction_type: 類型 (in/out/adjust)
- quantity: 數量
- vendor: 廠商（進貨時）
- project_id: 關聯專案

#### Scenario: 記錄進貨
- **WHEN** 記錄進貨交易
- **THEN** tenant_id 自動從物料繼承
- **AND** 更新物料的 current_quantity

#### Scenario: 跨租戶物料存取
- **WHEN** 嘗試為其他租戶的物料記錄交易
- **THEN** 回傳「物料不存在」錯誤
- **AND** 交易不執行

### Requirement: Vendor Data Model
系統 SHALL 維護廠商資料模型：
- id: UUID 主鍵
- **tenant_id: UUID 租戶識別（必填）**
- name: 廠商名稱
- erp_code: ERP 編號
- contact_person: 聯絡人
- phone, email, address: 聯絡資訊
- tax_id: 統一編號
- is_active: 是否啟用

#### Scenario: 建立廠商
- **WHEN** 用戶建立新廠商
- **THEN** 自動帶入當前 session 的 tenant_id
- **AND** 廠商歸屬於該租戶

#### Scenario: 查詢廠商
- **WHEN** 用戶查詢廠商列表
- **THEN** 僅回傳當前租戶的廠商
- **AND** ERP 編號唯一性限定於租戶內

### Requirement: Low Stock Alert
系統 SHALL 監控庫存並發出低庫存警告：
- 比較 current_quantity 與 min_stock
- **警告範圍限定於租戶**
- 通知該租戶的管理員

#### Scenario: 低庫存查詢
- **WHEN** 查詢低庫存物料
- **THEN** 僅顯示當前租戶的低庫存項目
- **AND** 不顯示其他租戶的庫存狀態

## ADDED Requirements

### Requirement: Inventory Data Migration
系統 SHALL 支援庫存資料的租戶遷移：
- 匯出租戶所有物料和廠商資料
- 匯出庫存交易記錄
- 在目標租戶匯入並保持資料關聯

#### Scenario: 庫存資料匯出
- **WHEN** 管理員匯出租戶庫存資料
- **THEN** 包含所有物料、廠商、交易記錄
- **AND** 保留專案關聯資訊

#### Scenario: 庫存資料匯入
- **WHEN** 管理員匯入庫存資料
- **THEN** 物料和廠商建立於目標租戶
- **AND** 交易記錄重新關聯
