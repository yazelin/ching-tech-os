# Proposal: 修復權限管理系統

## 問題描述

目前權限管理系統有多個嚴重問題：

### 1. App 權限預設值錯誤
**位置**: `frontend/js/permissions.js:75`
```javascript
return user.permissions?.apps?.[appId] ?? true;  // 預設為 true
```
**問題**: 當權限未設定時，預設允許存取，導致使用者看到所有 app

### 2. 使用者列表能見度問題
- 平台管理員應該看到所有租戶的使用者
- 租戶管理員只能看到同一租戶內的使用者
- 目前沒有正確的租戶隔離

### 3. 操作權限階層問題
正確的權限階層應該是：
```
platform_admin > tenant_admin > user
```
- 租戶管理員不應該能操作平台管理員
- 租戶管理員不應該能操作其他租戶的使用者
- 一般使用者只能管理自己的資料

### 4. 後端 API 權限檢查不一致
- `/api/admin/users` 使用舊的 `is_admin()` 檢查
- 沒有正確區分 `platform_admin` 和 `tenant_admin`
- 沒有租戶隔離檢查

## 解決方案

### Phase 1: 修復前端 App 權限判斷（緊急）

修改 `canAccessApp()` 邏輯：
```javascript
function canAccessApp(appId) {
  const user = getCurrentUser();
  if (!user) return false;

  // 平台管理員擁有所有權限
  if (user.role === 'platform_admin') return true;

  // 租戶管理員擁有所有權限（除了平台管理）
  if (user.role === 'tenant_admin') {
    // 平台管理 app 需要 platform_admin
    const platformOnlyApps = ['platform-admin'];
    if (platformOnlyApps.includes(appId)) return false;
    return true;
  }

  // 一般使用者：檢查權限設定，預設為 false
  if (!user.permissions?.apps) return false;
  return user.permissions.apps[appId] === true;
}
```

### Phase 2: 後端權限檢查統一

1. **新增統一的權限檢查函數**：
   - `require_platform_admin()` - 僅平台管理員
   - `require_tenant_admin_or_above()` - 租戶管理員或平台管理員
   - `require_same_tenant()` - 確保操作對象在同一租戶

2. **修改使用者列表 API**：
   - 平台管理員：可查詢所有租戶使用者
   - 租戶管理員：只能查詢同租戶使用者

3. **修改使用者操作 API**：
   - 新增權限階層檢查
   - 禁止越權操作

### Phase 3: 前端使用者管理介面

1. **租戶管理員的管理介面**：
   - 使用 `/api/tenant/users` 取得同租戶使用者
   - 只能設定一般使用者的權限

2. **平台管理員的管理介面**（現有）：
   - 可選擇租戶篩選
   - 可管理租戶管理員

## 影響範圍

### 後端
- `api/user.py` - 使用者管理 API
- `api/tenant.py` - 租戶相關 API
- `api/admin/tenants.py` - 平台管理 API
- `services/user.py` - 使用者服務

### 前端
- `js/permissions.js` - 權限判斷模組
- `js/desktop.js` - 桌面應用程式顯示
- `js/user-management.js` - 使用者管理介面
- `js/platform-admin.js` - 平台管理介面

## 風險評估

- **低風險**: 修改權限預設值可能影響現有使用者體驗
- **中風險**: 後端權限檢查修改需要全面測試

## 時程建議

- Phase 1: 緊急修復（立即）
- Phase 2: 後端權限統一（1-2 天）
- Phase 3: 前端介面調整（1 天）
