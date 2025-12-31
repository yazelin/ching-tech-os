# Tasks: add-linebot-image-ai

## Implementation Tasks

- [x] 1. 新增暫存圖片工具函式
  - 在 `linebot.py` 新增 `get_temp_image_path(message_id)` 函式
  - 暫存目錄：`/tmp/linebot-images/`
  - 新增 `ensure_temp_image(message_id, nas_path)` 從 NAS 複製到暫存

- [x] 2. 修改 `get_conversation_context` 包含圖片訊息
  - 在 `linebot_ai.py` 修改 SQL 查詢，包含 image 類型訊息
  - 圖片訊息格式化為 `[上傳圖片: {temp_path}]`
  - JOIN line_files 取得 nas_path 和 line_message_id

- [x] 3. 處理 `quotedMessageId` 回覆舊圖片
  - 在 `linebot_router.py` 取得 `message.quotedMessageId`
  - 傳遞到 `handle_text_message`
  - 如果回覆的是圖片，額外載入該圖片到暫存

- [x] 4. 新增 `ensure_temp_images_exist` 函式
  - 在 AI 處理前，確保對話歷史中的圖片暫存檔存在
  - 從 NAS 讀取並寫入暫存路徑

- [x] 5. 將 Read 工具加入允許清單
  - 在 `process_message_with_ai` 的 tools 列表加入 `"Read"`

- [x] 6. 新增暫存清理排程
  - 在 `scheduler.py` 新增清理任務
  - 每小時執行，刪除超過 1 小時的暫存檔

- [x] 7. 測試驗證
  - 傳送圖片後問「這是什麼」→ AI 應讀取圖片並描述
  - 傳送圖片後問「查專案進度」→ AI 應查專案，不讀圖片
  - 回覆很久以前的圖片詢問 → AI 應能讀取該圖片
  - 純文字對話 → 行為不變

## Notes

- 暫存檔使用 line_message_id 作為檔名，確保唯一性
- 對話歷史限制 20 則，圖片暫存不會太多
- quotedMessageId 是 Line 訊息 ID，需對應到內部 message_id
