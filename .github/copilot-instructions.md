# ChingTech OS Copilot 指引

## Build / Test / Lint 指令

### 安裝依賴
- 後端：`cd backend && uv sync`
- 根目錄前端建置工具（esbuild）：`npm ci`
- `frontend/` 內 Vite 工具鏈：`cd frontend && npm ci`

### 建置
- 主線建置（CI 同步使用）：`npm run build`
  - 會執行 `scripts/build-frontend.mjs`
  - 輸出到 `frontend/dist/`
- Vite 建置（模組入口）：`cd frontend && npm run build`

### 測試
- 全量後端測試：`cd backend && uv run pytest`
- 單一測試檔：`cd backend && uv run pytest tests/test_bot_api_routes.py -v`
- 單一測試案例：`cd backend && uv run pytest tests/test_bot_api_routes.py::test_bot_groups_returns_200 -v`
- 依關鍵字跑測試：`cd backend && uv run pytest -k permissions -v`
- 前端目前沒有自動化單元/整合測試。

### Lint
- 專案目前未定義獨立 lint script（`package.json`、`frontend/package.json`、`backend/pyproject.toml` 皆無）。
- 目前品質檢查主要在 `.github/workflows/lighthouse.yml`（建置後執行 Lighthouse 門檻檢查）。

## 高層架構（Big Picture）

- 單一 repo，三個主要層次：
  1. **Frontend (`frontend/`)**：Vanilla JS + IIFE 模組，桌面式 Web UI。
  2. **Backend (`backend/src/ching_tech_os/`)**：FastAPI + Socket.IO + DB/NAS 服務。
  3. **Bot / MCP 層**：Line/Telegram Bot 與 FastMCP 工具，共用同一組業務能力。

- 後端組裝入口：`backend/src/ching_tech_os/main.py`
  - 建立 FastAPI app，並包成 `socket_app = socketio.ASGIApp(sio, app)`。
  - 註冊 REST routers（auth、knowledge、ai、bot、files、share、skills...）。
  - 註冊 Socket.IO 事件（AI 串流、Terminal、訊息中心）。
  - 掛載前端靜態檔與本機資料資產路徑。

- 即時通訊路徑：
  - 前端連線：`frontend/js/socket-client.js`
  - 後端事件：`api/ai.py`、`api/terminal.py`、`api/message_events.py`

- AI 流程：
  - REST：`api/ai_router.py`、`api/ai_management.py`
  - Socket：`api/ai.py`
  - 核心服務：`services/claude_agent.py`、`services/ai_chat.py`

- MCP 流程：
  - 相容入口：`services/mcp_server.py`
  - 實作與註冊：`services/mcp/`（`__init__.py` 透過 import 子模組觸發 `@mcp.tool()` 註冊）
  - CLI 入口：`python -m ching_tech_os.mcp_cli`
  - Bot 與 MCP client 共用同一套工具定義。

- 資料邊界：
  - PostgreSQL + Alembic migration
  - NAS/SMB 檔案存取（檔案管理與 Bot 附件流程）
  - 啟動時建立知識庫/專案等本機資產目錄

## 關鍵慣例（專案特有）

### 語言
- 回覆與程式碼註解使用繁體中文。

### 前端
- 維持 Vanilla JS IIFE 模式（不引入框架）。
- 新增共享資源時，通常要同步確認 `index.html` 與 `login.html` 的載入。
- 新增桌面 App 需更新 `frontend/js/desktop.js`（`applications` 與開啟/懶載入映射）。
- `getIcon()` 必須包在 `<span class="icon">...</span>` 內。
- JS/CSS 路徑不要加 `?v=...`。

### 子路徑部署（`/ctos`、`/trial`、`/dev`）
- `frontend/js/config.js` 會自動處理 `fetch('/api/...')` 與 Socket.IO path。
- 但 HTML 屬性與 `window.open()` 仍要手動加 `${window.API_BASE || ''}`：
  - `<a href="/api/...">`
  - `<img src="/api/...">`
  - `window.open('/api/...')`

### CSS
- 優先使用 `frontend/css/main.css` 既有變數（`--text-*`、`--bg-*`、`--color-*`），避免硬編碼顏色。
- 下拉選單需同時定義 `select` 與 `option` 樣式（避免深色主題顯示異常）。

### 後端
- 新增 API router 後，必須在 `backend/src/ching_tech_os/main.py` 註冊。
- 資料庫 schema 變更只能走 Alembic（`backend/migrations/versions/`）。

### MCP
- 新工具應放在 `backend/src/ching_tech_os/services/mcp/`（`services/mcp_server.py` 僅相容層）。
- MCP 工具若要查 DB，先呼叫 `await ensure_db_connection()`。
- 有權限需求的工具，使用 `check_mcp_tool_permission(...)`。
- MCP 連線設定在 `.mcp.json`（範例在 `.mcp.json.example`）；目前包含 `ching-tech-os`、`erpnext`、`nanobanana`、`playwright`。

### 版本號
- 採 SemVer，且以下三處需同步：
  - `backend/pyproject.toml`
  - `backend/src/ching_tech_os/__init__.py`
  - `backend/src/ching_tech_os/main.py`

## 主要參考文件
- `README.md`
- `CLAUDE.md`
- `AGENTS.md`
- `docs/backend.md`
- `docs/frontend.md`
- `docs/realtime.md`
- `docs/ai-agent-design.md`
- `docs/mcp-server.md`
