## MODIFIED Requirements

### Requirement: BotContext 對話情境
系統 SHALL 使用統一的 BotContext 管理對話情境，不包含租戶資訊。

#### Scenario: 建構對話情境
- **WHEN** 收到訊息觸發 AI 處理
- **THEN** 系統建構 `BotContext` 包含 `platform_type`、`user_id`、`group_id`、`conversation_type`
- **AND** 不包含 `tenant_id` 欄位
- **AND** 平台 Adapter 負責從平台事件填充 context

#### Scenario: 依情境選擇 Agent
- **WHEN** 系統需要選擇 AI Agent
- **THEN** 根據 `BotContext.conversation_type`（private/group）選擇對應 Agent
- **AND** Agent 選擇邏輯與平台無關

---

### Requirement: 多平台資料儲存
系統 SHALL 使用統一的資料表結構儲存多平台資料，不包含租戶欄位。

#### Scenario: bot_groups 資料表
- **WHEN** 系統儲存群組
- **THEN** 群組資料存於 `bot_groups` 資料表
- **AND** 包含 `platform_type` 欄位（'line'、'telegram' 等）
- **AND** 包含 `platform_group_id` 欄位（平台原生群組 ID）
- **AND** 不包含 `tenant_id` 欄位

#### Scenario: bot_users 資料表
- **WHEN** 系統儲存使用者
- **THEN** 使用者資料存於 `bot_users` 資料表
- **AND** 包含 `platform_type` 欄位
- **AND** 包含 `platform_user_id` 欄位（平台原生用戶 ID）
- **AND** 不包含 `tenant_id` 欄位

#### Scenario: bot_messages 資料表
- **WHEN** 系統儲存訊息
- **THEN** 訊息資料存於 `bot_messages` 資料表
- **AND** 關聯到 `bot_groups` 和 `bot_users`
- **AND** 不包含 `tenant_id` 欄位

#### Scenario: bot_files 資料表
- **WHEN** 系統儲存檔案
- **THEN** 檔案資料存於 `bot_files` 資料表
- **AND** 關聯到 `bot_messages`
- **AND** 不包含 `tenant_id` 欄位

#### Scenario: bot_binding_codes 資料表
- **WHEN** 系統產生綁定驗證碼
- **THEN** 驗證碼資料存於 `bot_binding_codes` 資料表
- **AND** 不包含 `tenant_id` 欄位

#### Scenario: bot_group_memories 和 bot_user_memories 資料表
- **WHEN** 系統儲存自訂記憶
- **THEN** 記憶資料存於 `bot_group_memories` 和 `bot_user_memories` 資料表
- **AND** 分別關聯到 `bot_groups` 和 `bot_users`
- **AND** 不包含 `tenant_id` 欄位

---

### Requirement: 平台無關的 AI 處理核心
系統 SHALL 將 AI 處理邏輯抽離為平台無關的共用模組，不處理租戶邏輯。

#### Scenario: 統一的 AI 處理流程
- **WHEN** 任何平台觸發 AI 處理
- **THEN** 共用核心負責：Agent 選擇、system prompt 建構、對話歷史組合、Claude CLI 呼叫、回應解析
- **AND** 不處理租戶相關邏輯

#### Scenario: system prompt 建構
- **WHEN** 系統建構 AI system prompt
- **THEN** 核心邏輯組合：Agent 基礎 prompt + 使用者權限 + 對話情境 + 自訂記憶
- **AND** 不包含租戶資訊

## REMOVED Requirements

### Requirement: 租戶相關的 BotContext 欄位
**Reason**: 移除多租戶架構
**Migration**: BotContext 不再包含 tenant_id，所有查詢不需要租戶過濾
