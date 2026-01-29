## ADDED Requirements

### Requirement: 共享 AI 處理協調器
系統 SHALL 提供平台無關的 AI 處理協調器，統一處理所有平台的 AI 對話流程。

#### Scenario: 統一處理入口
- **WHEN** 任何平台的 Handler 觸發 AI 處理
- **THEN** 呼叫 `bot/processor.py` 的共享處理函式
- **AND** 傳入 `BotContext`（平台、租戶、用戶、群組）和 `BotMessage`（訊息內容）
- **AND** 傳入平台的 `BotAdapter` 實例

#### Scenario: 進度通知自動適配
- **WHEN** AI 處理過程中有 tool 執行
- **AND** 傳入的 Adapter 實作了 `ProgressNotifier` Protocol
- **THEN** 自動啟用即時進度更新
- **WHEN** Adapter 未實作 `ProgressNotifier`
- **THEN** 不發送進度通知（Line Bot 現有行為不變）

#### Scenario: 回應透過 Adapter 發送
- **WHEN** AI 處理完成
- **THEN** 協調器透過傳入的 `BotAdapter` 發送結果
- **AND** 文字透過 `send_text`、圖片透過 `send_image`、檔案透過 `send_file`

### Requirement: 多平台綁定支援
系統 SHALL 支援同一個 CTOS 用戶同時綁定多個平台。

#### Scenario: 同一用戶綁定多平台
- **WHEN** CTOS 用戶已綁定 Line
- **AND** 該用戶在 Telegram 完成綁定
- **THEN** 系統建立新的 `bot_users` 記錄（`platform_type='telegram'`）
- **AND** `user_id` 指向同一個 CTOS 用戶
- **AND** Line 的 `bot_users` 記錄不受影響

#### Scenario: 各平台訊息隔離
- **WHEN** 同一 CTOS 用戶同時使用 Line 和 Telegram
- **THEN** Line 的對話歷史只包含 Line 的 `bot_user` 的 `bot_messages`
- **AND** Telegram 的對話歷史只包含 Telegram 的 `bot_user` 的 `bot_messages`
- **AND** AI 處理時只載入對應平台的歷史記錄

#### Scenario: 綁定狀態查詢
- **WHEN** CTOS 用戶請求 `GET /api/bot/binding/status`
- **THEN** 系統回傳所有平台的綁定狀態
- **AND** 每個平台各自顯示是否已綁定、顯示名稱、綁定時間

## MODIFIED Requirements

### Requirement: 多平台資料儲存
系統 SHALL 使用統一的資料表結構儲存多平台資料，欄位名使用平台無關的命名。

#### Scenario: bot_groups 資料表
- **WHEN** 系統儲存群組
- **THEN** 群組資料存於 `bot_groups` 資料表
- **AND** 包含 `platform_type` 欄位（'line'、'telegram' 等）
- **AND** 包含 `platform_group_id` 欄位（平台原生群組 ID）
- **AND** 唯一索引為 `(tenant_id, platform_type, platform_group_id)`

#### Scenario: bot_users 資料表
- **WHEN** 系統儲存使用者
- **THEN** 使用者資料存於 `bot_users` 資料表
- **AND** 包含 `platform_type` 欄位
- **AND** 包含 `platform_user_id` 欄位（平台原生用戶 ID）
- **AND** 唯一索引為 `(tenant_id, platform_type, platform_user_id)`
- **AND** 同一個 `user_id`（CTOS 帳號）可對應多筆不同 `platform_type` 的記錄

#### Scenario: bot_messages 資料表
- **WHEN** 系統儲存訊息
- **THEN** 訊息資料存於 `bot_messages` 資料表
- **AND** 關聯欄位為 `bot_group_id` 和 `bot_user_id`

#### Scenario: bot_files 資料表
- **WHEN** 系統儲存檔案
- **THEN** 檔案資料存於 `bot_files` 資料表
- **AND** 關聯欄位為 `bot_message_id` 和 `bot_group_id`

#### Scenario: bot_binding_codes 資料表
- **WHEN** 系統產生綁定驗證碼
- **THEN** 驗證碼資料存於 `bot_binding_codes` 資料表
- **AND** 已使用欄位為 `used_by_bot_user_id`

#### Scenario: bot_group_memories 和 bot_user_memories 資料表
- **WHEN** 系統儲存自訂記憶
- **THEN** 記憶資料存於 `bot_group_memories` 和 `bot_user_memories` 資料表
- **AND** 關聯欄位為 `bot_group_id` 和 `bot_user_id`
