## MODIFIED Requirements

### Requirement: 管理員識別

系統 SHALL 使用資料庫中的 `users.role` 欄位識別管理員身份，僅支援 `admin` 和 `user` 兩種角色。

#### Scenario: 判斷管理員身份
- **WHEN** 使用者在 `users` 表中的 `role` 欄位為 `admin`
- **THEN** 系統識別該使用者為管理員
- **AND** `GET /api/user/me` 回應 `role: "admin"`

#### Scenario: 管理員擁有所有權限
- **WHEN** 使用者為管理員（role = 'admin'）
- **THEN** 所有應用程式權限均為 `true`
- **AND** 所有知識庫權限均為 `true`
- **AND** 可存取使用者管理功能

#### Scenario: 一般使用者依權限設定
- **WHEN** 使用者為一般使用者（role = 'user'）
- **THEN** 權限依據 `users.preferences.permissions` 設定
- **AND** 無法存取使用者管理功能

---

### Requirement: User Role Determination Service
系統 SHALL 提供 `get_user_role()` 服務函數，用於判斷用戶角色，僅支援 `admin` 和 `user` 兩種角色。

#### Scenario: 判斷管理員
- **WHEN** 用戶名稱在 `ADMINS` 環境變數清單中
- **THEN** 回傳角色 `admin`

#### Scenario: 判斷資料庫中的管理員
- **WHEN** 用戶在 `users` 表的 `role` 欄位為 `admin`
- **THEN** 回傳角色 `admin`

#### Scenario: 判斷一般用戶
- **WHEN** 用戶不符合管理員條件
- **THEN** 回傳角色 `user`

---

### Requirement: NAS 認證登入
系統 SHALL 透過區網 NAS 的 SMB 認證來驗證使用者身份，不需要提供租戶代碼。

#### Scenario: 使用正確的 NAS 帳密登入
- **WHEN** 使用者在登入頁面
- **AND** 輸入正確的 NAS 帳號和密碼並送出
- **THEN** 系統回傳成功並提供 session token
- **AND** 系統在 users 表建立或更新該使用者記錄
- **AND** 使用者被導向桌面頁面

#### Scenario: 登入 API 請求格式
- **WHEN** 客戶端呼叫 `POST /api/auth/login`
- **THEN** 請求 body 僅需 `username` 和 `password` 欄位
- **AND** 不需要 `tenant_code` 欄位

#### Scenario: 登入 API 回應格式
- **WHEN** 登入成功
- **THEN** 回應包含 `token`、`username`、`role`
- **AND** 不包含 `tenant` 物件

---

### Requirement: Session 管理
系統 SHALL 使用 token 管理使用者登入狀態，Session 資料不包含租戶資訊。

#### Scenario: Session 資料結構
- **WHEN** 系統建立 session
- **THEN** session 包含 `username`、`password`、`user_id`、`role`、`app_permissions`
- **AND** 不包含 `tenant_id` 欄位

#### Scenario: 使用有效 token 存取 API
- **WHEN** 使用者已登入並持有有效 token
- **AND** 使用該 token 呼叫需認證的 API
- **THEN** API 正常回應

---

### Requirement: 使用者權限管理

系統 SHALL 提供 API 讓管理員管理使用者權限。

#### Scenario: 取得使用者列表
- **WHEN** 管理員已登入
- **AND** 呼叫 `GET /api/admin/users`
- **THEN** 系統回傳所有使用者列表
- **AND** 每個使用者包含 id、username、display_name、role、permissions、last_login_at

#### Scenario: 非管理員存取使用者列表
- **WHEN** 非管理員使用者已登入
- **AND** 呼叫 `GET /api/admin/users`
- **THEN** 系統回傳 403 權限錯誤

#### Scenario: 更新使用者權限
- **WHEN** 管理員已登入
- **AND** 呼叫 `PATCH /api/admin/users/{user_id}/permissions`
- **THEN** 系統更新該使用者的權限設定

#### Scenario: 更新使用者角色
- **WHEN** 管理員已登入
- **AND** 呼叫 `PATCH /api/admin/users/{user_id}/role`
- **AND** 提供 `role` 參數（`admin` 或 `user`）
- **THEN** 系統更新該使用者的角色

---

### Requirement: 使用者資訊 API
系統 SHALL 提供 API 讓登入後的使用者查看個人資訊。

#### Scenario: 取得目前使用者資訊
- **WHEN** 使用者已登入
- **AND** 呼叫 `GET /api/user/me`
- **THEN** 系統回傳該使用者的資訊
- **AND** 包含 username、display_name、role、permissions、created_at、last_login_at
- **AND** 不包含 tenant 相關欄位

## REMOVED Requirements

### Requirement: 租戶管理員擁有租戶內完整權限
**Reason**: 移除多租戶架構，不再有租戶管理員角色
**Migration**: 原租戶管理員統一轉換為 admin 角色

### Requirement: 平台管理員設定租戶管理員權限
**Reason**: 移除多租戶架構，不再有平台管理員和租戶管理員角色
**Migration**: 使用 admin 角色管理所有使用者

### Requirement: 租戶管理員只能看到有權限的 App
**Reason**: 移除多租戶架構
**Migration**: 權限控制統一由 admin/user 角色和 app_permissions 處理

### Requirement: 租戶管理員無法修改自己的權限
**Reason**: 移除多租戶架構
**Migration**: admin 可修改任何非 admin 使用者的權限

### Requirement: 租戶管理員只能修改一般使用者權限
**Reason**: 移除多租戶架構
**Migration**: admin 可修改任何非 admin 使用者的權限

### Requirement: 新建租戶管理員自動初始化權限
**Reason**: 移除多租戶架構
**Migration**: 新使用者使用預設權限，admin 手動調整

### Requirement: Tenant Deletion with CASCADE
**Reason**: 移除多租戶架構，不再有租戶表
**Migration**: 不需要，租戶概念已移除

### Requirement: Migration Validation
**Reason**: 移除多租戶架構，不再有 tenant_id 欄位
**Migration**: 不需要，tenant_id 欄位已移除
