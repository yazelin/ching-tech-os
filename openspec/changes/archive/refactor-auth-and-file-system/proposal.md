# Change: 重構認證系統與檔案管理架構

## Why

目前系統採用 NAS SMB 帳號作為唯一認證方式，存在以下限制：

1. **綁定 NAS 帳號**：使用者必須擁有公司 NAS 帳號才能使用系統，限制了 SaaS 部署和外部用戶場景
2. **密碼儲存於 Session**：SMB 密碼需存於伺服器記憶體以供檔案操作，Server 重啟後 Session 失效
3. **單一 NAS 來源**：檔案管理器固定連接環境變數指定的 NAS，無法讓用戶動態連接其他 NAS
4. **無獨立會員系統**：無法獨立於 NAS 管理使用者帳號、密碼重設等

這個變更將把 CTOS 從「NAS 輔助工具」轉型為「獨立的工作平台」。

## What Changes

### 1. 認證系統重構（**BREAKING**）

- **移除 NAS SMB 認證登入**：不再使用 SMB 驗證作為主要登入機制
- **新增獨立會員系統**（由管理員建立帳號，不開放自助註冊）：
  - 使用者表新增 `password_hash`、`email`（可選）等欄位
  - 支援 username + 密碼登入（租戶範圍內唯一）
  - 支援密碼重設功能（管理員設定或 Email 重設）
- **階層式帳號管理**：
  - **平台管理員**：建立租戶、指定租戶管理員
  - **租戶管理員**：建立該租戶內的使用者帳號
  - **一般使用者**：登入使用，可綁定 Line 帳號
- **帳號隔離**：username 在租戶範圍內唯一（不同租戶可有相同 username）
- **Session 結構變更**：移除 `password` 欄位，改為儲存 user_id 和必要的權限資訊

### 2. 檔案管理架構重構（**BREAKING**）

- **移除自動 NAS 連線**：開啟檔案管理器時不再自動連接預設 NAS
- **新增 NAS 連線對話框**：
  - 使用者開啟檔案管理器時，彈出對話框輸入 NAS IP、帳號、密碼
  - 支援記住連線設定（可選，憑證加密儲存於本地）
  - 支援多個 NAS 連線配置
- **連線生命週期**：NAS 連線僅在檔案管理視窗開啟期間有效，關閉後斷開
- **NAS 憑證隔離**：NAS 帳密不再與系統登入綁定，Session 中不儲存 NAS 密碼

### 3. 後端 API 變更

- **新增帳號管理 API**（管理員專用）：
  - `POST /api/admin/tenants/{id}/users` - 平台管理員建立租戶使用者
  - `POST /api/tenant/users` - 租戶管理員建立使用者
  - `PATCH /api/tenant/users/{id}` - 更新使用者
  - `POST /api/tenant/users/{id}/reset-password` - 重設使用者密碼
- **修改登入 API**：從 SMB 驗證改為密碼雜湊驗證
- **新增 NAS 連線 API**：
  - `POST /api/nas/connect` - 建立 NAS 連線（回傳連線 token）
  - `DELETE /api/nas/disconnect` - 斷開 NAS 連線
  - `GET /api/nas/shares` 等現有 API 需改為接受 NAS 連線 token

### 4. 資料遷移考量

- **現有使用者遷移**：現有 users 表的使用者需由管理員設定密碼才能登入
- **平台管理員帳號**：需另外建立 platform_admin 帳號
- **username 唯一性約束變更**：從全域唯一改為 (tenant_id, username) 複合唯一

## Impact

- **Affected specs**:
  - `backend-auth` - 完全重寫認證機制
  - `file-manager` - 新增 NAS 連線流程
  - `user-management` - 新增帳號管理功能
- **Affected code**:
  - `backend/src/ching_tech_os/api/auth.py` - 認證 API 重寫
  - `backend/src/ching_tech_os/api/tenant.py` - 租戶管理員功能
  - `backend/src/ching_tech_os/services/session.py` - Session 結構變更
  - `backend/src/ching_tech_os/services/smb.py` - NAS 連線管理
  - `backend/src/ching_tech_os/api/nas.py` - NAS API 重構
  - `frontend/js/login.js` - 登入介面
  - `frontend/js/file-manager.js` - NAS 連線對話框
  - `backend/migrations/versions/` - 多個資料庫遷移

## Risk Assessment

| 風險 | 等級 | 緩解措施 |
|------|------|----------|
| 現有使用者無法登入 | 高 | 提供遷移腳本，管理員為現有用戶設定臨時密碼 |
| SMB 檔案操作中斷 | 中 | NAS 連線 token 機制確保連線持續有效 |
| 資料庫遷移失敗 | 中 | 分階段遷移，每階段可回滾 |

## Migration Strategy

1. **Phase 1**：新增資料庫欄位，修改 username 唯一性約束
2. **Phase 2**：部署新 API 端點（與舊端點並存）
3. **Phase 3**：前端支援兩種登入模式
4. **Phase 4**：遷移現有用戶（管理員設定密碼）
5. **Phase 5**：移除舊 SMB 認證代碼
