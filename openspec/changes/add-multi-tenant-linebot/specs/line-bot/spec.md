# Line Bot Specification Delta

## ADDED Requirements

### Requirement: 多租戶 Line Bot 設定
每個租戶 SHALL 能夠設定自己的 Line Bot 憑證，讓群組自動歸屬對應租戶。

#### Scenario: 租戶設定 Line Bot 憑證
- **WHEN** 租戶管理員在設定頁面輸入 Line Bot 憑證
- **AND** 提供 Channel ID、Channel Secret、Access Token
- **THEN** 系統加密儲存憑證到 TenantSettings
- **AND** 該租戶的 Bot 開始接收訊息

#### Scenario: 憑證加密儲存
- **WHEN** 系統儲存 Line Bot 憑證
- **THEN** Channel Secret 和 Access Token 使用 AES-256 加密
- **AND** 加密 key 從環境變數 `TENANT_SECRET_KEY` 取得

#### Scenario: 查詢 Line Bot 設定狀態
- **WHEN** 租戶管理員請求 `GET /api/tenant/linebot-settings`
- **THEN** 系統回傳設定狀態（已設定/未設定）
- **AND** 回傳 Channel ID
- **AND** 不回傳 Secret 和 Token（安全考量）

#### Scenario: 測試 Line Bot 連線
- **WHEN** 租戶管理員請求 `POST /api/tenant/linebot-settings/test`
- **AND** 提供完整憑證
- **THEN** 系統使用該憑證呼叫 Line API 取得 Bot 資訊
- **AND** 回傳 Bot 名稱、頭像 URL
- **AND** 如憑證無效則回傳錯誤訊息

---

### Requirement: Webhook 多租戶自動識別
Line Bot Webhook SHALL 自動識別請求來自哪個租戶的 Bot。

#### Scenario: 多租戶簽名驗證
- **WHEN** Line 伺服器發送 POST 請求到 `/api/linebot/webhook`
- **THEN** 系統遍歷所有租戶的 Channel Secret
- **AND** 使用 HMAC-SHA256 驗證 X-Line-Signature
- **AND** 驗證成功則識別為該租戶

#### Scenario: 租戶識別成功
- **WHEN** 簽名驗證成功識別租戶 A
- **THEN** 後續處理使用租戶 A 的設定
- **AND** 使用租戶 A 的 Access Token 回覆訊息
- **AND** 新群組自動歸屬租戶 A

#### Scenario: 所有租戶驗證失敗（Fallback）
- **WHEN** 所有租戶的 Secret 都驗證失敗
- **THEN** 系統使用環境變數的預設 Bot 憑證驗證
- **AND** 驗證成功則歸屬 default 租戶
- **AND** 驗證失敗則回傳 HTTP 400

#### Scenario: 租戶 Secrets 快取
- **WHEN** 系統載入租戶 Secrets
- **THEN** 結果快取 5 分鐘
- **AND** 租戶更新設定時快取失效

---

### Requirement: 群組自動歸屬租戶
Line Bot SHALL 在群組加入時自動歸屬到對應租戶，不需人工介入。

#### Scenario: 租戶 Bot 加入群組
- **WHEN** 使用者將租戶 A 的 Bot 加入 Line 群組
- **AND** 收到 JoinEvent
- **THEN** 系統建立 `line_groups` 記錄
- **AND** `tenant_id` 自動設定為租戶 A
- **AND** 平台管理員不需要手動指定

#### Scenario: 預設 Bot 加入群組（共用 Bot 模式）
- **WHEN** 使用者將預設 Bot（共用 Bot）加入 Line 群組
- **THEN** `tenant_id` 設定為 NULL（未綁定）
- **AND** 群組進入「等待綁定」狀態

---

### Requirement: 共用 Bot 群組綁定指令
共用 Bot 模式下，群組 SHALL 透過 `/綁定` 指令安全地歸屬到租戶。

#### Scenario: 綁定指令格式
- **WHEN** 用戶在未綁定的群組發送 `/綁定 {公司代碼}`
- **THEN** 系統解析指令並取得公司代碼

#### Scenario: 綁定驗證 - 發送者身份
- **WHEN** 系統收到綁定指令
- **THEN** 驗證發送者是否已綁定 CTOS 帳號
- **AND** 若未綁定，回覆：「請先綁定您的帳號後再試」
- **AND** 不執行綁定操作

#### Scenario: 綁定驗證 - 公司代碼
- **WHEN** 發送者已綁定 CTOS 帳號
- **THEN** 驗證公司代碼是否存在
- **AND** 若不存在，回覆：「找不到此公司代碼，請確認後再試」
- **AND** 不執行綁定操作

#### Scenario: 綁定驗證 - 租戶歸屬
- **WHEN** 公司代碼存在
- **THEN** 驗證發送者是否屬於該租戶
- **AND** 若不屬於，回覆：「您不屬於此公司，無法綁定」
- **AND** 不執行綁定操作

#### Scenario: 綁定成功
- **WHEN** 所有驗證通過
- **THEN** 更新 `line_groups.tenant_id` 為該租戶
- **AND** 回覆：「此群組已成功綁定到 {公司名稱}」
- **AND** 後續訊息使用該租戶設定處理

#### Scenario: 未綁定群組的訊息處理
- **WHEN** 收到訊息但群組 `tenant_id` 為 NULL
- **AND** 訊息不是 `/綁定` 指令
- **THEN** Bot 回覆：「請先使用 /綁定 公司代碼 綁定此群組」
- **AND** 不觸發 AI 處理

#### Scenario: 已綁定群組重新綁定
- **WHEN** 用戶在已綁定的群組發送 `/綁定` 指令
- **THEN** 回覆：「此群組已綁定到 {公司名稱}，如需變更請聯繫管理員」
- **AND** 不執行綁定操作

---

### Requirement: 群組解除綁定
租戶管理員或平台管理員 SHALL 能夠解除群組的租戶綁定。

#### Scenario: 解除綁定指令
- **WHEN** 租戶管理員在群組發送 `/解綁`
- **THEN** 驗證發送者是該群組所屬租戶的管理員
- **AND** 若驗證通過，將 `tenant_id` 設為 NULL
- **AND** 回覆：「此群組已解除綁定」

#### Scenario: 解除綁定權限不足
- **WHEN** 非管理員用戶發送 `/解綁`
- **THEN** 回覆：「只有管理員可以解除群組綁定」
- **AND** 不執行解綁操作

#### Scenario: 群組訊息處理
- **WHEN** 群組收到訊息
- **THEN** 系統根據 `line_groups.tenant_id` 使用對應租戶設定
- **AND** 使用該租戶的 Access Token 回覆

---

### Requirement: 租戶管理 Line Bot 設定 UI
租戶管理介面 SHALL 提供 Line Bot 設定功能。

#### Scenario: Line Bot 設定區塊
- **WHEN** 租戶管理員開啟租戶管理介面
- **THEN** 顯示「Line Bot 設定」區塊
- **AND** 顯示目前設定狀態

#### Scenario: 設定 Line Bot 憑證
- **WHEN** 租戶管理員填寫 Channel ID、Secret、Token
- **AND** 點擊儲存
- **THEN** 系統驗證格式正確
- **AND** 加密儲存到資料庫
- **AND** 顯示儲存成功訊息

#### Scenario: 測試連線按鈕
- **WHEN** 租戶管理員點擊「測試連線」
- **THEN** 系統使用填入的憑證測試 Line API
- **AND** 成功則顯示 Bot 名稱
- **AND** 失敗則顯示錯誤訊息

#### Scenario: 清除 Line Bot 設定
- **WHEN** 租戶管理員清空所有欄位並儲存
- **THEN** 系統清除該租戶的 Line Bot 設定
- **AND** 該租戶的群組將使用預設 Bot 處理

## MODIFIED Requirements

### Requirement: Line Bot Webhook 處理
Line Bot SHALL 接收並處理 Line Messaging API 的 Webhook 事件，支援多租戶自動識別。

#### Scenario: 接收 Webhook 請求
- **WHEN** Line 伺服器發送 POST 請求到 `/api/linebot/webhook`
- **THEN** 系統遍歷租戶 Secrets 驗證 X-Line-Signature 簽章
- **AND** 識別請求來自哪個租戶的 Bot
- **AND** 解析請求 body 取得事件列表
- **AND** 回傳 HTTP 200 OK

#### Scenario: 簽章驗證失敗
- **WHEN** 所有租戶的 Secret 和預設 Secret 都驗證失敗
- **THEN** 系統回傳 HTTP 400 Bad Request
- **AND** 不處理該請求的任何事件

#### Scenario: 處理文字訊息事件
- **WHEN** 收到 MessageEvent 且訊息類型為 TextMessage
- **THEN** 系統記錄訊息到資料庫
- **AND** 使用識別到的 tenant_id 關聯資料
- **AND** 檢查用戶綁定狀態與群組設定
- **AND** 依據存取控制結果決定是否觸發 AI 處理

#### Scenario: 處理加入群組事件
- **WHEN** 收到 JoinEvent
- **THEN** 系統建立或更新群組記錄
- **AND** `tenant_id` 設定為 Webhook 驗證識別的租戶
- **AND** 設定群組狀態為 active
- **AND** 設定 `allow_ai_response = false`
