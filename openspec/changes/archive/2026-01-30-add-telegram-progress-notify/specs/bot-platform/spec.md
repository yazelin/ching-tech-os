## MODIFIED Requirements

### Requirement: ProgressNotifier 整合至 AI 處理流程
系統 SHALL 在 AI 處理期間透過 ProgressNotifier 即時通知用戶 tool 執行進度。

#### Scenario: claude_agent 提供即時 tool callback
- **WHEN** 呼叫 `call_claude()` 時傳入 `on_tool_start` 和 `on_tool_end` callback
- **THEN** 系統在偵測到 `tool_use` 事件時 await `on_tool_start(name, input)`
- **AND** 在偵測到 `tool_result` 事件時 await `on_tool_end(name, {"duration_ms": int, "output": str})`
- **AND** callback 為可選參數，不傳時行為與現有完全一致

#### Scenario: Telegram Bot 顯示 tool 進度通知
- **WHEN** Telegram 用戶觸發 AI 處理且 AI 呼叫了 tool
- **THEN** 系統送出進度通知訊息顯示 tool 名稱和狀態（⏳ 執行中）
- **AND** tool 完成時原地更新為 ✅ 完成（含耗時）
- **AND** AI 回應完成後刪除進度通知訊息
- **AND** 無 tool 呼叫時不顯示進度通知

#### Scenario: 進度通知錯誤不影響 AI 處理
- **WHEN** 進度通知的 send/update/finish 操作發生錯誤（如 Telegram API 限流）
- **THEN** 系統記錄錯誤日誌但繼續正常 AI 處理
- **AND** 不影響最終回覆的發送
