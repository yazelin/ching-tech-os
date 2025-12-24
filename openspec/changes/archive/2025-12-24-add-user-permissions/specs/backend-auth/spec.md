# backend-auth Specification Delta

## ADDED Requirements

### Requirement: 管理員識別

系統 SHALL 使用環境變數識別管理員帳號。

#### Scenario: 判斷管理員身份
- Given 環境變數 `ADMIN_USERNAME` 設定為特定使用者名稱
- When 該使用者登入系統
- Then 系統識別該使用者為管理員
- And `GET /api/user/me` 回應 `is_admin: true`

#### Scenario: 管理員擁有所有權限
- Given 使用者為管理員
- When 取得該使用者權限
- Then 所有應用程式權限均為 `true`
- And 所有知識庫權限均為 `true`

---

### Requirement: 使用者權限管理

系統 SHALL 提供 API 讓管理員管理使用者權限。

#### Scenario: 取得使用者列表
- Given 管理員已登入
- When 呼叫 `GET /api/admin/users`
- Then 系統回傳所有使用者列表
- And 每個使用者包含 id、username、display_name、is_admin、permissions、last_login_at

#### Scenario: 非管理員存取使用者列表
- Given 非管理員使用者已登入
- When 呼叫 `GET /api/admin/users`
- Then 系統回傳 403 權限錯誤

#### Scenario: 更新使用者權限
- Given 管理員已登入
- When 呼叫 `PATCH /api/admin/users/{user_id}/permissions`
- And 提供要修改的權限設定
- Then 系統更新該使用者的 `preferences.permissions`
- And 只更新請求中指定的欄位

#### Scenario: 無法修改管理員權限
- Given 管理員已登入
- When 嘗試修改另一個管理員的權限
- Then 系統回傳 400 錯誤
- And 顯示「無法修改管理員權限」訊息

#### Scenario: 取得預設權限設定
- Given 管理員已登入
- When 呼叫 `GET /api/admin/default-permissions`
- Then 系統回傳所有權限的預設值

---

### Requirement: 使用者資訊擴充

系統 SHALL 在使用者資訊 API 回傳權限資訊。

#### Scenario: 取得目前使用者權限
- Given 使用者已登入
- When 呼叫 `GET /api/user/me`
- Then 回應包含 `is_admin` 布林值
- And 回應包含 `permissions` 物件（合併預設值後的完整權限）

---

### Requirement: 權限預設值

系統 SHALL 定義所有功能的預設權限值。

#### Scenario: 應用程式預設權限
- Given 新使用者首次登入
- When 系統計算該使用者權限
- Then 終端機預設為關閉
- And 程式編輯器預設為關閉
- And 其他應用程式預設為開放

#### Scenario: 知識庫預設權限
- Given 新使用者首次登入
- When 系統計算該使用者權限
- Then 全域知識讀取預設為開放
- And 全域知識寫入預設為關閉
- And 全域知識刪除預設為關閉
