# Tasks: add-ai-tool-tracing

## 任務列表

### 1. 後端：修改 ClaudeResponse 資料結構
- [x] 新增 `ToolCall` dataclass
- [x] 修改 `ClaudeResponse` 新增 `tool_calls`、`input_tokens`、`output_tokens` 欄位
- **驗證**：單元測試確認資料結構正確

### 2. 後端：修改 call_claude 使用 stream-json
- [x] 修改 CLI 參數加入 `--output-format stream-json --verbose`
- [x] 實作 stream-json 輸出解析邏輯
- [x] 提取工具調用記錄（tool_use + tool_result 配對）
- [x] 提取最終回應文字和 token 統計
- **驗證**：手動測試 Claude CLI 調用，確認解析正確

### 3. 後端：更新 AI Log 記錄
- [x] 修改 `api/ai.py` 的 `ai_chat_event`，將 `tool_calls` 存入 `parsed_response`
- [x] 記錄 `input_tokens` 和 `output_tokens`
- [x] 修改 Line Bot 相關調用處（`linebot_ai.py`）
- **驗證**：透過 Web Chat 發送訊息，確認 AI Log 記錄完整

### 4. 前端：新增執行流程區塊
- [x] 修改 `ai-log.js` 的 `selectLog` 函數
- [x] 解析 `parsed_response.tool_calls` 並渲染執行流程
- [x] 實作收合/展開功能
- [x] JSON 格式化顯示
- **驗證**：開啟 AI Log 應用，確認執行流程正確顯示

### 5. 前端：執行流程樣式
- [x] 新增 `.ai-log-flow` 相關 CSS 樣式
- [x] 工具調用區塊樣式（圖示、邊框、收合按鈕）
- [x] 輸入輸出區塊樣式
- [x] 最終回應區塊樣式
- **驗證**：視覺檢查樣式正確

### 6. 整合測試
- [x] 測試 Web Chat 發送訊息，AI Log 正確記錄
- [x] 測試 Line Bot 發送訊息，AI Log 正確記錄
- [x] 測試無工具調用的情況，不顯示執行流程區塊
- [x] 測試舊 Log（無 parsed_response），正常顯示

## 依賴關係

```
[1] → [2] → [3] → [6]
              ↘
         [4] → [5] → [6]
```

- 任務 1、2、3 需依序執行（後端）
- 任務 4、5 可與 3 並行執行（前端）
- 任務 6 需等所有任務完成
