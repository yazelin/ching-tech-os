# Change: 新增平台管理 UI

## Why

目前多租戶平台的管理功能只有 API，缺乏圖形化管理介面。平台管理員（ADMIN_USERNAME）需要透過 curl 或其他工具才能：

1. **建立新租戶**：新公司/組織註冊時需要建立租戶
2. **管理租戶狀態**：啟用、停用租戶
3. **管理 Line 群組**：將群組綁定到正確的租戶
4. **查看平台使用情況**：監控各租戶的使用量

這對於日常運維非常不便，需要一個專屬的平台管理 UI。

## What Changes

### 新增前端應用程式
- 建立 `js/platform-admin.js` - 平台管理應用程式
- 建立 `css/platform-admin.css` - 平台管理樣式
- 在 `desktop.js` 註冊新應用程式（僅平台管理員可見）

### 功能模組
1. **租戶列表**：顯示所有租戶、狀態、使用量
2. **建立租戶**：表單輸入 code、名稱、方案、試用天數
3. **租戶詳情**：查看/編輯租戶設定、管理員列表
4. **Line 群組管理**：列出所有群組、變更群組所屬租戶

### 現有 API
後端 API 已完備（`/api/admin/tenants/*`），無需新增：
- `GET /api/admin/tenants` - 列出租戶
- `POST /api/admin/tenants` - 建立租戶
- `PUT /api/admin/tenants/{id}` - 更新租戶
- `POST /api/admin/tenants/{id}/suspend` - 停用
- `POST /api/admin/tenants/{id}/activate` - 啟用
- `GET /api/admin/tenants/{id}/usage` - 使用量
- `GET /api/admin/tenants/line-groups` - Line 群組列表
- `PATCH /api/admin/tenants/line-groups/{id}/tenant` - 變更群組租戶

## Impact

### Affected Files
- `frontend/js/platform-admin.js` - 新增
- `frontend/css/platform-admin.css` - 新增
- `frontend/js/desktop.js` - 修改（新增應用程式）
- `frontend/js/api-client.js` - 修改（新增 API 方法）
- `frontend/index.html` - 修改（引入新檔案）
- `frontend/login.html` - 修改（引入新檔案）

### 權限控制
- 應用程式僅對 `platform_admin` 角色可見
- API 層已有權限檢查，前端僅為 UI 層

### 不影響
- 現有租戶管理（tenant-admin.js）功能
- 一般使用者操作流程
- 後端 API 結構
