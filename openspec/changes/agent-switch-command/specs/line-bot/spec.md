## MODIFIED Requirements

### Requirement: Line Bot Agent 整合
Line Bot SHALL 使用資料庫中的 Agent/Prompt 設定進行 AI 對話處理，支援對話級別的 Agent 偏好覆蓋。

#### Scenario: 個人對話使用 bot-personal Agent
- **WHEN** Line 用戶在個人對話中發送訊息
- **AND** 觸發 AI 處理
- **AND** 該用戶的 `bot_users.active_agent_id` 為 NULL
- **THEN** 系統從資料庫取得 `bot-personal` Agent 設定（向後相容 `linebot-personal`）
- **AND** 使用該 Agent 的 model 設定
- **AND** 使用該 Agent 的 system_prompt 內容

#### Scenario: 個人對話使用偏好 Agent
- **WHEN** Line 用戶在個人對話中發送訊息
- **AND** 觸發 AI 處理
- **AND** 該用戶的 `bot_users.active_agent_id` 不為 NULL
- **THEN** 系統從資料庫取得 `active_agent_id` 對應的 Agent 設定
- **AND** 使用該 Agent 的 model、system_prompt 和 tools 設定

#### Scenario: 群組對話使用 bot-group Agent
- **WHEN** Line 用戶在群組中觸發 AI 處理
- **AND** 該群組的 `bot_groups.active_agent_id` 為 NULL
- **THEN** 系統從資料庫取得 `bot-group` Agent 設定（向後相容 `linebot-group`）
- **AND** 使用該 Agent 的 model 設定
- **AND** 使用該 Agent 的 system_prompt 內容
- **AND** 動態附加群組資訊和綁定專案資訊到 prompt

#### Scenario: 群組對話使用偏好 Agent
- **WHEN** Line 用戶在群組中觸發 AI 處理
- **AND** 該群組的 `bot_groups.active_agent_id` 不為 NULL
- **THEN** 系統從資料庫取得 `active_agent_id` 對應的 Agent 設定
- **AND** 使用該 Agent 的 model、system_prompt 和 tools 設定
- **AND** 動態附加群組資訊和綁定專案資訊到 prompt

#### Scenario: Agent 不存在時的 Fallback
- **WHEN** 系統找不到對應的 Agent 設定（包含偏好 Agent 被刪除的情況）
- **THEN** 系統使用硬編碼的預設 Prompt 作為 fallback
- **AND** 記錄警告日誌

### Requirement: 資料庫儲存
Line Bot SHALL 使用 PostgreSQL 資料庫儲存資料，不包含租戶欄位。

#### Scenario: bot_groups 資料表
- **WHEN** 系統儲存 Line 群組
- **THEN** 群組資料存於 `bot_groups` 資料表
- **AND** `platform_type` 設為 `'line'`
- **AND** `platform_group_id` 對應 Line group ID
- **AND** 包含欄位：id、platform_type、platform_group_id、name、project_id、status、allow_ai_response、active_agent_id、created_at、updated_at
- **AND** `active_agent_id` 為 nullable UUID FK 指向 `ai_agents.id`（`ON DELETE SET NULL`）
- **AND** 不包含 `tenant_id` 欄位

#### Scenario: bot_users 資料表
- **WHEN** 系統儲存 Line 使用者
- **THEN** 使用者資料存於 `bot_users` 資料表
- **AND** `platform_type` 設為 `'line'`
- **AND** `platform_user_id` 對應 Line user ID
- **AND** 包含欄位：id、platform_type、platform_user_id、display_name、picture_url、user_id、is_friend、active_agent_id、created_at、updated_at
- **AND** `active_agent_id` 為 nullable UUID FK 指向 `ai_agents.id`（`ON DELETE SET NULL`）
- **AND** 不包含 `tenant_id` 欄位
