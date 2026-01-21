# Proposal: 修復管理員管理功能

## 概述

目前平台管理員在管理租戶管理員時遇到以下問題：
1. 移除管理員後無法重新新增相同帳號（因為帳號仍存在於 users 表）
2. 無法從租戶現有使用者中指派管理員
3. 缺少平台管理員查詢租戶使用者的 API

## 問題分析

### 現況

```
移除管理員流程：
├─ 刪除 tenant_admins 記錄 ✓
└─ users 表中的帳號仍存在（預期行為）

新增管理員流程（使用已存在的 username）：
├─ 前端只支援「建立新帳號」模式
├─ 後端檢查 username 已存在
└─ 報錯「帳號已存在」 ✗
```

### 根本原因

1. **後端已支援兩種模式**，但前端只實作了一種：
   - 模式一：`user_id` - 從現有使用者選擇（未實作 UI）
   - 模式二：`username` - 建立新帳號（已實作）

2. **缺少 API** 讓平台管理員查詢租戶內的使用者列表

## 解決方案

### 1. 新增 API：列出租戶使用者

```
GET /api/admin/tenants/{tenant_id}/users
```

回傳租戶內所有使用者，讓平台管理員可以選擇指派為管理員。

### 2. 前端支援兩種新增管理員模式

新增管理員對話框提供兩個選項：
- **從現有使用者選擇**：下拉選單列出租戶內的使用者（排除已是管理員的）
- **建立新帳號**：現有功能

### 3. 移除管理員時的額外選項（可選）

提供選項讓平台管理員決定是否同時刪除使用者帳號：
- 僅移除管理員權限（預設，保留帳號）
- 移除管理員並刪除帳號

## 影響範圍

### 後端變更
- `api/admin/tenants.py`：新增 GET users endpoint
- `services/tenant.py`：新增 list_tenant_users 函數
- `services/tenant.py`：修改 remove_tenant_admin 支援刪除帳號選項

### 前端變更
- `js/platform-admin.js`：修改 openAddTenantAdminDialog
- `css/platform-admin.css`：新增相關樣式

## 不在此 Proposal 範圍

- 租戶管理員 UI 的修改（Tenant Admin app）
- 使用者權限管理的變更
- 密碼策略變更

## 相容性

- 完全向後相容
- 現有 API 不變
- 僅新增功能

## 時程估計

- Phase 1（API）：2-3 小時
- Phase 2（前端）：2-3 小時
- Phase 3（測試）：1 小時
