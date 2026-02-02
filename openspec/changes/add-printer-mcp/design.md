# Design: Add Printer MCP Integration

## 架構決策

### 決策 1：雙層整合架構

**選擇**：同時整合 printer-mcp（Claude Code 用）+ 自建列印工具（Bot 用）

**原因**：
- printer-mcp 作為獨立 MCP Server，Claude Code 可直接呼叫其 `print_file`，路徑由使用者或 AI 提供
- Line/Telegram Bot 的 AI Agent 透過 ching-tech-os MCP Server 的包裝工具列印，自動處理虛擬路徑轉換
- 兩層各司其職，不重複造輪子

**架構圖**：
```
┌─────────────────────────────────────────────────┐
│ Claude Code（開發者使用）                         │
│   → 直接呼叫 printer-mcp 的 print_file          │
│   → 路徑：使用者提供絕對路徑                      │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Line / Telegram Bot（AI Agent）                  │
│   → 呼叫 ching-tech-os MCP 的 print_file        │
│   → 路徑：虛擬路徑 → PathManager 轉換 → CUPS lp │
└─────────────────────────────────────────────────┘
```

### 決策 2：ching-tech-os MCP 工具直接呼叫 CUPS

**選擇**：直接使用 `subprocess` 呼叫 CUPS `lp` / `lpstat` 指令

**原因**：
- printer-mcp 本身就是 CUPS 的薄封裝，邏輯簡單
- 避免 MCP Server 之間互相呼叫的複雜度
- `lp` 指令穩定且廣泛支援

**替代方案（不採用）**：
- ❌ 從 ching-tech-os MCP 呼叫 printer-mcp：MCP-to-MCP 通訊複雜
- ❌ 使用 pycups Python 綁定：額外依賴，CUPS CLI 已足夠

### 決策 3：檔案格式處理策略

**直接列印**：PDF、純文字、圖片（CUPS 原生支援）

**自動轉換後列印**：Office 文件（.docx, .xlsx, .pptx, .doc, .xls, .ppt, .odt, .ods, .odp）
- 伺服器已安裝 LibreOffice 24.2
- 使用 `libreoffice --headless --convert-to pdf --outdir {tmp_dir} {file}` 轉換
- 轉換後的 PDF 暫存於 `/tmp/ctos/print/`，列印完成後清除

## 工具設計

### `print_file` 工具

```python
@mcp.tool()
async def print_file(
    file_path: str,          # 虛擬路徑或絕對路徑
    printer: str = "",       # 印表機名稱，空字串=預設
    copies: int = 1,         # 份數
    page_size: str = "A4",   # 紙張大小
    orientation: str = "portrait",  # 方向
) -> str:
    """列印檔案到指定印表機"""
```

**路徑解析流程**：
1. 若以 `ctos://`、`shared://`、`nas://` 開頭 → PathManager 轉換
2. 若以 `/` 開頭 → 視為絕對路徑，驗證在允許範圍內
3. 驗證檔案存在且副檔名受支援
4. 呼叫 `lp -d {printer} -n {copies} -o media={page_size} -o {orientation} {path}`

**安全限制**：
- 只允許列印 `/mnt/nas/` 和 `/tmp/ctos/` 下的檔案
- 禁止路徑穿越（`..`）

### `list_printers` 工具

```python
@mcp.tool()
async def list_printers() -> str:
    """列出所有可用的印表機及其狀態"""
```

- 呼叫 `lpstat -a` 取得印表機清單
- 呼叫 `lpstat -d` 取得預設印表機

## 權限設計

在 `TOOL_APP_MAPPING` 新增：
```python
"print_file": "printer",
"list_printers": "printer",
```

在 `APP_DISPLAY_NAMES` 新增：
```python
"printer": "列印",
```

## Prompt 更新

AI Agent prompt 需新增列印功能說明：
- 告知有 `print_file` 和 `list_printers` 工具
- 說明支援的檔案格式
- 說明如何取得檔案路徑（搭配 `search_nas_files`、`get_knowledge_attachments` 等工具）
