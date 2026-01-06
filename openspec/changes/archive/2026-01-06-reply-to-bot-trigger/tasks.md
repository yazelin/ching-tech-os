# 實作任務清單

## 1. 新增查詢訊息來源的函數
- [x] 1.1 在 `linebot.py` 新增 `is_bot_message` 函數
  - 參數：`line_message_id`（Line 訊息 ID）
  - 查詢 `line_messages` 表的 `source_type` 欄位
  - 返回 `True` 如果是 bot 發送的訊息

## 2. 修改 AI 觸發判斷邏輯
- [x] 2.1 修改 `should_trigger_ai` 函數簽名
  - 新增參數 `is_reply_to_bot: bool = False`
- [x] 2.2 更新觸發邏輯
  - 群組對話：@ 機器人 **或** 回覆機器人訊息都觸發

## 3. 更新調用端
- [x] 3.1 修改 `process_message_with_ai` 調用 `should_trigger_ai` 的邏輯
  - 先查詢 `quoted_message_id` 是否為機器人訊息
  - 將結果傳入 `should_trigger_ai`
