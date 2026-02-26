## ADDED Requirements

### Requirement: 使用量追蹤資料表
系統 SHALL 使用 `bot_usage_tracking` 資料表追蹤每個 bot_user 的訊息使用量。

#### Scenario: 資料表結構
- **WHEN** 系統儲存使用量記錄
- **THEN** 記錄存於 `bot_usage_tracking` 資料表
- **AND** 包含欄位：`id`（UUID）、`bot_user_id`（UUID, FK bot_users）、`period_type`（VARCHAR, 'hourly' 或 'daily'）、`period_key`（VARCHAR, 如 '2026-02-26-14' 或 '2026-02-26'）、`message_count`（INT）、`created_at`、`updated_at`
- **AND** `(bot_user_id, period_type, period_key)` 為唯一索引
- **AND** `bot_user_id` 設定 `ON DELETE CASCADE`

#### Scenario: UPSERT 計數
- **WHEN** 受限模式訊息處理完成
- **THEN** 系統 SHALL 對 `bot_usage_tracking` 執行 UPSERT
- **AND** 若記錄不存在則建立（`message_count=1`）
- **AND** 若記錄已存在則 `message_count = message_count + 1`
- **AND** 同時更新 `hourly` 和 `daily` 兩個 period_type 的記錄

### Requirement: 頻率限制檢查
系統 SHALL 在受限模式 AI 處理之前檢查用戶使用量是否超過限額。

#### Scenario: 啟用頻率限制
- **WHEN** `BOT_RATE_LIMIT_ENABLED` 設為 `true`（預設）
- **AND** `BOT_UNBOUND_USER_POLICY` 為 `restricted`
- **AND** 未綁定用戶發送訊息
- **THEN** 系統 SHALL 查詢該用戶的 hourly 和 daily 使用量
- **AND** 與 `BOT_RATE_LIMIT_HOURLY` 和 `BOT_RATE_LIMIT_DAILY` 比較

#### Scenario: 超過每小時限額
- **WHEN** 用戶本小時的 `message_count` >= `BOT_RATE_LIMIT_HOURLY`（預設 20）
- **THEN** 系統 SHALL 回覆「您已達到本小時的使用上限，請稍後再試」
- **AND** 不進行 AI 處理

#### Scenario: 超過每日限額
- **WHEN** 用戶今日的 `message_count` >= `BOT_RATE_LIMIT_DAILY`（預設 50）
- **THEN** 系統 SHALL 回覆「您已達到今日的使用上限，請明天再試」
- **AND** 不進行 AI 處理

#### Scenario: 未超過限額
- **WHEN** 用戶的 hourly 和 daily 使用量均未超過限額
- **THEN** 系統 SHALL 正常進行受限模式 AI 處理

#### Scenario: 已綁定用戶不受限
- **WHEN** 已綁定 CTOS 帳號的用戶發送訊息
- **THEN** 系統 SHALL 不進行頻率限制檢查
- **AND** 不記錄使用量

### Requirement: 頻率限制配置
系統 SHALL 透過環境變數配置頻率限制參數。

#### Scenario: 預設配置值
- **WHEN** 未設定頻率限制相關環境變數
- **THEN** 系統 SHALL 使用以下預設值：
- **AND** `BOT_RATE_LIMIT_ENABLED` = `true`
- **AND** `BOT_RATE_LIMIT_HOURLY` = `20`
- **AND** `BOT_RATE_LIMIT_DAILY` = `50`

#### Scenario: 停用頻率限制
- **WHEN** `BOT_RATE_LIMIT_ENABLED` 設為 `false`
- **THEN** 系統 SHALL 不進行頻率限制檢查
- **AND** 仍記錄使用量（供後台統計）

#### Scenario: 自訂限額
- **WHEN** `BOT_RATE_LIMIT_HOURLY` 設為 `10`
- **AND** `BOT_RATE_LIMIT_DAILY` 設為 `100`
- **THEN** 系統 SHALL 使用自訂值進行限額檢查

### Requirement: reject 策略下不啟用 rate limiter
當 `BOT_UNBOUND_USER_POLICY` 為 `reject` 時，系統 SHALL 不執行任何頻率限制邏輯。

#### Scenario: reject 策略無 rate limiting
- **WHEN** `BOT_UNBOUND_USER_POLICY` 為 `reject`
- **THEN** 系統 SHALL 不查詢 `bot_usage_tracking` 表
- **AND** 不記錄使用量
- **AND** 不進行頻率限制檢查
