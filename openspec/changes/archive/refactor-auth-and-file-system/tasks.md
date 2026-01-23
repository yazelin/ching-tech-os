# Tasks: 認證系統與檔案管理架構重構

## Phase 1：資料庫準備（非破壞性）

- [ ] 1.1 建立 migration：users 表新增欄位
  - `email` VARCHAR(255) UNIQUE（允許 NULL）
  - `password_hash` VARCHAR(255)（允許 NULL）
  - `email_verified` BOOLEAN DEFAULT FALSE
  - `email_verified_at` TIMESTAMPTZ
  - `password_changed_at` TIMESTAMPTZ
  - `must_change_password` BOOLEAN DEFAULT FALSE
- [ ] 1.2 建立 migration：email_verification_tokens 表
- [ ] 1.3 建立 migration：password_reset_tokens 表
- [ ] 1.4 新增 bcrypt 依賴到 pyproject.toml
- [ ] 1.5 執行 migration 並驗證

## Phase 2：後端 - 新增會員 API（與舊 API 並存）

- [ ] 2.1 建立 `services/password.py`：密碼雜湊/驗證服務
- [ ] 2.2 建立 `services/email.py`：Email 發送服務（SMTP/SendGrid）
- [ ] 2.3 建立 `services/auth_token.py`：驗證 Token 管理
- [ ] 2.4 新增 API：`POST /api/auth/register`
  - 驗證 Email 格式和唯一性
  - 密碼複雜度檢查
  - 建立使用者並發送驗證信
- [ ] 2.5 新增 API：`POST /api/auth/verify-email`
  - 驗證 Token
  - 更新 email_verified
- [ ] 2.6 新增 API：`POST /api/auth/resend-verification`
  - 產生新 Token
  - 重新發送驗證信
- [ ] 2.7 新增 API：`POST /api/auth/forgot-password`
  - 產生重設 Token
  - 發送重設信
- [ ] 2.8 新增 API：`POST /api/auth/reset-password`
  - 驗證 Token
  - 更新密碼
- [ ] 2.9 新增 API：`POST /api/auth/change-password`
  - 驗證目前密碼
  - 更新密碼
- [ ] 2.10 修改 `POST /api/auth/login`：支援 Email + 密碼登入
  - 檢測登入方式（Email vs 舊 SMB）
  - 暫時保留舊 SMB 登入
- [ ] 2.11 單元測試：註冊流程
- [ ] 2.12 單元測試：登入流程
- [ ] 2.13 單元測試：密碼重設流程

## Phase 3：後端 - NAS 連線管理 API

- [ ] 3.1 建立 `services/nas_connection.py`：NAS 連線池管理
  - Connection 類別（封裝 SMB 連線）
  - 連線 Token 產生/驗證
  - 逾時清理機制
- [ ] 3.2 新增 API：`POST /api/nas/connect`
  - 驗證 NAS 憑證
  - 建立連線並回傳 Token
- [ ] 3.3 新增 API：`DELETE /api/nas/disconnect`
  - 關閉 NAS 連線
- [ ] 3.4 修改現有 NAS API：改為接受 X-NAS-Token header
  - `GET /api/nas/shares`
  - `GET /api/nas/browse`
  - `GET /api/nas/file`
  - `POST /api/nas/upload`
  - `DELETE /api/nas/file`
  - `PATCH /api/nas/rename`
  - `POST /api/nas/mkdir`
  - `GET /api/nas/search`
  - `GET /api/nas/download`
- [ ] 3.5 新增 FastAPI Dependency：驗證 NAS Token
- [ ] 3.6 單元測試：NAS 連線管理
- [ ] 3.7 單元測試：NAS API Token 驗證

## Phase 4：後端 - 管理員功能增強

- [ ] 4.1 新增 API：`POST /api/admin/users/{user_id}/invite`
  - 產生邀請 Token
  - 發送邀請信
- [ ] 4.2 新增 API：`POST /api/admin/users/{user_id}/set-password`
  - 設定臨時密碼
  - 標記需更改密碼
- [ ] 4.3 新增 API：`POST /api/admin/users/{user_id}/resend-verification`
  - 重新發送驗證信
- [ ] 4.4 修改 `GET /api/admin/users`：回傳 Email 驗證狀態
- [ ] 4.5 單元測試：管理員 API

## Phase 5：前端 - 登入/註冊頁面

- [ ] 5.1 修改 `login.html`：更新登入表單
  - Email 輸入欄位
  - 忘記密碼連結
  - 註冊連結
- [ ] 5.2 建立 `register.html`：註冊頁面
- [ ] 5.3 建立 `verify-email.html`：Email 驗證頁面
- [ ] 5.4 建立 `forgot-password.html`：忘記密碼頁面
- [ ] 5.5 建立 `reset-password.html`：重設密碼頁面
- [ ] 5.6 修改 `login.js`：支援 Email 登入
- [ ] 5.7 建立 `js/register.js`：註冊邏輯
- [ ] 5.8 建立 `js/password-reset.js`：密碼重設邏輯
- [ ] 5.9 建立 `css/auth-pages.css`：認證頁面樣式

## Phase 6：前端 - 檔案管理器 NAS 連線

- [ ] 6.1 建立 `js/nas-connection-dialog.js`：NAS 連線對話框模組
  - 連線表單 UI
  - 連線設定儲存（加密）
  - 已儲存連線列表
- [ ] 6.2 修改 `file-manager.js`：整合 NAS 連線對話框
  - 開啟時檢查連線狀態
  - 顯示連線對話框
  - 連線成功後載入檔案
- [ ] 6.3 修改 `file-manager.js`：所有 API 呼叫帶入 NAS Token
- [ ] 6.4 新增狀態列：顯示 NAS 連線資訊
- [ ] 6.5 新增「斷開連線」按鈕
- [ ] 6.6 新增「連線其他 NAS」功能
- [ ] 6.7 建立 `css/nas-connection.css`：連線對話框樣式

## Phase 7：前端 - 管理介面更新

- [ ] 7.1 修改使用者列表：顯示 Email 驗證狀態
- [ ] 7.2 新增「發送邀請連結」按鈕
- [ ] 7.3 新增「設定臨時密碼」按鈕
- [ ] 7.4 新增「重新發送驗證信」按鈕

## Phase 8：Session 結構變更

- [ ] 8.1 修改 `SessionData` model：移除 password 欄位
- [ ] 8.2 修改 `session.py`：更新 Session 建立邏輯
- [ ] 8.3 確認所有使用 Session password 的地方已改用 NAS Token
- [ ] 8.4 整合測試：完整登入 → 檔案操作流程

## Phase 9：使用者遷移

- [ ] 9.1 建立遷移腳本：為現有使用者產生邀請連結
- [ ] 9.2 建立遷移腳本：管理員可批次設定臨時密碼
- [ ] 9.3 建立文件：使用者遷移指南
- [ ] 9.4 執行測試環境遷移

## Phase 10：清理與最終化

- [ ] 10.1 移除舊 SMB 認證登入代碼
- [ ] 10.2 移除 Session 中 password 欄位的所有引用
- [ ] 10.3 更新 API 文件
- [ ] 10.4 更新使用者手冊
- [ ] 10.5 效能測試：NAS 連線池
- [ ] 10.6 安全測試：認證流程
- [ ] 10.7 更新 openspec 規格（archive）

## 環境變數新增

- `EMAIL_SMTP_HOST` - SMTP 伺服器
- `EMAIL_SMTP_PORT` - SMTP 埠號
- `EMAIL_SMTP_USER` - SMTP 帳號
- `EMAIL_SMTP_PASSWORD` - SMTP 密碼
- `EMAIL_FROM_ADDRESS` - 發件人地址
- `EMAIL_FROM_NAME` - 發件人名稱
- `EMAIL_REQUIRED` - 是否強制 Email 驗證（預設 true）
- `PASSWORD_MIN_LENGTH` - 密碼最小長度（預設 8）
- `NAS_CONNECTION_TIMEOUT_MINUTES` - NAS 連線逾時（預設 30）

## 依賴新增

- `bcrypt` - 密碼雜湊
- `email-validator` - Email 格式驗證
- `aiosmtplib` - 非同步 SMTP（或 httpx + SendGrid API）
