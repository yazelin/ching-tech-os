# Tasks: Line Bot PDF 轉圖片功能

## 1. PDF 轉換函式實作

- [x] 1.1 在 `document_reader.py` 新增 `convert_pdf_to_images()` 函式
- [x] 1.2 使用現有 PyMuPDF 進行轉換
- [x] 1.3 支援參數：dpi、output_format、max_pages
- [x] 1.4 複用現有錯誤處理（PasswordProtectedError 等）

## 2. MCP 工具實作

- [x] 2.1 在 `mcp_server.py` 新增 `convert_pdf_to_images` MCP 工具
- [x] 2.2 建立輸出目錄 `/mnt/nas/ctos/linebot/files/pdf-converted/{date}/{uuid}/`
- [x] 2.3 呼叫 `document_reader.convert_pdf_to_images()` 執行轉換
- [x] 2.4 回傳轉換結果和圖片路徑列表

## 3. Line Bot 整合

- [x] 3.1 確認 PDF 上傳後對話歷史顯示格式
- [x] 3.2 AI 可識別用戶的轉換請求並呼叫 MCP 工具
- [x] 3.3 轉換完成後搭配 `prepare_file_message` 發送圖片

## 4. Prompt 更新

- [x] 4.1 更新 `linebot-personal` 和 `linebot-group` 的 system prompt
- [x] 4.2 說明 `convert_pdf_to_images` 工具的使用方式
- [x] 4.3 建立 Alembic migration 更新資料庫中的 prompt

## 5. 專案附件支援

- [x] 5.1 修改 `get_project_attachments` 回傳 `storage_path` 欄位
- [x] 5.2 測試專案附件 PDF 轉換

## 6. Bug 修復

- [x] 6.1 修復 PDF 上傳後只顯示 .txt 路徑的問題
- [x] 6.2 同時保留 PDF 原始檔和 .txt 文字版
- [x] 6.3 對話歷史顯示格式改為 `[上傳 PDF: xxx.pdf（文字版: xxx.txt）]`
- [x] 6.4 修復 `read_document` 不支援 `nas://` 路徑格式的問題

## 7. 測試與驗證

- [x] 7.1 測試上傳 PDF 後請求轉換
- [x] 7.2 測試上傳 PDF 後讀取文字內容
- [x] 7.3 測試指定 NAS 路徑的 PDF 轉換
- [x] 7.4 測試專案附件 PDF 轉換
- [x] 7.5 測試多頁 PDF 轉換
- [x] 7.6 測試轉換後圖片發送到 Line
