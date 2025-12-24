## ADDED Requirements

### Requirement: Line 用戶與 CTOS 帳號綁定
Line Bot SHALL 提供 Line 用戶與 CTOS 帳號的綁定機制。

#### Scenario: 產生綁定驗證碼
- **WHEN** 已登入的 CTOS 用戶請求 `POST /api/linebot/binding/generate-code`
- **THEN** 系統產生 6 位數字驗證碼
- **AND** 驗證碼有效期為 5 分鐘
- **AND** 同一用戶的舊驗證碼自動失效
- **AND** 回傳驗證碼與到期時間

#### Scenario: Line 用戶傳送驗證碼完成綁定
- **WHEN** Line 用戶在個人對話中傳送 6 位數字
- **AND** 該數字為有效的驗證碼
- **THEN** 系統將該 Line 用戶綁定到對應的 CTOS 帳號
- **AND** 更新 `line_users.user_id` 欄位
- **AND** 標記驗證碼為已使用
- **AND** 回覆綁定成功訊息

#### Scenario: 驗證碼無效或過期
- **WHEN** Line 用戶傳送的驗證碼不存在或已過期
- **THEN** 系統回覆「驗證碼無效或已過期，請重新產生」

#### Scenario: Line 帳號已綁定其他 CTOS 帳號
- **WHEN** Line 用戶嘗試綁定，但該 Line 帳號已綁定另一個 CTOS 帳號
- **THEN** 系統回覆「此 Line 帳號已綁定其他帳號，請先解除綁定」

#### Scenario: 查詢綁定狀態
- **WHEN** 已登入的 CTOS 用戶請求 `GET /api/linebot/binding/status`
- **THEN** 系統回傳綁定狀態
- **AND** 若已綁定，包含 Line 顯示名稱與綁定時間

#### Scenario: 解除綁定
- **WHEN** 已登入的 CTOS 用戶請求 `DELETE /api/linebot/binding`
- **AND** 該用戶已綁定 Line 帳號
- **THEN** 系統將 `line_users.user_id` 設為 NULL
- **AND** 該 Line 帳號將無法再使用 Bot
- **AND** 回傳解除成功訊息

---

### Requirement: Line Bot 存取控制
Line Bot SHALL 限制只有已綁定帳號的用戶才能使用。

#### Scenario: 未綁定用戶的個人對話
- **WHEN** 未綁定 CTOS 帳號的 Line 用戶在個人對話中發送訊息
- **AND** 訊息不是驗證碼格式
- **THEN** 系統回覆「請先在 CTOS 綁定您的 Line 帳號才能使用此功能」
- **AND** 訊息不觸發 AI 處理

#### Scenario: 未綁定用戶的群組訊息
- **WHEN** 未綁定 CTOS 帳號的 Line 用戶在群組中 @ 提及 Bot
- **THEN** 系統靜默不回應
- **AND** 訊息仍記錄到資料庫

#### Scenario: 已綁定用戶的正常使用
- **WHEN** 已綁定 CTOS 帳號的 Line 用戶發送訊息
- **AND** 符合 AI 觸發條件
- **THEN** 系統正常處理訊息並回應

---

### Requirement: 群組 AI 回應控制
Line Bot SHALL 支援群組層級的 AI 回應開關。

#### Scenario: 群組預設不回應
- **WHEN** Bot 新加入一個群組
- **THEN** 該群組的 `allow_ai_response` 預設為 `false`
- **AND** Bot 不會回應該群組的訊息

#### Scenario: 開啟群組 AI 回應
- **WHEN** 管理者請求 `PATCH /api/linebot/groups/{id}`
- **AND** 設定 `allow_ai_response = true`
- **THEN** Bot 開始回應該群組中已綁定用戶的訊息

#### Scenario: 關閉群組 AI 回應
- **WHEN** 管理者請求 `PATCH /api/linebot/groups/{id}`
- **AND** 設定 `allow_ai_response = false`
- **THEN** Bot 停止回應該群組的訊息
- **AND** 訊息仍繼續記錄

#### Scenario: 群組 AI 回應的雙重檢查
- **WHEN** Line 用戶在群組中 @ 提及 Bot
- **AND** 群組 `allow_ai_response = true`
- **AND** 該用戶未綁定 CTOS 帳號
- **THEN** 系統靜默不回應

---

## MODIFIED Requirements

### Requirement: Line Bot Webhook 處理
Line Bot SHALL 接收並處理 Line Messaging API 的 Webhook 事件，並加入存取控制檢查。

#### Scenario: 接收 Webhook 請求
- **WHEN** Line 伺服器發送 POST 請求到 `/api/linebot/webhook`
- **THEN** 系統驗證 X-Line-Signature 簽章
- **AND** 解析請求 body 取得事件列表
- **AND** 回傳 HTTP 200 OK

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

---

### Requirement: Line 使用者管理 API
Line Bot SHALL 記錄並管理 Line 使用者資訊，包含綁定狀態。

#### Scenario: 自動建立使用者
- **WHEN** 收到訊息且發送者為新使用者
- **THEN** 系統建立 line_users 記錄
- **AND** `user_id` 初始為 NULL（未綁定）
- **AND** 嘗試取得使用者 displayName 與頭像

#### Scenario: 取得使用者列表
- **WHEN** 使用者請求 `GET /api/linebot/users`
- **THEN** 系統回傳所有 Line 使用者列表
- **AND** 包含每個用戶的綁定狀態（user_id, 綁定的 CTOS 用戶名稱）

#### Scenario: 取得使用者對話歷史
- **WHEN** 使用者請求 `GET /api/linebot/users/{id}/messages`
- **THEN** 系統回傳該使用者的個人對話歷史
- **AND** 支援分頁與日期範圍過濾
