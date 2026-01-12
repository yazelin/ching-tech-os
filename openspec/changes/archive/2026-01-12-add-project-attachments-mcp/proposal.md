# Proposal: 專案附件與連結 MCP 工具

## Why

目前專案管理中的附件和連結功能只有網頁介面可以操作。為了讓 AI 助手能夠幫助用戶管理專案資料，需要新增 MCP 工具讓 AI 可以：

1. 為專案新增連結（如相關文件 URL、參考資料等）
2. 為專案新增附件（從 Line 對話中上傳的檔案或 NAS 上的現有檔案）
3. 查詢和管理專案的附件與連結

## What Changes

### 新增 MCP 工具

**連結管理**（簡單，直接 CRUD）：
- `add_project_link`: 新增專案連結
- `update_project_link`: 更新連結資訊
- `delete_project_link`: 刪除連結
- `get_project_links`: 查詢專案連結

**附件管理**（從現有檔案添加引用）：
- `add_project_attachment`: 從 NAS 路徑添加附件到專案
- `update_project_attachment`: 更新附件描述
- `delete_project_attachment`: 刪除附件
- `get_project_attachments`: 查詢專案附件

### AI 附件處理方式

AI 無法直接「上傳」檔案，但可以處理以下情況：

1. **Line 對話中的檔案**：
   - 用戶在 Line 發送的圖片/檔案會自動存到 NAS
   - AI 用 `get_message_attachments` 查詢這些檔案的 NAS 路徑
   - 然後用 `add_project_attachment` 將檔案添加到專案

2. **NAS 上的現有檔案**：
   - AI 用 `search_nas_files` 搜尋 NAS 檔案
   - 然後用 `add_project_attachment` 將檔案添加到專案

### Prompt 更新

更新 Line Bot prompts 說明新工具的使用方式。

### 分享連結支援

擴充 `create_share_link` MCP 工具支援 `project_attachment` 資源類型：
- AI 可為專案附件建立公開分享連結
- 公開頁面能正確顯示附件資訊和下載按鈕
- 支援從不同 NAS 路徑格式讀取附件（Line Bot 上傳、專案上傳）

## Scope

- 後端：MCP 工具、服務函數、分享連結 API
- 資料庫：無變更（使用現有的 project_attachments 和 project_links 表）
- 前端：公開分享頁面新增 project_attachment 支援
