# Tasks

## 1. 後端修改 - displayName 問題

- [x] 1.1 在 `linebot.py` 新增 `get_group_member_profile(group_id, user_id)` 函數
  - 呼叫 `api.get_group_member_profile(group_id, user_id)`
  - 回傳 `{"displayName": ..., "pictureUrl": ...}` 或 `None`

- [x] 1.2 修改 `save_message()` 函數
  - 群組訊息時：呼叫 `get_group_member_profile(line_group_id, line_user_id)`
  - 個人對話時：維持使用 `get_user_profile(line_user_id)`

## 2. 後端修改 - is_friend 問題

- [x] 2.1 修改 `get_or_create_user()` 函數
  - 新增 `is_friend` 參數
  - 建立用戶時設定正確的 `is_friend` 值
  - 更新用戶時不覆蓋 `is_friend`（好友狀態由事件決定）

- [x] 2.2 修改 `save_message()` 函數
  - 群組訊息：傳入 `is_friend=False`
  - 個人對話：傳入 `is_friend=True`

- [x] 2.3 修改 `get_or_create_bot_user()` 函數
  - Bot 用戶設定 `is_friend=False`
  - 現有 Bot 用戶如果 `is_friend=true` 會自動修正

## 3. 驗證

- [x] 3.1 在測試群組中發送訊息，確認記錄顯示正確的 displayName
- [x] 3.2 確認 MCP `summarize_chat` 工具顯示正確的用戶名稱
- [x] 3.3 確認前端用戶列表頁面不再顯示「未知用戶」
- [x] 3.4 確認群組用戶顯示「非好友」，個人對話用戶顯示「好友」
- [x] 3.5 確認 Bot（ChingTech AI）顯示「非好友」
