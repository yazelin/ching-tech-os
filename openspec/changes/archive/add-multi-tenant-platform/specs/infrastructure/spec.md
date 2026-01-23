# Infrastructure Specification - Multi-Tenant Changes

## MODIFIED Requirements

### Requirement: Database Schema Management
系統 SHALL 使用 Alembic 管理資料庫 schema 變更：
- 所有 schema 變更必須透過 migration 檔案
- Migration 檔案放置於 backend/migrations/versions/
- 檔案命名格式：00X_description.py
- **所有資料表 MUST 包含 tenant_id 欄位（除系統表外）**
- **tenant_id 欄位 MUST 為外鍵參照 tenants 表**

#### Scenario: 新增資料表
- **WHEN** 需要新增資料表
- **THEN** MUST 包含 tenant_id UUID 欄位
- **AND** MUST 建立對應的複合索引 (tenant_id, primary_key)

#### Scenario: 查詢資料
- **WHEN** 執行資料查詢
- **THEN** MUST 包含 WHERE tenant_id = $current_tenant_id 條件

## ADDED Requirements

### Requirement: Tenant Table Structure
系統 SHALL 維護 tenants 主表，作為所有租戶資料的根：
- id: UUID 主鍵
- code: VARCHAR(50) 唯一，用於識別
- name: VARCHAR(200) 租戶名稱
- status: VARCHAR(20) 狀態 (active/suspended/trial)
- plan: VARCHAR(50) 方案 (trial/basic/pro/enterprise)
- settings: JSONB 租戶設定
- storage_quota_mb: BIGINT 儲存配額
- storage_used_mb: BIGINT 已使用儲存
- trial_ends_at: TIMESTAMPTZ 試用期結束
- created_at, updated_at: TIMESTAMPTZ 時間戳

#### Scenario: 建立預設租戶
- **WHEN** 系統初始化或升級
- **THEN** 建立 UUID 為 00000000-0000-0000-0000-000000000000 的預設租戶
- **AND** 現有資料遷移至該租戶

### Requirement: File Storage Isolation
系統 SHALL 在檔案系統層級隔離租戶資料：
- 租戶檔案儲存於 /mnt/nas/ctos/tenants/{tenant_id}/
- 每個租戶獨立的子目錄：knowledge/, linebot/, attachments/
- 系統共用檔案儲存於 /mnt/nas/ctos/system/
- PathManager 自動注入租戶路徑

#### Scenario: 租戶檔案路徑
- **WHEN** 租戶 A 儲存知識庫檔案
- **THEN** 檔案儲存於 /mnt/nas/ctos/tenants/{tenant_a_id}/knowledge/
- **AND** 租戶 B 無法存取該路徑

#### Scenario: 向後相容檔案路徑
- **WHEN** 單租戶模式
- **THEN** 建立符號連結 /mnt/nas/ctos/knowledge → /mnt/nas/ctos/tenants/default/knowledge
- **AND** 現有程式碼無需修改

### Requirement: Database Connection Pooling
系統 SHALL 支援多租戶資料庫連線池管理：
- 共用單一連線池（適合中小規模）
- 連線上下文包含當前租戶資訊
- 考慮未來支援每租戶獨立連線池

#### Scenario: 連線租戶上下文
- **WHEN** 取得資料庫連線
- **THEN** 可注入當前租戶 ID
- **AND** 供 Row-Level Security 使用（可選）

### Requirement: Tenant Database Indexes
系統 SHALL 為租戶查詢建立最佳化索引：
- 所有表格建立 (tenant_id) 單欄索引
- 常用查詢建立 (tenant_id, status)、(tenant_id, created_at) 等複合索引
- ai_logs 分區表考慮租戶分區

#### Scenario: 專案查詢效能
- **WHEN** 查詢租戶的 active 專案
- **THEN** 使用 idx_projects_tenant_status (tenant_id, status) 索引
- **AND** 查詢效能與單租戶相當
