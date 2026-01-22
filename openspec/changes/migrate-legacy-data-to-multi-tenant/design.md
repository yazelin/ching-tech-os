# Design: migrate-legacy-data-to-multi-tenant

## 架構概覽

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           遷移流程架構圖                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐                    ┌──────────────────┐               │
│  │   舊系統          │                    │   新系統          │               │
│  │  192.168.11.11   │    ═══════════>    │   本機            │               │
│  └──────────────────┘                    └──────────────────┘               │
│                                                                              │
│  資料庫                                   資料庫                              │
│  ┌────────────────┐                      ┌────────────────┐                 │
│  │ users (無 tid) │  ─────────────────>  │ users          │                 │
│  │ projects       │                      │ + tenant_id    │                 │
│  │ line_groups    │                      │ = chingtech    │                 │
│  │ ...            │                      │ ...            │                 │
│  └────────────────┘                      └────────────────┘                 │
│                                                                              │
│  檔案系統                                 檔案系統                             │
│  ┌────────────────┐                      ┌────────────────────────────────┐ │
│  │ data/          │                      │ /mnt/nas/ctos/tenants/         │ │
│  │   knowledge/   │  ─────────────────>  │   {chingtech_id}/              │ │
│  │     entries/   │                      │     knowledge/                 │ │
│  │     assets/    │                      │       entries/                 │ │
│  └────────────────┘                      │       assets/                  │ │
│                                          └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 遷移腳本設計

### 腳本結構

```
backend/scripts/
└── migrate_legacy_data.py    # 主遷移腳本
```

### 遷移步驟

```python
class LegacyDataMigrator:
    """舊系統資料遷移器"""

    def __init__(self, source_db_url: str, target_db_url: str):
        self.source_db_url = source_db_url  # 遠端 PostgreSQL
        self.target_db_url = target_db_url  # 本機 PostgreSQL

    async def migrate(self, dry_run: bool = True):
        """執行遷移"""

        # 1. 建立 chingtech 租戶
        tenant_id = await self.create_tenant()

        # 2. 遷移使用者（users）
        user_id_map = await self.migrate_users(tenant_id)

        # 3. 遷移專案相關資料
        await self.migrate_projects(tenant_id)
        await self.migrate_project_members(tenant_id, user_id_map)
        await self.migrate_project_meetings(tenant_id)
        # ... 其他專案相關表格

        # 4. 遷移 Line Bot 資料
        await self.migrate_line_groups(tenant_id)
        await self.migrate_line_users(tenant_id, user_id_map)
        await self.migrate_line_messages(tenant_id)
        # ... 其他 Line 相關表格

        # 5. 遷移 AI 相關資料
        await self.migrate_ai_agents(tenant_id)
        await self.migrate_ai_prompts(tenant_id)
        await self.migrate_ai_chats(tenant_id, user_id_map)

        # 6. 遷移其他資料
        await self.migrate_vendors(tenant_id)
        await self.migrate_inventory(tenant_id)

        # 7. 遷移檔案
        await self.migrate_files(tenant_id)

        # 8. 產生報告
        return self.generate_report()
```

### 使用者 ID 對應

由於新舊系統的 `users.id` 可能不同（舊系統的 ID 可能與新系統衝突），
需要建立使用者 ID 對應表：

```python
user_id_map = {
    old_user_id: new_user_id,
    # 例如：1 → 100（yazelin）
}
```

處理策略：
1. 檢查 username 是否已存在於新系統
2. 若存在，使用現有 user_id
3. 若不存在，插入新記錄，取得新 user_id
4. 更新所有關聯表格的 user_id 欄位

## NAS 登入驗證設計

### 登入流程

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         NAS 登入驗證流程                                   │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  User                    Frontend                 Backend                 │
│   │                         │                        │                    │
│   │  1. 輸入帳號/密碼       │                        │                    │
│   │  ─────────────────────> │                        │                    │
│   │                         │  2. POST /api/auth/login                    │
│   │                         │  ─────────────────────> │                    │
│   │                         │                        │                    │
│   │                         │        3. 解析 tenant_code                   │
│   │                         │        ─────────────────┐                   │
│   │                         │                        │ │                   │
│   │                         │        4. 取得租戶設定  │ │                   │
│   │                         │        <───────────────┘ │                   │
│   │                         │                        │                    │
│   │                         │        5. 檢查 enable_nas_auth              │
│   │                         │        ┌────────────────┴────────────────┐  │
│   │                         │        │                                 │  │
│   │                         │        │ [true] 嘗試 SMB 驗證            │  │
│   │                         │        │  - 連接到租戶指定的 NAS         │  │
│   │                         │        │  - 或使用系統預設 NAS           │  │
│   │                         │        │                                 │  │
│   │                         │        │ [false] 只用密碼驗證            │  │
│   │                         │        └────────────────┬────────────────┘  │
│   │                         │                        │                    │
│   │                         │  6. 回傳結果           │                    │
│   │                         │  <───────────────────── │                    │
│   │  7. 顯示結果            │                        │                    │
│   │  <───────────────────── │                        │                    │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### 程式碼修改

#### 1. 租戶設定模型（models/tenant.py）

```python
class TenantSettings(BaseModel):
    # ... 現有欄位 ...

    # NAS SMB 登入設定
    enable_nas_auth: bool = False
    nas_auth_host: str | None = None      # 預設使用系統設定
    nas_auth_port: int | None = None      # 預設 445
    nas_auth_share: str | None = None     # 用於驗證的共享名稱
```

#### 2. 認證服務（api/auth.py）

```python
async def login(request: LoginRequest, req: Request) -> LoginResponse:
    # ... 現有邏輯 ...

    # 取得租戶設定
    tenant_settings = await get_tenant_settings(tenant_id)

    # 認證邏輯
    if user_data and user_data.get("password_hash"):
        # 使用密碼認證
        use_password_auth = True
        # ... 現有密碼驗證邏輯 ...

    elif tenant_settings.enable_nas_auth:
        # 租戶啟用 NAS 驗證
        nas_host = tenant_settings.nas_auth_host or settings.nas_host
        nas_share = tenant_settings.nas_auth_share or settings.nas_share

        smb = create_smb_service(
            request.username,
            request.password,
            host=nas_host,
            share=nas_share,
        )
        try:
            smb.test_auth()
            auth_success = True
        except SMBAuthError:
            auth_success = False

    else:
        # 租戶未啟用 NAS 驗證，且使用者無密碼
        return LoginResponse(success=False, error="帳號不存在")
```

### 管理介面

在租戶設定頁面新增 NAS 登入驗證區塊：

```
┌─────────────────────────────────────────┐
│ NAS 登入驗證                             │
├─────────────────────────────────────────┤
│                                          │
│ [✓] 允許使用 NAS 帳號登入               │
│                                          │
│ NAS 主機: [ 192.168.11.50         ]     │
│           (留空使用系統預設)             │
│                                          │
│ 驗證共享: [ 擎添開發              ]     │
│           (用於驗證的 SMB 共享名稱)      │
│                                          │
│ [ 測試連線 ]                             │
│                                          │
└─────────────────────────────────────────┘
```

## 檔案遷移設計

### 目錄結構對照

```
舊系統 (192.168.11.11:/home/ct/SDD/ching-tech-os/)
├── data/
│   └── knowledge/
│       ├── index.json              → 遷移到新系統後需更新路徑
│       ├── entries/
│       │   ├── kb-001.md
│       │   ├── kb-002.md
│       │   └── ...
│       └── assets/
│           └── images/
│               ├── kb-001-*.jpg
│               └── ...

新系統 (/mnt/nas/ctos/tenants/{chingtech_id}/)
├── knowledge/
│   ├── index.json                  ← 更新後的索引
│   ├── entries/
│   │   ├── kb-001.md              ← 直接複製
│   │   ├── kb-002.md
│   │   └── ...
│   └── assets/
│       └── images/
│           ├── kb-001-*.jpg       ← 直接複製
│           └── ...
├── linebot/                        ← 新目錄（Line Bot 檔案）
└── attachments/                    ← 新目錄（專案附件）
```

### 遷移指令

```bash
# 1. 從遠端複製檔案到本機暫存
scp -r ct@192.168.11.11:/home/ct/SDD/ching-tech-os/data/knowledge /tmp/legacy-migration/

# 2. 建立租戶目錄
mkdir -p /mnt/nas/ctos/tenants/{chingtech_id}/knowledge/

# 3. 複製檔案到租戶目錄
cp -r /tmp/legacy-migration/knowledge/* /mnt/nas/ctos/tenants/{chingtech_id}/knowledge/

# 4. 更新 index.json 中的路徑
python scripts/update_knowledge_paths.py --tenant-id {chingtech_id}
```

## 資料庫遷移詳細設計

### 使用者表格（users）

```sql
-- 舊結構
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(100),
    preferences JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP
);

-- 遷移 SQL（使用 dblink 跨資料庫查詢）
INSERT INTO users (
    username, display_name, preferences, created_at, last_login_at,
    tenant_id, role, is_active
)
SELECT
    u.username,
    u.display_name,
    u.preferences,
    u.created_at,
    u.last_login_at,
    '{chingtech_tenant_id}'::uuid,  -- 新增 tenant_id
    'user',                          -- 預設 role
    true                             -- 預設 is_active
FROM dblink(
    'host=192.168.11.11 dbname=ching_tech_os user=ching_tech password=xxx',
    'SELECT id, username, display_name, preferences, created_at, last_login_at FROM users'
) AS u(id int, username varchar, display_name varchar, preferences jsonb, created_at timestamp, last_login_at timestamp)
ON CONFLICT (tenant_id, username) DO UPDATE SET
    last_login_at = EXCLUDED.last_login_at;
```

### 專案表格（projects）

```sql
-- 直接插入，保留原有 UUID
INSERT INTO projects (
    id, name, description, status, start_date, end_date,
    created_at, updated_at, created_by,
    tenant_id
)
SELECT
    id, name, description, status, start_date, end_date,
    created_at, updated_at, created_by,
    '{chingtech_tenant_id}'::uuid
FROM dblink(...)
ON CONFLICT (id) DO NOTHING;
```

### Line 群組（line_groups）

```sql
INSERT INTO line_groups (
    id, line_group_id, name, picture_url, member_count,
    project_id, is_active, allow_ai_response,
    joined_at, left_at, created_at, updated_at,
    tenant_id
)
SELECT
    id, line_group_id, name, picture_url, member_count,
    project_id, is_active, allow_ai_response,
    joined_at, left_at, created_at, updated_at,
    '{chingtech_tenant_id}'::uuid
FROM dblink(...)
ON CONFLICT (line_group_id) DO NOTHING;
```

## 錯誤處理

### 遷移失敗回滾

```python
async def migrate_with_rollback(self, dry_run: bool = True):
    """帶有回滾機制的遷移"""

    async with self.target_pool.acquire() as conn:
        async with conn.transaction():
            try:
                # 執行所有遷移操作
                await self._do_migrate(conn)

                if dry_run:
                    # 驗證模式：回滾所有變更
                    raise DryRunComplete("Dry run completed")

            except DryRunComplete:
                # 正常的 dry run 結束
                raise
            except Exception as e:
                # 其他錯誤：記錄並回滾
                logger.error(f"遷移失敗: {e}")
                raise
```

### 衝突處理策略

| 情境 | 處理方式 |
|------|----------|
| 使用者名稱衝突 | 更新現有記錄，不建立新記錄 |
| 專案 UUID 衝突 | 跳過（ON CONFLICT DO NOTHING）|
| Line 群組 ID 衝突 | 跳過，記錄到報告 |
| 檔案已存在 | 覆蓋（加上備份）|

## 測試計畫

### 單元測試

1. NAS 驗證邏輯測試
2. 租戶設定解析測試
3. 路徑轉換測試

### 整合測試

1. 完整遷移流程測試（使用測試資料庫）
2. NAS 登入流程測試
3. 遷移後資料完整性驗證

### 驗收測試

1. 使用 yazelin 帳號登入 chingtech 租戶
2. 瀏覽所有專案和會議記錄
3. 查看知識庫文件和附件
4. 檢查 Line Bot 群組設定
