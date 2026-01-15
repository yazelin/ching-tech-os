# Design: add-document-reader

## Overview
本設計說明文件讀取功能的技術架構，包含套件選型、處理流程、以及與現有系統的整合方式。

## Package Selection

### 評估的套件選項

#### All-in-One 方案
| 套件 | 優點 | 缺點 |
|------|------|------|
| [pyxtxt](https://pypi.org/project/pyxtxt/) | 支援多種格式、包含舊版 Office | 較新，社群較小 |
| [textract](https://textract.readthedocs.io/) | 成熟、格式多 | 需要系統相依（antiword, pdftotext） |
| [MagicConvert](https://pypi.org/project/MagicConvert/) | 轉 Markdown、OCR 支援 | 較新 |

#### 專用套件方案
| 格式 | 套件 | 下載量/月 | 維護狀態 |
|------|------|-----------|----------|
| DOCX | [python-docx](https://python-docx.readthedocs.io/) | 8M+ | 活躍 |
| XLSX | [openpyxl](https://openpyxl.readthedocs.io/) | 25M+ | 活躍 |
| PPTX | [python-pptx](https://python-pptx.readthedocs.io/) | 4M+ | 活躍 |
| PDF | [PyMuPDF](https://pymupdf.readthedocs.io/) | 6M+ | 活躍 |

### 決策：採用專用套件組合

**理由**：
1. **穩定性** - 專用套件經過長期測試，處理特定格式更可靠
2. **無系統相依** - 純 Python 實作，Docker 部署簡單
3. **彈性** - 可針對各格式調整輸出方式（如 Excel 表格格式化）
4. **維護性** - 各套件獨立更新，問題隔離

**選定套件**：
```
python-docx>=1.1.0   # Word .docx
openpyxl>=3.1.0      # Excel .xlsx
python-pptx>=0.6.0   # PowerPoint .pptx
PyMuPDF>=1.24.0      # PDF
```

## Architecture

### 元件設計

```
┌─────────────────────────────────────────────────────────────┐
│                    Document Reader Service                   │
│  backend/src/ching_tech_os/services/document_reader.py      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ DocxReader  │  │ XlsxReader  │  │ PptxReader  │         │
│  │ python-docx │  │ openpyxl    │  │ python-pptx │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  ┌─────────────┐                                           │
│  │ PdfReader   │                                           │
│  │ PyMuPDF     │                                           │
│  └─────────────┘                                           │
│                                                             │
│  + extract_text(file_path: str) -> DocumentContent         │
│  + get_supported_extensions() -> set[str]                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌─────────────────┐   ┌──────────────────┐
│  Line Bot AI  │   │   MCP Server    │   │  Knowledge API   │
│ (對話文件分析) │   │ (read_document) │   │ (附件內容查詢)   │
└───────────────┘   └─────────────────┘   └──────────────────┘
```

### 資料結構

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class DocumentContent:
    """文件解析結果"""
    text: str                      # 提取的純文字內容
    format: str                    # 原始格式 (docx, xlsx, pptx, pdf)
    page_count: Optional[int]      # 頁數（PDF）或工作表數（Excel）
    metadata: dict                 # 額外資訊（標題、作者等）
    truncated: bool                # 是否因大小限制而截斷
    error: Optional[str]           # 解析錯誤訊息（部分成功時）
```

### 文字提取策略

#### Word (.docx)
```python
def extract_docx(file_path: str) -> str:
    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs]
    # 也提取表格內容
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text for cell in row.cells)
            paragraphs.append(row_text)
    return "\n".join(paragraphs)
```

#### Excel (.xlsx)
```python
def extract_xlsx(file_path: str) -> str:
    """
    提取所有工作表的內容。
    AI 可讀取完整內容後自行判斷需要哪些資料，
    或詢問用戶想知道哪些工作表/欄位的資訊。
    """
    wb = load_workbook(file_path, data_only=True)
    result = []
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        result.append(f"=== 工作表: {sheet_name} ===")
        for row in sheet.iter_rows(values_only=True):
            # 過濾空行
            if any(cell is not None for cell in row):
                row_text = " | ".join(str(c) if c else "" for c in row)
                result.append(row_text)
    return "\n".join(result)
```

#### PowerPoint (.pptx)
```python
def extract_pptx(file_path: str) -> str:
    prs = Presentation(file_path)
    result = []
    for i, slide in enumerate(prs.slides, 1):
        result.append(f"=== 投影片 {i} ===")
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                result.append(shape.text)
    return "\n".join(result)
```

#### PDF
```python
def extract_pdf(file_path: str) -> str:
    doc = fitz.open(file_path)
    result = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            result.append(text)
    return "\n".join(result)
```

## Integration Points

### 1. Line Bot 檔案處理

修改 `linebot.py` 的 `READABLE_FILE_EXTENSIONS`：

```python
# 現有
READABLE_FILE_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv", ".log",
    ".xml", ".yaml", ".yml", ".pdf",
}

# 新增
READABLE_FILE_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv", ".log",
    ".xml", ".yaml", ".yml", ".pdf",
    ".docx", ".xlsx", ".pptx",  # 新增 Office 格式
    ".xls",  # 舊版 Excel (可選)
}
```

修改 `linebot_ai.py` 的暫存檔準備邏輯：

```python
async def prepare_file_for_ai(nas_path: str, temp_dir: str) -> str:
    """準備檔案供 AI 讀取"""
    ext = Path(nas_path).suffix.lower()

    if ext in {".docx", ".xlsx", ".pptx", ".pdf", ".xls"}:
        # 使用 document_reader 解析
        content = await document_reader.extract_text(nas_path)
        # 寫入純文字暫存檔
        temp_path = f"{temp_dir}/{Path(nas_path).stem}.txt"
        async with aiofiles.open(temp_path, "w") as f:
            await f.write(content.text)
        return temp_path
    else:
        # 原有邏輯：直接複製檔案
        ...
```

### 2. MCP 工具

新增 `read_document` 工具：

```python
@mcp.tool()
async def read_document(
    file_path: str,
    max_chars: int = 50000
) -> str:
    """
    讀取文件內容（支援 Word、Excel、PowerPoint、PDF）

    Args:
        file_path: NAS 檔案路徑
        max_chars: 最大字元數限制，預設 50000
    """
    content = await document_reader.extract_text(file_path)

    if len(content.text) > max_chars:
        return content.text[:max_chars] + f"\n\n[內容已截斷，原文共 {len(content.text)} 字元]"

    return content.text
```

### 3. Line Bot Prompt 更新

更新 AI prompt 說明新支援的檔案類型：

```
支援的檔案類型：
- 純文字：txt, md, json, csv, log, xml, yaml, yml
- Office 文件：docx, xlsx, pptx（自動轉換為純文字）
- PDF 文件：pdf（自動提取文字）

注意：Office 文件會自動轉換為純文字格式，可能遺失格式資訊。
```

## Constraints & Limits

### 檔案大小限制

| 格式 | 最大檔案大小 | 原因 |
|------|-------------|------|
| PDF | 10 MB | 頁數多時解析慢 |
| DOCX | 10 MB | 含嵌入圖片時可能很大 |
| XLSX | 5 MB | 大型試算表解析慢 |
| PPTX | 10 MB | 含嵌入媒體時可能很大 |

### 文字輸出限制

- 最大輸出字元數：100,000 字元
- 超過時截斷並標註
- Excel 會轉出所有工作表，AI 自行判斷或詢問用戶需要哪些資訊

### 不支援的情況

1. **加密文件** - 需要密碼的文件回傳錯誤訊息「此文件有密碼保護，無法讀取」
2. **損壞文件** - 無法解析時回傳錯誤
3. **純圖片 PDF** - 回傳提示「此 PDF 為掃描圖片，建議截圖後上傳讓 AI 讀取」
4. **舊版格式** - .doc, .xls, .ppt 提示用戶轉存為新版格式 (.docx, .xlsx, .pptx)

## Error Handling

```python
class DocumentReadError(Exception):
    """文件讀取錯誤"""
    pass

class PasswordProtectedError(DocumentReadError):
    """文件有密碼保護"""
    pass

class CorruptedFileError(DocumentReadError):
    """文件損壞"""
    pass

class UnsupportedFormatError(DocumentReadError):
    """不支援的格式"""
    pass
```

## Testing Strategy

1. **單元測試** - 各格式解析函式的測試
2. **整合測試** - Line Bot 完整流程測試
3. **測試檔案** - 準備各種格式的測試文件：
   - 基本文件（純文字）
   - 含表格文件
   - 多頁/多工作表文件
   - 大檔案（邊界測試）
   - 損壞/加密檔案

## Migration Notes

1. 新增 Python 套件到 `pyproject.toml`
2. 更新 `READABLE_FILE_EXTENSIONS`
3. 建立 migration 更新 Line Bot prompt
4. 無資料庫 schema 變更
