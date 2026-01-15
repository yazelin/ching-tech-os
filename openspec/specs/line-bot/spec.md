# line-bot Specification

## Purpose
TBD - created by archiving change add-line-bot. Update Purpose after archive.
## Requirements
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

### Requirement: 群組訊息記錄
Line Bot SHALL 記錄群組內的所有訊息。

#### Scenario: 記錄文字訊息
- **WHEN** 群組收到文字訊息
- **THEN** 系統記錄發送者、訊息內容、時間戳記
- **AND** 如果群組已綁定專案，訊息關聯到該專案

#### Scenario: 記錄媒體訊息
- **WHEN** 群組收到圖片或檔案訊息
- **THEN** 系統記錄訊息類型、檔案路徑
- **AND** 建立 line_files 記錄

#### Scenario: 查詢群組訊息歷史
- **WHEN** 使用者請求 `GET /api/linebot/groups/{id}/messages`
- **THEN** 系統回傳該群組的訊息列表
- **AND** 支援分頁與日期範圍過濾

---

### Requirement: 群組與專案綁定
Line Bot SHALL 支援手動綁定群組到專案。

#### Scenario: 設定群組綁定專案
- **WHEN** 管理者請求 `PUT /api/linebot/groups/{id}/project`
- **AND** 提供 project_id 參數
- **THEN** 系統更新群組的 project_id
- **AND** 後續該群組訊息自動關聯到該專案

#### Scenario: 解除群組綁定
- **WHEN** 管理者請求 `DELETE /api/linebot/groups/{id}/project`
- **THEN** 系統將群組的 project_id 設為 null

#### Scenario: 查詢群組綁定狀態
- **WHEN** 使用者請求 `GET /api/linebot/groups/{id}`
- **THEN** 系統回傳群組資訊，包含綁定的專案 ID 與名稱

---

### Requirement: 檔案儲存管理
Line Bot SHALL 將圖片與檔案統一儲存到 NAS。

#### Scenario: 儲存圖片到 NAS
- **WHEN** 收到圖片訊息
- **THEN** 系統將圖片儲存到 `nas://linebot/groups/{group_id}/images/{date}/{message_id}.{ext}`
- **AND** 記錄儲存路徑到 line_files 表

#### Scenario: 儲存檔案到 NAS
- **WHEN** 收到檔案訊息
- **THEN** 系統將檔案儲存到 `nas://linebot/groups/{group_id}/files/{date}/{message_id}_{filename}`
- **AND** 記錄儲存路徑、檔名、大小到 line_files 表

#### Scenario: 查詢群組檔案列表
- **WHEN** 使用者請求 `GET /api/linebot/groups/{id}/files`
- **THEN** 系統回傳該群組的檔案列表
- **AND** 每個檔案包含檔名、類型、大小、縮圖路徑（如有）、建立時間

#### Scenario: 下載檔案
- **WHEN** 使用者請求 `GET /api/linebot/files/{id}/download`
- **THEN** 系統從 NAS 讀取檔案
- **AND** 回傳檔案內容供下載

---

### Requirement: 個人對話助理功能
Line Bot SHALL 在個人對話中提供助理功能。

#### Scenario: 記錄個人對話
- **WHEN** 收到個人訊息
- **THEN** 系統記錄訊息內容到 line_messages 表
- **AND** source_type 設為 'user'

#### Scenario: 查詢知識庫
- **WHEN** 使用者發送「查詢 {關鍵字}」格式訊息
- **THEN** 系統搜尋知識庫中符合關鍵字的內容
- **AND** 回覆搜尋結果摘要（最多 3 筆）

#### Scenario: 查詢專案狀態
- **WHEN** 使用者發送「專案 {專案名}」格式訊息
- **THEN** 系統搜尋符合名稱的專案
- **AND** 回覆專案狀態、最近里程碑、待處理事項

#### Scenario: 新增知識庫筆記
- **WHEN** 使用者發送「筆記 {內容}」格式訊息
- **THEN** 系統在知識庫建立新筆記
- **AND** 標籤設為 line-note
- **AND** 回覆建立成功訊息

#### Scenario: 一般對話
- **WHEN** 使用者發送非指令格式的訊息
- **THEN** 系統記錄訊息
- **AND** 可選擇使用 AI 回應或回覆使用說明

---

### Requirement: Line 群組管理 API
Line Bot SHALL 提供群組管理 RESTful API，包含刪除功能。

#### Scenario: 刪除群組
- **WHEN** 使用者請求 `DELETE /api/linebot/groups/{id}`
- **THEN** 系統刪除群組記錄
- **AND** 級聯刪除該群組的所有訊息記錄
- **AND** 級聯刪除該群組的所有檔案記錄
- **AND** 返回刪除結果（含已刪除的訊息數量）
- **AND** NAS 實體檔案不自動刪除

---

### Requirement: Line 使用者管理 API
Line Bot SHALL 記錄並管理 Line 使用者資訊，包含綁定狀態與好友狀態。

#### Scenario: 自動建立使用者
- **WHEN** 收到訊息且發送者為新使用者
- **THEN** 系統建立 line_users 記錄
- **AND** `user_id` 初始為 NULL（未綁定）
- **AND** 取得使用者 displayName 與頭像
- **AND** 根據訊息來源設定 `is_friend` 欄位

#### Scenario: 群組訊息取得用戶資料
- **WHEN** 收到群組訊息
- **THEN** 系統使用 `get_group_member_profile(group_id, user_id)` API 取得用戶資料
- **AND** 更新用戶的 displayName 與頭像
- **AND** 新用戶的 `is_friend` 設為 `false`

#### Scenario: 個人對話取得用戶資料
- **WHEN** 收到個人對話訊息
- **THEN** 系統使用 `get_profile(user_id)` API 取得用戶資料
- **AND** 更新用戶的 displayName 與頭像
- **AND** 新用戶的 `is_friend` 設為 `true`

#### Scenario: Bot 用戶記錄
- **WHEN** 系統建立 Bot 用戶記錄（ChingTech AI）
- **THEN** `is_friend` 設為 `false`

#### Scenario: 取得使用者列表
- **WHEN** 使用者請求 `GET /api/linebot/users`
- **THEN** 系統回傳所有 Line 使用者列表
- **AND** 包含每個用戶的綁定狀態（user_id, 綁定的 CTOS 用戶名稱）
- **AND** 包含每個用戶的好友狀態（is_friend）

#### Scenario: 取得使用者對話歷史
- **WHEN** 使用者請求 `GET /api/linebot/users/{id}/messages`
- **THEN** 系統回傳該使用者的個人對話歷史
- **AND** 支援分頁與日期範圍過濾

### Requirement: Line Bot 前端管理介面
Line Bot SHALL 提供桌面應用程式管理介面，包含群組刪除功能。

#### Scenario: 刪除群組操作
- **WHEN** 使用者在群組詳情頁面點擊「刪除群組」按鈕
- **THEN** 系統顯示確認對話框
- **AND** 對話框顯示群組名稱與將刪除的訊息數量
- **WHEN** 使用者確認刪除
- **THEN** 系統呼叫 DELETE API 刪除群組
- **AND** 刪除成功後重新載入群組列表
- **AND** 顯示刪除成功通知

### Requirement: 資料庫儲存
Line Bot SHALL 使用 PostgreSQL 資料庫儲存資料。

#### Scenario: line_groups 資料表
- **WHEN** 系統儲存群組
- **THEN** 群組資料存於 `line_groups` 資料表
- **AND** 包含欄位：id、line_group_id、name、project_id、status、allow_ai_response、created_at、updated_at

#### Scenario: line_users 資料表
- **WHEN** 系統儲存使用者
- **THEN** 使用者資料存於 `line_users` 資料表
- **AND** 包含欄位：id、line_user_id、display_name、picture_url、created_at、updated_at

#### Scenario: line_messages 資料表
- **WHEN** 系統儲存訊息
- **THEN** 訊息資料存於 `line_messages` 資料表
- **AND** 包含欄位：id、line_group_id、line_user_id、message_type、content、media_path、metadata、source_type、created_at

#### Scenario: line_files 資料表
- **WHEN** 系統儲存檔案
- **THEN** 檔案資料存於 `line_files` 資料表
- **AND** 包含欄位：id、line_message_id、line_group_id、file_name、file_type、file_size、storage_path、thumbnail_path、created_at

#### Scenario: line_binding_codes 資料表
- **WHEN** 系統產生綁定驗證碼
- **THEN** 驗證碼資料存於 `line_binding_codes` 資料表
- **AND** 包含欄位：id、user_id、code、expires_at、used_at、used_by_line_user_id、created_at

#### Scenario: 級聯刪除
- **WHEN** 刪除群組
- **THEN** 同時刪除關聯的訊息與檔案記錄
- **AND** NAS 檔案需另行清理（不自動刪除）

---

### Requirement: 用戶綁定與存取控制
Line Bot SHALL 實作用戶綁定機制，限制只有 CTOS 用戶才能使用 Bot。

#### Scenario: 產生綁定驗證碼
- **WHEN** CTOS 用戶請求 `POST /api/linebot/binding/generate-code`
- **THEN** 系統產生 6 位數字驗證碼
- **AND** 驗證碼有效期為 5 分鐘
- **AND** 清除該用戶之前未使用的驗證碼

#### Scenario: 驗證綁定碼
- **WHEN** Line 用戶私訊 Bot 發送 6 位數字
- **AND** 數字為有效的綁定驗證碼
- **THEN** 系統綁定該 Line 帳號與 CTOS 帳號
- **AND** 回覆綁定成功訊息

#### Scenario: 驗證碼無效
- **WHEN** Line 用戶私訊 Bot 發送 6 位數字
- **AND** 數字不是有效的綁定驗證碼
- **THEN** 系統回覆驗證碼無效或已過期

#### Scenario: 解除綁定
- **WHEN** CTOS 用戶請求 `DELETE /api/linebot/binding`
- **THEN** 系統解除該用戶的 Line 綁定
- **AND** 該 Line 帳號無法再使用 Bot

#### Scenario: 查詢綁定狀態
- **WHEN** CTOS 用戶請求 `GET /api/linebot/binding/status`
- **THEN** 系統回傳用戶的 Line 綁定狀態
- **AND** 如已綁定，回傳 Line 顯示名稱與頭像

#### Scenario: 個人對話存取控制
- **WHEN** 未綁定 CTOS 帳號的 Line 用戶私訊 Bot
- **THEN** Bot 回覆提示訊息，說明需要綁定帳號
- **AND** 不執行 AI 處理

#### Scenario: 群組對話存取控制
- **WHEN** Line 群組收到訊息觸發 AI
- **AND** 發送者未綁定 CTOS 帳號或群組未開啟 AI 回應
- **THEN** Bot 靜默不回應

#### Scenario: 群組 AI 回應開關
- **WHEN** 管理者請求 `PATCH /api/linebot/groups/{id}` 更新 allow_ai_response
- **THEN** 系統更新群組的 AI 回應設定
- **AND** 只有開啟 AI 回應的群組才會觸發 AI 處理

#### Scenario: 前端綁定管理
- **WHEN** 使用者在 Line Bot 管理介面
- **THEN** 顯示「我的 Line 綁定」分頁
- **AND** 可產生驗證碼、解除綁定
- **AND** 顯示目前綁定狀態

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

### Requirement: Line Bot Agent 整合
Line Bot SHALL 使用資料庫中的 Agent/Prompt 設定進行 AI 對話處理。

#### Scenario: 個人對話使用 linebot-personal Agent
- **WHEN** Line 用戶在個人對話中發送訊息
- **AND** 觸發 AI 處理
- **THEN** 系統從資料庫取得 `linebot-personal` Agent 設定
- **AND** 使用該 Agent 的 model 設定
- **AND** 使用該 Agent 的 system_prompt 內容

#### Scenario: 群組對話使用 linebot-group Agent
- **WHEN** Line 用戶在群組中觸發 AI 處理
- **THEN** 系統從資料庫取得 `linebot-group` Agent 設定
- **AND** 使用該 Agent 的 model 設定
- **AND** 使用該 Agent 的 system_prompt 內容
- **AND** 動態附加群組資訊和綁定專案資訊到 prompt

#### Scenario: Agent 不存在時的 Fallback
- **WHEN** 系統找不到對應的 Agent 設定
- **THEN** 系統使用硬編碼的預設 Prompt 作為 fallback
- **AND** 記錄警告日誌

---

### Requirement: 預設 Line Bot Agent 初始化
系統 SHALL 在啟動時確保預設的 Line Bot Agent 存在。

#### Scenario: 應用程式啟動時檢查並建立預設 Agent
- **WHEN** 應用程式啟動
- **THEN** 系統檢查 `linebot-personal` Agent 是否存在
- **AND** 若不存在則建立預設的 `linebot-personal` Agent 和對應的 Prompt
- **AND** 系統檢查 `linebot-group` Agent 是否存在
- **AND** 若不存在則建立預設的 `linebot-group` Agent 和對應的 Prompt

#### Scenario: 保留使用者修改
- **WHEN** 應用程式啟動
- **AND** Agent 已存在
- **THEN** 系統不覆蓋現有 Agent 設定
- **AND** 保留使用者透過 UI 修改的內容

#### Scenario: linebot-personal Agent 預設設定
- **WHEN** 系統建立 `linebot-personal` Agent
- **THEN** Agent 的 model 為 `claude-sonnet`
- **AND** Prompt 類別為 `linebot`
- **AND** Prompt 內容包含 MCP 工具說明（專案查詢、知識庫搜尋等）

#### Scenario: linebot-group Agent 預設設定
- **WHEN** 系統建立 `linebot-group` Agent
- **THEN** Agent 的 model 為 `claude-haiku`
- **AND** Prompt 類別為 `linebot`
- **AND** Prompt 內容包含 MCP 工具說明
- **AND** Prompt 內容限制回覆長度（不超過 200 字）

---

### Requirement: Line Bot AI Log 記錄
Line Bot 的 AI 呼叫記錄 SHALL 正確關聯到 Agent。

#### Scenario: AI Log 記錄關聯 Agent
- **WHEN** Line Bot 完成一次 AI 呼叫
- **THEN** AI Log 的 agent_id 關聯到實際使用的 Agent（`linebot-personal` 或 `linebot-group`）
- **AND** 前端 AI Log 頁面顯示正確的 Agent 名稱

---

### Requirement: 個人對話重置功能
Line Bot SHALL 支援個人對話的對話歷史重置。

#### Scenario: 重置對話歷史
- **WHEN** Line 用戶在個人對話中發送 `/新對話` 或 `/reset`
- **THEN** 系統更新用戶的 `conversation_reset_at` 為當前時間
- **AND** 回覆「已清除對話歷史，開始新對話！」
- **AND** 後續 AI 處理不會看到重置前的對話內容

#### Scenario: 群組不支援重置
- **WHEN** Line 用戶在群組中發送重置指令
- **THEN** 系統靜默忽略，不執行重置操作

### Requirement: Line Bot 對話歷史包含圖片資訊
Line Bot 的對話歷史 SHALL 包含用戶上傳的圖片資訊，讓 AI 能夠感知並自行決定是否處理。

#### Scenario: 對話歷史包含圖片訊息
- **WHEN** 系統組合對話歷史給 AI
- **AND** 歷史中包含圖片訊息
- **THEN** 圖片訊息格式化為 `[上傳圖片: /tmp/linebot-images/{line_message_id}.jpg]`
- **AND** AI 可以看到用戶上傳了圖片及其路徑

#### Scenario: 確保圖片暫存檔存在
- **WHEN** 系統準備呼叫 AI
- **AND** 對話歷史中包含圖片路徑
- **THEN** 系統檢查暫存檔是否存在
- **AND** 如不存在，從 NAS 讀取圖片並寫入暫存路徑
- **AND** AI 處理時可透過 Read 工具讀取圖片

#### Scenario: AI 自行判斷是否讀取圖片
- **WHEN** AI 收到對話歷史（包含圖片路徑）和用戶訊息
- **THEN** AI 根據用戶意圖自行判斷是否需要讀取圖片
- **AND** 如需讀取，使用 Read 工具讀取暫存路徑的圖片
- **AND** 如不需讀取，直接處理用戶的其他請求

#### Scenario: Read 工具可用
- **WHEN** Line Bot 呼叫 Claude CLI
- **THEN** 允許的工具列表包含 `Read`
- **AND** Claude 可以使用 Read 工具讀取圖片檔案

---

### Requirement: Line Bot 回覆舊圖片處理
Line Bot SHALL 支援用戶回覆舊圖片訊息時的圖片分析。

#### Scenario: 用戶回覆圖片訊息
- **WHEN** 用戶使用 Line 的回覆功能回覆一則圖片訊息
- **AND** 發送文字訊息
- **THEN** 系統從 `quotedMessageId` 取得被回覆的訊息 ID
- **AND** 如果被回覆的是圖片訊息，載入該圖片到暫存
- **AND** 在用戶訊息中標註 `[回覆圖片: {temp_path}]`
- **AND** AI 可以讀取該圖片回答問題

#### Scenario: 回覆非圖片訊息
- **WHEN** 用戶回覆的不是圖片訊息
- **THEN** 系統按原有流程處理，不載入額外圖片

---

### Requirement: Line Bot 圖片暫存清理
Line Bot SHALL 定期清理過期的圖片與檔案暫存檔。

#### Scenario: 定期清理暫存檔
- **WHEN** 排程任務執行（每小時）
- **THEN** 系統掃描 `/tmp/linebot-images/` 目錄
- **AND** 系統掃描 `/tmp/linebot-files/` 目錄
- **AND** 刪除修改時間超過 1 小時的檔案
- **AND** 不影響 NAS 上的原始檔案

### Requirement: Line Bot 對話歷史包含檔案資訊
Line Bot 的對話歷史 SHALL 包含用戶上傳的可讀取檔案資訊，讓 AI 能夠感知並自行決定是否處理。

#### Scenario: 對話歷史包含檔案訊息
- **WHEN** 系統組合對話歷史給 AI
- **AND** 歷史中包含檔案訊息
- **AND** 檔案副檔名為可讀取類型（txt, md, json, csv, log, xml, yaml, yml, pdf）
- **THEN** 檔案訊息格式化為 `[上傳檔案: /tmp/linebot-files/{line_message_id}_{filename}]`
- **AND** AI 可以看到用戶上傳了檔案及其路徑

#### Scenario: 確保檔案暫存檔存在
- **WHEN** 系統準備呼叫 AI
- **AND** 對話歷史中包含檔案路徑
- **THEN** 系統檢查暫存檔是否存在
- **AND** 如不存在，從 NAS 讀取檔案並寫入 `/tmp/linebot-files/`
- **AND** AI 處理時可透過 Read 工具讀取檔案內容

#### Scenario: AI 自行判斷是否讀取檔案
- **WHEN** AI 收到對話歷史（包含檔案路徑）和用戶訊息
- **THEN** AI 根據用戶意圖自行判斷是否需要讀取檔案
- **AND** 如需讀取，使用 Read 工具讀取暫存路徑的檔案
- **AND** 如不需讀取，直接處理用戶的其他請求

#### Scenario: 不支援的檔案類型
- **WHEN** 用戶上傳不支援的檔案（如 docx, pptx, xlsx）
- **THEN** 系統不將檔案複製到暫存
- **AND** 對話歷史顯示 `[上傳檔案: {filename}（無法讀取此類型）]`
- **AND** AI 可告知用戶此檔案類型暫不支援

#### Scenario: 大檔案限制
- **WHEN** 用戶上傳超過 5MB 的檔案
- **THEN** 系統不將檔案複製到暫存
- **AND** 對話歷史顯示 `[上傳檔案: {filename}（檔案過大）]`

---

### Requirement: Line Bot 回覆舊檔案處理
Line Bot SHALL 支援用戶回覆舊檔案訊息時的檔案讀取。

#### Scenario: 用戶回覆檔案訊息
- **WHEN** 用戶使用 Line 的回覆功能回覆一則檔案訊息
- **AND** 發送文字訊息
- **AND** 被回覆的檔案為可讀取類型
- **THEN** 系統從 `quotedMessageId` 取得被回覆的訊息 ID
- **AND** 載入該檔案到暫存
- **AND** 在用戶訊息中標註 `[回覆檔案: {temp_path}]`
- **AND** AI 可以讀取該檔案回答問題

#### Scenario: 回覆不可讀取的檔案
- **WHEN** 用戶回覆的檔案為不支援的類型
- **THEN** 系統在用戶訊息中標註 `[回覆檔案: {filename}（無法讀取此類型）]`
- **AND** AI 可告知用戶此檔案類型暫不支援

---

### Requirement: Line Bot 多訊息回覆
Line Bot SHALL 支援一次回覆多則訊息（文字 + 圖片混合）。

#### Scenario: 回覆文字和圖片
- **WHEN** AI 回應包含檔案訊息標記
- **AND** reply_token 有效
- **THEN** 系統解析 AI 回應提取檔案資訊
- **AND** 組合 TextMessage 和 ImageMessage
- **AND** 使用 `reply_message` 一次發送（最多 5 則）

#### Scenario: 訊息數量超過限制
- **WHEN** AI 回應包含超過 4 張圖片
- **THEN** 系統只發送前 4 張圖片
- **AND** 其餘圖片以連結形式附加在文字中

#### Scenario: reply_token 過期 fallback
- **WHEN** reply_token 已過期
- **AND** 有檔案訊息需要發送
- **THEN** 系統改用 push_message 發送
- **AND** 記錄警告日誌

---

### Requirement: AI 回應解析
Line Bot SHALL 解析 AI 回應中的檔案訊息標記。

#### Scenario: 解析 FILE_MESSAGE 標記
- **WHEN** AI 回應包含 `[FILE_MESSAGE:{...}]` 格式標記
- **THEN** 系統提取 JSON 內容
- **AND** 移除標記保留純文字回覆
- **AND** 根據 type 欄位決定訊息類型（image/file）

#### Scenario: 無效的 JSON 格式
- **WHEN** FILE_MESSAGE 標記中的 JSON 格式無效
- **THEN** 系統忽略該標記
- **AND** 將標記原文保留在回覆中
- **AND** 記錄警告日誌

#### Scenario: 回應不含標記
- **WHEN** AI 回應不包含任何 FILE_MESSAGE 標記
- **THEN** 系統按原有邏輯回覆純文字

### Requirement: 群組專案操作限制
Line Bot 在群組對話中 SHALL 根據是否綁定專案決定操作規則。

#### Scenario: 群組有綁定專案
- **WHEN** AI 處理群組對話
- **AND** 群組有綁定專案
- **THEN** system prompt 明確告知「此群組綁定專案：{專案名稱}（ID: {專案ID}）」
- **AND** AI 只能操作此綁定專案，不可操作其他專案
- **AND** 不檢查成員權限（群組內都可以操作）

#### Scenario: 群組未綁定專案
- **WHEN** AI 處理群組對話
- **AND** 群組未綁定專案
- **THEN** system prompt 說明「此群組尚未綁定專案」
- **AND** 可操作任意專案，但需檢查成員權限（與個人對話規則相同）

#### Scenario: 用戶要求操作其他專案（有綁定時）
- **WHEN** 群組已綁定專案 A
- **AND** 用戶要求操作專案 B
- **THEN** AI 應拒絕並說明「此群組只能操作綁定的專案 A」

---

### Requirement: 個人對話專案推斷與權限
Line Bot 在個人對話中 SHALL 從對話上下文推斷用戶要操作的專案，並檢查成員權限。

#### Scenario: 從對話上下文推斷專案
- **WHEN** AI 處理個人對話
- **AND** 用戶之前提到過某個專案
- **THEN** AI 從對話歷史推斷用戶要操作的專案

#### Scenario: 無法推斷時詢問
- **WHEN** 用戶請求專案相關操作
- **AND** AI 無法從對話上下文確定是哪個專案
- **THEN** AI 應詢問用戶要操作哪個專案

#### Scenario: 成員權限檢查
- **WHEN** 用戶嘗試更新專案資料
- **AND** 用戶不是該專案的成員（`project_members.user_id`）
- **THEN** 系統拒絕操作並回傳「您不是此專案的成員，無法進行此操作」

#### Scenario: 成員可操作
- **WHEN** 用戶嘗試更新專案資料
- **AND** 用戶是該專案的成員
- **THEN** 系統允許操作

### Requirement: AI 圖片生成
Line Bot 個人 AI 助手 SHALL 支援根據用戶文字描述生成圖片。

#### Scenario: 用戶請求生成圖片
- **WHEN** 用戶發送「畫一隻貓」或類似的圖片生成請求
- **THEN** AI 呼叫 `mcp__nanobanana__generate_image` 生成圖片
- **AND** AI 呼叫 `prepare_file_message` 準備圖片訊息
- **AND** 圖片透過 Line Bot 發送給用戶

#### Scenario: 圖片生成使用英文 prompt
- **WHEN** AI 處理圖片生成請求
- **THEN** AI 將用戶的中文描述轉換為英文 prompt
- **BECAUSE** nanobanana 使用英文 prompt 效果較佳

#### Scenario: 圖片生成後自動發送
- **WHEN** AI 呼叫 `generate_image` 成功生成圖片
- **AND** AI 回應中沒有包含對應的 `[FILE_MESSAGE:...]` 標記
- **THEN** 系統自動呼叫 `prepare_file_message` 並補上 FILE_MESSAGE 標記
- **BECAUSE** 確保用戶一定能收到生成的圖片，不依賴 AI 是否正確呼叫 prepare_file_message

#### Scenario: AI 已處理圖片則不重複發送
- **WHEN** AI 呼叫 `generate_image` 成功生成圖片
- **AND** AI 回應中已包含對應的 `[FILE_MESSAGE:...]` 標記
- **THEN** 系統跳過自動處理，不重複發送圖片

### Requirement: nanobanana 輸出路徑
系統 SHALL 自動設定 nanobanana 輸出路徑到 NAS 目錄，讓生成的圖片可透過 Line Bot 發送。

#### Scenario: 自動建立 symlink
- **WHEN** Claude Agent 啟動時
- **THEN** 系統檢查並建立 `/tmp/ching-tech-os-cli/nanobanana-output` symlink
- **AND** symlink 指向 `/mnt/nas/ctos/linebot/files/ai-images`

#### Scenario: NAS 目錄不存在時自動建立
- **WHEN** `/mnt/nas/ctos/linebot/files/ai-images` 目錄不存在
- **AND** NAS 掛載點 `/mnt/nas/ctos/linebot/files` 存在
- **THEN** 系統自動建立 `ai-images` 目錄

### Requirement: 群組對話回應時 Mention 用戶
Line Bot 在群組對話中回應時 SHALL mention（@）發問的用戶，讓用戶清楚知道回應對象。

#### Scenario: 群組對話回應包含 mention
- **WHEN** Bot 在群組中回覆用戶的訊息
- **THEN** 回覆訊息使用 `TextMessageV2` 格式
- **AND** 訊息開頭 mention 發問的用戶
- **AND** 用戶會收到 Line 的提及通知

#### Scenario: 個人對話不使用 mention
- **WHEN** Bot 在個人對話中回覆用戶
- **THEN** 回覆訊息使用一般的 `TextMessage` 格式
- **AND** 不包含 mention（因為一對一不需要）

#### Scenario: 混合訊息回覆（文字+圖片）
- **WHEN** Bot 在群組中回覆包含圖片的訊息
- **THEN** 第一則文字訊息使用 `TextMessageV2` 並 mention 用戶
- **AND** 後續的圖片訊息使用 `ImageMessage`
- **AND** 整體回覆順序維持：文字在前、圖片在後

#### Scenario: 無法取得用戶 ID 時的 fallback
- **WHEN** Bot 需要回覆但無法取得發問用戶的 Line User ID
- **THEN** 使用一般的 `TextMessage` 回覆
- **AND** 不阻擋回覆流程

### Requirement: Line Bot PDF 轉圖片功能
Line Bot SHALL 支援將用戶上傳或 NAS 上的 PDF 檔案轉換為圖片，方便在 Line 中預覽。

#### Scenario: 用戶上傳 PDF 後請求轉換
- **WHEN** 用戶在 Line 上傳 PDF 檔案
- **AND** 發送訊息要求轉換為圖片（如「幫我轉成圖片」、「轉換成 png」）
- **THEN** AI 先查詢 PDF 頁數
- **AND** 根據頁數決定後續流程（單頁直接轉、多頁先詢問）

#### Scenario: 用戶指定 NAS 上的 PDF 轉換
- **WHEN** 用戶請求轉換 NAS 上的 PDF（如「把 xx 專案的 layout.pdf 轉成圖片」）
- **THEN** AI 先使用 `search_nas_files` 找到 PDF 路徑
- **AND** 查詢 PDF 頁數後決定後續流程

#### Scenario: 單頁 PDF 直接轉換
- **WHEN** PDF 只有 1 頁
- **THEN** AI 直接轉換並發送圖片
- **AND** 不需要詢問用戶

#### Scenario: 多頁 PDF 先詢問用戶
- **WHEN** PDF 有 2 頁以上
- **THEN** AI 詢問用戶「這份 PDF 共有 X 頁，要轉換哪幾頁？」
- **AND** 提供選項建議（如：全部、前 3 頁、第 1 頁）
- **WHEN** 用戶回覆後
- **THEN** AI 根據回覆設定頁面範圍進行轉換

#### Scenario: 用戶指定頁面範圍
- **WHEN** 用戶明確指定要轉換的頁面（如「轉換第 1-3 頁」、「只要第一頁」）
- **THEN** AI 直接按指定範圍轉換
- **AND** 不需要額外詢問

#### Scenario: PDF 頁數超過限制
- **WHEN** 用戶要求轉換的頁數超過最大限制（預設 20 頁）
- **THEN** AI 告知用戶限制並詢問是否轉換前 20 頁

#### Scenario: 對話歷史包含 PDF 訊息
- **WHEN** 系統組合對話歷史給 AI
- **AND** 歷史中包含 PDF 檔案訊息
- **THEN** PDF 訊息格式化為 `[上傳 PDF: /tmp/linebot-files/{line_message_id}_{filename}]`
- **AND** AI 可以看到用戶上傳了 PDF 及其路徑

---

### Requirement: Line Bot PDF 檔案處理
Line Bot SHALL 將用戶上傳的 PDF 檔案儲存到 NAS 以供後續轉換使用。

#### Scenario: 儲存 PDF 到 NAS
- **WHEN** 收到 PDF 類型的檔案訊息
- **THEN** 系統將 PDF 儲存到 `nas://linebot/files/{group_or_user}/{date}/{message_id}_{filename}`
- **AND** 記錄儲存路徑到 line_files 表

#### Scenario: PDF 複製到暫存供 AI 讀取
- **WHEN** 系統準備呼叫 AI
- **AND** 對話歷史中包含 PDF 路徑
- **THEN** 系統將 PDF 複製到 `/tmp/linebot-files/`
- **AND** AI 可透過 `convert_pdf_to_images` 工具處理該 PDF

