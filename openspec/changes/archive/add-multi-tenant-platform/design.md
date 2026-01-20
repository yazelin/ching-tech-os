# Multi-Tenant Platform Design

## Context

Ching-Tech OS 目前是單租戶架構，需要轉型為支援多租戶的 SaaS 平台，同時保持向後相容性讓現有單一公司部署繼續運作。

### 利害關係人
- **平台營運方**：管理多個租戶、計費、資源配額
- **租戶管理員**：管理自己公司的用戶和資源
- **租戶用戶**：使用系統功能
- **現有部署客戶**：不想遷移到多租戶架構

### 約束條件
- 必須支援現有單租戶部署模式
- 資料隔離必須在資料庫層級實現（非僅應用層）
- Line Bot 整合需要考慮多租戶
- 試用到正式的資料遷移必須無縫

## Goals / Non-Goals

### Goals
- 實現租戶層級的資料隔離（資料庫 + 檔案系統）
- 支援試用租戶建立和資料匯出
- 支援單租戶和多租戶兩種部署模式
- 現有資料可無縫遷移到新架構
- MCP 工具和 Line Bot 支援多租戶

### Non-Goals
- 不實現租戶間的資料共享功能
- 不實現複雜的計費系統（第一版）
- 不實現租戶自訂 UI 主題
- 不實現 Kubernetes 多叢集部署

## Decisions

### 決策 1: 租戶隔離策略

**選擇**: 資料庫層級隔離（Shared Database, Shared Schema）

```
┌─────────────────────────────────────────────┐
│                  PostgreSQL                  │
├─────────────────────────────────────────────┤
│  tenants          │ id, name, settings      │
│  users            │ id, tenant_id, ...      │
│  projects         │ id, tenant_id, ...      │
│  knowledge_items  │ id, tenant_id, ...      │
│  ...              │ id, tenant_id, ...      │
└─────────────────────────────────────────────┘
```

**理由**:
- 最易於實現和維護
- 單一資料庫備份/還原
- 查詢效能可透過索引優化
- 適合中小規模租戶數量（<1000）

**替代方案**:
- Schema 隔離：每租戶獨立 schema，管理複雜
- Database 隔離：每租戶獨立 DB，資源浪費

### 決策 2: 租戶識別方式

**選擇**: 混合識別（Subdomain + Tenant Code）

```
# SaaS 模式 - Subdomain
https://acme.ching-tech.com → tenant_id = 'acme'

# SaaS 模式 - Tenant Code（登入時輸入）
https://app.ching-tech.com
登入畫面：公司代碼 [acme] + 帳號 + 密碼

# 單租戶模式 - 自動使用預設租戶
https://192.168.1.100 → tenant_id = 'default'
```

**理由**:
- Subdomain 提供最佳用戶體驗
- Tenant Code 適合沒有自訂網域的租戶
- 單租戶模式透明運作

### 決策 3: 檔案儲存結構

**選擇**: 租戶路徑隔離

```
/mnt/nas/ctos/
├── system/                    # 系統檔案（跨租戶）
│   ├── templates/
│   └── defaults/
└── tenants/
    ├── {tenant-id-1}/
    │   ├── knowledge/
    │   │   ├── entries/
    │   │   └── assets/
    │   ├── linebot/
    │   │   ├── groups/
    │   │   └── users/
    │   ├── ai-generated/
    │   └── attachments/
    │       ├── projects/
    │       └── knowledge/
    └── {tenant-id-2}/
        └── ...
```

**理由**:
- 清晰的檔案隔離
- 易於備份單一租戶
- 便於資料匯出/轉移

### 決策 4: Session 與 Token 設計

**選擇**: JWT Token 包含租戶資訊

```python
# Token Payload
{
    "sub": "user-uuid",
    "tenant_id": "tenant-uuid",
    "username": "john",
    "role": "admin",           # 租戶內角色
    "exp": 1234567890
}

# SessionData 擴展
@dataclass
class SessionData:
    user_id: UUID
    tenant_id: UUID
    username: str
    role: str
    created_at: datetime
```

**理由**:
- 每個請求自帶租戶上下文
- 無需額外資料庫查詢
- 易於驗證和傳遞

### 決策 5: Line Bot 多租戶策略

**選擇**: 共享 Bot + 租戶綁定

```
┌─────────────────┐
│  Line Platform  │
└────────┬────────┘
         │ Webhook
         ▼
┌─────────────────┐      ┌──────────────┐
│  CTOS Line Bot  │ ───► │ line_groups  │
│  (Shared)       │      │ tenant_id    │
└─────────────────┘      │ line_group_id│
                         └──────────────┘
```

**流程**:
1. Line 群組首次互動時，要求綁定租戶代碼
2. 綁定後，該群組所有訊息歸屬該租戶
3. 支援解除綁定和重新綁定

**替代方案**:
- 每租戶獨立 Bot：管理複雜，需要多個 Channel

### 決策 6: 單租戶相容模式

**選擇**: 環境變數控制 + 預設租戶

```python
# config.py
MULTI_TENANT_MODE = os.getenv("MULTI_TENANT_MODE", "false").lower() == "true"
DEFAULT_TENANT_ID = os.getenv("DEFAULT_TENANT_ID", "00000000-0000-0000-0000-000000000000")

# 登入流程
if MULTI_TENANT_MODE:
    # 要求租戶識別
    tenant_id = resolve_tenant(subdomain or tenant_code)
else:
    # 自動使用預設租戶
    tenant_id = DEFAULT_TENANT_ID
```

**理由**:
- 現有部署零修改
- 新部署可選擇模式
- 代碼邏輯統一

### 決策 7: 資料庫查詢模式

**選擇**: Repository Pattern + Tenant Filter Middleware

```python
# 基礎 Repository
class TenantAwareRepository:
    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id

    async def find_all(self, **filters):
        filters['tenant_id'] = self.tenant_id
        return await self._query(filters)

    async def find_by_id(self, id: UUID):
        row = await self._fetch_one(id)
        if row and row['tenant_id'] != self.tenant_id:
            raise TenantAccessDenied()
        return row

# 使用示例
class ProjectService:
    def __init__(self, session: SessionData):
        self.repo = ProjectRepository(session.tenant_id)

    async def list_projects(self):
        return await self.repo.find_all(status='active')
```

**理由**:
- 統一的租戶過濾邏輯
- 減少遺漏租戶檢查的風險
- 易於測試

### 決策 8: MCP Server 租戶傳遞

**選擇**: 透過工具參數傳遞租戶上下文

```python
# MCP 工具定義
@mcp.tool()
async def query_project(
    project_id: str,
    ctos_user_id: int = None,     # 現有：用於權限檢查
    ctos_tenant_id: str = None,   # 新增：租戶識別
) -> str:
    await ensure_db_connection()

    # 驗證租戶
    if ctos_tenant_id:
        tenant_id = UUID(ctos_tenant_id)
    else:
        # 向後相容：使用預設租戶
        tenant_id = DEFAULT_TENANT_ID

    # 查詢時加入租戶過濾
    row = await conn.fetchrow("""
        SELECT * FROM projects
        WHERE id = $1 AND tenant_id = $2
    """, UUID(project_id), tenant_id)
```

**理由**:
- 與現有 `ctos_user_id` 模式一致
- AI Agent Prompt 可傳遞租戶資訊
- 向後相容

## Risks / Trade-offs

### 風險 1: 資料隔離漏洞
- **風險**：忘記在某個查詢加入 tenant_id 過濾
- **緩解**：
  - Repository Pattern 統一處理
  - 資料庫 Row-Level Security (RLS) 作為第二道防線
  - 自動化測試驗證隔離

### 風險 2: 效能下降
- **風險**：所有查詢多一個 tenant_id 條件
- **緩解**：
  - 複合索引 (tenant_id, primary_key)
  - 分區表（ai_logs 已有分區，可擴展）
  - 監控查詢效能

### 風險 3: 遷移失敗
- **風險**：現有資料遷移到新結構失敗
- **緩解**：
  - 分階段遷移
  - nullable tenant_id 過渡期
  - 完整備份和回滾計劃

### 風險 4: Line Bot 混亂
- **風險**：群組綁定錯誤租戶
- **緩解**：
  - 綁定確認流程
  - 管理員可修正綁定
  - 操作日誌審計

## Data Model

### 新增表格

```sql
-- 租戶主表
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,      -- 租戶代碼（用於登入）
    name VARCHAR(200) NOT NULL,            -- 租戶名稱
    status VARCHAR(20) DEFAULT 'active',   -- active, suspended, trial
    plan VARCHAR(50) DEFAULT 'trial',      -- trial, basic, pro, enterprise
    settings JSONB DEFAULT '{}',           -- 租戶設定
    storage_quota_mb BIGINT DEFAULT 5120,  -- 儲存配額 (MB)
    storage_used_mb BIGINT DEFAULT 0,      -- 已使用儲存
    trial_ends_at TIMESTAMPTZ,             -- 試用期結束
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 租戶管理員（平台級）
CREATE TABLE tenant_admins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    role VARCHAR(50) DEFAULT 'admin',      -- admin, owner
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 修改表格

```sql
-- 所有核心表格新增 tenant_id
ALTER TABLE users ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE projects ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE project_members ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE project_meetings ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE project_milestones ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE project_delivery_schedules ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE project_links ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE project_attachments ADD COLUMN tenant_id UUID REFERENCES tenants(id);

ALTER TABLE ai_chats ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE ai_logs ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE ai_agents ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE ai_prompts ADD COLUMN tenant_id UUID REFERENCES tenants(id);

ALTER TABLE line_groups ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE line_users ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE line_messages ADD COLUMN tenant_id UUID REFERENCES tenants(id);

ALTER TABLE inventory_items ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE inventory_transactions ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE vendors ADD COLUMN tenant_id UUID REFERENCES tenants(id);

ALTER TABLE public_share_links ADD COLUMN tenant_id UUID REFERENCES tenants(id);

-- 索引
CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_projects_tenant_status ON projects(tenant_id, status);
CREATE INDEX idx_ai_logs_tenant_created ON ai_logs(tenant_id, created_at);
-- ... 其他表格
```

## API Changes

### 新增 API

```
# 租戶管理（平台管理員）
POST   /api/admin/tenants              # 建立租戶
GET    /api/admin/tenants              # 列出所有租戶
GET    /api/admin/tenants/{id}         # 租戶詳情
PATCH  /api/admin/tenants/{id}         # 更新租戶
DELETE /api/admin/tenants/{id}         # 刪除租戶

# 租戶自助服務
GET    /api/tenant                     # 取得當前租戶資訊
PATCH  /api/tenant                     # 更新租戶設定
GET    /api/tenant/usage               # 使用量統計
POST   /api/tenant/export              # 匯出租戶資料
POST   /api/tenant/import              # 匯入租戶資料
```

### 認證 API 變更

```
# 登入 - 新增 tenant_code 參數
POST /api/auth/login
Body: {
    "username": "john",
    "password": "secret",
    "tenant_code": "acme"      # 新增（SaaS 模式必填）
}

Response: {
    "token": "jwt...",
    "user": {...},
    "tenant": {                # 新增
        "id": "uuid",
        "name": "Acme Corp",
        "plan": "trial"
    }
}
```

## Migration Plan

### Step 1: 準備階段

```sql
-- Migration 037: 建立 tenants 表
CREATE TABLE tenants (...);

-- 建立預設租戶
INSERT INTO tenants (id, code, name, status, plan)
VALUES ('00000000-0000-0000-0000-000000000000', 'default', '預設租戶', 'active', 'enterprise');
```

### Step 2: 欄位新增

```sql
-- Migration 038: 新增 tenant_id 欄位（nullable）
ALTER TABLE users ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE projects ADD COLUMN tenant_id UUID REFERENCES tenants(id);
-- ... 其他表格
```

### Step 3: 資料遷移

```sql
-- Migration 039: 遷移現有資料到預設租戶
UPDATE users SET tenant_id = '00000000-0000-0000-0000-000000000000' WHERE tenant_id IS NULL;
UPDATE projects SET tenant_id = '00000000-0000-0000-0000-000000000000' WHERE tenant_id IS NULL;
-- ... 其他表格
```

### Step 4: 約束啟用

```sql
-- Migration 040: 設定 NOT NULL 約束
ALTER TABLE users ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE projects ALTER COLUMN tenant_id SET NOT NULL;
-- ... 其他表格

-- 建立索引
CREATE INDEX idx_users_tenant ON users(tenant_id);
-- ...
```

### Step 5: 檔案遷移

```bash
# 現有知識庫遷移到預設租戶目錄
mkdir -p /mnt/nas/ctos/tenants/00000000-0000-0000-0000-000000000000/
mv /mnt/nas/ctos/knowledge /mnt/nas/ctos/tenants/00000000-0000-0000-0000-000000000000/
mv /mnt/nas/ctos/linebot /mnt/nas/ctos/tenants/00000000-0000-0000-0000-000000000000/
# 建立向後相容的符號連結
ln -s /mnt/nas/ctos/tenants/00000000-0000-0000-0000-000000000000/knowledge /mnt/nas/ctos/knowledge
```

## Open Questions

1. **計費整合**：第一版是否需要整合 Stripe 或其他支付系統？
   - 建議：第一版先用手動管理，後續再整合

2. **租戶自訂網域**：是否支援租戶使用自己的網域？
   - 建議：第一版僅支援 subdomain

3. **跨租戶協作**：是否允許不同租戶的用戶協作？
   - 建議：第一版不支援，保持簡單

4. **知識庫全資料庫化**：是否將知識庫從檔案系統完全遷移到資料庫？
   - 建議：保持檔案系統 + 資料庫索引，漸進式遷移

5. **資料保留政策**：試用期結束後資料保留多久？
   - 建議：30 天後自動刪除，可付費延長
