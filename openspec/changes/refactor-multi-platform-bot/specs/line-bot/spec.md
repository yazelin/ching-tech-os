## MODIFIED Requirements

### Requirement: 資料庫儲存
Line Bot SHALL 使用 PostgreSQL 資料庫儲存資料，使用多平台統一的資料表結構。

#### Scenario: bot_groups 資料表（原 line_groups）
- **WHEN** 系統儲存 Line 群組
- **THEN** 群組資料存於 `bot_groups` 資料表
- **AND** `platform_type` 設為 `'line'`
- **AND** `platform_group_id` 對應 Line group ID
- **AND** 包含欄位：id、platform_type、platform_group_id、name、project_id、status、allow_ai_response、tenant_id、created_at、updated_at

#### Scenario: bot_users 資料表（原 line_users）
- **WHEN** 系統儲存 Line 使用者
- **THEN** 使用者資料存於 `bot_users` 資料表
- **AND** `platform_type` 設為 `'line'`
- **AND** `platform_user_id` 對應 Line user ID
- **AND** 包含欄位：id、platform_type、platform_user_id、display_name、picture_url、user_id、is_friend、created_at、updated_at

#### Scenario: bot_messages 資料表（原 line_messages）
- **WHEN** 系統儲存 Line 訊息
- **THEN** 訊息資料存於 `bot_messages` 資料表
- **AND** 包含欄位：id、bot_group_id、bot_user_id、message_type、content、media_path、metadata、source_type、created_at

#### Scenario: bot_files 資料表（原 line_files）
- **WHEN** 系統儲存 Line 檔案
- **THEN** 檔案資料存於 `bot_files` 資料表
- **AND** 包含欄位：id、bot_message_id、bot_group_id、file_name、file_type、file_size、storage_path、thumbnail_path、created_at

#### Scenario: bot_binding_codes 資料表（原 line_binding_codes）
- **WHEN** 系統產生綁定驗證碼
- **THEN** 驗證碼資料存於 `bot_binding_codes` 資料表
- **AND** 包含欄位：id、user_id、code、expires_at、used_at、used_by_bot_user_id、created_at

#### Scenario: 級聯刪除
- **WHEN** 刪除群組
- **THEN** 同時刪除關聯的訊息與檔案記錄
- **AND** NAS 檔案需另行清理（不自動刪除）

### Requirement: Line Bot 自訂記憶資料儲存
Line Bot SHALL 支援儲存群組和個人的自訂記憶 prompt，使用多平台統一資料表。

#### Scenario: bot_group_memories 資料表（原 line_group_memories）
- **WHEN** 系統儲存群組記憶
- **THEN** 記憶資料存於 `bot_group_memories` 資料表
- **AND** 包含欄位：id、bot_group_id、title、content、is_active、created_by、created_at、updated_at
- **AND** bot_group_id 關聯到 bot_groups 表，ON DELETE CASCADE
- **AND** created_by 關聯到 bot_users 表，ON DELETE SET NULL

#### Scenario: bot_user_memories 資料表（原 line_user_memories）
- **WHEN** 系統儲存個人記憶
- **THEN** 記憶資料存於 `bot_user_memories` 資料表
- **AND** 包含欄位：id、bot_user_id、title、content、is_active、created_at、updated_at
- **AND** bot_user_id 關聯到 bot_users 表，ON DELETE CASCADE

### Requirement: Line Bot Agent 整合
Line Bot SHALL 使用資料庫中的 Agent/Prompt 設定進行 AI 對話處理，透過通用 AI 核心模組。

#### Scenario: 個人對話使用 bot-personal Agent
- **WHEN** Line 用戶在個人對話中發送訊息
- **AND** 觸發 AI 處理
- **THEN** 系統從資料庫取得 `bot-personal` Agent 設定（向後相容 `linebot-personal`）
- **AND** 使用該 Agent 的 model 設定
- **AND** 使用該 Agent 的 system_prompt 內容

#### Scenario: 群組對話使用 bot-group Agent
- **WHEN** Line 用戶在群組中觸發 AI 處理
- **THEN** 系統從資料庫取得 `bot-group` Agent 設定（向後相容 `linebot-group`）
- **AND** 使用該 Agent 的 model 設定
- **AND** 使用該 Agent 的 system_prompt 內容
- **AND** 動態附加群組資訊和綁定專案資訊到 prompt

#### Scenario: Agent 不存在時的 Fallback
- **WHEN** 系統找不到對應的 Agent 設定
- **THEN** 系統使用硬編碼的預設 Prompt 作為 fallback
- **AND** 記錄警告日誌

### Requirement: 預設 Line Bot Agent 初始化
系統 SHALL 在啟動時確保預設的 Bot Agent 存在。

#### Scenario: 應用程式啟動時檢查並建立預設 Agent
- **WHEN** 應用程式啟動
- **THEN** 系統檢查 `bot-personal` Agent 是否存在（同時檢查舊名 `linebot-personal`）
- **AND** 若不存在則建立預設的 `bot-personal` Agent 和對應的 Prompt
- **AND** 系統檢查 `bot-group` Agent 是否存在（同時檢查舊名 `linebot-group`）
- **AND** 若不存在則建立預設的 `bot-group` Agent 和對應的 Prompt

#### Scenario: 保留使用者修改
- **WHEN** 應用程式啟動
- **AND** Agent 已存在（無論新名或舊名）
- **THEN** 系統不覆蓋現有 Agent 設定
- **AND** 保留使用者透過 UI 修改的內容
