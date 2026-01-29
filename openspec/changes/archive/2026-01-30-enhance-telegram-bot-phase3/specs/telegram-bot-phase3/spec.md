## MODIFIED Requirements

### Requirement: Telegram Bot 文字訊息處理（增強）
原 Phase 2 僅做單輪 AI 對話，Phase 3 SHALL 加入完整的訊息生命週期。

#### Scenario: 儲存用戶訊息
- **WHEN** 收到任何 Telegram 訊息（文字/圖片/檔案）
- **THEN** 系統儲存到 `bot_messages`
- **AND** `bot_user_id` 關聯到對應的 `bot_users` 記錄
- **AND** 群組訊息同時設定 `bot_group_id`

#### Scenario: 儲存 Bot 回覆
- **WHEN** Bot 回覆文字或檔案
- **THEN** 系統儲存到 `bot_messages`（`is_from_bot=true`）
- **AND** 保留 Telegram message_id 以支援回覆上下文查詢

#### Scenario: AI 對話含歷史上下文
- **WHEN** 已綁定用戶發送文字訊息
- **THEN** 系統查詢最近 20 則對話歷史
- **AND** 將歷史傳入 AI 處理
- **AND** AI 能引用之前的對話內容

#### Scenario: AI Log 記錄
- **WHEN** AI 處理完成（成功或失敗）
- **THEN** 系統寫入 `ai_logs` 表
- **AND** `context_type` 為 `"telegram-personal"` 或 `"telegram-group"`
- **AND** 記錄 model、duration_ms、input/output tokens、allowed_tools

## ADDED Requirements

### Requirement: Telegram 訊息儲存基礎
系統 SHALL 為每則 Telegram 訊息建立完整的資料庫記錄。

#### Scenario: 自動建立 bot_user
- **WHEN** 收到 Telegram 訊息
- **AND** 該 Telegram user 尚無 `bot_users` 記錄
- **THEN** 系統自動建立 `bot_users` 記錄
- **AND** `platform_type='telegram'`、`platform_user_id` 為 Telegram user ID
- **AND** `display_name` 從 `user.full_name` 取得
- **AND** `user_id` 為 NULL（尚未綁定）

#### Scenario: 自動建立 bot_group
- **WHEN** 收到 Telegram 群組訊息
- **AND** 該群組尚無 `bot_groups` 記錄
- **THEN** 系統自動建立 `bot_groups` 記錄
- **AND** `platform_type='telegram'`、`platform_group_id` 為 Telegram chat ID
- **AND** `group_name` 從 `chat.title` 取得
- **AND** `allow_ai_response` 預設為 `false`

### Requirement: Telegram 用戶綁定
系統 SHALL 支援 Telegram 用戶透過驗證碼綁定 CTOS 帳號。

#### Scenario: 驗證碼綁定成功
- **WHEN** Telegram 用戶在私訊發送 6 位數字
- **AND** 該驗證碼在 `bot_binding_codes` 中存在且未過期
- **THEN** 系統更新 `bot_users.user_id` 為對應的 CTOS 帳號
- **AND** 標記驗證碼為已使用
- **AND** 回覆「綁定成功！」

#### Scenario: 驗證碼無效
- **WHEN** Telegram 用戶在私訊發送 6 位數字
- **AND** 驗證碼不存在或已過期
- **THEN** 回覆「驗證碼無效或已過期」

#### Scenario: 未綁定用戶私訊
- **WHEN** 未綁定的 Telegram 用戶發送非驗證碼訊息
- **THEN** 回覆提示需要綁定帳號的說明
- **AND** 不執行 AI 處理

#### Scenario: 未綁定用戶在群組
- **WHEN** 未綁定的 Telegram 用戶在群組 @Bot
- **THEN** Bot 靜默不回應

### Requirement: Telegram 群組 AI 觸發
系統 SHALL 在群組中僅回應明確指向 Bot 的訊息。

#### Scenario: @Bot mention 觸發
- **WHEN** 用戶在群組訊息中 @Bot username
- **AND** 群組 `allow_ai_response = true`
- **AND** 用戶已綁定
- **THEN** 觸發 AI 處理（去除 @username 後的文字作為 prompt）

#### Scenario: 回覆 Bot 訊息觸發
- **WHEN** 用戶回覆 Bot 發送的訊息
- **AND** 群組 `allow_ai_response = true`
- **AND** 用戶已綁定
- **THEN** 觸發 AI 處理

#### Scenario: 一般群組訊息不觸發
- **WHEN** 群組訊息未 @Bot 且非回覆 Bot
- **THEN** 不觸發 AI 處理
- **AND** 訊息仍記錄到 `bot_messages`（如有需要）

### Requirement: Telegram 圖片與檔案接收
系統 SHALL 處理 Telegram 用戶發送的圖片和檔案。

#### Scenario: 接收圖片
- **WHEN** 用戶發送圖片
- **THEN** 系統下載最高解析度版本（`photo[-1]`）
- **AND** 儲存到 NAS
- **AND** 記錄到 `bot_messages`（message_type='image'）和 `bot_files`
- **AND** 觸發 AI 處理（附帶圖片路徑）

#### Scenario: 接收檔案
- **WHEN** 用戶發送檔案（document）
- **THEN** 系統下載檔案
- **AND** 儲存到 NAS
- **AND** 記錄到 `bot_messages`（message_type='file'）和 `bot_files`
- **AND** 若為可讀類型，觸發 AI 處理（附帶檔案路徑）

### Requirement: 對話重置完整實作
系統 SHALL 在重置對話時正確更新資料庫。

#### Scenario: 私訊對話重置
- **WHEN** 用戶在私訊發送 `/reset` 或 `/新對話`
- **THEN** 系統更新 `bot_users.conversation_reset_at` 為當前時間
- **AND** 後續 `get_conversation_context` 不返回重置前的訊息
- **AND** 回覆「已清除對話歷史，開始新對話！」

#### Scenario: 群組中重置指令
- **WHEN** 用戶在群組發送重置指令
- **THEN** Bot 靜默忽略
