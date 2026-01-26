# backend-auth spec delta

## ADDED Requirements

### Requirement: User Role Determination Service
系統 SHALL 提供獨立的 `get_user_role()` 服務函數，用於判斷用戶角色。

#### Scenario: 判斷平台管理員
- **WHEN** 用戶名稱在 `PLATFORM_ADMINS` 清單中
- **THEN** 回傳角色 `platform_admin`

#### Scenario: 判斷租戶管理員
- **WHEN** 用戶在 `tenant_admins` 表中有對應記錄
- **THEN** 回傳角色 `tenant_admin`

#### Scenario: 判斷一般用戶
- **WHEN** 用戶不是平台管理員也不是租戶管理員
- **THEN** 回傳角色 `user`

### Requirement: Tenant Deletion with CASCADE
系統 SHALL 在刪除租戶時利用資料庫 CASCADE 機制自動刪除關聯資料，僅對無法設定外鍵的分割資料表執行手動刪除。

#### Scenario: 刪除租戶時自動清理關聯資料
- **WHEN** 刪除一個租戶
- **THEN** 透過 CASCADE 自動刪除 users, projects, vendors 等有外鍵關聯的資料

#### Scenario: 手動清理分割資料表
- **WHEN** 刪除一個租戶
- **THEN** 手動刪除 ai_logs, messages 等分割資料表的資料

### Requirement: Migration Validation
資料庫 Migration SHALL 在設定 NOT NULL 約束前進行明確的驗證，並提供清晰的錯誤訊息。

#### Scenario: 發現未遷移資料
- **WHEN** 執行 migration 且有資料表的 tenant_id 為 NULL
- **THEN** 拋出例外並說明哪個資料表有問題、有多少筆未遷移資料
