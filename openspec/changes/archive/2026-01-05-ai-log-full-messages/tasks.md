# Tasks: AI Log 完整輸入記錄

## 任務列表

### 1. 修正 input_prompt 記錄邏輯 ✅
- [x] 修改 `ai_manager.py:call_agent()` 記錄完整對話

### 2. 新增 allowed_tools 欄位 ✅
- [x] 建立 migration `015_add_allowed_tools_to_ai_logs.py`
- [x] 執行 migration

### 3. 後端記錄 allowed_tools ✅
- [x] 更新 `AiLogCreate` model 新增 `allowed_tools` 欄位
- [x] 更新 `AiLogResponse` model
- [x] 更新 `AiLogListItem` model 新增 `allowed_tools` 和 `used_tools`
- [x] 更新 `ai_manager.py:create_log()` INSERT 語句
- [x] 更新 `ai_manager.py:get_log()` SELECT 語句
- [x] 更新 `ai_manager.py:get_logs()` SELECT 語句（含 used_tools 解析）
- [x] 修改 `ai_manager.py:call_agent()` 記錄 `allowed_tools`

### 4. 修復 LineBot AI 記錄 ✅
- [x] 修改 `linebot_ai.py:log_linebot_ai_call()` 新增 `history` 和 `allowed_tools` 參數
- [x] 使用 `compose_prompt_with_history()` 組合完整輸入
- [x] 調用處傳遞 `history` 和 `all_tools`

### 5. 修復對話歷史重複問題 ✅
- [x] 修改 `get_conversation_context()` 新增 `exclude_message_id` 參數
- [x] SQL 查詢使用 `($3::uuid IS NULL OR m.id != $3)` 條件排除當前訊息
- [x] 避免歷史已包含當前訊息導致 `compose_prompt_with_history` 重複加入

### 6. 修復 raw_response 包含 user 訊息問題 ✅
- [x] 修改 `claude_agent.py:_parse_stream_json()`
- [x] 只在 `result_text` 為空時才使用 `result` 事件的內容
- [x] 避免覆蓋從 `assistant` 事件累積的正確回應

### 7. 前端 Log 列表新增 Tools 欄位 ✅
- [x] 修改 `ai-log.js` 表格新增 Tools 欄
- [x] 實作 `renderToolsBadges()` 顯示邏輯：
  - 可用且有使用：實心背景 + 白字
  - 可用但未使用：色框 + 色字
- [x] 新增 CSS 樣式（`.ai-log-tool-badge`, `.ai-log-tool-badge.used`）

### 8. 前端詳情頁調整 ✅
- [x] Tool Calls 區塊預設折疊（改為 `data-expanded="false"`）
- [x] 新增「複製完整請求」按鈕
- [x] 實作 `buildFullRequest()` 組合邏輯（system_prompt + allowed_tools + input_prompt）
- [x] 實作 `copyToClipboard()` 支援非 HTTPS 環境

### 9. 修復 AI 輸出排版問題 ✅
- [x] 修改 `ai-log.css` 的 `.ai-log-detail-text`
- [x] 將 `white-space: pre-wrap` 改為 `pre-line`（合併多餘空格但保留換行）

### 10. 驗證 ✅
- [x] 測試新 Log 正確記錄 allowed_tools
- [x] 測試列表 Tools 顯示正確
- [x] 測試複製完整請求功能
- [x] 測試對話歷史不重複
- [x] 測試 AI 輸出不包含 user: 訊息
