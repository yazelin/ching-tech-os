# Proposal: refactor-send-file-to-reply

## Summary
將 `send_nas_file` MCP 工具從 `push_message`（消耗額度）改為 `reply_message`（完全免費）架構，讓 AI 發送檔案不再消耗每月 200 則的推播配額。

## Motivation
目前 `send_nas_file` 使用 Line `push_message` API 直接發送圖片或連結：
- **push_message**：每月免費 200 則，超過需付費（¥5/則）
- **reply_message**：回應用戶訊息時使用，**完全免費**，每次最多 5 則訊息

由於 Line Bot 的使用場景主要是用戶主動詢問（有 reply_token 可用），改用 reply 架構可以完全避免額度消耗。

## Proposed Changes

### 架構變更
**現行架構**：
```
用戶訊息 → AI 處理 → MCP send_nas_file → push_image/push_text → 用戶收到
                                ↑
                          （消耗 push 額度）
```

**新架構**：
```
用戶訊息 → AI 處理 → MCP prepare_file_message → 回傳圖片資訊
              ↓
    linebot_ai.py 解析 AI 回應
              ↓
    reply_message (TextMessage + ImageMessage) → 用戶收到
                    ↑
              （完全免費）
```

### 主要變更

1. **新增 `prepare_file_message` MCP 工具**
   - 取代 `send_nas_file`，不再直接發送
   - 回傳結構化資訊：`[FILE_MESSAGE:{"type":"image","url":"...","name":"..."}]`
   - AI 回應會包含這個標記

2. **修改 `linebot_ai.py` 回覆邏輯**
   - 解析 AI 回應中的 `[FILE_MESSAGE:...]` 標記
   - 將文字和圖片組合成多則訊息
   - 使用 `reply_message` 一次發送（最多 5 則）

3. **新增 `reply_messages` 函數**
   - 支援一次回覆多則訊息（TextMessage + ImageMessage）
   - 取代目前只能回覆單則文字的 `reply_text`

4. **Prompt 移除 `send_nas_file` 說明**
   - 程式碼保留但不在 prompt 中提及
   - AI 只會使用 `prepare_file_message`
   - 未來視需求決定是否恢復 push 方式

## Impact

### 優點
- **成本降低**：從每月可能消耗的推播額度變為零成本
- **用戶體驗更好**：圖片和文字在同一則回覆中，更自然
- **效能提升**：減少 API 呼叫次數（一次 reply vs 多次 push）

### 限制
- reply_token 有效期約 30 秒，AI 處理超時可能導致無法回覆
  - 現有架構已有此問題，改用 reply 不會更糟
  - 目前 AI 處理超時後本來就無法回覆，行為一致
- 每次 reply 最多 5 則訊息
  - 足夠應付「1 則文字 + 數張圖片」的場景

## Files Affected
- `backend/src/ching_tech_os/services/mcp_server.py` - 新增 prepare_file_message
- `backend/src/ching_tech_os/services/linebot.py` - 新增 reply_messages
- `backend/src/ching_tech_os/services/linebot_ai.py` - 修改回覆邏輯
- `backend/src/ching_tech_os/services/linebot_agents.py` - 更新 prompt
- `backend/migrations/versions/019_*.py` - 更新資料庫 prompt

## Related Specs
- `line-bot` - Line Bot 回覆機制
- `mcp-tools` - MCP 工具定義
