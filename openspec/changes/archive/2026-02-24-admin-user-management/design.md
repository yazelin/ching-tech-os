## Context

系統目前已有雙軌認證機制（密碼認證優先、SMB/NAS 備援），但管理員只能透過資料庫手動操作使用者帳號。後端服務層（`services/user.py`）已實作完整的 CRUD 函數（`create_user`、`reset_user_password`、`deactivate_user`、`activate_user`、`update_user_info`），密碼服務（`services/password.py`）也有 `hash_password`、`generate_temporary_password`、`validate_password_strength` 等工具。前端「系統設定」App（`settings.js`）已有使用者列表和權限管理對話框。

關鍵現狀：
- 後端 API 層（`api/user.py`）只暴露了 `GET /api/admin/users`、`PATCH /api/admin/users/{id}/permissions`、`GET /api/admin/default-permissions`
- 前端使用者列表只有「設定權限」操作按鈕
- 沒有 `clear_user_password()` 服務函數可以把使用者從密碼認證切回 NAS 認證
- 沒有預設管理員帳號，若 NAS 不可用則無法登入系統

## Goals / Non-Goals

**Goals:**
- 透過 Migration 建立預設管理員帳號（`ct` / `36274806`），首次登入強制改密碼
- 管理員可從 UI 建立 CTOS 本地帳號（含密碼），新帳號登入時不依賴 NAS
- 管理員可編輯使用者資訊（顯示名稱、Email、角色）
- 管理員可重設使用者密碼（產生臨時密碼 + 強制下次登入變更）
- 管理員可停用/啟用使用者帳號
- 管理員可清除使用者密碼，使其恢復為 NAS 認證模式
- 使用者列表清楚顯示每位使用者的認證方式（密碼 / NAS）

**Non-Goals:**
- 使用者自行註冊（不提供公開註冊頁面）
- 批次匯入使用者
- 修改登入頁面 UI（登入流程維持不變）
- LDAP / OAuth 等其他認證方式整合

## Decisions

### 1. 預設管理員帳號：Migration 種子資料

在新的 Alembic migration（`007_seed_admin_user.py`）中插入預設管理員：
- 帳號：`ct`，密碼：`36274806`（bcrypt hash）
- `role = 'admin'`、`must_change_password = True`
- 使用 `ON CONFLICT (username) DO NOTHING` 避免重複執行時報錯

**理由**：與現有 `002_seed_data.py` 模式一致，部署時 `alembic upgrade head` 即可自動建立。

### 2. API 端點設計：延伸現有 admin_router

在 `api/user.py` 的 `admin_router` 下新增端點，複用 `require_admin` 依賴：

| 端點 | 方法 | 用途 |
|------|------|------|
| `/api/admin/users` | POST | 建立使用者 |
| `/api/admin/users/{user_id}` | PATCH | 編輯使用者資訊 |
| `/api/admin/users/{user_id}/reset-password` | POST | 重設密碼 |
| `/api/admin/users/{user_id}/status` | PATCH | 停用/啟用帳號 |
| `/api/admin/users/{user_id}/clear-password` | POST | 清除密碼（恢復 NAS 認證） |

### 3. 建立使用者：管理員設定初始密碼 + 強制變更

管理員建立帳號時設定初始密碼，系統自動標記 `must_change_password=True`。前端已有 `showChangePasswordDialog` 處理此流程。

### 4. 清除密碼：新增 `clear_user_password()` 到 services/user.py

將 `password_hash` 設為 NULL、`must_change_password` 設為 False。登入邏輯自然 fallback 到 SMB 認證，不需修改 `api/auth.py`。

### 5. 前端 UI：操作下拉選單取代單一按鈕

將使用者列表的「設定權限」單一按鈕替換為操作下拉選單，包含：設定權限、編輯資訊、重設密碼、停用/啟用、清除密碼。

新增「新增使用者」按鈕於列表上方，點擊開啟對話框（帳號、密碼、顯示名稱、角色）。

### 6. 認證方式顯示

`AdminUserInfo` model 新增 `has_password: bool`，後端根據 `password_hash is not None` 設定。前端顯示「密碼」或「NAS」badge。

### 7. 安全性：管理員自我保護

後端 API 層強制限制（不只靠前端隱藏）：
- 管理員不能停用自己的帳號
- 管理員不能清除自己的密碼
- 管理員不能降級自己的角色

## Risks / Trade-offs

- **帳號名稱衝突** → 建立帳號 UI 加入提示：「如果 NAS 上已有同名帳號，該使用者將改為密碼認證」
- **清除密碼後 NAS 不可用** → 後端 API 檢查 `ENABLE_NAS_AUTH` 設定，若為 False 則拒絕清除密碼並回傳錯誤
- **預設管理員密碼** → `must_change_password=True` 確保首次登入必須改密碼，降低風險
