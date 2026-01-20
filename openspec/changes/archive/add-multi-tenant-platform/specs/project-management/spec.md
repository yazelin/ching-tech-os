# Project Management Specification - Multi-Tenant Changes

## MODIFIED Requirements

### Requirement: Project Data Model
系統 SHALL 維護專案（Project）資料模型：
- id: UUID 主鍵
- **tenant_id: UUID 租戶識別（必填）**
- name: 專案名稱
- description: 專案描述
- status: 專案狀態 (active/completed/on_hold/cancelled)
- start_date, end_date: 起訖日期
- created_by: 建立者
- created_at, updated_at: 時間戳

#### Scenario: 建立專案
- **WHEN** 用戶建立新專案
- **THEN** 自動帶入當前 session 的 tenant_id
- **AND** 專案歸屬於該租戶

#### Scenario: 查詢專案列表
- **WHEN** 用戶查詢專案列表
- **THEN** 僅回傳當前租戶的專案
- **AND** 不顯示其他租戶的專案

### Requirement: Project Member Management
系統 SHALL 管理專案成員：
- project_id: 專案 ID
- **tenant_id: 租戶識別（必填）**
- user_id: 用戶 ID（內部成員）
- name: 成員名稱
- role: 角色
- is_internal: 是否為內部人員

#### Scenario: 新增專案成員
- **WHEN** 新增專案成員
- **THEN** 成員的 tenant_id 必須與專案相同
- **AND** 跨租戶成員新增被拒絕

### Requirement: Project Milestones
系統 SHALL 管理專案里程碑：
- id: UUID 主鍵
- project_id: 專案 ID
- **tenant_id: 租戶識別（必填）**
- name: 里程碑名稱
- planned_date, actual_date: 計畫與實際日期
- status: 狀態

#### Scenario: 里程碑租戶一致性
- **WHEN** 新增里程碑
- **THEN** tenant_id 自動從專案繼承
- **AND** 確保資料一致性

### Requirement: Project Delivery Schedules
系統 SHALL 管理專案發包/交貨記錄：
- id: UUID 主鍵
- project_id: 專案 ID
- **tenant_id: 租戶識別（必填）**
- vendor: 廠商名稱
- item: 料件名稱
- status: 狀態

#### Scenario: 交貨記錄租戶隔離
- **WHEN** 查詢交貨記錄
- **THEN** 僅顯示當前租戶的記錄

### Requirement: Project Meetings
系統 SHALL 管理專案會議記錄：
- id: UUID 主鍵
- project_id: 專案 ID
- **tenant_id: 租戶識別（必填）**
- title: 會議標題
- content: 會議內容
- meeting_date: 會議日期

#### Scenario: 會議記錄查詢
- **WHEN** 查詢專案會議記錄
- **THEN** 僅回傳當前租戶的會議

### Requirement: Project Attachments
系統 SHALL 管理專案附件：
- id: UUID 主鍵
- project_id: 專案 ID
- **tenant_id: 租戶識別（必填）**
- nas_path: NAS 檔案路徑
- description: 描述

#### Scenario: 附件檔案路徑
- **WHEN** 上傳專案附件
- **THEN** 檔案儲存於租戶專屬目錄
- **AND** nas_path 包含租戶路徑前綴

### Requirement: Project Links
系統 SHALL 管理專案相關連結：
- id: UUID 主鍵
- project_id: 專案 ID
- **tenant_id: 租戶識別（必填）**
- title: 連結標題
- url: URL

#### Scenario: 連結租戶隔離
- **WHEN** 查詢專案連結
- **THEN** 僅顯示當前租戶的連結
