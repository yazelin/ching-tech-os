# Tasks: Line Bot 存取控制

## 1. 資料庫 Migration
- [x] 1.1 新增 `line_groups.allow_ai_response` 欄位（預設 false）
- [x] 1.2 新增 `line_binding_codes` 表
- [x] 1.3 執行 migration 測試

## 2. 後端 - 綁定服務
- [x] 2.1 實作 `generate_binding_code()` - 產生 6 位數字驗證碼
- [x] 2.2 實作 `verify_binding_code()` - 驗證並完成綁定
- [x] 2.3 實作 `unbind_line_user()` - 解除綁定
- [x] 2.4 實作 `get_binding_status()` - 查詢綁定狀態

## 3. 後端 - 存取控制
- [x] 3.1 實作 `check_line_access()` - 檢查用戶是否有權限
- [x] 3.2 修改 `process_message_event()` - 加入綁定驗證碼處理
- [x] 3.3 修改 `should_trigger_ai()` - 加入存取控制檢查
- [x] 3.4 實作未綁定用戶的回覆訊息

## 4. 後端 - API 端點
- [x] 4.1 `POST /api/linebot/binding/generate-code` - 產生驗證碼
- [x] 4.2 `GET /api/linebot/binding/status` - 查詢綁定狀態
- [x] 4.3 `DELETE /api/linebot/binding` - 解除綁定
- [x] 4.4 `PATCH /api/linebot/groups/{id}` - 更新群組設定（allow_ai_response）
- [x] 4.5 更新 `GET /api/linebot/users` - 包含綁定狀態資訊

## 5. 前端 - Line Bot 管理介面
- [x] 5.1 新增「我的 Line 綁定」區塊
  - 顯示綁定狀態
  - 產生驗證碼按鈕
  - 解除綁定按鈕
- [x] 5.2 群組列表新增「允許 AI 回應」開關
- [x] 5.3 用戶列表顯示綁定狀態欄位

## 6. 規格更新
- [x] 6.1 更新 line-bot spec
- [x] 6.2 更新 backend-auth spec（如需要）- 不需要

## 7. 測試與驗證
- [x] 7.1 測試綁定流程（產生驗證碼 → Line 傳送 → 綁定成功）
- [x] 7.2 測試解除綁定流程
- [x] 7.3 測試存取控制（未綁定用戶不回應）
- [x] 7.4 測試群組 AI 回應開關
