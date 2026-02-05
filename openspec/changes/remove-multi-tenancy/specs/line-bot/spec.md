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

---

### Requirement: Bot 憑證設定 API（遷移自 /api/tenant/bot）
系統 SHALL 提供 API 讓管理員管理 Bot 憑證設定，端點遷移至 `/api/admin/bot-settings/`。

#### Scenario: 取得 Line Bot 設定
- **WHEN** 管理員呼叫 `GET /api/admin/bot-settings/line`
- **THEN** 系統回傳 Line Bot 設定狀態
- **AND** 包含 `configured`（布林）表示是否已設定憑證
- **AND** 不回傳實際憑證值（安全考量）

#### Scenario: 更新 Line Bot 憑證
- **WHEN** 管理員呼叫 `PUT /api/admin/bot-settings/line`
- **AND** 提供 `channel_access_token` 和/或 `channel_secret`
- **THEN** 系統加密儲存到 `bot_settings` 表
- **AND** 回傳更新成功訊息
- **AND** 新憑證立即生效（不需重啟）

#### Scenario: 測試 Line Bot 連線
- **WHEN** 管理員呼叫 `POST /api/admin/bot-settings/line/test`
- **THEN** 系統使用設定的憑證呼叫 Line API 的 getBotInfo
- **AND** 回傳測試結果（成功時包含 Bot 名稱等資訊）

#### Scenario: 清除 Line Bot 憑證
- **WHEN** 管理員呼叫 `DELETE /api/admin/bot-settings/line`
- **THEN** 系統刪除 `bot_settings` 表中的 Line 憑證
- **AND** 回傳清除成功訊息

#### Scenario: 非管理員存取 Bot 設定
- **WHEN** 非管理員使用者呼叫 Bot 設定 API
- **THEN** 系統回傳 403 權限錯誤

---

### Requirement: Telegram Bot 憑證設定 API（遷移自 /api/tenant/telegram-bot）
系統 SHALL 提供 API 讓管理員管理 Telegram Bot 憑證設定。

#### Scenario: 取得 Telegram Bot 設定
- **WHEN** 管理員呼叫 `GET /api/admin/bot-settings/telegram`
- **THEN** 系統回傳 Telegram Bot 設定狀態
- **AND** 包含 `configured`（布林）表示是否已設定憑證

#### Scenario: 更新 Telegram Bot 憑證
- **WHEN** 管理員呼叫 `PUT /api/admin/bot-settings/telegram`
- **AND** 提供 `bot_token`
- **THEN** 系統加密儲存到 `bot_settings` 表
- **AND** 回傳更新成功訊息

#### Scenario: 測試 Telegram Bot 連線
- **WHEN** 管理員呼叫 `POST /api/admin/bot-settings/telegram/test`
- **THEN** 系統使用設定的憑證呼叫 Telegram API 的 getMe
- **AND** 回傳測試結果

#### Scenario: 清除 Telegram Bot 憑證
- **WHEN** 管理員呼叫 `DELETE /api/admin/bot-settings/telegram`
- **THEN** 系統刪除 `bot_settings` 表中的 Telegram 憑證

---

### Requirement: Bot 憑證儲存
系統 SHALL 使用獨立的 `bot_settings` 表儲存 Bot 憑證。

#### Scenario: bot_settings 資料表結構
- **WHEN** 系統儲存 Bot 設定
- **THEN** 設定存於 `bot_settings` 資料表
- **AND** 包含欄位：id、platform（varchar 20）、key（varchar 100）、value（text，加密）、updated_at
- **AND** platform + key 為唯一索引
- **AND** 不包含 tenant_id 欄位

#### Scenario: 憑證加密儲存
- **WHEN** 儲存 Bot 憑證
- **THEN** `value` 使用 Fernet 加密儲存
- **AND** 加密金鑰來自 `BOT_SECRET_KEY` 環境變數

---

### Requirement: 資料庫儲存
Line Bot SHALL 使用 PostgreSQL 資料庫儲存資料，不包含租戶欄位。

#### Scenario: bot_groups 資料表
- **WHEN** 系統儲存 Line 群組
- **THEN** 群組資料存於 `bot_groups` 資料表
- **AND** `platform_type` 設為 `'line'`
- **AND** `platform_group_id` 對應 Line group ID
- **AND** 包含欄位：id、platform_type、platform_group_id、name、project_id、status、allow_ai_response、created_at、updated_at
- **AND** 不包含 `tenant_id` 欄位

#### Scenario: bot_users 資料表
- **WHEN** 系統儲存 Line 使用者
- **THEN** 使用者資料存於 `bot_users` 資料表
- **AND** `platform_type` 設為 `'line'`
- **AND** `platform_user_id` 對應 Line user ID
- **AND** 包含欄位：id、platform_type、platform_user_id、display_name、picture_url、user_id、is_friend、created_at、updated_at
- **AND** 不包含 `tenant_id` 欄位

---

### Requirement: 檔案儲存管理
Line Bot SHALL 將圖片與檔案統一儲存到 NAS，使用簡化的路徑結構。

#### Scenario: 儲存圖片到 NAS
- **WHEN** 收到圖片訊息
- **THEN** 系統將圖片儲存到 `/mnt/nas/ctos/linebot/groups/{group_id}/images/{date}/{message_id}.{ext}`
- **AND** 記錄儲存路徑到 bot_files 表
- **AND** 路徑不包含 tenant 層級

#### Scenario: 儲存檔案到 NAS
- **WHEN** 收到檔案訊息
- **THEN** 系統將檔案儲存到 `/mnt/nas/ctos/linebot/groups/{group_id}/files/{date}/{message_id}_{filename}`
- **AND** 記錄儲存路徑、檔名、大小到 bot_files 表
- **AND** 路徑不包含 tenant 層級

---

### Requirement: Bot 設定前端介面（遷移自 tenant-admin.js）
系統 SHALL 在系統設定中提供 Bot 憑證管理介面，僅限管理員存取。

#### Scenario: 開啟 Bot 設定頁面
- **WHEN** 管理員開啟「系統設定」App
- **AND** 切換到「Bot 設定」分頁
- **THEN** 顯示 Line Bot 和 Telegram Bot 的設定區塊

#### Scenario: 顯示 Line Bot 設定狀態
- **WHEN** Bot 設定頁面載入
- **THEN** 顯示 Line Bot 憑證設定狀態
- **AND** 若已設定顯示「已設定」標籤和 Bot 名稱
- **AND** 若未設定顯示「未設定」警告

#### Scenario: 編輯 Line Bot 憑證
- **WHEN** 管理員點擊「編輯憑證」按鈕
- **THEN** 顯示編輯彈出視窗
- **AND** 包含 Channel Access Token 和 Channel Secret 輸入欄位
- **AND** 欄位為密碼類型（隱藏輸入）

#### Scenario: 測試 Line Bot 連線
- **WHEN** 管理員點擊「測試連線」按鈕
- **THEN** 系統呼叫測試 API
- **AND** 顯示測試結果（成功顯示 Bot 名稱，失敗顯示錯誤訊息）

#### Scenario: 非管理員看不到 Bot 設定
- **WHEN** 非管理員使用者開啟系統設定 App
- **THEN** 不顯示「Bot 設定」分頁

## REMOVED Requirements

### Requirement: 多租戶憑證管理
**Reason**: 移除多租戶架構，改用獨立的 bot_settings 表
**Migration**:
- 原 `tenants.line_credentials` 遷移到 `bot_settings` 表（platform='line'）
- 原 `tenants.telegram_credentials` 遷移到 `bot_settings` 表（platform='telegram'）
- API 端點從 `/api/tenant/bot` 遷移到 `/api/admin/bot-settings/line`
- API 端點從 `/api/tenant/telegram-bot` 遷移到 `/api/admin/bot-settings/telegram`

### Requirement: 租戶自訂 Line Bot 憑證
**Reason**: 移除多租戶架構，單一實例只需一組憑證
**Migration**: 使用 bot_settings 表儲存單一實例的憑證設定
