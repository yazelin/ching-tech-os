# Design: 平台與租戶管理 UI

## 架構概覽

```
桌面應用程式
├── Platform Admin（平台管理）
│   ├── 側邊欄導航
│   │   ├── 租戶管理
│   │   ├── Line 群組
│   │   └── Line Bot 設定
│   ├── 租戶列表（表格）
│   ├── 建立租戶（對話框）
│   ├── 租戶詳情（面板）
│   │   ├── 基本資訊
│   │   ├── 使用量統計
│   │   ├── 管理員列表
│   │   └── Line Bot 設定
│   └── Line 群組管理
│       ├── 群組列表
│       └── 變更租戶（對話框）
│
└── Tenant Admin（租戶管理）
    ├── 側邊欄導航
    │   ├── 使用者管理
    │   └── 租戶資訊
    ├── 使用者列表（表格）
    ├── 新增使用者（對話框）
    ├── 使用者詳情（面板）
    └── 租戶資訊面板
```

## UI 設計

### 共用佈局模式

參考現有應用程式（如 project-management），採用側邊欄 + 主內容區佈局：

```html
<div class="[app]-container">
  <!-- 側邊欄 -->
  <nav class="[app]-sidebar">
    <ul class="[app]-nav">
      <li class="[app]-nav-item active" data-section="xxx">區段名稱</li>
    </ul>
  </nav>

  <!-- 主內容區 -->
  <main class="[app]-content">
    <section class="[app]-section" id="section-xxx">
      <!-- 標題列 -->
      <div class="[app]-section-header">
        <h2>區段標題</h2>
        <div class="[app]-section-actions">
          <button>操作按鈕</button>
        </div>
      </div>
      <!-- 內容 -->
      <div class="[app]-section-body">
        ...
      </div>
    </section>
  </main>
</div>
```

### Platform Admin UI

#### 租戶列表

| 代碼 | 名稱 | 狀態 | 方案 | 使用者 | 專案 | 操作 |
|------|------|------|------|--------|------|------|
| default | 預設租戶 | ✓ 啟用 | standard | 5 | 10 | 詳情 |
| company1 | 測試公司 | ⏸ 停用 | trial | 2 | 3 | 詳情 |

篩選功能：
- 狀態篩選：全部 / 啟用 / 停用 / 試用中
- 方案篩選：全部 / standard / trial

#### 建立租戶對話框

```
┌─────────────────────────────────────────┐
│ 建立新租戶                          [X] │
├─────────────────────────────────────────┤
│                                         │
│ 租戶代碼 *                              │
│ ┌─────────────────────────────────────┐ │
│ │ company1                            │ │
│ └─────────────────────────────────────┘ │
│ 小寫英文、數字、底線，2-50 字元         │
│                                         │
│ 租戶名稱 *                              │
│ ┌─────────────────────────────────────┐ │
│ │ 測試公司股份有限公司                │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 方案                                    │
│ ┌─────────────────────────────────────┐ │
│ │ standard                        [v] │ │
│ └─────────────────────────────────────┘ │
│                                         │
├─────────────────────────────────────────┤
│                    [取消]    [建立租戶] │
└─────────────────────────────────────────┘
```

#### 租戶詳情面板

```
┌─────────────────────────────────────────┐
│ 測試公司                           [X]  │
├─────────────────────────────────────────┤
│ [基本資訊] [管理員] [Line Bot]          │
├─────────────────────────────────────────┤
│                                         │
│ 基本資訊                                │
│ ─────────────────────────────────────── │
│ 代碼：company1                          │
│ 狀態：✓ 啟用        [停用租戶]          │
│ 方案：standard                          │
│ 建立時間：2025-01-20                    │
│                                         │
│ 使用量統計                              │
│ ─────────────────────────────────────── │
│ 使用者數：5 人                          │
│ 專案數：10 個                           │
│ 知識庫：25 筆                           │
│ AI 使用量：1,234 次                     │
│                                         │
└─────────────────────────────────────────┘
```

#### 租戶管理員 Tab

```
┌─────────────────────────────────────────┐
│ 管理員列表                  [新增管理員]│
├─────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐ │
│ │ 👤 admin1                           │ │
│ │    管理員                   [移除]  │ │
│ ├─────────────────────────────────────┤ │
│ │ 👤 manager                          │ │
│ │    經理                     [移除]  │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ℹ️ 管理員可管理租戶內的使用者和設定     │
└─────────────────────────────────────────┘
```

新增管理員對話框：
```
┌─────────────────────────────────────────┐
│ 新增租戶管理員                     [X]  │
├─────────────────────────────────────────┤
│                                         │
│ 使用者名稱 *                            │
│ ┌─────────────────────────────────────┐ │
│ │ newadmin                            │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 顯示名稱                                │
│ ┌─────────────────────────────────────┐ │
│ │ 新管理員                            │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 初始密碼 *                              │
│ ┌─────────────────────────────────────┐ │
│ │ ••••••••                            │ │
│ └─────────────────────────────────────┘ │
│ ☑ 首次登入需變更密碼                    │
│                                         │
├─────────────────────────────────────────┤
│                    [取消]    [建立帳號] │
└─────────────────────────────────────────┘
```

#### Line 群組管理

| 群組名稱 | 目前租戶 | 成員數 | 最後活動 | 操作 |
|----------|----------|--------|----------|------|
| 測試群組 | 預設租戶 | 3 | 2025-01-20 | [變更租戶] |
| 公司群組 | (未綁定) | 5 | 2025-01-19 | [變更租戶] |

### Tenant Admin UI

#### 使用者列表

| 帳號 | 顯示名稱 | 角色 | 狀態 | 最後登入 | 操作 |
|------|----------|------|------|----------|------|
| admin1 | 管理員 | tenant_admin | ✓ 啟用 | 2025-01-20 | [編輯] |
| user1 | 使用者一 | user | ✓ 啟用 | 2025-01-19 | [編輯] |
| user2 | 使用者二 | user | ⏸ 停用 | 2025-01-15 | [編輯] |

#### 新增使用者對話框

```
┌─────────────────────────────────────────┐
│ 新增使用者                         [X]  │
├─────────────────────────────────────────┤
│                                         │
│ 使用者名稱 *                            │
│ ┌─────────────────────────────────────┐ │
│ │ newuser                             │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 顯示名稱                                │
│ ┌─────────────────────────────────────┐ │
│ │ 新使用者                            │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 初始密碼 *                              │
│ ┌─────────────────────────────────────┐ │
│ │ ••••••••                            │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 角色                                    │
│ ┌─────────────────────────────────────┐ │
│ │ user                            [v] │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ☑ 首次登入需變更密碼                    │
│                                         │
├─────────────────────────────────────────┤
│                    [取消]    [建立帳號] │
└─────────────────────────────────────────┘
```

#### 使用者詳情/編輯面板

```
┌─────────────────────────────────────────┐
│ 使用者詳情：user1                  [X]  │
├─────────────────────────────────────────┤
│                                         │
│ 使用者名稱                              │
│ user1 (不可修改)                        │
│                                         │
│ 顯示名稱                                │
│ ┌─────────────────────────────────────┐ │
│ │ 使用者一                            │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 角色                                    │
│ ┌─────────────────────────────────────┐ │
│ │ user                            [v] │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 狀態：✓ 啟用                            │
│ 建立時間：2025-01-15                    │
│ 最後登入：2025-01-20 10:30              │
│                                         │
│ 密碼管理                                │
│ ─────────────────────────────────────── │
│ [重設密碼]                              │
│                                         │
├─────────────────────────────────────────┤
│ [停用帳號]      [取消]    [儲存變更]    │
└─────────────────────────────────────────┘
```

## CSS 命名規範

### Platform Admin

```css
/* 容器 */
.pa-container { }
.pa-sidebar { }
.pa-content { }

/* 導航 */
.pa-nav { }
.pa-nav-item { }
.pa-nav-item.active { }

/* 區段 */
.pa-section { }
.pa-section-header { }
.pa-section-body { }

/* 表格 */
.pa-table { }
.pa-table-row { }
.pa-status-badge { }
.pa-status-badge.active { }
.pa-status-badge.suspended { }

/* 對話框 */
.pa-dialog-overlay { }
.pa-dialog { }
.pa-dialog-header { }
.pa-dialog-body { }
.pa-dialog-footer { }

/* 詳情面板 */
.pa-detail-panel { }
.pa-detail-tabs { }
.pa-detail-content { }

/* 表單 */
.pa-form-group { }
.pa-form-label { }
.pa-form-input { }
.pa-form-hint { }
.pa-form-error { }
```

### Tenant Admin

```css
/* 容器 */
.ta-container { }
.ta-sidebar { }
.ta-content { }

/* 類似 Platform Admin 的命名模式，前綴改為 ta- */
```

## API Client 設計

### PlatformAdminAPI

```javascript
const PlatformAdminAPI = {
  // 租戶管理
  listTenants: (params) => APIClient.get('/admin/tenants', { params }),
  createTenant: (data) => APIClient.post('/admin/tenants', data),
  getTenant: (id) => APIClient.get(`/admin/tenants/${id}`),
  updateTenant: (id, data) => APIClient.put(`/admin/tenants/${id}`, data),
  suspendTenant: (id) => APIClient.post(`/admin/tenants/${id}/suspend`),
  activateTenant: (id) => APIClient.post(`/admin/tenants/${id}/activate`),
  getTenantUsage: (id) => APIClient.get(`/admin/tenants/${id}/usage`),

  // 租戶管理員
  listTenantAdmins: (id) => APIClient.get(`/admin/tenants/${id}/admins`),
  addTenantAdmin: (id, data) => APIClient.post(`/admin/tenants/${id}/admins`, data),
  removeTenantAdmin: (id, userId) => APIClient.delete(`/admin/tenants/${id}/admins/${userId}`),

  // Line 群組
  listLineGroups: (params) => APIClient.get('/admin/tenants/line-groups', { params }),
  updateLineGroupTenant: (groupId, tenantId) =>
    APIClient.patch(`/admin/tenants/line-groups/${groupId}/tenant`, { tenant_id: tenantId }),

  // Line Bot 設定
  getLineBotSettings: (id) => APIClient.get(`/admin/tenants/${id}/linebot`),
  updateLineBotSettings: (id, data) => APIClient.put(`/admin/tenants/${id}/linebot`, data),
  testLineBot: (id) => APIClient.post(`/admin/tenants/${id}/linebot/test`),
  deleteLineBot: (id) => APIClient.delete(`/admin/tenants/${id}/linebot`),
};
```

### TenantAdminAPI

```javascript
const TenantAdminAPI = {
  // 租戶資訊
  getInfo: () => APIClient.get('/tenants/info'),
  getUsage: () => APIClient.get('/tenants/usage'),

  // 使用者管理
  listUsers: (params) => APIClient.get('/tenants/users', { params }),
  createUser: (data) => APIClient.post('/tenants/users', data),
  getUser: (id) => APIClient.get(`/tenants/users/${id}`),
  updateUser: (id, data) => APIClient.patch(`/tenants/users/${id}`, data),
  resetPassword: (id, newPassword) =>
    APIClient.post(`/tenants/users/${id}/reset-password`, { new_password: newPassword }),
  deactivateUser: (id) => APIClient.post(`/tenants/users/${id}/deactivate`),
  activateUser: (id) => APIClient.post(`/tenants/users/${id}/activate`),
};
```

## 響應式設計

### 桌面版 (≥768px)
- 側邊欄固定寬度 200px
- 表格完整顯示所有欄位
- 對話框置中顯示

### 手機版 (<768px)
- 側邊欄改為底部 Tab Bar 或漢堡選單
- 表格改為卡片式顯示
- 對話框全螢幕顯示

## 權限檢查

### 桌面圖示顯示

```javascript
// desktop.js 已有的 requireRole 機制
{ id: 'platform-admin', ..., requireRole: 'platform_admin' },
{ id: 'tenant-admin', ..., requireRole: ['platform_admin', 'tenant_admin'] },
```

### API 層

後端 API 已有權限檢查，前端只需顯示友善的錯誤訊息。

## 深色主題

使用 CSS 變數確保相容（參考 main.css）：

```css
.pa-container {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.pa-table th {
  background: var(--bg-surface-dark);
  border-color: var(--border-light);
}

.pa-status-badge.active {
  background: var(--color-success);
}

.pa-status-badge.suspended {
  background: var(--color-warning);
}
```
