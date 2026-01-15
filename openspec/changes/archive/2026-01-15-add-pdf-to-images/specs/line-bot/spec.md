## ADDED Requirements

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
