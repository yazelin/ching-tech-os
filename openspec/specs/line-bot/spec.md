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
Line Bot SHALL 提供群組管理 RESTful API。

#### Scenario: 取得群組列表
- **WHEN** 使用者請求 `GET /api/linebot/groups`
- **THEN** 系統回傳所有群組列表
- **AND** 每個群組包含 id、名稱、狀態、綁定專案、訊息數量

#### Scenario: 取得群組詳情
- **WHEN** 使用者請求 `GET /api/linebot/groups/{id}`
- **THEN** 系統回傳群組完整資訊

#### Scenario: 更新群組資訊
- **WHEN** 使用者請求 `PUT /api/linebot/groups/{id}`
- **THEN** 系統更新群組名稱、狀態等欄位

#### Scenario: 停用群組
- **WHEN** 使用者請求 `DELETE /api/linebot/groups/{id}`
- **THEN** 系統將群組狀態設為 inactive
- **AND** 不再處理該群組訊息

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

### Requirement: Line Bot 前端管理介面
Line Bot SHALL 提供桌面應用程式管理介面。

#### Scenario: 開啟 Line Bot 管理
- **WHEN** 使用者點擊 Taskbar 的 Line Bot 圖示
- **THEN** 開啟 Line Bot 管理視窗
- **AND** 顯示群組列表標籤頁

#### Scenario: 群組列表頁面
- **WHEN** 使用者在群組列表標籤頁
- **THEN** 顯示所有群組卡片
- **AND** 每個卡片顯示群組名稱、狀態、綁定專案、訊息數量

#### Scenario: 群組詳情頁面
- **WHEN** 使用者點擊群組卡片
- **THEN** 切換到群組詳情頁面
- **AND** 顯示群組資訊與專案綁定設定
- **AND** 顯示最近訊息列表

#### Scenario: 專案綁定操作
- **WHEN** 使用者在群組詳情選擇專案下拉選單
- **THEN** 顯示所有可用專案列表
- **WHEN** 使用者選擇專案並確認
- **THEN** 系統更新群組綁定

#### Scenario: 對話歷史頁面
- **WHEN** 使用者切換到對話歷史標籤頁
- **THEN** 顯示群組/使用者選擇器
- **AND** 顯示對話訊息列表

#### Scenario: 檔案庫覽頁面
- **WHEN** 使用者切換到檔案庫覽標籤頁
- **THEN** 顯示群組檔案列表
- **AND** 圖片顯示縮圖，可點擊預覽
- **AND** 檔案可點擊下載

---

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

