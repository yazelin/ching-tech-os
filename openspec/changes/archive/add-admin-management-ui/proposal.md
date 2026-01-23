# Change: 新增平台與租戶管理 UI

## Why

目前多租戶平台的管理功能僅有後端 API，缺乏前端圖形化管理介面：

1. **平台管理員（yazelin）無法透過 UI**：
   - 建立新租戶
   - 管理租戶狀態（啟用/停用）
   - 為租戶建立管理員帳號
   - 管理 Line 群組綁定

2. **租戶管理員無法透過 UI**：
   - 管理租戶內的使用者
   - 新增/停用使用者帳號
   - 重設使用者密碼

後端 API 已完備（`/api/admin/tenants/*` 和 `/api/tenants/*`），但沒有對應的前端介面，導致所有管理操作都必須透過 curl 或其他工具執行。

## What Changes

### 新增檔案

| 檔案 | 用途 |
|------|------|
| `js/platform-admin.js` | 平台管理應用程式（僅 platform_admin 可用）|
| `css/platform-admin.css` | 平台管理樣式 |
| `js/tenant-admin.js` | 租戶管理應用程式（tenant_admin 可用）|
| `css/tenant-admin.css` | 租戶管理樣式 |

### 修改檔案

| 檔案 | 變更 |
|------|------|
| `index.html` | 引入新的 JS/CSS 檔案 |
| `js/api-client.js` | 新增 PlatformAdminAPI 和 TenantAdminAPI 方法 |

### 功能範圍

#### Platform Admin（平台管理）
- 租戶列表：顯示所有租戶、狀態、使用量
- 建立租戶：表單輸入 code、名稱、方案
- 租戶詳情：查看設定、管理員列表
- 租戶管理員：新增/移除租戶管理員帳號
- 租戶狀態：啟用/停用租戶
- Line 群組：列出群組、變更群組所屬租戶
- Line Bot 設定：為租戶設定 Line Bot Channel

#### Tenant Admin（租戶管理）
- 使用者列表：顯示租戶內所有使用者
- 新增使用者：建立新帳號並設定臨時密碼
- 使用者管理：編輯、停用/啟用、重設密碼
- 租戶資訊：查看租戶使用量和設定

## Impact

### 使用現有 API

不需要修改後端，所有 API 已完備：

**Platform Admin API** (`/api/admin/tenants`):
- `GET /` - 列出租戶
- `POST /` - 建立租戶
- `GET /{id}` - 租戶詳情
- `PUT /{id}` - 更新租戶
- `POST /{id}/suspend` - 停用租戶
- `POST /{id}/activate` - 啟用租戶
- `GET /{id}/usage` - 使用量統計
- `GET /{id}/admins` - 列出管理員
- `POST /{id}/admins` - 新增管理員
- `DELETE /{id}/admins/{user_id}` - 移除管理員
- `GET /line-groups` - 列出 Line 群組
- `PATCH /line-groups/{id}/tenant` - 變更群組租戶
- `GET /{id}/linebot` - 取得 Line Bot 設定
- `PUT /{id}/linebot` - 更新 Line Bot 設定
- `POST /{id}/linebot/test` - 測試 Line Bot
- `DELETE /{id}/linebot` - 刪除 Line Bot 設定

**Tenant Admin API** (`/api/tenants`):
- `GET /info` - 租戶資訊
- `GET /usage` - 使用量
- `GET /users` - 使用者列表
- `POST /users` - 新增使用者
- `GET /users/{id}` - 使用者詳情
- `PATCH /users/{id}` - 更新使用者
- `POST /users/{id}/reset-password` - 重設密碼
- `POST /users/{id}/deactivate` - 停用使用者
- `POST /users/{id}/activate` - 啟用使用者

### 權限控制

- Platform Admin 應用程式：僅 `platform_admin` 角色可見
- Tenant Admin 應用程式：`platform_admin` 和 `tenant_admin` 角色可見

### 不影響

- 現有桌面應用程式功能
- 後端 API 結構
- 一般使用者操作流程
