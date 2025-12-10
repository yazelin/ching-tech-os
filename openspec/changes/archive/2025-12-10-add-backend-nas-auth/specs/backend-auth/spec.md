# Capability: backend-auth

後端認證與 NAS 檔案存取服務。

---

## ADDED Requirements

### Requirement: NAS 認證登入
系統 SHALL 透過區網 NAS 的 SMB 認證來驗證使用者身份。

#### Scenario: 使用正確的 NAS 帳密登入
- Given 使用者在登入頁面
- When 輸入正確的 NAS 帳號和密碼並送出
- Then 系統回傳成功並提供 session token
- And 系統在 users 表建立或更新該使用者記錄
- And 使用者被導向桌面頁面

#### Scenario: 首次登入建立使用者記錄
- Given 使用者從未登入過此系統
- When 使用正確的 NAS 帳密首次登入
- Then 系統在 users 表新增該使用者
- And 記錄 created_at 和 last_login_at

#### Scenario: 再次登入更新登入時間
- Given 使用者曾經登入過此系統
- When 使用正確的 NAS 帳密再次登入
- Then 系統更新 users 表的 last_login_at

#### Scenario: 使用錯誤的帳密登入
- Given 使用者在登入頁面
- When 輸入錯誤的帳號或密碼並送出
- Then 系統回傳認證失敗錯誤
- And 顯示「帳號或密碼錯誤」訊息

#### Scenario: NAS 無法連線時登入
- Given NAS 伺服器無法連線
- When 使用者嘗試登入
- Then 系統回傳連線錯誤
- And 顯示「無法連線至檔案伺服器」訊息

---

### Requirement: Session 管理
系統 SHALL 使用 token 管理使用者登入狀態，憑證 MUST 儲存於 server 記憶體。

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

### Requirement: NAS 共享資料夾列表
系統 SHALL 提供 API 讓登入後的使用者查看 NAS 上的共享資料夾。

#### Scenario: 列出共享資料夾
- Given 使用者已登入
- When 呼叫取得共享資料夾 API
- Then 系統回傳該使用者有權存取的共享資料夾列表
- And 每個項目包含名稱和類型

---

### Requirement: 瀏覽 NAS 資料夾內容
系統 SHALL 提供 API 讓登入後的使用者瀏覽 NAS 資料夾內的檔案和子資料夾。

#### Scenario: 瀏覽資料夾內容
- Given 使用者已登入
- When 指定路徑呼叫瀏覽 API
- Then 系統回傳該資料夾內的檔案和子資料夾列表
- And 每個項目包含名稱、類型、大小（檔案）、修改時間

#### Scenario: 瀏覽無權限的資料夾
- Given 使用者已登入
- When 嘗試瀏覽無權限的資料夾
- Then 系統回傳 403 權限錯誤
- And 顯示「無權限存取此資料夾」訊息

---

## Related Capabilities
- `web-desktop`: 前端桌面介面，登入頁面整合
