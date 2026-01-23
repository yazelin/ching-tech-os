## ADDED Requirements

### Requirement: 使用者資料模型擴充

系統 SHALL 擴充使用者資料模型以支援獨立會員系統。

#### Scenario: 使用者表新增欄位
- Given 系統執行資料庫遷移
- Then users 表新增以下欄位：
  - `password_hash` VARCHAR(255) - bcrypt 密碼雜湊
  - `email` VARCHAR(255) - 使用者 Email（可選）
  - `password_changed_at` TIMESTAMPTZ - 密碼最後更改時間
  - `must_change_password` BOOLEAN DEFAULT FALSE - 下次登入需更改密碼
  - `is_active` BOOLEAN DEFAULT TRUE - 帳號是否啟用

#### Scenario: username 唯一性約束變更
- Given 系統執行資料庫遷移
- Then 移除 username 全域唯一約束
- And 新增 (tenant_id, username) 複合唯一約束
- And 不同租戶可有相同 username

#### Scenario: Email 租戶內唯一
- Given 系統執行資料庫遷移
- Then 新增 (tenant_id, email) 部分索引（email IS NOT NULL）
- And 同一租戶內 Email 不可重複

#### Scenario: 密碼重設 Token 表
- Given 系統執行資料庫遷移
- Then 建立 password_reset_tokens 表：
  - `id` UUID PRIMARY KEY
  - `user_id` INTEGER REFERENCES users(id)
  - `token` VARCHAR(64) UNIQUE NOT NULL
  - `expires_at` TIMESTAMPTZ NOT NULL
  - `created_at` TIMESTAMPTZ DEFAULT NOW()

---

### Requirement: 登入頁面更新

系統 SHALL 更新登入頁面以支援新的認證機制。

#### Scenario: 登入頁面顯示
- Given 使用者訪問登入頁面
- Then 顯示登入表單
- And 包含租戶代碼輸入欄位（多租戶模式）
- And 包含 username 輸入欄位
- And 包含密碼輸入欄位
- And 顯示「忘記密碼」連結（若有 Email 功能）

#### Scenario: 單租戶模式登入
- Given 系統為單租戶模式
- Then 登入頁面隱藏租戶代碼欄位
- And 使用者僅需輸入 username 和密碼

#### Scenario: 強制變更密碼頁面
- Given 使用者登入成功但需強制變更密碼
- Then 顯示密碼變更表單
- And 使用者必須輸入新密碼
- And 變更成功後才能進入桌面

---

### Requirement: 密碼重設頁面

系統 SHALL 提供密碼重設流程的相關頁面。

#### Scenario: 忘記密碼頁面
- Given 使用者點擊「忘記密碼」
- Then 顯示忘記密碼表單
- And 包含租戶代碼輸入欄位（多租戶模式）
- And 包含 Email 輸入欄位
- And 包含「發送重設連結」按鈕

#### Scenario: 重設密碼頁面
- Given 使用者點擊 Email 中的重設連結
- When token 有效
- Then 顯示重設密碼表單
- And 包含新密碼輸入欄位
- And 包含確認新密碼輸入欄位

#### Scenario: 重設連結無效頁面
- Given 使用者點擊 Email 中的重設連結
- When token 無效或已過期
- Then 顯示錯誤頁面
- And 訊息：「此連結已失效或過期」
- And 提供「重新請求密碼重設」按鈕

---

### Requirement: 租戶管理員使用者管理介面

系統 SHALL 提供租戶管理員管理使用者的介面。

#### Scenario: 使用者列表頁面
- Given 租戶管理員登入
- When 進入使用者管理頁面
- Then 顯示該租戶的使用者列表
- And 每個使用者顯示：username、顯示名稱、Email、角色、最後登入時間、帳號狀態

#### Scenario: 新增使用者對話框
- Given 租戶管理員在使用者列表
- When 點擊「新增使用者」
- Then 顯示新增使用者對話框
- And 包含 username（必填）、顯示名稱、Email、角色選擇
- And 包含密碼選項：「自訂密碼」或「產生臨時密碼」

#### Scenario: 新增使用者成功
- Given 租戶管理員填寫新增使用者表單
- When 選擇「產生臨時密碼」並提交
- Then 系統建立使用者
- And 顯示臨時密碼（僅一次）
- And 提示管理員將密碼告知使用者

#### Scenario: 重設使用者密碼
- Given 租戶管理員在使用者列表
- When 對某使用者點擊「重設密碼」
- Then 系統產生新的臨時密碼
- And 顯示臨時密碼（僅一次）
- And 該使用者下次登入需變更密碼

#### Scenario: 停用使用者帳號
- Given 租戶管理員在使用者列表
- When 對某使用者點擊「停用」
- Then 系統標記該使用者為停用
- And 該使用者無法再登入
- And 列表顯示「已停用」狀態

---

### Requirement: NAS 連線 API

系統 SHALL 提供 NAS 連線管理 API。

#### Scenario: 建立 NAS 連線
- Given 使用者已登入 CTOS
- When 呼叫 POST /api/nas/connect
- And 提供 NAS IP、帳號、密碼
- Then 系統驗證憑證
- And 建立 NAS 連線
- And 回傳連線 token（有效期 30 分鐘）

#### Scenario: 建立 NAS 連線失敗 - 認證錯誤
- Given 使用者已登入 CTOS
- When 呼叫 POST /api/nas/connect
- And 提供錯誤的 NAS 憑證
- Then 系統回傳 401 錯誤
- And 訊息：「NAS 帳號或密碼錯誤」

#### Scenario: 建立 NAS 連線失敗 - 無法連線
- Given 使用者已登入 CTOS
- When 呼叫 POST /api/nas/connect
- And NAS 主機無法連線
- Then 系統回傳 503 錯誤
- And 訊息：「無法連線至 NAS 伺服器」

#### Scenario: 斷開 NAS 連線
- Given 使用者已建立 NAS 連線
- When 呼叫 DELETE /api/nas/disconnect
- And 提供連線 token
- Then 系統關閉該 NAS 連線
- And 刪除連線 token
- And 回傳成功訊息

#### Scenario: NAS 操作需帶入連線 token
- Given 使用者已建立 NAS 連線
- When 呼叫任何 NAS 檔案操作 API
- Then 請求 MUST 包含 X-NAS-Token header
- And 系統驗證 token 有效性
- And 使用對應連線執行操作

#### Scenario: NAS 連線 token 過期
- Given 使用者的 NAS 連線 token 已過期
- When 呼叫 NAS 檔案操作 API
- Then 系統回傳 401 錯誤
- And 錯誤碼為 NAS_TOKEN_EXPIRED
- And 前端顯示重新連線對話框

#### Scenario: NAS 操作延長連線
- Given 使用者已建立 NAS 連線
- When 進行檔案操作
- Then 系統自動延長連線有效期
- And 重設為 30 分鐘後過期
