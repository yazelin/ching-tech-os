# Tasks: Line Bot Mention 用戶功能

## 1. 後端實作

- [x] 1.1 在 `linebot.py` 新增 import（`TextMessageV2`, `MentionSubstitutionObject`, `UserMentionTarget`）
- [x] 1.2 建立 `create_text_message_with_mention()` 輔助函數
- [x] 1.3 修改 `reply_messages()` 支援 `TextMessageV2` 訊息類型

## 2. AI 回應整合

- [x] 2.1 修改 `send_ai_response()` 新增 `mention_line_user_id` 參數
- [x] 2.2 在群組對話時，使用 `TextMessageV2` 帶 mention
- [x] 2.3 修改 `process_message_with_ai()` 傳遞 Line 用戶 ID

## 3. 測試驗證

- [x] 3.1 在測試群組發送訊息 @Bot，確認回覆有 mention
- [x] 3.2 確認被 mention 的用戶收到 Line 通知
- [x] 3.3 確認個人對話正常運作（無 mention）
- [x] 3.4 確認圖片+文字混合回覆仍正常
