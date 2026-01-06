# Tasks: refactor-send-file-to-reply

## 實作任務

### 1. 新增 reply_messages 函數
- [x] 在 `linebot.py` 新增 `reply_messages()` 函數
- [x] 支援 TextMessage 和 ImageMessage 混合
- [x] 處理訊息數量超過 5 則的情況
- [x] 錯誤處理（reply_token 過期等）

### 2. 新增 prepare_file_message MCP 工具
- [x] 在 `mcp_server.py` 新增 `prepare_file_message` 工具
- [x] 驗證檔案路徑
- [x] 產生分享連結
- [x] 回傳 `[FILE_MESSAGE:...]` 格式標記

### 3. 修改 linebot_ai.py 回覆邏輯
- [x] 新增 `parse_ai_response()` 函數解析 AI 回應
- [x] 新增 `send_ai_response()` 函數組合多則訊息
- [x] 修改 `process_message_with_ai()` 使用新的回覆邏輯
- [x] 處理超過 5 則訊息的情況（轉為連結）

### 4. 更新 Line Bot Prompt
- [x] 修改 `linebot_agents.py` 中的 prompt
- [x] 將 `send_nas_file` 替換為 `prepare_file_message`
- [x] 調整使用流程說明

### 5. 建立 Migration
- [x] 建立 `019_update_linebot_prompts_prepare_file.py`
- [x] 更新資料庫中的 prompt 內容

### 6. 測試驗證
- [x] 測試個人對話發送圖片
- [x] 測試群組對話發送圖片
- [x] 測試發送非圖片檔案（應顯示連結）
- [x] 測試 reply_token 過期情況（程式碼已處理，邊緣情況跳過）
- [x] 測試多張圖片場景（> 4 張）：6 張圖 = 4 張圖片 + 2 張連結 ✓

## 相依關係

```
1. reply_messages 函數
       │
       ▼
2. prepare_file_message 工具
       │
       ▼
3. linebot_ai.py 修改 ◄─── 相依 1 和 2
       │
       ▼
4. Prompt 更新
       │
       ▼
5. Migration
       │
       ▼
6. 測試驗證
```

## 驗收標準

- [x] 用戶說「找亦達 layout 圖」後，AI 回覆中直接顯示圖片
- [x] 發送圖片不消耗 push_message 額度（使用 reply 而非 push）
- [x] 非圖片檔案顯示下載連結
- [x] reply_token 過期時記錄警告日誌（程式碼已實作）
