# Platform Admin UI 設計文件

## 架構概覽

```
平台管理應用程式 (platform-admin.js)
├── 側邊欄導航
│   ├── 租戶管理
│   └── Line 群組
├── 租戶管理區段
│   ├── 租戶列表（表格）
│   ├── 建立租戶（對話框）
│   └── 租戶詳情（面板/對話框）
└── Line 群組區段
    ├── 群組列表（表格）
    └── 變更租戶（對話框）
```

## UI 結構

### 應用程式佈局

參考現有 `tenant-admin.js` 的佈局模式：

```html
<div class="platform-admin-container">
  <!-- 側邊欄 -->
  <nav class="platform-admin-sidebar">
    <ul class="platform-admin-nav">
      <li data-section="tenants">租戶管理</li>
      <li data-section="line-groups">Line 群組</li>
    </ul>
  </nav>

  <!-- 主內容區 -->
  <main class="platform-admin-content">
    <section id="section-tenants">...</section>
    <section id="section-line-groups">...</section>
  </main>
</div>
```

### 租戶列表表格

| 代碼 | 名稱 | 狀態 | 方案 | 使用者 | 專案 | 操作 |
|------|------|------|------|--------|------|------|
| default | 預設租戶 | ✓ 啟用 | trial | 5 | 10 | 詳情 \| 停用 |

### 建立租戶表單

```
┌─────────────────────────────────┐
│ 建立新租戶                       │
├─────────────────────────────────┤
│ 租戶代碼 *   [________________] │
│ 租戶名稱 *   [________________] │
│ 方案         [trial ▼        ] │
│ 試用天數     [30             ] │
│ 儲存配額(MB) [5120           ] │
├─────────────────────────────────┤
│              [取消] [建立]      │
└─────────────────────────────────┘
```

### Line 群組列表

| 群組名稱 | 目前租戶 | 成員數 | 最後活動 | 操作 |
|----------|----------|--------|----------|------|
| 測試群組 | 預設租戶 | 3 | 2025-01-20 | 變更租戶 |

## CSS 命名規範

遵循專案既有模式（參考 tenant-admin.css）：

```css
/* 容器 */
.platform-admin-container { }
.platform-admin-sidebar { }
.platform-admin-content { }

/* 導航 */
.platform-admin-nav { }
.platform-admin-nav-item { }
.platform-admin-nav-item.active { }

/* 區段 */
.platform-admin-section { }
.platform-admin-section-title { }

/* 表格 */
.platform-admin-table { }
.platform-admin-table th { }
.platform-admin-table td { }

/* 對話框 */
.platform-admin-dialog-overlay { }
.platform-admin-dialog { }
.platform-admin-dialog-header { }
.platform-admin-dialog-body { }
.platform-admin-dialog-footer { }

/* 狀態 */
.platform-admin-loading { }
.platform-admin-error { }
.platform-admin-empty { }
```

## API 呼叫

### PlatformAdminAPI 物件

```javascript
const PlatformAdminAPI = {
  // 租戶
  listTenants: (params) => fetch('/api/admin/tenants', ...),
  createTenant: (data) => fetch('/api/admin/tenants', { method: 'POST', ... }),
  updateTenant: (id, data) => fetch(`/api/admin/tenants/${id}`, { method: 'PUT', ... }),
  suspendTenant: (id) => fetch(`/api/admin/tenants/${id}/suspend`, { method: 'POST' }),
  activateTenant: (id) => fetch(`/api/admin/tenants/${id}/activate`, { method: 'POST' }),
  getTenantUsage: (id) => fetch(`/api/admin/tenants/${id}/usage`),

  // Line 群組
  listLineGroups: (params) => fetch('/api/admin/tenants/line-groups', ...),
  updateLineGroupTenant: (groupId, newTenantId) =>
    fetch(`/api/admin/tenants/line-groups/${groupId}/tenant`, { method: 'PATCH', ... }),
};
```

## 權限控制

### 桌面圖示顯示條件

```javascript
// desktop.js
const applications = [
  // ... 其他應用程式
  {
    id: 'platform-admin',
    name: '平台管理',
    icon: 'shield-crown',
    // 僅平台管理員可見
    requireRole: 'platform_admin'
  },
];

// 過濾可見應用程式
function getVisibleApps() {
  const session = LoginModule.getSession();
  return applications.filter(app => {
    if (app.requireRole) {
      return session?.role === app.requireRole;
    }
    return true;
  });
}
```

### API 層權限

後端 API 已實作 `require_platform_admin()` 檢查，前端無需額外處理，但應顯示友善的錯誤訊息。

## 響應式設計

### 桌面版 (≥768px)
- 側邊欄固定寬度 200px
- 表格完整顯示所有欄位

### 手機版 (<768px)
- 底部 Tab Bar 取代側邊欄
- 表格改為卡片式顯示或水平滾動

## 深色主題

使用 CSS 變數確保相容：

```css
.platform-admin-container {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.platform-admin-table th {
  background: var(--bg-surface-dark);
  border-color: var(--border-light);
}
```
