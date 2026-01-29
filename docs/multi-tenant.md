# 多租戶架構

ChingTech OS 支援多租戶 (Multi-tenant) 部署模式，允許多個組織在同一系統上運作，同時保持資料完全隔離。

## 概述

### 部署模式

系統支援兩種部署模式：

1. **單租戶模式** (預設)
   - 適合單一組織內部使用
   - 所有資料自動歸屬預設租戶
   - 無需額外設定

2. **多租戶模式**
   - 適合 SaaS 服務或多組織部署
   - 每個組織有獨立的資料空間
   - 需設定 `MULTI_TENANT_MODE=true`

### 資料隔離策略

採用 **Shared Database, Shared Schema** 策略：

```
┌─────────────────────────────────────────────────────┐
│                    PostgreSQL                        │
├─────────────────────────────────────────────────────┤
│  tenants          │ id, code, name, settings        │
│  users            │ id, tenant_id, username, ...    │
│  projects         │ id, tenant_id, name, ...        │
│  inventory_items  │ id, tenant_id, name, ...        │
│  ...              │ id, tenant_id, ...              │
└─────────────────────────────────────────────────────┘
```

- 所有核心資料表都包含 `tenant_id` 欄位
- 查詢自動過濾當前租戶的資料
- 透過複合索引確保查詢效能

## 啟用多租戶模式

### 環境變數

```bash
# .env
MULTI_TENANT_MODE=true
DEFAULT_TENANT_ID=00000000-0000-0000-0000-000000000000
```

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `MULTI_TENANT_MODE` | 是否啟用多租戶模式 | `false` |
| `DEFAULT_TENANT_ID` | 預設租戶 UUID | `00000000-0000-0000-0000-000000000000` |

### 登入流程

**多租戶模式**：
1. 使用者輸入租戶代碼（公司代碼）
2. 系統驗證租戶代碼是否存在
3. 使用 NAS SMB 帳號密碼驗證身份
4. Session 自動綁定租戶

**單租戶模式**：
1. 直接輸入帳號密碼
2. 自動使用預設租戶

## 架構設計

### 檔案系統結構

```
/mnt/nas/ctos/
├── system/                           # 系統共用檔案
└── tenants/
    ├── {tenant-uuid-1}/
    │   ├── knowledge/                # 知識庫
    │   │   ├── entries/
    │   │   └── assets/
    │   ├── linebot/                  # Line Bot 檔案
    │   ├── ai-generated/             # AI 生成檔案
    │   └── attachments/              # 附件
    └── {tenant-uuid-2}/
        └── ...
```

### Session 結構

```python
@dataclass
class SessionData:
    user_id: int
    tenant_id: UUID          # 租戶 ID
    username: str
    role: str                # user, tenant_admin, platform_admin
    created_at: datetime
    expires_at: datetime
```

### 資料庫查詢

所有資料操作自動帶入 `tenant_id` 過濾：

```python
# services/project.py
async def list_projects(tenant_id: UUID) -> list[Project]:
    async with get_connection() as conn:
        rows = await conn.fetch("""
            SELECT * FROM projects
            WHERE tenant_id = $1 AND status != 'deleted'
            ORDER BY created_at DESC
        """, tenant_id)
        return [Project(**row) for row in rows]
```

## API 參考

### 租戶自助 API

供租戶管理員使用：

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/tenant/info` | GET | 取得租戶資訊 |
| `/api/tenant/usage` | GET | 取得使用量統計 |
| `/api/tenant/settings` | PUT | 更新租戶設定 |
| `/api/tenant/admins` | GET | 列出租戶管理員 |
| `/api/tenant/admins` | POST | 新增租戶管理員 |
| `/api/tenant/admins/{user_id}` | DELETE | 移除租戶管理員 |
| `/api/tenant/export` | POST | 匯出租戶資料 |
| `/api/tenant/import` | POST | 匯入租戶資料 |
| `/api/tenant/validate` | GET | 驗證資料完整性 |

### 平台管理 API

供平台管理員使用：

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/admin/tenants` | GET | 列出所有租戶 |
| `/api/admin/tenants` | POST | 建立新租戶 |
| `/api/admin/tenants/{id}` | GET | 取得租戶詳情 |
| `/api/admin/tenants/{id}` | PATCH | 更新租戶 |
| `/api/admin/tenants/{id}` | DELETE | 刪除租戶 |
| `/api/admin/tenants/{id}/admins` | GET | 列出租戶管理員 |

### 登入 API 變更

```
POST /api/auth/login
Content-Type: application/json

{
    "username": "john",
    "password": "secret",
    "tenant_code": "acme"    // 多租戶模式必填
}

Response:
{
    "success": true,
    "token": "...",
    "username": "john",
    "tenant": {
        "id": "uuid",
        "code": "acme",
        "name": "Acme Corporation",
        "plan": "basic"
    }
}
```

## 資料匯出/匯入

### 匯出格式

匯出為 ZIP 檔案，結構如下：

```
tenant_export_20240115_103000.zip
├── manifest.json           # 匯出摘要
├── data/
│   ├── users.json
│   ├── projects.json
│   ├── project_members.json
│   ├── inventory_items.json
│   └── ...
└── files/                  # 租戶檔案（可選）
    ├── knowledge/
    ├── linebot/
    └── attachments/
```

### 匯出 API

```
POST /api/tenant/export
Content-Type: application/json

{
    "include_files": true,     // 是否包含檔案
    "include_ai_logs": false   // 是否包含 AI 日誌
}

Response: ZIP 檔案下載
```

### 匯入 API

```
POST /api/tenant/import
Content-Type: multipart/form-data

file: <ZIP 檔案>
merge_mode: "replace" | "merge"  // 取代或合併
```

### 合併模式

- **replace**: 清除現有資料，完全取代
- **merge**: 保留現有資料，僅新增不存在的記錄

## Line Bot 整合

系統支援兩種 Line Bot 部署模式：

### 獨立 Bot 模式

租戶可設定自己的 Line Bot，Bot 加入群組時自動歸屬到該租戶。

**設定步驟**：
1. 租戶在 Line Developers Console 申請 Messaging API Channel
2. 設定 Webhook URL：`https://your-domain/api/bot/line/webhook`
3. 平台管理員在租戶管理介面設定憑證：
   - Channel ID
   - Channel Secret（加密儲存）
   - Channel Access Token（加密儲存）

**API 端點**：

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/admin/tenants/{id}/linebot` | GET | 取得設定狀態 |
| `/api/admin/tenants/{id}/linebot` | PUT | 設定憑證 |
| `/api/admin/tenants/{id}/linebot/test` | POST | 測試憑證 |
| `/api/admin/tenants/{id}/linebot` | DELETE | 清除設定 |

**設定環境變數**：
```bash
# Line Bot 憑證加密金鑰（必須設定，32 bytes）
TENANT_SECRET_KEY=your-32-byte-secret-key-here
```

### 共用 Bot 模式

多個租戶共用平台提供的 Line Bot。

**群組綁定**：

Line 群組需要綁定到租戶才能使用 AI 功能：

1. 將 Bot 加入群組
2. 在群組中輸入：`/綁定 {租戶代碼}` 或 `/bind {租戶代碼}`
3. Bot 確認綁定成功

**自動租戶判定**：

未綁定群組的訊息處理優先順序：
1. 群組綁定的租戶
2. 發送者 CTOS 帳號綁定的租戶
3. 預設租戶

### 解除綁定

租戶管理員可在 Line Bot 管理介面解除群組綁定。

### Webhook 多租戶驗證

Webhook 收到訊息時的驗證流程：

```
收到 Webhook 請求
        │
        ▼
遍歷各租戶 channel_secret 驗證
        │
    ┌───┴───┐
    │       │
  成功    全部失敗
    │       │
    ▼       ▼
使用該租戶  嘗試環境變數 secret
    │       │
    │   ┌───┴───┐
    │   │       │
    │ 成功    失敗
    │   │       │
    │   ▼       ▼
    │ 從群組綁定  拒絕請求
    │ 判斷租戶
    │   │
    └───┴─── 繼續處理訊息
```

## MCP 工具

MCP 工具透過 `ctos_tenant_id` 參數傳遞租戶上下文：

```python
@mcp.tool()
async def query_project(
    project_id: str | None = None,
    keyword: str | None = None,
    ctos_tenant_id: str | None = None,  # 租戶 ID
) -> str:
    tid = _get_tenant_id(ctos_tenant_id)
    # 查詢自動過濾租戶
```

AI Agent 會自動從對話上下文中取得並傳遞租戶 ID。

## 角色與權限

### 角色類型

| 角色 | 說明 |
|------|------|
| `user` | 一般使用者 |
| `tenant_admin` | 租戶管理員，可管理租戶設定和成員 |
| `platform_admin` | 平台管理員，可管理所有租戶 |

### 租戶管理員權限

- 查看和更新租戶設定
- 新增/移除租戶管理員
- 匯出/匯入租戶資料
- 驗證資料完整性

## 資料庫遷移

### 遷移歷史

| Migration | 說明 |
|-----------|------|
| 037 | 建立 `tenants` 和 `tenant_admins` 表 |
| 038 | `users` 表加入 `tenant_id` |
| 039 | `projects` 相關表加入 `tenant_id` |
| 040 | AI 相關表加入 `tenant_id` |
| 041 | Line 相關表加入 `tenant_id` |
| 042 | 庫存相關表加入 `tenant_id` |
| 043 | 其他表加入 `tenant_id` |
| 044 | 設定 `NOT NULL` 約束 |

### 執行遷移

```bash
cd backend
uv run alembic upgrade head
```

### 資料遷移

現有資料會自動遷移到預設租戶 (`00000000-0000-0000-0000-000000000000`)。

## 測試

### 執行測試

```bash
cd backend
uv run pytest tests/test_tenant_*.py -v
```

### 測試覆蓋

| 測試檔案 | 說明 |
|----------|------|
| `test_tenant_isolation.py` | 租戶隔離單元測試 |
| `test_auth_tenant.py` | 認證流程整合測試 |
| `test_tenant_data.py` | 資料遷移測試 |
| `test_mcp_tenant.py` | MCP 工具租戶測試 |

## 常見問題

### Q: 如何從單租戶遷移到多租戶？

1. 確保已執行所有 migration
2. 設定 `MULTI_TENANT_MODE=true`
3. 現有資料已在預設租戶中
4. 建立新租戶並遷移使用者

### Q: 租戶之間可以共享資料嗎？

目前不支援跨租戶資料共享。每個租戶的資料完全隔離。

### Q: 如何備份單一租戶？

使用租戶自助 API 的匯出功能：
```bash
curl -X POST /api/tenant/export \
  -H "Authorization: Bearer <token>" \
  -d '{"include_files": true}' \
  -o backup.zip
```

### Q: 租戶被停用後資料會怎樣？

- 資料會保留但無法存取
- 平台管理員可重新啟用
- 可匯出資料後再刪除租戶

## 參考資料

- [設計文件](../openspec/changes/add-multi-tenant-platform/design.md)
- [API 文件](backend.md)
- [資料庫設計](database-design.md)
