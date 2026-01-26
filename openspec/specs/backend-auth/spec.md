# backend-auth Specification

## Purpose
TBD - created by archiving change add-backend-nas-auth. Update Purpose after archive.
## Requirements
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

### Requirement: 使用者資訊 API
系統 SHALL 提供 API 讓登入後的使用者查看和更新個人資訊。

#### Scenario: 取得目前使用者資訊
- Given 使用者已登入
- When 呼叫 GET /api/user/me
- Then 系統回傳該使用者的資訊
- And 包含 username、display_name、created_at、last_login_at

#### Scenario: 更新顯示名稱
- Given 使用者已登入
- When 呼叫 PATCH /api/user/me 並提供新的 display_name
- Then 系統更新資料庫中的 display_name
- And 回傳更新後的使用者資訊

#### Scenario: 未登入時存取使用者資訊
- Given 使用者未登入或 token 無效
- When 呼叫使用者資訊 API
- Then 系統回傳 401 未授權錯誤

### Requirement: NAS 檔案操作 API
系統 SHALL 提供 API 讓登入後的使用者對 NAS 檔案執行讀取、上傳、刪除、重命名、建立資料夾等操作。

#### Scenario: 讀取文字檔內容
- Given 使用者已登入
- When 呼叫 GET /api/nas/file?path=/share/folder/file.txt
- Then 系統回傳檔案內容
- And Content-Type 為 text/plain 或對應的 MIME 類型

#### Scenario: 讀取圖片檔
- Given 使用者已登入
- When 呼叫 GET /api/nas/file?path=/share/folder/image.jpg
- Then 系統回傳圖片二進位資料
- And Content-Type 為 image/jpeg 或對應的 MIME 類型

#### Scenario: 下載檔案
- Given 使用者已登入
- When 呼叫 GET /api/nas/download?path=/share/folder/file.txt
- Then 系統回傳檔案二進位資料
- And Content-Disposition 設定為 attachment
- And 檔案名稱正確編碼

#### Scenario: 上傳檔案
- Given 使用者已登入
- When 呼叫 POST /api/nas/upload 並附帶檔案和目標路徑
- Then 檔案儲存到 NAS 指定位置
- And 回傳成功訊息

#### Scenario: 刪除檔案
- Given 使用者已登入
- When 呼叫 DELETE /api/nas/file?path=/share/folder/file.txt
- Then 檔案從 NAS 刪除
- And 回傳成功訊息

#### Scenario: 刪除資料夾
- Given 使用者已登入且資料夾為空或允許遞迴刪除
- When 呼叫 DELETE /api/nas/file?path=/share/folder
- Then 資料夾從 NAS 刪除
- And 回傳成功訊息

#### Scenario: 重命名檔案或資料夾
- Given 使用者已登入
- When 呼叫 PATCH /api/nas/rename 並提供路徑和新名稱
- Then 項目重命名
- And 回傳成功訊息

#### Scenario: 建立資料夾
- Given 使用者已登入
- When 呼叫 POST /api/nas/mkdir 並提供路徑
- Then 在 NAS 建立新資料夾
- And 回傳成功訊息

#### Scenario: 操作無權限的檔案
- Given 使用者已登入
- When 對無權限的檔案或資料夾執行操作
- Then 系統回傳 403 權限錯誤
- And 顯示「無權限執行此操作」訊息

#### Scenario: 搜尋檔案
- Given 使用者已登入
- When 呼叫 GET /api/nas/search?path=/share&query=*.py&max_depth=3&max_results=100
- Then 系統遞迴搜尋指定路徑下符合條件的檔案和資料夾
- And 回傳結果列表包含 name、path、type
- And 支援萬用字元 * 和 ?

#### Scenario: 搜尋結果限制
- Given 使用者已登入
- When 搜尋結果超過 max_results 限制
- Then 系統回傳前 max_results 筆結果
- And max_depth 限制搜尋深度（預設 3 層，最大 10 層）
- And max_results 限制結果數量（預設 100，最大 500）

### Requirement: 管理員識別

系統 SHALL 使用資料庫中的 `users.role` 欄位識別管理員身份。

#### Scenario: 判斷管理員身份
- Given 使用者在 `users` 表中的 `role` 欄位為 `platform_admin`
- When 該使用者登入系統
- Then 系統識別該使用者為平台管理員
- And `GET /api/user/me` 回應 `role: "platform_admin"`

#### Scenario: 平台管理員擁有所有權限
- Given 使用者為平台管理員（role = 'platform_admin'）
- When 取得該使用者權限
- Then 所有應用程式權限均為 `true`
- And 所有知識庫權限均為 `true`

#### Scenario: 租戶管理員擁有租戶內完整權限
- Given 使用者為租戶管理員（role = 'tenant_admin'）
- When 取得該使用者權限
- Then 租戶範圍內的權限均為 `true`
- And 平台管理功能權限為 `false`

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

### Requirement: 使用者 App 權限控制
系統 SHALL 支援為每個使用者設定獨立的 App 權限，權限限制適用於 Web UI、後端 API 和 Line Bot AI。

#### Scenario: 平台管理員設定租戶管理員權限
- Given 平台管理員已登入
- When 修改某租戶管理員的 permissions.apps 設定
- Then 系統儲存該設定到 users 表
- And 該租戶管理員的可用功能立即受限

#### Scenario: 租戶管理員只能看到有權限的 App
- Given 租戶管理員已登入
- And 其 permissions.apps 中 "inventory" 為 false
- When 租戶管理員查看桌面
- Then 不顯示「庫存管理」App
- And 直接存取該 App URL 時顯示無權限錯誤

#### Scenario: 租戶管理員無法修改自己的權限
- Given 租戶管理員已登入
- When 嘗試修改自己的 permissions.apps
- Then 系統回傳 403 權限錯誤
- And 顯示「無法修改自己的權限」訊息

#### Scenario: 租戶管理員只能修改一般使用者權限
- Given 租戶管理員已登入
- When 嘗試修改另一個租戶管理員的權限
- Then 系統回傳 403 權限錯誤

#### Scenario: 新建租戶管理員自動初始化權限
- Given 平台管理員建立新的租戶管理員
- When 使用者建立成功
- Then 系統自動設定預設的 App 權限
- And 預設開啟大部分功能（除了 platform-admin、terminal、code-editor）

---

### Requirement: 後端 API App 權限檢查
系統 SHALL 在後端 API 層檢查使用者是否有對應的 App 權限，無權限時回傳 403 錯誤。

#### Scenario: 無專案管理權限時存取專案 API
- Given 使用者已登入
- And 其 permissions.apps 中 "project-management" 為 false
- When 呼叫 GET /api/project/list
- Then 系統回傳 403 權限錯誤
- And 回傳訊息說明需要「專案管理」權限

#### Scenario: 有權限時正常存取 API
- Given 使用者已登入
- And 其 permissions.apps 中 "project-management" 為 true
- When 呼叫 GET /api/project/list
- Then API 正常回應專案列表

#### Scenario: 平台管理員不受 API 權限限制
- Given 平台管理員已登入
- When 呼叫任何 API
- Then API 正常回應
- Note 平台管理員擁有所有權限

---

### Requirement: Line Bot AI App 權限控制
系統 SHALL 根據使用者的 App 權限，動態調整 Line Bot AI 可用的工具和 Prompt。

#### Scenario: 無專案管理權限的使用者使用 Line Bot
- Given 使用者透過 Line 與 Bot 對話
- And 其 permissions.apps 中 "project-management" 為 false
- When 使用者詢問專案相關問題
- Then AI 回應說明使用者沒有專案管理權限
- And AI 不會嘗試呼叫專案相關工具

#### Scenario: AI 只看到有權限的工具
- Given 使用者透過 Line 與 Bot 對話
- And 其 permissions.apps 只有 "knowledge-base" 為 true
- When AI 處理使用者訊息
- Then AI 的可用工具列表只包含知識庫相關工具
- And Prompt 只說明知識庫功能

#### Scenario: 執行時權限檢查（雙重保險）
- Given 使用者透過 Line 與 Bot 對話
- And 其 permissions.apps 中 "inventory" 為 false
- When AI 嘗試呼叫庫存相關工具（繞過前置過濾）
- Then 系統在執行工具時檢查權限
- And 回傳「您沒有庫存管理權限」訊息

#### Scenario: 群組對話中的權限檢查
- Given 使用者在群組中與 Bot 對話
- And 該使用者的 permissions.apps 有限制
- When AI 處理該使用者的訊息
- Then 權限檢查基於發訊息的使用者
- And 不是基於群組設定

### Requirement: User Role Determination Service
系統 SHALL 提供獨立的 `get_user_role()` 服務函數，用於判斷用戶角色。

#### Scenario: 判斷平台管理員
- **WHEN** 用戶名稱在 `PLATFORM_ADMINS` 清單中
- **THEN** 回傳角色 `platform_admin`

#### Scenario: 判斷租戶管理員
- **WHEN** 用戶在 `tenant_admins` 表中有對應記錄
- **THEN** 回傳角色 `tenant_admin`

#### Scenario: 判斷一般用戶
- **WHEN** 用戶不是平台管理員也不是租戶管理員
- **THEN** 回傳角色 `user`

### Requirement: Tenant Deletion with CASCADE
系統 SHALL 在刪除租戶時利用資料庫 CASCADE 機制自動刪除關聯資料，僅對無法設定外鍵的分割資料表執行手動刪除。

#### Scenario: 刪除租戶時自動清理關聯資料
- **WHEN** 刪除一個租戶
- **THEN** 透過 CASCADE 自動刪除 users, projects, vendors 等有外鍵關聯的資料

#### Scenario: 手動清理分割資料表
- **WHEN** 刪除一個租戶
- **THEN** 手動刪除 ai_logs, messages 等分割資料表的資料

### Requirement: Migration Validation
資料庫 Migration SHALL 在設定 NOT NULL 約束前進行明確的驗證，並提供清晰的錯誤訊息。

#### Scenario: 發現未遷移資料
- **WHEN** 執行 migration 且有資料表的 tenant_id 為 NULL
- **THEN** 拋出例外並說明哪個資料表有問題、有多少筆未遷移資料

