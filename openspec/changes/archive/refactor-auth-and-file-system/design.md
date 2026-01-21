# Design: 認證系統與檔案管理架構重構

## Context

### 現有架構

```
┌─────────────────────────────────────────────────────────────┐
│                        目前架構                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   使用者                    後端                    NAS      │
│    ┌───┐                   ┌───┐                  ┌───┐    │
│    │登入│──帳號+密碼───────▶│SMB├──認證────────────▶│NAS│    │
│    │頁面│                   │驗證│                  │   │    │
│    └───┘                   └─┬─┘                  └───┘    │
│                              │                              │
│                              ▼                              │
│                        ┌─────────┐                          │
│                        │ Session │                          │
│                        │ (含密碼) │                          │
│                        └────┬────┘                          │
│                             │                               │
│                             ▼                               │
│   ┌───────┐           ┌─────────┐                          │
│   │檔案管理│──────────▶│ NAS API │──用 Session 密碼────────▶│
│   │  器   │           │（自動連線）│                         │
│   └───────┘           └─────────┘                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘

問題：
1. 必須有 NAS 帳號才能登入 CTOS
2. NAS 密碼存於 Session（記憶體）
3. 檔案管理器自動使用登入帳號的 NAS 權限
4. 無獨立的會員/密碼管理
```

### 目標架構

```
┌─────────────────────────────────────────────────────────────┐
│                        目標架構                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   使用者                    後端                             │
│    ┌───┐                   ┌────────┐                       │
│    │登入│──租戶+帳號+密碼──▶│ 密碼雜湊 │                       │
│    │頁面│                   │  驗證   │                       │
│    └───┘                   └───┬────┘                       │
│                                │                            │
│                                ▼                            │
│                          ┌─────────┐                        │
│                          │ Session │                        │
│                          │(無 NAS  │                        │
│                          │  密碼)  │                        │
│                          └────┬────┘                        │
│                               │                             │
│                               ▼                             │
│   ┌───────┐    ┌───────────────────────────────┐   ┌───┐  │
│   │檔案管理│───▶│    NAS 連線對話框               │──▶│NAS│  │
│   │  器   │    │ IP + 帳號 + 密碼（使用者輸入）  │   │   │  │
│   └───────┘    └───────────────────────────────┘   └───┘  │
│                               │                             │
│                               ▼                             │
│                      ┌───────────────┐                      │
│                      │ NAS 連線 Token │                      │
│                      │ (短期/視窗級) │                       │
│                      └───────────────┘                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘

優點：
1. CTOS 帳號與 NAS 帳號完全分離
2. Session 不儲存敏感密碼
3. 使用者可連接任何 NAS
4. 階層式帳號管理（平台→租戶→使用者）
```

## Goals / Non-Goals

### Goals

1. **獨立會員系統**：使用者透過 username + 密碼登入（管理員建立帳號）
2. **階層式帳號管理**：平台管理員 → 租戶管理員 → 一般使用者
3. **帳號租戶隔離**：各租戶的 username 互不衝突
4. **NAS 連線解耦**：NAS 存取改為檔案管理器內的獨立操作
5. **安全性提升**：Session 不再儲存明文密碼
6. **向後相容**：提供現有使用者遷移路徑

### Non-Goals

1. **自助註冊**：不開放使用者自行註冊，由管理員建立帳號
2. **OAuth/SSO 整合**：本次不實作第三方登入（Google、Azure AD 等）
3. **多因子認證**：本次不實作 TOTP 或 SMS 驗證
4. **NAS 憑證集中管理**：不實作管理員統一配置 NAS 的功能

## Decisions

### 1. 帳號唯一性與租戶隔離

**決定**：username 在租戶範圍內唯一（複合唯一鍵）

**資料庫約束**：
```sql
-- 移除舊的全域唯一約束
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key;

-- 新增租戶範圍內唯一約束
ALTER TABLE users ADD CONSTRAINT users_tenant_username_unique
    UNIQUE (tenant_id, username);
```

**效果**：
- 租戶 A 可以有 `john`
- 租戶 B 也可以有 `john`
- 同一租戶內不能有兩個 `john`

### 2. 密碼雜湊演算法

**決定**：使用 `bcrypt` 進行密碼雜湊

**理由**：
- Python `bcrypt` 套件成熟穩定
- 內建 salt，防止彩虹表攻擊
- 可調整 cost factor 應對硬體升級
- 業界標準做法

### 3. 階層式帳號管理

**決定**：三級管理架構

```
平台管理員 (platform_admin)
    │
    ├── 建立租戶
    ├── 指定租戶管理員
    └── 建立租戶內使用者（可選）
          │
          ▼
租戶管理員 (tenant_admin)
    │
    ├── 建立該租戶內的使用者
    ├── 設定/重設使用者密碼
    └── 停用使用者帳號
          │
          ▼
一般使用者 (user)
    │
    ├── 登入系統
    ├── 變更自己的密碼
    └── 綁定 Line 帳號
```

**API 權限對應**：
| API | platform_admin | tenant_admin | user |
|-----|----------------|--------------|------|
| `POST /api/admin/tenants` | ✓ | ✗ | ✗ |
| `POST /api/admin/tenants/{id}/users` | ✓ | ✗ | ✗ |
| `POST /api/tenant/users` | ✓ | ✓ | ✗ |
| `POST /api/tenant/users/{id}/reset-password` | ✓ | ✓ | ✗ |
| `POST /api/auth/change-password` | ✓ | ✓ | ✓ |

### 4. 登入流程

**決定**：租戶代碼 + username + 密碼

**流程**：
```
1. 使用者輸入：租戶代碼、username、密碼
2. 系統驗證租戶代碼是否存在且未停用
3. 在該租戶範圍內查找 username
4. 驗證密碼雜湊
5. 建立 Session（不含密碼）
```

**單租戶模式**：
- 可省略租戶代碼輸入
- 自動使用預設租戶

### 5. 密碼重設機制

**決定**：雙軌制 - 管理員設定 + Email 重設（可選）

**方式一：管理員直接設定**
```
租戶管理員 → 呼叫 API 設定臨時密碼 → 告知使用者 → 使用者登入後強制變更
```

**方式二：Email 重設（若使用者有設定 Email）**
```
使用者請求重設 → 系統發送重設連結 → 使用者點擊設定新密碼
```

**欄位設計**：
- `email` - 可選欄位（主要用於密碼重設和通知）
- `must_change_password` - 下次登入強制變更密碼

### 6. NAS 連線管理

**決定**：使用伺服器端 NAS 連線池（Connection Pool）+ 連線 Token

**架構**：
```python
# NAS 連線管理器
class NASConnectionManager:
    _connections: dict[str, NASConnection]  # token -> connection

    def create_connection(host, username, password) -> str:
        """建立連線，回傳 token"""
        token = uuid4()
        self._connections[token] = NASConnection(host, username, password)
        return token

    def get_connection(token) -> NASConnection | None:
        """取得連線"""
        return self._connections.get(token)

    def close_connection(token):
        """關閉連線"""
        if token in self._connections:
            self._connections[token].close()
            del self._connections[token]
```

**連線生命週期**：
- 連線 Token 預設 30 分鐘過期
- 檔案操作自動延長過期時間
- 前端關閉檔案管理視窗時主動斷開

### 7. 記住 NAS 連線設定

**決定**：可選的本地儲存 + 加密

**實作**：
```javascript
// 前端（可選）
const savedConnections = localStorage.getItem('nas_connections');
// 格式：[{ host, username, password_encrypted, last_used }]
// 使用 Web Crypto API 加密密碼
```

**安全考量**：
- 預設不儲存密碼
- 使用者勾選「記住密碼」才儲存
- 使用 AES-GCM 加密，key 衍生自 CTOS 帳號
- 儲存於 localStorage（不上傳伺服器）

### 8. Session 結構變更

**決定**：移除 `password` 欄位，保留必要資訊

**新結構**：
```python
class SessionData:
    user_id: int
    tenant_id: UUID
    username: str
    email: str | None  # 可選
    role: str  # user, tenant_admin, platform_admin
    created_at: datetime
    expires_at: datetime
    # 移除：password, nas_host
```

### 9. 資料庫 Schema 變更

**決定**：擴充 users 表 + 新增 token 表

**users 表變更**：
```sql
-- 新增欄位
ALTER TABLE users ADD COLUMN password_hash VARCHAR(255);
ALTER TABLE users ADD COLUMN email VARCHAR(255);
ALTER TABLE users ADD COLUMN password_changed_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT FALSE;

-- 修改唯一約束
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key;
ALTER TABLE users ADD CONSTRAINT users_tenant_username_unique
    UNIQUE (tenant_id, username);

-- email 在租戶內唯一（若有設定）
CREATE UNIQUE INDEX idx_users_tenant_email
    ON users (tenant_id, email)
    WHERE email IS NOT NULL;
```

**密碼重設 token 表**（Email 重設用，可選）：
```sql
CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Risks / Trade-offs

### 風險 1：現有使用者無法登入

**情況**：切換後，現有使用者沒有密碼

**緩解**：
1. 遷移腳本讓管理員批次設定臨時密碼
2. 標記 `must_change_password = true`
3. 使用者首次登入後強制變更密碼

### 風險 2：忘記租戶代碼

**情況**：使用者忘記自己屬於哪個租戶

**緩解**：
1. 若有 Email，可透過 Email 查詢所屬租戶
2. 聯繫平台管理員查詢
3. 登入頁面提供「忘記租戶代碼」提示

### 風險 3：NAS 連線中斷

**情況**：使用者輸入錯誤憑證或 NAS 不可達

**緩解**：
1. 連線前先測試（類似目前 SMB auth test）
2. 清楚的錯誤訊息（「無法連線」vs「認證失敗」）
3. 連線逾時後自動清理

### Trade-off：使用者體驗

**變化**：
- 之前：登入即可存取 NAS
- 之後：需額外步驟連接 NAS

**補償**：
- 記住連線設定（可選）
- 最近連線清單
- 預設連線提示

## Migration Plan

### Phase 1：資料庫準備（非破壞性）

1. 新增 `password_hash`, `email`, `must_change_password` 等欄位（允許 NULL）
2. 建立 password_reset_tokens 表
3. 不影響現有功能

### Phase 2：修改唯一性約束

1. 移除 `username` 全域唯一約束
2. 新增 `(tenant_id, username)` 複合唯一約束
3. 確認現有資料符合新約束

### Phase 3：新增 API 端點

1. 新增帳號管理 API（租戶管理員建立使用者）
2. 新增 NAS 連線 API
3. 舊 API 繼續運作

### Phase 4：前端更新

1. 登入頁面支援 username + 密碼（新流程）
2. 檔案管理器新增 NAS 連線對話框
3. 管理介面新增使用者管理功能
4. 舊流程仍可用（向後相容）

### Phase 5：使用者遷移

1. 執行遷移腳本，為現有使用者：
   - 設定臨時密碼
   - 標記 `must_change_password = true`
2. 管理員通知使用者新密碼

### Phase 6：清理（Breaking Change）

1. 移除 SMB 認證登入代碼
2. 移除 Session 中的 password 欄位
3. 移除舊的 NAS API 端點（若有）

### 回滾計畫

每個 Phase 可獨立回滾：
- Phase 1-2：還原資料庫結構
- Phase 3：移除新 API 路由
- Phase 4：還原前端代碼
- Phase 5：無需回滾（資料已遷移）
- Phase 6：需要重新部署舊版本

## Open Questions

1. **密碼複雜度要求**：最小長度？需要大小寫數字特殊字元？（建議：至少 8 字元）
2. **NAS 連線記住期限**：記住 NAS 憑證的有效期？（建議：30 天或直到登出）
3. **臨時密碼格式**：隨機字串還是讓管理員自訂？（建議：隨機 12 字元）
4. **Email 功能**：是否需要 Email 重設密碼？還是純靠管理員？（建議：可選，有設定 Email 才支援）
