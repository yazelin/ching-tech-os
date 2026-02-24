## ADDED Requirements

### Requirement: 預設管理員帳號
系統 SHALL 透過資料庫 migration 建立預設管理員帳號，確保系統在無 NAS 認證時仍可登入。

#### Scenario: Migration 建立預設管理員
- **WHEN** 執行 `alembic upgrade head`
- **THEN** 系統在 users 表建立帳號 `ct`，密碼為 `36274806` 的 bcrypt hash
- **AND** `role` 為 `admin`
- **AND** `must_change_password` 為 `True`
- **AND** `is_active` 為 `True`

#### Scenario: 預設管理員已存在時不重複建立
- **WHEN** 執行 migration 但 `ct` 帳號已存在
- **THEN** migration 不修改現有帳號（`ON CONFLICT DO NOTHING`）

#### Scenario: 預設管理員首次登入強制改密碼
- **WHEN** 預設管理員以初始密碼登入
- **THEN** 系統回傳 `must_change_password: true`
- **AND** 前端顯示變更密碼對話框
- **AND** 使用者必須設定新密碼才能進入桌面

---

### Requirement: 建立使用者
系統 SHALL 提供管理員 API 建立 CTOS 本地帳號，新帳號使用密碼認證登入。

#### Scenario: 管理員建立新使用者
- **WHEN** 管理員呼叫 `POST /api/admin/users`
- **AND** 提供 `username`、`password`、`display_name`（選填）、`role`（選填，預設 `user`）
- **THEN** 系統建立使用者，密碼以 bcrypt hash 儲存
- **AND** `must_change_password` 設為 `True`
- **AND** 回傳新使用者的 id、username、display_name、role

#### Scenario: 帳號名稱已存在
- **WHEN** 管理員建立使用者時 username 已存在
- **THEN** 系統回傳 400 錯誤：「使用者名稱已存在」

#### Scenario: 密碼強度不足
- **WHEN** 管理員建立使用者時密碼少於 8 個字元
- **THEN** 系統回傳 400 錯誤：「密碼至少需要 8 個字元」

#### Scenario: 非管理員嘗試建立使用者
- **WHEN** 非管理員呼叫 `POST /api/admin/users`
- **THEN** 系統回傳 403 錯誤：「需要管理員權限」

---

### Requirement: 編輯使用者資訊
系統 SHALL 提供管理員 API 編輯使用者的顯示名稱、Email 和角色。

#### Scenario: 管理員編輯使用者資訊
- **WHEN** 管理員呼叫 `PATCH /api/admin/users/{user_id}`
- **AND** 提供 `display_name`、`email`、`role` 中的一項或多項
- **THEN** 系統更新對應欄位
- **AND** 回傳更新後的使用者資訊

#### Scenario: 管理員不能降級自己的角色
- **WHEN** 管理員嘗試將自己的 role 從 `admin` 改為 `user`
- **THEN** 系統回傳 400 錯誤：「不能降級自己的角色」

#### Scenario: 編輯不存在的使用者
- **WHEN** 管理員編輯不存在的 user_id
- **THEN** 系統回傳 404 錯誤：「使用者不存在」

---

### Requirement: 重設使用者密碼
系統 SHALL 提供管理員 API 重設使用者密碼，重設後使用者必須於下次登入時變更密碼。

#### Scenario: 管理員重設使用者密碼
- **WHEN** 管理員呼叫 `POST /api/admin/users/{user_id}/reset-password`
- **AND** 提供 `new_password`
- **THEN** 系統將密碼更新為新密碼的 bcrypt hash
- **AND** `must_change_password` 設為 `True`
- **AND** 回傳成功訊息

#### Scenario: 重設密碼強度不足
- **WHEN** 管理員重設密碼時新密碼少於 8 個字元
- **THEN** 系統回傳 400 錯誤：「密碼至少需要 8 個字元」

---

### Requirement: 停用與啟用使用者帳號
系統 SHALL 提供管理員 API 停用或啟用使用者帳號，停用的帳號無法登入。

#### Scenario: 管理員停用使用者帳號
- **WHEN** 管理員呼叫 `PATCH /api/admin/users/{user_id}/status`
- **AND** 提供 `is_active: false`
- **THEN** 系統將使用者的 `is_active` 設為 `False`
- **AND** 回傳成功訊息

#### Scenario: 管理員啟用使用者帳號
- **WHEN** 管理員呼叫 `PATCH /api/admin/users/{user_id}/status`
- **AND** 提供 `is_active: true`
- **THEN** 系統將使用者的 `is_active` 設為 `True`
- **AND** 回傳成功訊息

#### Scenario: 管理員不能停用自己的帳號
- **WHEN** 管理員嘗試停用自己的帳號
- **THEN** 系統回傳 400 錯誤：「不能停用自己的帳號」

#### Scenario: 停用帳號無法登入
- **WHEN** 帳號 `is_active` 為 `False` 的使用者嘗試登入
- **THEN** 系統回傳認證失敗：「此帳號已被停用」

---

### Requirement: 清除使用者密碼（恢復 NAS 認證）
系統 SHALL 提供管理員 API 清除使用者的密碼，使其認證方式恢復為 NAS SMB 認證。

#### Scenario: 管理員清除使用者密碼
- **WHEN** 管理員呼叫 `POST /api/admin/users/{user_id}/clear-password`
- **THEN** 系統將使用者的 `password_hash` 設為 NULL
- **AND** `must_change_password` 設為 `False`
- **AND** 回傳成功訊息

#### Scenario: 管理員不能清除自己的密碼
- **WHEN** 管理員嘗試清除自己的密碼
- **THEN** 系統回傳 400 錯誤：「不能清除自己的密碼」

#### Scenario: NAS 認證未啟用時拒絕清除密碼
- **WHEN** 管理員清除密碼但 `ENABLE_NAS_AUTH` 為 `False`
- **THEN** 系統回傳 400 錯誤：「NAS 認證未啟用，清除密碼後使用者將無法登入」

---

### Requirement: 使用者列表顯示認證方式
系統 SHALL 在管理員的使用者列表 API 回傳每位使用者的認證方式資訊。

#### Scenario: 使用者列表包含認證方式
- **WHEN** 管理員呼叫 `GET /api/admin/users`
- **THEN** 每位使用者資料包含 `has_password` 布林欄位
- **AND** `has_password` 為 `True` 表示密碼認證
- **AND** `has_password` 為 `False` 表示 NAS 認證

---

### Requirement: 使用者管理前端介面
系統 SHALL 在「系統設定」App 的使用者管理 Tab 提供完整的帳號管理 UI。

#### Scenario: 新增使用者按鈕與對話框
- **WHEN** 管理員在使用者管理 Tab
- **THEN** 列表上方顯示「新增使用者」按鈕
- **AND** 點擊後開啟對話框，包含帳號、密碼、顯示名稱、角色欄位
- **AND** 送出後呼叫建立使用者 API 並重新載入列表

#### Scenario: 使用者列表操作下拉選單
- **WHEN** 管理員在使用者列表中點擊非管理員使用者的操作按鈕
- **THEN** 顯示下拉選單，包含：設定權限、編輯資訊、重設密碼、停用/啟用、清除密碼

#### Scenario: 認證方式 Badge 顯示
- **WHEN** 使用者列表渲染
- **THEN** 每位使用者旁顯示「密碼」或「NAS」badge，標示其認證方式

#### Scenario: 停用狀態視覺區分
- **WHEN** 使用者帳號為停用狀態
- **THEN** 該列顯示降低不透明度或刪除線等視覺標記
- **AND** 操作選單中顯示「啟用」而非「停用」
