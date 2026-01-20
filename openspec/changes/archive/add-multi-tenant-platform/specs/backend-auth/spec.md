# Backend Auth Specification - Multi-Tenant Changes

## MODIFIED Requirements

### Requirement: User Login
系統 SHALL 提供使用者登入功能：
- 使用者輸入帳號、密碼進行登入
- **多租戶模式時，需額外提供租戶代碼**
- 系統透過 NAS SMB 驗證帳號密碼
- **驗證租戶存在且狀態為 active**
- 驗證成功後建立 session 並回傳 JWT token
- **Token 包含 tenant_id 資訊**
- Token 有效期限為 24 小時

#### Scenario: 多租戶模式登入成功
- **WHEN** 用戶提供有效的租戶代碼、帳號和密碼
- **AND** 租戶狀態為 active
- **THEN** 回傳 JWT token 和用戶資訊
- **AND** token 包含 tenant_id claim

#### Scenario: 單租戶模式登入成功
- **WHEN** MULTI_TENANT_MODE=false
- **AND** 用戶提供有效的帳號和密碼
- **THEN** 使用預設租戶 ID
- **AND** 回傳 JWT token 和用戶資訊

#### Scenario: 租戶不存在
- **WHEN** 用戶提供不存在的租戶代碼
- **THEN** 回傳 401 Unauthorized「租戶不存在或已停用」

#### Scenario: 租戶已停用
- **WHEN** 用戶提供已停用租戶的代碼
- **THEN** 回傳 401 Unauthorized「租戶不存在或已停用」

### Requirement: Session Data Structure
系統 SHALL 維護包含租戶資訊的 session 資料結構：
- user_id: 用戶唯一識別碼
- **tenant_id: 租戶唯一識別碼**
- username: 用戶名稱
- **role: 用戶在租戶內的角色**
- created_at: session 建立時間
- expires_at: session 過期時間

#### Scenario: Session 包含租戶資訊
- **WHEN** 用戶成功登入
- **THEN** session 資料包含 tenant_id
- **AND** 後續 API 請求可從 session 取得租戶資訊

### Requirement: API Authentication Middleware
系統 SHALL 提供 API 認證中介層：
- 驗證 Authorization header 中的 JWT token
- 解析 token 取得 user_id 和 **tenant_id**
- 將 session 資料注入到請求上下文
- **自動為所有資料查詢加入租戶過濾**

#### Scenario: Token 驗證成功
- **WHEN** 請求包含有效的 JWT token
- **THEN** 從 token 取得 user_id 和 tenant_id
- **AND** 注入到請求上下文供後續使用

#### Scenario: Token 租戶不匹配
- **WHEN** token 中的 tenant_id 與 subdomain 不匹配
- **THEN** 回傳 401 Unauthorized
- **AND** 要求重新登入

## ADDED Requirements

### Requirement: Tenant Resolution
系統 SHALL 支援多種方式解析租戶識別：
- 優先順序：Subdomain > X-Tenant-ID Header > Body tenant_code
- 解析後驗證租戶存在且狀態為 active
- 單租戶模式時使用預設租戶

#### Scenario: Subdomain 解析
- **WHEN** 請求來自 acme.ching-tech.com
- **THEN** 解析 subdomain 為 "acme"
- **AND** 查詢對應的 tenant_id

#### Scenario: Header 解析
- **WHEN** 請求包含 X-Tenant-ID header
- **THEN** 使用 header 值作為租戶識別

### Requirement: Tenant Admin Authentication
系統 SHALL 支援租戶管理員和平台管理員的區分：
- 租戶管理員：管理自己租戶內的資源
- 平台管理員：管理所有租戶（超級管理員）
- 透過 role 欄位區分權限層級

#### Scenario: 平台管理員存取
- **WHEN** 用戶 role 為 platform_admin
- **THEN** 可存取 /api/admin/* 端點
- **AND** 可管理所有租戶

#### Scenario: 租戶管理員存取限制
- **WHEN** 用戶 role 為 tenant_admin
- **THEN** 只能存取自己租戶的資源
- **AND** 無法存取 /api/admin/* 端點
