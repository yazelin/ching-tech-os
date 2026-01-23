# Tasks: 修復權限管理系統

## Phase 1: 修復前端 App 權限判斷（緊急）

### 1.1 修改 permissions.js
- [x] 1.1.1 修改 `canAccessApp()` 函數
  - 平台管理員：所有權限
  - 租戶管理員：除了 platform-admin 外所有權限
  - 一般使用者：依據 permissions.apps 設定，**預設為 false**

- [x] 1.1.2 修改 `isAdmin()` 函數
  - 改為檢查 role 而非舊的 is_admin 欄位

### 1.2 驗證修復
- [ ] 1.2.1 測試一般使用者只能看到被允許的 app
- [ ] 1.2.2 測試租戶管理員可看到除了平台管理外的所有 app
- [ ] 1.2.3 測試平台管理員可看到所有 app

## Phase 2: 後端權限檢查統一

### 2.1 統一權限檢查函數
- [x] 2.1.1 在 `api/auth.py` 新增統一的 dependency 函數
  - `require_platform_admin()`
  - `require_tenant_admin_or_above()`
  - `require_can_manage_target()`

- [x] 2.1.2 新增權限階層檢查函數
  ```python
  ROLE_HIERARCHY = {"user": 1, "tenant_admin": 2, "platform_admin": 3}

  def can_manage_user(operator_role, target_role) -> bool:
      # platform_admin 可管理所有人
      # tenant_admin 只能管理 user
      # user 不能管理任何人
  ```

### 2.2 修改使用者列表 API
- [x] 2.2.1 修改 `GET /api/admin/users`
  - 平台管理員：可查詢所有租戶（新增 tenant_id 篩選參數）
  - 租戶管理員：自動篩選同租戶

- [x] 2.2.2 新增 `GET /api/tenant/users`
  - 租戶管理員專用 API
  - 自動限制為同租戶

### 2.3 修改使用者操作 API
- [x] 2.3.1 修改 `PATCH /api/admin/users/{id}/permissions`
  - 新增權限階層檢查
  - 禁止操作更高權限的使用者

- [x] 2.3.2 修改租戶 API 的使用者操作
  - `PATCH /api/tenant/users/{id}` - 新增權限階層檢查
  - `POST /api/tenant/users/{id}/reset-password` - 新增權限階層檢查
  - `POST /api/tenant/users/{id}/deactivate` - 新增權限階層檢查
  - `POST /api/tenant/users/{id}/activate` - 新增權限階層檢查

### 2.4 修改後端 is_admin 判斷
- [x] 2.4.1 修改 API 回應中的 `is_admin` 欄位
  - 改為基於 role 判斷（tenant_admin 或 platform_admin）
  - `/api/user/me` 和 `PATCH /api/user/me` 已更新

## Phase 3: 前端使用者管理介面

### 3.1 租戶管理員介面
- [x] 3.1.1 確認「使用者管理」在系統設定中對管理員可見
- [x] 3.1.2 修改使用者列表載入
  - 租戶管理員使用 `/api/tenant/users`
  - 平台管理員使用 `/api/admin/users`

- [x] 3.1.3 修改權限編輯功能
  - 根據權限階層判斷是否顯示「設定權限」按鈕
  - 使用 `canManageUser()` 函數檢查

### 3.2 平台管理員介面
- [x] 3.2.1 顯示使用者所屬租戶（平台管理員可見）
- [x] 3.2.2 顯示角色標籤（platform_admin、tenant_admin、user）
- [x] 3.2.3 根據權限階層顯示操作按鈕

## Phase 4: 測試

### 4.1 權限測試
- [ ] 4.1.1 測試一般使用者
  - 只能看到允許的 app
  - 不能存取使用者管理
  - 不能修改其他人的資料

- [ ] 4.1.2 測試租戶管理員
  - 可看到除了平台管理外的所有 app
  - 可管理同租戶的一般使用者
  - 不能看到其他租戶的使用者
  - 不能操作平台管理員

- [ ] 4.1.3 測試平台管理員
  - 可看到所有 app
  - 可管理所有租戶的使用者
  - 可指派/移除租戶管理員

---

## 變更記錄

### 2026-01-21 Phase 1-3 實作完成

#### 後端變更
- `api/auth.py`: 新增 `ROLE_HIERARCHY`、`can_manage_user()`、`require_platform_admin()`、`require_tenant_admin_or_above()`、`require_can_manage_target()` 權限檢查函數
- `api/user.py`:
  - 新增 `tenant_router` 路由，提供 `/api/tenant/users` API
  - 修改 `require_admin()` 改為基於 role 判斷
  - 修改 `/api/admin/users` 支援平台管理員查詢所有租戶
  - 修改權限更新 API 加入權限階層檢查
  - 修改 `/api/user/me` 的 `is_admin` 改為基於 role 判斷
- `api/tenant.py`: 在 `update_user`、`reset_password`、`deactivate_user_endpoint`、`activate_user_endpoint` 加入權限階層檢查
- `services/user.py`:
  - 新增 `get_all_users_cross_tenant()` 函數
  - 修改 `get_user_by_id()` 回傳 `tenant_id` 和 `role` 欄位
- `models/user.py`: `AdminUserInfo` 新增 `tenant_name` 欄位
- `main.py`: 註冊 `user.tenant_router`

#### 前端變更
- `js/permissions.js`:
  - 修改 `canAccessApp()` 預設為 false，並根據角色判斷
  - 修改 `isAdmin()` 改為基於 role 判斷
- `js/settings.js`:
  - 新增 `canManageUser()` 和 `getRoleDisplay()` 輔助函數
  - 修改 `loadUsersList()` 根據角色選擇 API
  - 修改 `renderUsersList()` 顯示角色標籤和根據權限階層顯示按鈕
- `js/icons.js`: 新增 `crown` 圖示
- `css/settings.css`: 新增 `.role-badge` 相關樣式
