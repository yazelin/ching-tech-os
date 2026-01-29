## ADDED Requirements

### Requirement: Telegram Bot Webhook 處理
Telegram Bot SHALL 透過 Webhook 模式接收 Telegram Bot API 的更新事件。

#### Scenario: 接收 Webhook 請求
- **WHEN** Telegram 伺服器發送 POST 請求到 `/api/bot/telegram/webhook`
- **THEN** 系統驗證 `X-Telegram-Bot-Api-Secret-Token` header
- **AND** 解析 Update JSON
- **AND** 回傳 HTTP 200 OK

#### Scenario: Secret Token 驗證失敗
- **WHEN** `X-Telegram-Bot-Api-Secret-Token` header 不正確或缺失
- **THEN** 系統回傳 HTTP 403 Forbidden
- **AND** 不處理該更新

#### Scenario: 應用程式啟動時註冊 Webhook
- **WHEN** FastAPI 應用程式啟動
- **AND** `telegram_bot_token` 已設定
- **THEN** 系統呼叫 Telegram `setWebhook` API 註冊 Webhook URL
- **AND** 設定 `secret_token` 供後續驗證

#### Scenario: 處理文字訊息事件
- **WHEN** 收到包含文字的 Message Update
- **THEN** 系統記錄訊息到 `bot_messages`（`platform_type='telegram'`）
- **AND** 檢查用戶綁定狀態與群組設定
- **AND** 依據存取控制結果決定是否觸發 AI 處理

#### Scenario: 處理圖片訊息事件
- **WHEN** 收到包含 photo 的 Message Update
- **THEN** 系統透過 Telegram `getFile` API 下載圖片
- **AND** 儲存到 NAS
- **AND** 記錄到 `bot_messages` 和 `bot_files`

#### Scenario: 處理檔案訊息事件
- **WHEN** 收到包含 document 的 Message Update
- **THEN** 系統透過 Telegram `getFile` API 下載檔案
- **AND** 儲存到 NAS
- **AND** 記錄到 `bot_messages` 和 `bot_files`

#### Scenario: 處理 Bot 加入群組
- **WHEN** 收到 `my_chat_member` Update 且 Bot 狀態變為 member
- **THEN** 系統建立或更新 `bot_groups` 記錄（`platform_type='telegram'`）
- **AND** `allow_ai_response` 預設為 `false`

#### Scenario: 處理 Bot 離開群組
- **WHEN** 收到 `my_chat_member` Update 且 Bot 狀態變為 left/kicked
- **THEN** 系統更新群組狀態為 inactive

---

### Requirement: Telegram Bot Adapter 實作
Telegram Bot SHALL 實作 BotAdapter、EditableMessageAdapter、ProgressNotifier 三個 Protocol。

#### Scenario: 發送文字訊息
- **WHEN** 系統呼叫 `send_text(target, text)`
- **THEN** 透過 Telegram `sendMessage` API 發送文字
- **AND** 回傳 `SentMessage`（包含 message_id、platform_type='telegram'）

#### Scenario: 發送圖片訊息
- **WHEN** 系統呼叫 `send_image(target, image_url)`
- **THEN** 透過 Telegram `sendPhoto` API 發送圖片
- **AND** 如果 image_url 是本地檔案路徑，以 InputFile 方式上傳

#### Scenario: 發送檔案訊息
- **WHEN** 系統呼叫 `send_file(target, file_url, file_name)`
- **THEN** 透過 Telegram `sendDocument` API 發送檔案
- **AND** 保留原始檔案名稱

#### Scenario: 編輯已發送訊息
- **WHEN** 系統呼叫 `edit_message(target, message_id, new_text)`
- **THEN** 透過 Telegram `editMessageText` API 更新訊息內容

#### Scenario: 刪除已發送訊息
- **WHEN** 系統呼叫 `delete_message(target, message_id)`
- **THEN** 透過 Telegram `deleteMessage` API 刪除訊息

#### Scenario: 進度通知
- **WHEN** AI 處理開始
- **THEN** `send_progress` 發送進度訊息
- **AND** `update_progress` 透過 `editMessageText` 即時更新 tool 狀態
- **AND** `finish_progress` 刪除進度訊息

---

### Requirement: Telegram 帳號綁定
Telegram Bot SHALL 支援 Telegram 用戶與 CTOS 帳號的綁定，與其他平台獨立。

#### Scenario: Telegram 用戶綁定
- **WHEN** Telegram 用戶在私訊中發送 6 位數字驗證碼
- **AND** 驗證碼有效
- **THEN** 系統建立 `bot_users` 記錄（`platform_type='telegram'`、`platform_user_id` 為 Telegram user ID）
- **AND** 設定 `user_id` 關聯到對應的 CTOS 帳號
- **AND** 回覆綁定成功訊息

#### Scenario: 同一 CTOS 用戶綁定多平台
- **WHEN** CTOS 用戶已綁定 Line 帳號
- **AND** 該用戶在 Telegram 私訊發送有效驗證碼
- **THEN** 系統建立新的 `bot_users` 記錄（`platform_type='telegram'`）
- **AND** 不影響既有的 Line 綁定
- **AND** 該用戶同時擁有 Line 和 Telegram 兩個 bot_user 記錄

#### Scenario: 未綁定用戶的個人對話
- **WHEN** 未綁定 CTOS 帳號的 Telegram 用戶私訊 Bot
- **AND** 訊息不是驗證碼格式
- **THEN** Bot 回覆提示需要綁定帳號
- **AND** 不執行 AI 處理

---

### Requirement: Telegram 群組 AI 回應控制
Telegram Bot SHALL 支援群組層級的 AI 回應開關，與 Line Bot 行為一致。

#### Scenario: 群組 @Bot 觸發
- **WHEN** Telegram 用戶在群組中 @Bot（`@username`）或回覆 Bot 的訊息
- **AND** 群組 `allow_ai_response = true`
- **AND** 用戶已綁定 CTOS 帳號
- **THEN** 觸發 AI 處理

#### Scenario: 群組未啟用 AI
- **WHEN** 群組 `allow_ai_response = false`
- **THEN** Bot 不回應 AI 訊息
- **AND** 訊息仍記錄到資料庫

#### Scenario: 未綁定用戶在群組中 @Bot
- **WHEN** 未綁定用戶在群組中 @Bot
- **THEN** Bot 靜默不回應

---

### Requirement: Telegram Bot 指令
Telegram Bot SHALL 支援基本的 Telegram 指令。

#### Scenario: /start 指令
- **WHEN** 用戶發送 `/start`
- **THEN** Bot 回覆歡迎訊息和使用說明

#### Scenario: /help 指令
- **WHEN** 用戶發送 `/help`
- **THEN** Bot 回覆功能說明

#### Scenario: /reset 或 /新對話 指令
- **WHEN** 用戶在私訊中發送 `/reset` 或 `/新對話`
- **THEN** 系統更新該 Telegram bot_user 的 `conversation_reset_at`
- **AND** 回覆「已清除對話歷史，開始新對話！」
- **AND** 後續 AI 不會看到重置前的對話

#### Scenario: 群組不支援重置
- **WHEN** 用戶在群組中發送重置指令
- **THEN** Bot 靜默忽略

---

### Requirement: Telegram Bot 回覆上下文
Telegram Bot SHALL 支援用戶回覆舊訊息時的上下文處理。

#### Scenario: 用戶回覆圖片訊息
- **WHEN** 用戶回覆一則圖片訊息並發送文字
- **THEN** 系統下載被回覆的圖片到暫存
- **AND** 在用戶訊息中標註 `[回覆圖片: {temp_path}]`
- **AND** AI 可讀取該圖片

#### Scenario: 用戶回覆檔案訊息
- **WHEN** 用戶回覆一則檔案訊息並發送文字
- **AND** 檔案為可讀取類型
- **THEN** 系統下載被回覆的檔案到暫存
- **AND** 在用戶訊息中標註 `[回覆檔案: {temp_path}]`

#### Scenario: 用戶回覆文字訊息
- **WHEN** 用戶回覆一則文字訊息
- **THEN** 在用戶訊息中標註 `[回覆訊息: {被回覆的文字}]`

---

### Requirement: Telegram Bot 環境設定
系統 SHALL 支援透過環境變數設定 Telegram Bot。

#### Scenario: 必要設定項
- **WHEN** `TELEGRAM_BOT_TOKEN` 已設定
- **THEN** 系統啟動 Telegram Bot 功能
- **AND** 初始化 Telegram Application 並註冊 Webhook

#### Scenario: 未設定 Token
- **WHEN** `TELEGRAM_BOT_TOKEN` 未設定
- **THEN** 系統不啟動 Telegram Bot 功能
- **AND** `/api/bot/telegram/webhook` 路由回傳 503

#### Scenario: Webhook URL 設定
- **WHEN** `TELEGRAM_WEBHOOK_URL` 已設定
- **THEN** 系統使用該 URL 註冊 Webhook
- **WHEN** 未設定
- **THEN** 系統根據 `public_url` 自動組合 Webhook URL（`{public_url}/api/bot/telegram/webhook`）

#### Scenario: Webhook Secret
- **WHEN** `TELEGRAM_WEBHOOK_SECRET` 已設定
- **THEN** 使用該值驗證 webhook 請求
- **WHEN** 未設定
- **THEN** 系統自動產生隨機 secret 並在 `set_webhook` 時設定
