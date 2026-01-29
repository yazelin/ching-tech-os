## Phase 1: claude_agent.py callback 機制

- [x] 1.1 定義 `ToolNotifyCallback` 型態別名
  - `Callable[[str, dict], Awaitable[None]]`
- [x] 1.2 從 `_parse_stream_json_with_timing` 拆出 `_process_stream_event()` 單行事件處理函式
  - 偵測 `tool_use` 事件 → 呼叫 `on_tool_start(name, input)`
  - 偵測 `tool_result` 事件 → 呼叫 `on_tool_end(name, {"duration_ms": ..., "output": ...})`
  - 保持原有的 `ParseResult` 收集不變
- [x] 1.3 修改 `call_claude()` 新增 `on_tool_start` 和 `on_tool_end` 可選參數
- [x] 1.4 修改 `read_stdout()` 在讀取每行後呼叫 `_process_stream_event()`
- [x] 1.5 **驗證**：不傳 callback 時行為與現在完全一致（回歸）

## Phase 2: handler.py 接入進度通知

- [x] 2.1 新增 `_format_progress_text()` 函式，格式化 tool 狀態為通知文字
  - 參考 `~/SDD/telegram-bot` 的格式
  - 顯示 tool 名稱、前 2 個輸入參數、狀態（⏳/✅）
- [x] 2.2 在 `_handle_text_with_ai()` 中建立 `on_tool_start` / `on_tool_end` closure
  - `on_tool_start`：首次呼叫 `adapter.send_progress()`，後續呼叫 `adapter.update_progress()`
  - `on_tool_end`：更新對應 tool 狀態為 ✅ 完成 + 耗時
- [x] 2.3 AI 回應完成後呼叫 `adapter.finish_progress()` 刪除進度訊息
- [x] 2.4 Callback 內部加入 try/except，錯誤不影響 AI 處理
- [x] 2.5 **驗證**：
  - Telegram 私訊觸發有 tool 的對話，看到進度更新
  - Telegram 群組 @Bot 觸發，看到進度更新
  - 無 tool 的純文字回覆不出現進度訊息
  - Line Bot 不受影響（回歸測試）

### 依賴關係
- Phase 2 依賴 Phase 1
- Phase 1 可獨立測試（使用 print callback 驗證）
