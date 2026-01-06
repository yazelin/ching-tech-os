# public-share-links Specification

## Purpose
提供暫時性公開連結功能，讓使用者可以分享知識庫或專案給未登入者只讀查看。

## ADDED Requirements

### Requirement: 公開連結資料庫儲存
系統 SHALL 使用 PostgreSQL 儲存公開分享連結資料。

#### Scenario: public_share_links 資料表
- **WHEN** 系統儲存公開連結
- **THEN** 連結資料存於 `public_share_links` 資料表
- **AND** 包含欄位：id (UUID), token (VARCHAR 10 UNIQUE), resource_type, resource_id, created_by, expires_at, access_count, created_at

#### Scenario: Token 唯一索引
- **WHEN** 建立 public_share_links 表格
- **THEN** token 欄位建立唯一索引
- **AND** 確保 token 不重複

---

### Requirement: 公開連結 API（需登入）
系統 SHALL 提供需登入的 API 供使用者管理公開連結。

#### Scenario: 建立公開連結
- **WHEN** 使用者請求 `POST /api/share`
- **AND** 提供 resource_type（knowledge 或 project）、resource_id、expires_in（可選）
- **THEN** 系統產生 6 字元隨機 token
- **AND** 儲存連結記錄到資料庫
- **AND** 回傳 token、完整 URL、有效期資訊

#### Scenario: 建立連結權限檢查
- **WHEN** 使用者嘗試建立公開連結
- **AND** 使用者對該資源沒有編輯權限
- **THEN** 系統回傳 403 權限錯誤

#### Scenario: 列出我的連結
- **WHEN** 使用者請求 `GET /api/share`
- **THEN** 系統回傳該使用者建立的所有連結
- **AND** 每個連結包含 token、資源類型、資源 ID、資源名稱、有效期、存取次數、建立時間

#### Scenario: 撤銷連結
- **WHEN** 使用者請求 `DELETE /api/share/{token}`
- **AND** 該連結由該使用者建立
- **THEN** 系統刪除連結記錄
- **AND** 回傳成功狀態

#### Scenario: 撤銷他人連結
- **WHEN** 使用者嘗試撤銷他人建立的連結
- **THEN** 系統回傳 403 權限錯誤

---

### Requirement: 公開資源 API（無需登入）
系統 SHALL 提供無需登入的 API 供訪客存取公開資源。

#### Scenario: 取得公開資源
- **WHEN** 訪客請求 `GET /api/public/{token}`
- **AND** token 有效且未過期
- **THEN** 系統回傳資源內容
- **AND** 更新 access_count

#### Scenario: 取得公開知識庫
- **WHEN** 訪客請求公開知識庫
- **THEN** 回傳包含：id、標題、內容、附件列表、相關知識（僅標題）、分享者、分享時間

#### Scenario: 取得公開專案
- **WHEN** 訪客請求公開專案
- **THEN** 回傳包含：id、名稱、描述、狀態、里程碑列表、成員列表（僅姓名和角色）
- **AND** 隱藏敏感資訊（聯絡方式等）

#### Scenario: 連結過期
- **WHEN** 訪客請求已過期的連結
- **THEN** 系統回傳 410 Gone 狀態
- **AND** 回傳「此連結已過期」訊息

#### Scenario: 連結不存在
- **WHEN** 訪客請求不存在的 token
- **THEN** 系統回傳 404 Not Found 狀態

#### Scenario: 資源已刪除
- **WHEN** 訪客請求的資源已被刪除
- **THEN** 系統回傳 404 Not Found 狀態
- **AND** 回傳「原始內容已被刪除」訊息

#### Scenario: 取得公開附件
- **WHEN** 訪客請求 `GET /api/public/{token}/attachments/{path}`
- **AND** token 有效
- **THEN** 系統回傳附件內容

---

### Requirement: 公開文件頁面
系統 SHALL 提供獨立的公開文件頁面供訪客瀏覽。

#### Scenario: 短網址路由
- **WHEN** 訪客存取 `/s/{token}`
- **THEN** 系統導向 `public.html?t={token}`

#### Scenario: 公開頁面獨立性
- **WHEN** 公開頁面載入
- **THEN** 頁面使用獨立的 CSS 和 JS
- **AND** 不依賴 index.html 的任何資源

#### Scenario: 知識庫內容渲染
- **WHEN** 公開頁面顯示知識庫
- **THEN** 渲染 Markdown 內容
- **AND** 顯示附件列表（可預覽/下載）
- **AND** 顯示相關知識（若有公開連結可點擊）

#### Scenario: 專案內容渲染
- **WHEN** 公開頁面顯示專案
- **THEN** 渲染專案描述
- **AND** 顯示里程碑時間軸
- **AND** 顯示團隊成員（僅姓名和角色）

#### Scenario: 列印功能
- **WHEN** 訪客點擊列印按鈕
- **THEN** 以優化的列印樣式列印內容

#### Scenario: 錯誤頁面
- **WHEN** 連結無效或資源不存在
- **THEN** 顯示友善的錯誤提示頁面

---

### Requirement: 分享對話框
系統 SHALL 提供分享對話框讓使用者產生公開連結。

#### Scenario: 開啟分享對話框
- **WHEN** 使用者在知識庫或專案頁面點擊「分享」按鈕
- **THEN** 彈出分享對話框

#### Scenario: 選擇有效期
- **WHEN** 分享對話框開啟
- **THEN** 顯示有效期選項：1 小時、24 小時（預設）、7 天、永久

#### Scenario: 產生連結
- **WHEN** 使用者選擇有效期並點擊「產生分享連結」
- **THEN** 呼叫 API 產生連結
- **AND** 顯示產生的連結

#### Scenario: 複製連結
- **WHEN** 使用者點擊複製按鈕
- **THEN** 連結複製到剪貼簿
- **AND** 顯示複製成功提示

#### Scenario: 顯示 QR Code
- **WHEN** 連結產生成功
- **THEN** 顯示連結的 QR Code

#### Scenario: 顯示有效期資訊
- **WHEN** 連結產生成功
- **THEN** 顯示連結有效至的日期時間

---

### Requirement: 分享管理應用程式
系統 SHALL 提供分享管理桌面應用程式。

#### Scenario: 開啟分享管理
- **WHEN** 使用者從 Taskbar 點擊分享管理圖示
- **THEN** 開啟分享管理視窗

#### Scenario: 顯示連結列表
- **WHEN** 分享管理視窗開啟
- **THEN** 顯示使用者的所有分享連結
- **AND** 每個連結顯示：資源名稱、類型、短連結、有效期、存取次數、建立時間

#### Scenario: 過濾連結
- **WHEN** 使用者選擇過濾條件
- **THEN** 可按資源類型（全部/知識庫/專案）過濾
- **AND** 可按狀態（全部/有效/已過期）過濾

#### Scenario: 搜尋連結
- **WHEN** 使用者輸入搜尋關鍵字
- **THEN** 按資源名稱過濾連結

#### Scenario: 複製連結
- **WHEN** 使用者點擊連結的複製按鈕
- **THEN** 複製完整 URL 到剪貼簿

#### Scenario: 刪除連結
- **WHEN** 使用者點擊連結的刪除按鈕
- **THEN** 顯示確認對話框
- **WHEN** 使用者確認
- **THEN** 刪除連結並更新列表

#### Scenario: 狀態顯示
- **WHEN** 顯示連結列表
- **THEN** 有效連結顯示剩餘有效期
- **AND** 已過期連結顯示過期標記

---

### Requirement: Line Bot 分享連結工具
Line Bot MCP Server SHALL 提供分享連結產生工具。

#### Scenario: create_share_link 工具
- **WHEN** AI 呼叫 `create_share_link` 工具
- **AND** 提供 resource_type、resource_id、expires_in 參數
- **THEN** 系統產生公開連結
- **AND** 回傳完整 URL

#### Scenario: 預設有效期
- **WHEN** AI 呼叫 `create_share_link` 且未指定 expires_in
- **THEN** 預設使用 24 小時有效期

#### Scenario: AI 使用時機
- **WHEN** 用戶在 Line Bot 對話中要求分享連結
- **OR** AI 判斷內容太長不適合在對話中顯示
- **THEN** AI 使用 `create_share_link` 工具產生連結

---

### Requirement: Token 產生
系統 SHALL 使用安全的方式產生分享 token。

#### Scenario: Token 格式
- **WHEN** 系統產生 token
- **THEN** token 為 6 字元
- **AND** 包含 a-z、A-Z、0-9 字元

#### Scenario: Token 唯一性
- **WHEN** 系統產生 token
- **AND** token 已存在於資料庫
- **THEN** 重新產生新的 token

#### Scenario: 加密安全
- **WHEN** 系統產生 token
- **THEN** 使用 `secrets` 模組產生加密安全的隨機值

---

### Requirement: 有效期管理
系統 SHALL 支援多種有效期選項。

#### Scenario: 1 小時有效期
- **WHEN** 使用者選擇 1 小時有效期
- **THEN** expires_at 設為當前時間 + 1 小時

#### Scenario: 24 小時有效期
- **WHEN** 使用者選擇 24 小時有效期
- **THEN** expires_at 設為當前時間 + 24 小時

#### Scenario: 7 天有效期
- **WHEN** 使用者選擇 7 天有效期
- **THEN** expires_at 設為當前時間 + 7 天

#### Scenario: 永久有效
- **WHEN** 使用者選擇永久有效
- **THEN** expires_at 設為 NULL
- **AND** 連結除非手動撤銷否則永不過期
