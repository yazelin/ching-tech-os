# Tasks: 修復管理員管理功能

## Phase 1: 後端 API

### 1.1 列出租戶使用者 API
- [x] 1.1.1 在 `services/tenant.py` 新增 `list_tenant_users()` 函數
  - 參數：`tenant_id: UUID | str`
  - 回傳：使用者列表（id, username, display_name, role, is_admin）
  - 排除已停用的使用者（可選參數控制）

- [x] 1.1.2 在 `models/tenant.py` 新增回應模型
  ```python
  class TenantUserBrief(BaseModel):
      id: int
      username: str
      display_name: str | None
      role: str
      is_admin: bool  # 是否已是此租戶的管理員

  class TenantUserListResponse(BaseModel):
      users: list[TenantUserBrief]
  ```

- [x] 1.1.3 在 `api/admin/tenants.py` 新增 endpoint
  ```
  GET /api/admin/tenants/{tenant_id}/users
  ```
  - 僅平台管理員可存取
  - 回傳 TenantUserListResponse

### 1.2 移除管理員時可選刪除帳號
- [x] 1.2.1 修改 `remove_tenant_admin()` 函數
  - 新增參數：`delete_user: bool = False`
  - 如果 `delete_user=True`，同時刪除 users 表記錄

- [x] 1.2.2 修改 DELETE endpoint
  ```
  DELETE /api/admin/tenants/{tenant_id}/admins/{user_id}?delete_user=true
  ```
  - 新增 query parameter `delete_user`

## Phase 2: 前端 UI

### 2.1 新增管理員對話框改版
- [x] 2.1.1 修改 `openAddTenantAdminDialog()` 支援兩種模式
  - 新增 Tab 切換：「從現有使用者選擇」/「建立新帳號」

- [x] 2.1.2 實作「從現有使用者選擇」模式
  - 呼叫 API 取得使用者列表
  - 下拉選單顯示可選使用者（排除已是管理員的）
  - 選擇後送出 `{ user_id: xxx, role: "admin" }`

- [x] 2.1.3 保留「建立新帳號」模式（現有功能）
  - 維持原有的 username、display_name、password 表單

- [x] 2.1.4 新增相關 CSS 樣式
  - Tab 切換樣式（`.admin-mode-tabs`, `.admin-mode-tab`）
  - 下拉選單樣式（`#existingUserSelect`）

### 2.2 移除管理員確認對話框
- [x] 2.2.1 修改 `removeTenantAdmin()` 確認對話框
  - 改用自訂對話框取代 `confirm()`
  - 新增 checkbox：「同時刪除此使用者帳號」
  - 預設不勾選

- [x] 2.2.2 根據選項呼叫 API
  - 勾選時：`DELETE ...?delete_user=true`
  - 未勾選時：`DELETE ...`（現有行為）

## Phase 3: 測試

### 3.1 API 測試
- [ ] 3.1.1 測試 GET /admin/tenants/{id}/users
  - 正確回傳租戶使用者列表
  - 非平台管理員無法存取
  - 租戶不存在時回傳 404

- [ ] 3.1.2 測試 DELETE with delete_user
  - `delete_user=false`：僅移除 tenant_admins 記錄
  - `delete_user=true`：同時刪除 users 記錄

### 3.2 前端測試
- [ ] 3.2.1 測試「從現有使用者選擇」流程
  - 選擇使用者並新增為管理員
  - 成功後列表更新

- [ ] 3.2.2 測試「建立新帳號」流程（現有功能）
  - 確認仍正常運作

- [ ] 3.2.3 測試移除管理員流程
  - 僅移除權限（帳號保留）
  - 移除並刪除帳號

- [ ] 3.2.4 測試完整流程
  - 新增管理員 → 移除（僅權限）→ 重新從現有使用者選擇 → 成功

---

## 實作備註

### API 設計考量

**為什麼需要新的 endpoint？**

現有的 `/api/user/list` 和 `/api/admin/users` 需要該租戶的 session token，
平台管理員的 token 是屬於平台層級，不能直接存取租戶內的使用者資料。
因此需要新的 `/api/admin/tenants/{id}/users` endpoint。

### 安全性考量

1. **刪除帳號是敏感操作**
   - 確認對話框需明確告知後果
   - 可考慮要求輸入確認文字

2. **權限檢查**
   - 所有新 API 都需要 `require_platform_admin`

## 變更摘要

### 後端變更
- `models/tenant.py`: 新增 `TenantUserBrief`, `TenantUserListResponse` 模型
- `services/tenant.py`: 新增 `list_tenant_users()` 函數，修改 `remove_tenant_admin()` 支援 `delete_user` 參數
- `api/admin/tenants.py`: 新增 `GET /{tenant_id}/users` endpoint，修改 `DELETE /{tenant_id}/admins/{user_id}` 支援 `delete_user` query param

### 前端變更
- `js/platform-admin.js`:
  - `openAddTenantAdminDialog()`: 支援兩種模式切換
  - `loadTenantUsersForSelect()`: 新函數，載入租戶使用者供選擇
  - `removeTenantAdmin()`: 改用自訂確認對話框，支援刪除帳號選項
- `css/platform-admin.css`: 新增 `.admin-mode-tabs`, `.admin-mode-tab`, `#existingUserSelect` 樣式
