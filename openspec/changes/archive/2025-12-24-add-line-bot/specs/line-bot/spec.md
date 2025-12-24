## ADDED Requirements

### Requirement: Line Bot Webhook 處理
Line Bot SHALL 接收並處理 Line Messaging API 的 Webhook 事件。

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
- **AND** 依據來源類型（群組/個人）執行對應處理

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
Line Bot SHALL 記錄並管理 Line 使用者資訊。

#### Scenario: 自動建立使用者
- **WHEN** 收到訊息且發送者為新使用者
- **THEN** 系統建立 line_users 記錄
- **AND** 嘗試取得使用者 displayName 與頭像

#### Scenario: 取得使用者列表
- **WHEN** 使用者請求 `GET /api/linebot/users`
- **THEN** 系統回傳所有 Line 使用者列表

#### Scenario: 取得使用者對話歷史
- **WHEN** 使用者請求 `GET /api/linebot/users/{id}/messages`
- **THEN** 系統回傳該使用者的個人對話歷史
- **AND** 支援分頁與日期範圍過濾

---

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
- **AND** 包含欄位：id、line_group_id、name、project_id、status、created_at、updated_at

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

#### Scenario: 級聯刪除
- **WHEN** 刪除群組
- **THEN** 同時刪除關聯的訊息與檔案記錄
- **AND** NAS 檔案需另行清理（不自動刪除）
