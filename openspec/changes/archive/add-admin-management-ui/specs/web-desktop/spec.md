## ADDED Requirements

### Requirement: Platform Admin Application
The system SHALL provide a Platform Admin application accessible only to users with `platform_admin` role.

#### Scenario: Platform admin opens application
- **WHEN** a user with `platform_admin` role clicks the "平台管理" icon on desktop
- **THEN** the Platform Admin window opens with tenant management interface

#### Scenario: Non-admin cannot see application
- **WHEN** a user without `platform_admin` role views the desktop
- **THEN** the "平台管理" icon is not visible

### Requirement: Platform Admin Tenant Management
The Platform Admin application SHALL allow managing tenants including listing, creating, viewing details, and changing status.

#### Scenario: List tenants
- **WHEN** platform admin opens the tenant management section
- **THEN** all tenants are displayed in a table with code, name, status, plan, user count, and project count

#### Scenario: Create tenant
- **WHEN** platform admin fills the create tenant form with valid code, name, and plan
- **THEN** a new tenant is created and appears in the tenant list

#### Scenario: View tenant details
- **WHEN** platform admin clicks on a tenant row
- **THEN** a detail panel shows tenant information, usage statistics, and admin list

#### Scenario: Suspend tenant
- **WHEN** platform admin clicks "停用租戶" for an active tenant and confirms
- **THEN** the tenant status changes to suspended

#### Scenario: Activate tenant
- **WHEN** platform admin clicks "啟用租戶" for a suspended tenant
- **THEN** the tenant status changes to active

### Requirement: Platform Admin Tenant Administrator Management
The Platform Admin application SHALL allow managing tenant administrators.

#### Scenario: List tenant admins
- **WHEN** platform admin views a tenant's admin tab
- **THEN** all administrators for that tenant are displayed

#### Scenario: Add tenant admin
- **WHEN** platform admin fills the add admin form with username, display name, and password
- **THEN** a new tenant admin account is created with the specified credentials

#### Scenario: Remove tenant admin
- **WHEN** platform admin clicks remove on an admin and confirms
- **THEN** the admin is removed from the tenant (account remains but loses admin role)

### Requirement: Platform Admin Line Group Management
The Platform Admin application SHALL allow managing Line group tenant assignments.

#### Scenario: List Line groups
- **WHEN** platform admin opens the Line group section
- **THEN** all Line groups are displayed with name, current tenant, member count, and last activity

#### Scenario: Change Line group tenant
- **WHEN** platform admin selects a new tenant for a group and confirms
- **THEN** the group is reassigned to the new tenant

### Requirement: Platform Admin Line Bot Settings
The Platform Admin application SHALL allow configuring Line Bot settings per tenant.

#### Scenario: View Line Bot settings
- **WHEN** platform admin views a tenant's Line Bot tab
- **THEN** current Line Bot configuration is displayed (or "not configured" message)

#### Scenario: Configure Line Bot
- **WHEN** platform admin fills channel ID, secret, and access token
- **THEN** the tenant's Line Bot is configured with the provided credentials

#### Scenario: Test Line Bot
- **WHEN** platform admin clicks "測試連線"
- **THEN** the system verifies the Line Bot credentials and shows success or failure

### Requirement: Tenant Admin Application
The system SHALL provide a Tenant Admin application accessible to users with `tenant_admin` or `platform_admin` role.

#### Scenario: Tenant admin opens application
- **WHEN** a user with `tenant_admin` role clicks the "租戶管理" icon
- **THEN** the Tenant Admin window opens with user management interface

#### Scenario: Regular user cannot see application
- **WHEN** a user with only `user` role views the desktop
- **THEN** the "租戶管理" icon is not visible

### Requirement: Tenant Admin User Management
The Tenant Admin application SHALL allow managing users within the tenant.

#### Scenario: List users
- **WHEN** tenant admin opens the user management section
- **THEN** all users in the tenant are displayed with username, display name, role, status, and last login

#### Scenario: Create user
- **WHEN** tenant admin fills the create user form with username, display name, password, and role
- **THEN** a new user account is created in the tenant

#### Scenario: Edit user
- **WHEN** tenant admin modifies a user's display name or role and saves
- **THEN** the user information is updated

#### Scenario: Reset user password
- **WHEN** tenant admin clicks "重設密碼" and enters a new password
- **THEN** the user's password is changed and they must change it on next login

#### Scenario: Deactivate user
- **WHEN** tenant admin clicks "停用帳號" and confirms
- **THEN** the user account is deactivated and cannot login

#### Scenario: Activate user
- **WHEN** tenant admin clicks "啟用帳號" on a deactivated user
- **THEN** the user account is reactivated

### Requirement: Tenant Admin Tenant Info
The Tenant Admin application SHALL display tenant information and usage statistics.

#### Scenario: View tenant info
- **WHEN** tenant admin opens the tenant info section
- **THEN** tenant details including name, plan, and usage statistics are displayed
