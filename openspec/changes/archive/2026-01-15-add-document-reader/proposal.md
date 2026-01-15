# Proposal: add-document-reader

## Summary
實作文件讀取功能，讓 Line Bot AI 助手能夠讀取 Word、Excel、PowerPoint、PDF 等文件格式，提取文字內容進行總結或查詢分析。

## Problem Statement
目前 Line Bot 的 `READABLE_FILE_EXTENSIONS` 僅支援純文字格式（txt, md, json, csv, log, xml, yaml, yml）和 PDF。當用戶傳送 Word、Excel、PowerPoint 檔案時，系統會顯示「無法讀取此類型」，無法進行內容分析。

現有限制：
- 無法讀取 `.docx`、`.doc` Word 文件
- 無法讀取 `.xlsx`、`.xls` Excel 試算表
- 無法讀取 `.pptx`、`.ppt` PowerPoint 簡報
- PDF 目前標記為可讀，但實際上 Claude Read 工具無法解析二進位 PDF

## Proposed Solution
使用後端 Python 套件將文件轉換為純文字格式，再提供給 AI 處理。

### 支援格式

| 格式 | 副檔名 | Python 套件 |
|------|--------|------------|
| Word | .docx | python-docx |
| Excel | .xlsx | openpyxl |
| PowerPoint | .pptx | python-pptx |
| PDF | .pdf | PyMuPDF |

> 舊版格式 (.doc, .xls, .ppt) 第一版不支援，上傳時提示用戶轉存為新版格式。

### 整合點

1. **Line Bot 檔案處理** (`linebot.py`, `linebot_ai.py`)
   - 擴充 `READABLE_FILE_EXTENSIONS`
   - 新增文件解析邏輯，將文件轉為純文字暫存

2. **MCP 工具** (`mcp_server.py`)
   - 新增 `read_document` 工具，讓 AI 可讀取 NAS 上的文件

3. **知識庫** (可選延伸)
   - 支援讀取知識庫附件中的文件內容

## Scope
- **包含**：Word (.docx)、Excel (.xlsx)、PowerPoint (.pptx)、PDF 的文字提取
- **包含**：Line Bot 對話中的文件分析
- **包含**：NAS 檔案的文件讀取
- **延後**：舊版格式 (.doc, .xls, .ppt) 支援
- **延後**：OCR 圖片文字辨識
- **延後**：保留格式的轉換（如 Markdown）

## Risks & Mitigations

| 風險 | 影響 | 緩解措施 |
|------|------|---------|
| 大檔案處理緩慢 | 用戶體驗差 | 設定檔案大小上限（10MB），超過提示 |
| 複雜文件解析失敗 | 資訊遺失 | 回報部分成功，顯示可解析的內容 |
| 套件相依性增加 | 部署複雜度 | 選用純 Python 套件，避免系統相依 |

## Decisions (已確認)
1. **舊版格式** - 第一版不支援 .doc, .xls, .ppt，僅支援新版 Office 格式
2. **加密文件** - 不支援，遇到時顯示錯誤提示
3. **Excel 多工作表** - 全部轉出純文字，AI 可讀取完整內容後自行判斷或詢問用戶想知道哪些資訊

## Related Changes
- 無相依變更

## Deliverables
- [ ] design.md - 技術設計文件
- [ ] tasks.md - 實作任務清單
- [ ] specs/document-reader/spec.md - 功能規格
