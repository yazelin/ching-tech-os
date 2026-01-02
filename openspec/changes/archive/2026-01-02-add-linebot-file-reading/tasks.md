# Tasks: add-linebot-file-reading

## 任務列表

### 1. 後端：新增檔案暫存機制（linebot.py）
- [x] 定義 `TEMP_FILE_DIR = "/tmp/linebot-files"`
- [x] 定義可讀取的檔案副檔名列表（txt, md, json, csv, log, xml, yaml, yml, pdf）
- [x] 新增 `get_temp_file_path(line_message_id, filename)` 函數
- [x] 新增 `ensure_temp_file(line_message_id, nas_path, filename)` 函數
- [x] 新增 `get_file_info_by_line_message_id(line_message_id)` 函數（查詢 file 類型）
- [x] 新增 `is_readable_file(filename)` 函數（判斷是否為可讀取類型）
- **驗證**：手動測試函數正確建立暫存檔

### 2. 後端：修改對話歷史組合（linebot_ai.py）
- [x] 修改 `get_conversation_context()` SQL 查詢包含 file 類型訊息
- [x] 檔案訊息格式化為 `[上傳檔案: /tmp/linebot-files/{message_id}_{filename}]`
- [x] 不可讀取的檔案顯示 `[上傳檔案: {filename}（無法讀取此類型）]`
- [x] 呼叫 AI 前呼叫 `ensure_temp_file()` 確保暫存存在
- **驗證**：發送檔案後查看對話歷史包含檔案路徑

### 3. 後端：支援回覆檔案訊息（linebot_ai.py）
- [x] 修改 `handle_ai_chat()` 處理 `quotedMessageId` 為檔案訊息
- [x] 使用 `get_file_info_by_line_message_id()` 查詢被回覆的檔案
- [x] 載入被回覆的檔案到暫存
- [x] 在用戶訊息中標註 `[回覆檔案: {temp_path}]`
- **驗證**：回覆檔案訊息時 AI 能讀取該檔案

### 4. 後端：擴展 Scheduler 清理（scheduler.py）
- [x] 修改 `cleanup_linebot_temp_images()` 為 `cleanup_linebot_temp_files()`
- [x] 同時清理 `/tmp/linebot-images/` 和 `/tmp/linebot-files/`
- **驗證**：確認排程清理兩個目錄

### 5. 後端：支援 Google 文件連結（額外功能）
- [x] 在 prompt 中加入 Google Docs/Sheets/Slides 處理說明
- [x] 新增 WebFetch 工具到 agents（讀取網頁和 Google 匯出連結）
- [x] 測試 Google Slides export 功能正常（txt, pdf, pptx 都回傳 200）

### 6. 整合測試
- [x] 測試上傳 .txt 檔案，AI 能讀取內容
- [x] 測試上傳 .pdf 檔案，AI 能讀取內容
- [x] 測試回覆舊檔案訊息，AI 能讀取該檔案
- [x] 測試不支援的檔案類型（如 .docx），AI 告知無法讀取
- [x] 測試 Google 文件連結，AI 能讀取內容
- [x] 確認 scheduler 正確清理暫存

### 7. 額外改進：Prompt 架構優化
- [x] 將工具說明從 DB prompt 移至 build_system_prompt 動態組合
- [x] 統一 linebot-personal 和 linebot-group 的 prompt 格式
- [x] 區分群組專用工具（summarize_chat 只給群組）

## 依賴關係

```
[1] → [2] → [5]
 ↓     ↓
[4]   [3] → [5]
```

- 任務 1 為基礎設施
- 任務 2、3、4 依賴任務 1，可並行
- 任務 5 為最終整合測試
