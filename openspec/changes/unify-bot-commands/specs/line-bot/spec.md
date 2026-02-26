## MODIFIED Requirements

### Requirement: Line Bot Webhook 處理
Line Bot SHALL 接收並處理 Line Messaging API 的 Webhook 事件，使用 bot_settings 表或環境變數的憑證驗證。

#### Scenario: 接收 Webhook 請求
- **WHEN** Line 伺服器發送 POST 請求到 `/api/bot/line/webhook`
- **THEN** 系統使用設定的 Channel Secret 驗證 X-Line-Signature 簽章
- **AND** 解析請求 body 取得事件列表
- **AND** 回傳 HTTP 200 OK

#### Scenario: 憑證來源優先順序
- **WHEN** 系統需要 Line Bot 憑證
- **THEN** 優先使用資料庫 `bot_settings` 表的設定
- **AND** 若資料庫無設定，使用環境變數 `LINE_CHANNEL_ACCESS_TOKEN` 和 `LINE_CHANNEL_SECRET`
- **AND** 若都無設定，回傳錯誤訊息

#### Scenario: 簽章驗證失敗
- **WHEN** X-Line-Signature 簽章無效
- **THEN** 系統回傳 HTTP 400 Bad Request
- **AND** 不處理該請求的任何事件

#### Scenario: 處理文字訊息事件
- **WHEN** 收到 MessageEvent 且訊息類型為 TextMessage
- **THEN** 系統記錄訊息到資料庫
- **AND** 檢查用戶綁定狀態與群組設定
- **AND** 依據存取控制結果決定是否觸發 AI 處理

#### Scenario: 處理圖片訊息事件
- **WHEN** 收到 MessageEvent 且訊息類型為 ImageMessage
- **THEN** 系統下載圖片內容
- **AND** 儲存圖片到 NAS
- **AND** 記錄訊息與檔案資訊到資料庫

#### Scenario: 處理檔案訊息事件
- **WHEN** 收到 MessageEvent 且訊息類型為 FileMessage
- **THEN** 系統下載檔案內容
- **AND** 儲存檔案到 NAS
- **AND** 記錄訊息與檔案資訊到資料庫

#### Scenario: 處理加入群組事件
- **WHEN** 收到 JoinEvent
- **THEN** 系統建立或更新群組記錄
- **AND** 設定群組狀態為 active
- **AND** 設定 `allow_ai_response = false`

#### Scenario: 處理離開群組事件
- **WHEN** 收到 LeaveEvent
- **THEN** 系統更新群組狀態為 inactive

#### Scenario: 處理加好友事件發送歡迎訊息
- **WHEN** 收到 FollowEvent（用戶加好友）
- **THEN** 系統建立或更新用戶記錄
- **AND** 設定 `is_friend = true`
- **AND** 系統 SHALL 使用 push message 發送歡迎訊息
- **AND** 歡迎訊息內容與 `/start` 指令回覆相同
