## Why

LineBot 目前仰賴 Claude CLI 內建的 WebFetch 擷取網頁內容，但遇到需要 JavaScript 渲染的 SPA 網站（如 Next.js、React）時只能拿到空殼（`Loading...`），無法取得實際內容。需要一個基於 Playwright 的 MCP 工具作為補充，讓 AI 在 WebFetch 失效時有能力瀏覽 JS 渲染的網頁。

## What Changes

- 新增 `browse_webpage` MCP 工具，使用 Playwright Chromium headless 開啟網頁並回傳 accessibility snapshot
- 工具參數：`url`（必須 HTTPS）、`max_length`（預設 8,000 字）、`timeout`（預設 30 秒）
- 在 bot agent prompt 加入工具使用指引，引導 AI 在 WebFetch 無法處理 SPA 時選用此工具
- 瀏覽器每次呼叫新開新關，不常駐

## Capabilities

### New Capabilities

- `browse-webpage`: 基於 Playwright 的網頁瀏覽 MCP 工具，單頁擷取、accessibility snapshot 回傳、可設定內容長度上限

### Modified Capabilities

- `mcp-tools`: 新增 `web_tools` 模組載入與 prompt 整合

## Impact

- **新增檔案**：`backend/src/ching_tech_os/services/mcp/web_tools.py`
- **修改檔案**：
  - `backend/src/ching_tech_os/services/mcp/__init__.py`（import 新模組）
  - `backend/src/ching_tech_os/services/bot/agents.py`（BASE_TOOLS_PROMPT 加入工具說明）
- **依賴**：`playwright`（已在 pyproject.toml 中）
- **環境需求**：部署環境需安裝 Chromium binary（`playwright install chromium`），AppArmor 需允許 unprivileged user namespaces
- **不影響**：資料庫、前端、`.mcp.json`、權限系統
