## 1. 資料庫 Migration
- [x] 1.1 新增 `project_members.user_id` 欄位（INTEGER, 可 NULL, FK 到 users.id）
- [x] 1.2 更新 Prompt migration

## 2. 後端 API
- [x] 2.1 新增 `GET /api/user/list` API（列出所有用戶，供下拉選單使用）
- [x] 2.2 更新成員 API 支援 `user_id` 欄位

## 3. 前端 UI
- [x] 3.1 成員表單新增「關聯 CTOS 用戶」下拉選單
- [x] 3.2 勾選「內部人員」時顯示選擇器，取消時隱藏

## 4. MCP 工具實作
- [x] 4.1 實作 `update_project` 工具
- [x] 4.2 實作 `update_milestone` 工具
- [x] 4.3 實作 `update_project_member` 工具
- [x] 4.4 實作 `add_project_meeting` 工具
- [x] 4.5 實作 `update_project_meeting` 工具
- [x] 4.6 實作權限檢查共用函數（`check_project_member_permission`）

## 5. Line Bot Prompt 更新
- [x] 5.1 更新 `linebot_agents.py` 中的 Prompt 定義
- [x] 5.2 群組對話：說明只能操作綁定專案
- [x] 5.3 群組對話：說明未綁定時可操作任意專案
- [x] 5.4 個人對話：說明新工具可用

## 6. 權限控制實作（Phase 2）
- [x] 6.1 確認 `line_users.user_id` 已存在（可關聯 CTOS 用戶）
- [x] 6.2 更新 `linebot_ai.py` 在系統提示中加入 `ctos_user_id`
- [x] 6.3 MCP 更新工具加入 `ctos_user_id` 參數
- [x] 6.4 實作權限檢查（未關聯帳號/非成員的錯誤訊息）
- [x] 6.5 更新 Prompt 說明權限機制（migration 023）

## 7. 測試驗證
- [x] 7.1 測試各 MCP 工具功能
- [x] 7.2 測試群組綁定專案（結論：不需限制，由成員權限控制）
- [x] 7.3 測試成員權限檢查（成員可操作任意所屬專案）
- [x] 7.4 測試個人對話權限（只有成員可操作）
- [x] 7.5 測試非成員嘗試操作時的錯誤訊息
- [x] 7.6 測試未關聯 CTOS 帳號時的錯誤訊息
