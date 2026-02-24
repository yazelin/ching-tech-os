## 1. 預設管理員帳號 Migration

- [x] 1.1 建立 `007_seed_admin_user.py` migration，插入預設管理員帳號（`ct` / `36274806` bcrypt hash，role=admin，must_change_password=True），使用 `ON CONFLICT (username) DO NOTHING`
- [x] 1.2 執行 `alembic upgrade head` 驗證 migration 成功

## 2. 後端服務層

- [x] 2.1 在 `services/user.py` 新增 `clear_user_password(user_id)` 函數，將 password_hash、password_changed_at 設為 NULL，must_change_password 設為 False

## 3. 後端 Pydantic 模型

- [x] 3.1 在 `models/user.py` 新增請求模型：`CreateUserRequest`（username, password, display_name, role）、`UpdateUserInfoRequest`（display_name, email, role）、`UpdateUserStatusRequest`（is_active）、`ResetPasswordRequest`（new_password）
- [x] 3.2 在 `models/user.py` 新增回應模型：`CreateUserResponse`、`UserOperationResponse`（通用成功/失敗回應）
- [x] 3.3 在 `AdminUserInfo` 模型新增 `has_password: bool` 欄位

## 4. 後端 API 端點

- [x] 4.1 在 `api/user.py` 新增 `POST /api/admin/users`（建立使用者），包含密碼強度驗證、帳號重複檢查
- [x] 4.2 在 `api/user.py` 新增 `PATCH /api/admin/users/{user_id}`（編輯使用者資訊），包含自我降級保護
- [x] 4.3 在 `api/user.py` 新增 `POST /api/admin/users/{user_id}/reset-password`（重設密碼），包含密碼強度驗證
- [x] 4.4 在 `api/user.py` 新增 `PATCH /api/admin/users/{user_id}/status`（停用/啟用），包含自我停用保護
- [x] 4.5 在 `api/user.py` 新增 `POST /api/admin/users/{user_id}/clear-password`（清除密碼），包含自我操作保護和 ENABLE_NAS_AUTH 檢查
- [x] 4.6 修改 `GET /api/admin/users` 回傳中加入 `has_password` 欄位

## 5. 前端 UI — 使用者列表改造

- [x] 5.1 在 `settings.js` 的使用者列表上方新增「新增使用者」按鈕
- [x] 5.2 在使用者列表中新增認證方式 badge 欄位（「密碼」/「NAS」）
- [x] 5.3 將使用者列表的「設定權限」單一按鈕替換為操作下拉選單（設定權限、編輯資訊、重設密碼、停用/啟用、清除密碼）
- [x] 5.4 停用帳號在列表中顯示視覺區分（降低不透明度），操作選單顯示「啟用」而非「停用」

## 6. 前端 UI — 對話框

- [x] 6.1 實作「新增使用者」對話框（帳號、密碼、顯示名稱、角色欄位），送出呼叫 `POST /api/admin/users`
- [x] 6.2 實作「編輯使用者」對話框（顯示名稱、Email、角色欄位），送出呼叫 `PATCH /api/admin/users/{user_id}`
- [x] 6.3 實作「重設密碼」對話框（新密碼欄位），送出呼叫 `POST /api/admin/users/{user_id}/reset-password`
- [x] 6.4 實作「停用/啟用」確認對話框，送出呼叫 `PATCH /api/admin/users/{user_id}/status`
- [x] 6.5 實作「清除密碼」確認對話框（含警告提示），送出呼叫 `POST /api/admin/users/{user_id}/clear-password`

## 7. 前端 CSS

- [x] 7.1 在 `settings.css` 新增操作下拉選單樣式、認證 badge 樣式、新增使用者按鈕樣式、停用帳號視覺樣式
- [x] 7.2 新增對話框樣式（沿用現有 permissions-dialog 模式），包含行動版響應式適配

## 8. 驗證

- [x] 8.1 測試預設管理員帳號登入 + 強制改密碼流程（需重啟服務）
- [x] 8.2 測試建立新 CTOS 使用者 → 用新帳號登入 → 強制改密碼
- [x] 8.3 測試清除密碼後使用者恢復 NAS 認證登入
- [x] 8.4 測試停用帳號後該使用者無法登入
- [x] 8.5 測試管理員自我保護限制（不能停用自己、不能清除自己密碼、不能降級自己）
