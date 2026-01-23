# line-bot spec delta

## ADDED Requirements

### Requirement: Batch Push Message
系統 SHALL 支援使用 Line Push API 單次發送多則訊息（最多 5 則）。

#### Scenario: 合併發送文字和圖片
- **WHEN** 需要發送文字訊息和圖片訊息給用戶
- **THEN** 將訊息合併為單一 API 請求發送，確保順序正確

#### Scenario: 超過 5 則訊息時分批發送
- **WHEN** 需要發送超過 5 則訊息
- **THEN** 自動分批發送，每批最多 5 則

## MODIFIED Requirements

### Requirement: Reply Fallback to Push
當 reply_message 失敗時 fallback 到 push_message，SHALL 合併多則訊息為單一請求。

#### Scenario: Reply 失敗後合併 Push
- **WHEN** reply_message 因 token 過期失敗
- **AND** 有文字訊息和圖片訊息需要發送
- **THEN** 使用 push_messages 合併發送，而非分開多次呼叫
