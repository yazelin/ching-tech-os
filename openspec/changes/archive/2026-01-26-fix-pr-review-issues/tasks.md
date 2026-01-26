# Tasks

## 1. 簡化 delete_tenant 函數
- [x] 1.1 確認哪些資料表有設定 `ON DELETE CASCADE`
- [x] 1.2 移除 `delete_tenant` 中可透過 CASCADE 自動刪除的 DELETE 語句
- [x] 1.3 保留分割資料表（ai_logs, messages, login_records）的手動刪除邏輯
- [x] 1.4 加入註解說明保留手動刪除的原因

## 2. 改進 Migration 驗證
- [x] 2.1 修改 `055_set_tenant_not_null.py` 的空迴圈邏輯
- [x] 2.2 加入明確的 COUNT 檢查和錯誤訊息
- [x] 2.3 指出哪個資料表有未遷移的資料

## 3. 重構 user_role 判斷邏輯
- [x] 3.1 在 `services/user.py` 新增 `get_user_role()` 函數
- [x] 3.2 整合平台管理員、租戶管理員、一般用戶的判斷邏輯
- [x] 3.3 在 `api/auth.py` 的 login 函數中使用新函數
- [x] 3.4 確保其他需要判斷角色的地方也能複用

## 4. 合併 Push Message 發送
- [x] 4.1 在 `linebot.py` 新增 `push_messages()` 函數支援多則訊息
- [x] 4.2 修改 `linebot_ai.py` 中 fallback push 邏輯，合併文字和圖片訊息
- [x] 4.3 確保訊息順序正確（文字在前、圖片在後）
