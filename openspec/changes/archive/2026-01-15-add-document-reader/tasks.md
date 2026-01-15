# Tasks: add-document-reader

## Phase 1: 基礎建設

### 1.1 新增 Python 套件依賴
- [x] 在 `backend/pyproject.toml` 新增套件：
  - `python-docx>=1.1.0` (Word)
  - `openpyxl>=3.1.0` (Excel)
  - `python-pptx>=0.6.0` (PowerPoint)
  - `PyMuPDF>=1.24.0` (PDF)
- [x] 執行 `uv sync` 確認安裝成功
- [x] 驗證：可在 Python 中 import 各套件

### 1.2 建立 Document Reader Service
- [x] 建立 `backend/src/ching_tech_os/services/document_reader.py`
- [x] 實作 `DocumentContent` dataclass
- [x] 實作 `extract_text(file_path: str) -> DocumentContent` 主函式
- [x] 實作各格式解析器：
  - [x] `_extract_docx()` - Word 文件
  - [x] `_extract_xlsx()` - Excel 試算表
  - [x] `_extract_pptx()` - PowerPoint 簡報
  - [x] `_extract_pdf()` - PDF 文件
- [x] 實作錯誤處理（加密、損壞、格式不支援）
- [x] 實作大小限制和截斷邏輯
- [x] 驗證：可解析測試文件並輸出純文字

## Phase 2: Line Bot 整合

### 2.1 擴充可讀取檔案類型
- [x] 修改 `linebot.py` 的 `READABLE_FILE_EXTENSIONS`
  - 新增 `.docx`, `.xlsx`, `.pptx`
- [x] 新增 `LEGACY_OFFICE_EXTENSIONS` 和 `DOCUMENT_EXTENSIONS` 常數
- [x] 新增 `is_legacy_office_file()` 和 `is_document_file()` 函式
- [ ] 驗證：上傳 docx 檔案不再顯示「無法讀取此類型」（待用戶測試）

### 2.2 整合文件解析到 AI 流程
- [x] 修改 `linebot.py` 的 `ensure_temp_file()` 函式
- [x] Office 文件先解析成純文字再存入暫存
- [x] PDF 文件解析文字後存入暫存
- [x] 修改 `linebot_ai.py` 新增舊版格式提示
- [ ] 驗證：AI 可讀取 docx/xlsx/pptx/pdf 的文字內容（待用戶測試）

### 2.3 更新 Line Bot Prompt
- [x] 在 `linebot_ai.py` 的 `build_system_prompt()` 中更新檔案類型說明
- [x] 說明新支援的檔案類型（docx, xlsx, pptx）
- [x] 說明舊版格式不支援（.doc, .xls, .ppt）
- [ ] 驗證：AI 知道可以讀取 Office 文件（待用戶測試）

## Phase 3: MCP 工具

### 3.1 新增 read_document MCP 工具
- [x] 在 `mcp_server.py` 新增 `read_document` 工具
- [x] 支援讀取 NAS 上的文件
- [x] 實作字元數限制（預設 50000）
- [x] 更新 `get_nas_file_info` 回應，加入 `read_document` 可用操作
- [ ] 驗證：AI 可透過 MCP 工具讀取 NAS 文件（待用戶測試）

## Phase 4: 測試與文件

### 4.1 測試
- [ ] 準備各格式測試文件
- [ ] 測試 Line Bot 文件分析功能
- [ ] 測試大檔案處理
- [ ] 測試錯誤情況（加密、損壞）

### 4.2 文件更新
- [x] 更新 `docs/linebot.md` 說明文件讀取功能
- [x] 更新 `docs/mcp-server.md` 說明新工具

---

## 依賴關係

```
1.1 ──► 1.2 ──► 2.1 ──► 2.2 ──► 2.3
                              │
                              └──► 3.1 ──► 4.1 ──► 4.2
```

- Phase 1 為基礎，必須先完成
- Phase 2 為主要功能，依賴 Phase 1
- Phase 3 為延伸功能，可與 Phase 2.3 並行或之後
- Phase 4 為收尾，所有功能完成後進行

## 預估工作量

| Phase | 任務數 | 複雜度 |
|-------|--------|--------|
| 1 | 2 | 中 |
| 2 | 3 | 中 |
| 3 | 1 | 低 |
| 4 | 2 | 低 |

## 驗收標準

1. 用戶傳送 .docx 檔案到 Line Bot，AI 可總結文件內容
2. 用戶傳送 .xlsx 檔案，AI 可讀取試算表資料
3. 用戶傳送 .pptx 檔案，AI 可列出投影片內容
4. 用戶傳送 .pdf 檔案，AI 可提取並分析文字
5. 大檔案（>10MB）顯示適當的錯誤訊息
6. 加密文件顯示需要密碼的提示

## 實作摘要

### 新增檔案
- `backend/src/ching_tech_os/services/document_reader.py` - Document Reader Service

### 修改檔案
- `backend/pyproject.toml` - 新增套件依賴
- `backend/src/ching_tech_os/services/linebot.py` - 擴充檔案類型支援
- `backend/src/ching_tech_os/services/linebot_ai.py` - 更新 prompt 和檔案處理
- `backend/src/ching_tech_os/services/mcp_server.py` - 新增 read_document 工具
