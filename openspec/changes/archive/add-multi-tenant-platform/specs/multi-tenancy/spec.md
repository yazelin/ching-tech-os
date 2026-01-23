# Multi-Tenancy Specification

## ADDED Requirements

### Requirement: Tenant Data Model
系統 SHALL 維護租戶（Tenant）資料模型，包含以下屬性：
- 唯一識別碼（UUID）
- 租戶代碼（用於登入識別，唯一）
- 租戶名稱
- 狀態（active, suspended, trial）
- 方案（trial, basic, pro, enterprise）
- 設定（JSONB）
- 儲存配額與使用量
- 試用期結束時間
- 建立與更新時間

#### Scenario: 建立新租戶
- **WHEN** 平台管理員建立新租戶
- **THEN** 系統產生唯一 UUID 和租戶代碼
- **AND** 建立對應的檔案儲存目錄

#### Scenario: 租戶狀態變更
- **WHEN** 租戶狀態從 trial 變更為 suspended
- **THEN** 該租戶的所有用戶無法登入
- **AND** 資料保留但不可存取

### Requirement: Tenant Isolation
系統 SHALL 確保不同租戶的資料完全隔離：
- 資料庫層級：所有資料表包含 tenant_id 欄位
- 檔案系統層級：租戶檔案儲存於獨立目錄
- API 層級：所有請求自動過濾租戶資料

#### Scenario: 跨租戶資料存取拒絕
- **WHEN** 租戶 A 的用戶嘗試存取租戶 B 的專案
- **THEN** 系統回傳 404 Not Found（非 403，避免洩漏資源存在）

#### Scenario: 資料庫查詢自動過濾
- **WHEN** 執行任何資料查詢
- **THEN** 查詢結果僅包含當前租戶的資料

### Requirement: Tenant Identification
系統 SHALL 支援多種租戶識別方式：
- Subdomain 識別（如 acme.ching-tech.com）
- 租戶代碼識別（登入時輸入）
- 單租戶模式自動使用預設租戶

#### Scenario: Subdomain 識別
- **WHEN** 用戶透過 acme.ching-tech.com 存取
- **THEN** 系統自動識別為 acme 租戶

#### Scenario: 租戶代碼登入
- **WHEN** 用戶在登入頁面輸入租戶代碼 "acme"
- **THEN** 系統驗證該租戶存在且狀態為 active
- **AND** 後續驗證用戶帳號密碼

### Requirement: Tenant Administration
系統 SHALL 提供租戶管理功能給平台管理員：
- 建立、更新、刪除租戶
- 查看所有租戶列表
- 變更租戶狀態和方案
- 查看租戶使用統計

#### Scenario: 列出所有租戶
- **WHEN** 平台管理員呼叫 GET /api/admin/tenants
- **THEN** 回傳所有租戶列表，包含基本資訊和使用統計

#### Scenario: 停用租戶
- **WHEN** 平台管理員將租戶狀態設為 suspended
- **THEN** 該租戶所有用戶立即無法登入
- **AND** 已登入的 session 被終止

### Requirement: Tenant Self-Service
系統 SHALL 提供租戶自助服務功能給租戶管理員：
- 查看租戶資訊和使用量
- 更新租戶設定
- 匯出租戶資料
- 匯入租戶資料（用於遷移）

#### Scenario: 查看使用量
- **WHEN** 租戶管理員呼叫 GET /api/tenant/usage
- **THEN** 回傳儲存使用量、用戶數、專案數等統計

#### Scenario: 匯出租戶資料
- **WHEN** 租戶管理員呼叫 POST /api/tenant/export
- **THEN** 系統產生包含所有租戶資料的 ZIP 檔案
- **AND** 回傳下載連結

### Requirement: Single-Tenant Compatibility
系統 SHALL 支援單租戶部署模式以相容現有部署：
- 透過環境變數 MULTI_TENANT_MODE=false 啟用
- 自動建立並使用預設租戶
- 登入流程不要求租戶代碼
- 所有功能正常運作

#### Scenario: 單租戶模式登入
- **WHEN** MULTI_TENANT_MODE=false
- **AND** 用戶登入時不提供租戶代碼
- **THEN** 系統自動使用預設租戶 ID
- **AND** 登入成功

### Requirement: Tenant Storage Quota
系統 SHALL 管理每個租戶的儲存配額：
- 設定租戶儲存上限（MB）
- 追蹤已使用儲存空間
- 接近上限時發出警告
- 超過上限時拒絕新增檔案

#### Scenario: 儲存超過配額
- **WHEN** 租戶已使用 95% 以上儲存空間
- **AND** 用戶嘗試上傳新檔案
- **THEN** 系統回傳錯誤訊息「儲存空間不足」

### Requirement: Tenant Data Migration
系統 SHALL 支援租戶資料遷移（試用轉正式）：
- 完整匯出租戶資料（資料庫 + 檔案）
- 在目標系統匯入租戶資料
- 驗證資料完整性
- 支援跨實例遷移

#### Scenario: 試用轉正式遷移
- **WHEN** 管理員在試用系統匯出租戶資料
- **AND** 在正式系統匯入該資料
- **THEN** 所有專案、知識庫、用戶資料完整保留
- **AND** 檔案附件可正常存取
