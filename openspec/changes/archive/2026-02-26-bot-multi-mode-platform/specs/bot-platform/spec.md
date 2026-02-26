## MODIFIED Requirements

### Requirement: BotContext 對話情境
系統 SHALL 使用統一的 BotContext 管理對話情境，不包含租戶資訊。

#### Scenario: 建構對話情境
- **WHEN** 收到訊息觸發 AI 處理
- **THEN** 系統建構 `BotContext` 包含 `platform_type`、`user_id`、`group_id`、`conversation_type`
- **AND** 不包含 `tenant_id` 欄位
- **AND** 平台 Adapter 負責從平台事件填充 context

#### Scenario: 綁定狀態欄位
- **WHEN** 系統建構 `BotContext`
- **THEN** SHALL 包含 `binding_status` 欄位
- **AND** 當 `bot_users.user_id` 不為 NULL 時設為 `bound`
- **AND** 當 `bot_users.user_id` 為 NULL 時設為 `unbound`

#### Scenario: 依情境選擇 Agent
- **WHEN** 系統需要選擇 AI Agent
- **THEN** 根據 `BotContext.conversation_type`（private/group）和 `BotContext.binding_status`（bound/unbound）選擇對應 Agent
- **AND** Agent 選擇邏輯與平台無關
