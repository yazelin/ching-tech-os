# Tasks: 使用者功能權限系統

## 後端任務

### 權限核心功能

- [ ] 1. 在 config.py 新增 `admin_username` 設定（已完成於 refactor-config-env）
- [ ] 2. 新增 `permissions.py` 權限常數與預設值定義
- [ ] 3. 新增 `is_admin()` 函數檢查是否為管理員
- [ ] 4. 新增 `get_user_permissions()` 函數取得使用者權限（合併預設值）
- [ ] 5. 新增 `check_app_permission()` 函數檢查應用程式權限
- [ ] 6. 新增 `check_knowledge_permission()` 函數檢查知識庫權限

### 使用者 API 修改

- [ ] 7. 修改 `GET /api/user/me` 回應包含 `is_admin` 和 `permissions`
- [ ] 8. 新增 `GET /api/admin/users` 取得所有使用者列表（管理員限定）
- [ ] 9. 新增 `PATCH /api/admin/users/{user_id}/permissions` 更新使用者權限
- [ ] 10. 新增 `GET /api/admin/default-permissions` 取得預設權限設定

### 知識庫修改

- [ ] 11. 知識檔案新增 `owner` 和 `scope` 欄位
- [ ] 12. 修改知識庫搜尋 API 支援 scope 過濾
- [ ] 13. 修改知識庫寫入 API 檢查權限
- [ ] 14. 修改知識庫刪除 API 檢查權限
- [ ] 15. 新增 `POST /api/knowledge` 自動設定 owner 為目前使用者

## 前端任務

### 權限核心功能

- [ ] 16. 登入後儲存權限資訊到 `window.currentUser`
- [ ] 17. 新增 `canAccessApp(appId)` 權限檢查函數
- [ ] 18. 修改 `desktop.js` 根據權限過濾桌面圖示
- [ ] 19. 無權限應用程式顯示 toast 提示

### 使用者管理介面

- [ ] 20. 系統設定新增「使用者管理」分頁（管理員限定）
- [ ] 21. 使用者列表 UI：顯示使用者、顯示名稱、最後登入、操作按鈕
- [ ] 22. 權限設定對話框 UI：應用程式權限勾選、知識庫權限勾選
- [ ] 23. 儲存權限功能：呼叫 API 更新權限
- [ ] 24. 管理員標記：顯示管理員帳號且不可編輯

### 知識庫 UI 修改

- [ ] 25. 知識列表顯示 scope 標記（全域/個人）
- [ ] 26. 新增知識時可選擇 scope（預設個人）
- [ ] 27. 無權限操作顯示禁用狀態或提示

## 測試任務

- [ ] 28. 後端權限函數單元測試
- [ ] 29. 管理員 API 權限檢查測試
- [ ] 30. 知識庫權限檢查測試
- [ ] 31. 前端權限過濾功能測試

## 文件任務

- [ ] 32. 更新 backend-auth spec
- [ ] 33. 更新 knowledge-base spec
- [ ] 34. 新增 web-desktop spec 權限相關需求
