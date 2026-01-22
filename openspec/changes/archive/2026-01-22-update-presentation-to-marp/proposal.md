# Change: 統一簡報生成功能使用 Marp

## Why

目前簡報生成功能有兩套實作並存：
- MCP 工具使用 Marp（輸出 HTML/PDF）
- REST API 使用 python-pptx（輸出 .pptx）

這造成維護負擔，且 PowerPoint 版本在跨平台相容性上有問題（字型、版面）。統一使用 Marp 可簡化程式碼並提供更一致的輸出品質。

## What Changes

- **MODIFIED** `generate_presentation` MCP 工具 spec：從 PowerPoint 改為 Marp（HTML/PDF）
- **MODIFIED** REST API `/api/presentation/generate`：改用 `generate_html_presentation` 函數
- **MODIFIED** API 參數：`style` 改為 `theme`，新增 `output_format` 參數
- **REMOVED** 舊的 PowerPoint 相關參數：`design_json`、`designer_request`（Marp 使用內建主題）

## Impact

- Affected specs: `mcp-tools`
- Affected code:
  - `backend/src/ching_tech_os/api/presentation.py`（API 端點）
  - `backend/src/ching_tech_os/services/presentation.py`（可移除 PowerPoint 相關程式碼）
- **BREAKING**: API 參數名稱變更（`style` → `theme`），輸出格式從 `.pptx` 改為 `.html`/`.pdf`
