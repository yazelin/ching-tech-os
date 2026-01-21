## REMOVED Requirements

### Requirement: NAS 認證登入

**Reason**: 系統改為使用獨立會員系統，不再依賴 NAS SMB 認證作為主要登入機制。

**Migration**: 現有使用者需透過以下方式設定密碼：
1. 管理員直接設定臨時密碼
2. 管理員透過 Email 發送重設連結（若使用者有 Email）

---

## MODIFIED Requirements

### Requirement: Session 管理

系統 SHALL 使用 token 管理使用者登入狀態，Session MUST 儲存於 server 記憶體，Session 中 MUST NOT 儲存使用者密碼或 NAS 憑證。

#### Scenario: 使用有效 token 存取 API
- Given 使用者已登入並持有有效 token
- When 使用該 token 呼叫需認證的 API
- Then API 正常回應

#### Scenario: 使用無效 token 存取 API
- Given 使用者持有無效或過期的 token
- When 使用該 token 呼叫需認證的 API
- Then 系統回傳 401 未授權錯誤
- And 前端導向登入頁面

#### Scenario: 登出清除 session
- Given 使用者已登入
- When 使用者點擊登出
- Then 系統刪除該 session
- And token 立即失效
- And 使用者被導向登入頁面

#### Scenario: Session 過期自動清理
- Given Session 預設有效期為 8 小時
- When 超過有效期後使用該 token
- Then 系統回傳 401 未授權錯誤

---

### Requirement: 使用者資訊 API

系統 SHALL 提供 API 讓登入後的使用者查看和更新個人資訊。

#### Scenario: 取得目前使用者資訊
- Given 使用者已登入
- When 呼叫 GET /api/user/me
- Then 系統回傳該使用者的資訊
- And 包含 username、email（若有）、display_name、created_at、last_login_at

#### Scenario: 更新顯示名稱
- Given 使用者已登入
- When 呼叫 PATCH /api/user/me 並提供新的 display_name
- Then 系統更新資料庫中的 display_name
- And 回傳更新後的使用者資訊

#### Scenario: 未登入時存取使用者資訊
- Given 使用者未登入或 token 無效
- When 呼叫使用者資訊 API
- Then 系統回傳 401 未授權錯誤

---

## ADDED Requirements

### Requirement: 帳號密碼登入

系統 SHALL 支援使用者以租戶代碼、username 和密碼登入。

#### Scenario: 使用正確的憑證登入
- Given 使用者在登入頁面
- When 輸入正確的租戶代碼、username 和密碼
- Then 系統在該租戶範圍內查找 username
- And 驗證密碼雜湊
- And 回傳成功並提供 session token
- And 更新 users 表的 last_login_at
- And 使用者被導向桌面頁面

#### Scenario: 單租戶模式登入
- Given 系統為單租戶模式
- When 使用者輸入 username 和密碼（無需租戶代碼）
- Then 系統使用預設租戶進行驗證
- And 後續流程與多租戶模式相同

#### Scenario: 使用錯誤的密碼登入
- Given 使用者在登入頁面
- When 輸入正確的租戶代碼和 username 但錯誤的密碼
- Then 系統回傳認證失敗錯誤
- And 顯示「帳號或密碼錯誤」訊息
- And 記錄登入失敗事件

#### Scenario: 使用不存在的帳號登入
- Given 使用者在登入頁面
- When 輸入不存在的 username
- Then 系統回傳認證失敗錯誤
- And 顯示「帳號或密碼錯誤」訊息（不洩漏帳號是否存在）

#### Scenario: 需強制變更密碼
- Given 使用者的 must_change_password 為 true
- When 使用者成功登入
- Then 系統回傳成功但標記需變更密碼
- And 前端導向密碼變更頁面
- And 使用者必須變更密碼後才能使用其他功能

---

### Requirement: 帳號租戶隔離

系統 SHALL 確保各租戶的帳號（username）互不衝突。

#### Scenario: 不同租戶可有相同 username
- Given 租戶 A 有使用者 username = "john"
- When 租戶 B 的管理員建立 username = "john" 的使用者
- Then 系統成功建立
- And 兩個 "john" 是不同的使用者

#### Scenario: 同租戶內 username 唯一
- Given 租戶 A 已有使用者 username = "john"
- When 租戶 A 的管理員嘗試建立另一個 username = "john"
- Then 系統回傳錯誤「此帳號已存在」

#### Scenario: 登入時指定租戶
- Given 租戶 A 和租戶 B 都有 username = "john"
- When 使用者輸入租戶代碼 A 和 username "john"
- Then 系統驗證租戶 A 的 "john" 帳號

---

### Requirement: 管理員建立使用者

系統 SHALL 支援管理員為租戶建立使用者帳號（不開放自助註冊）。

#### Scenario: 租戶管理員建立使用者
- Given 租戶管理員已登入
- When 呼叫 POST /api/tenant/users
- And 提供 username、密碼（或產生臨時密碼）、顯示名稱、Email（可選）
- Then 系統在該租戶建立新使用者
- And 若使用臨時密碼則標記 must_change_password = true
- And 回傳使用者資訊（若為臨時密碼則回傳密碼，僅一次）

#### Scenario: 平台管理員建立使用者
- Given 平台管理員已登入
- When 呼叫 POST /api/admin/tenants/{tenant_id}/users
- And 提供使用者資訊
- Then 系統在指定租戶建立新使用者

#### Scenario: 一般使用者無法建立帳號
- Given 一般使用者已登入
- When 嘗試呼叫建立使用者 API
- Then 系統回傳 403 權限錯誤

#### Scenario: username 格式驗證
- Given 管理員建立使用者
- When 提供的 username 包含非法字元或過長
- Then 系統回傳錯誤「帳號格式不正確」
- And username MUST 為 3-50 字元
- And username MUST 只包含字母、數字、底線、減號

---

### Requirement: 密碼重設

系統 SHALL 提供密碼重設機制，支援管理員設定和 Email 重設（可選）。

#### Scenario: 管理員重設使用者密碼
- Given 租戶管理員已登入
- When 呼叫 POST /api/tenant/users/{user_id}/reset-password
- Then 系統產生隨機臨時密碼
- And 更新使用者密碼雜湊
- And 標記 must_change_password = true
- And 回傳臨時密碼給管理員（僅一次）

#### Scenario: Email 請求密碼重設
- Given 使用者有設定 Email
- When 在登入頁面輸入 Email 請求密碼重設
- Then 系統產生重設 token（有效期 1 小時）
- And 發送重設連結到該 Email
- And 顯示「如果此 Email 已註冊，您將收到重設密碼的郵件」

#### Scenario: 透過連結重設密碼
- Given 使用者點擊 Email 中的重設連結
- When token 有效且未過期
- And 使用者輸入新密碼
- Then 系統更新密碼雜湊
- And 清除 must_change_password 標記
- And 刪除重設 token
- And 顯示「密碼已更新，請重新登入」

#### Scenario: 重設連結過期
- Given 使用者點擊 Email 中的重設連結
- When token 已過期或不存在
- Then 系統顯示「重設連結已過期」
- And 提供重新請求的選項

---

### Requirement: 密碼變更

系統 SHALL 允許已登入的使用者變更密碼。

#### Scenario: 成功變更密碼
- Given 使用者已登入
- When 呼叫 POST /api/auth/change-password
- And 提供正確的目前密碼和新密碼
- Then 系統驗證目前密碼正確
- And 更新密碼雜湊
- And 設定 password_changed_at
- And 清除 must_change_password 標記

#### Scenario: 強制變更密碼
- Given 使用者的 must_change_password 為 true
- When 使用者登入後存取任何功能
- Then 系統要求先變更密碼
- And 變更完成後才能正常使用系統

#### Scenario: 目前密碼錯誤
- Given 使用者已登入
- When 呼叫 POST /api/auth/change-password
- And 目前密碼不正確
- Then 系統回傳錯誤「目前密碼錯誤」

#### Scenario: 新密碼不符要求
- Given 使用者變更密碼
- When 新密碼不符合複雜度要求
- Then 系統回傳錯誤「密碼需至少 8 個字元」

---

### Requirement: 使用者管理（租戶管理員）

系統 SHALL 允許租戶管理員管理該租戶內的使用者。

#### Scenario: 列出租戶內使用者
- Given 租戶管理員已登入
- When 呼叫 GET /api/tenant/users
- Then 系統回傳該租戶的所有使用者列表
- And 每個使用者包含 id、username、display_name、email、role、last_login_at

#### Scenario: 更新使用者資訊
- Given 租戶管理員已登入
- When 呼叫 PATCH /api/tenant/users/{user_id}
- And 提供要更新的欄位（display_name、email、role）
- Then 系統更新使用者資訊
- And 回傳更新後的資訊

#### Scenario: 停用使用者
- Given 租戶管理員已登入
- When 呼叫 DELETE /api/tenant/users/{user_id} 或設定 is_active = false
- Then 該使用者無法再登入
- And 現有 session 失效

#### Scenario: 無法操作其他租戶使用者
- Given 租戶 A 的管理員已登入
- When 嘗試操作租戶 B 的使用者
- Then 系統回傳 404 或 403 錯誤
