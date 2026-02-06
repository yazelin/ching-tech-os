
# 專案開發規則

## 語言
- 使用繁體中文回應
- 程式碼註解使用繁體中文

## 版本管理

版本號遵循 [Semantic Versioning](https://semver.org/)：`MAJOR.MINOR.PATCH`

### 版本號位置（需同步更新）
更新版本時，必須同時修改以下三個檔案：
- `backend/pyproject.toml` → `version = "x.x.x"`
- `backend/src/ching_tech_os/__init__.py` → `__version__ = "x.x.x"`
- `backend/src/ching_tech_os/main.py` → FastAPI `version="x.x.x"`

### 何時更新版本
- **MAJOR (x.0.0)**：破壞性變更（API 不相容、資料庫 schema 大改）
- **MINOR (0.x.0)**：新功能、重大整合（向下相容）
- **PATCH (0.0.x)**：Bug 修復、小改動、文件更新

### 版本更新指令
當用戶說「bump version」、「更新版本」或完成重大功能時，主動詢問是否需要更新版本號。

## 資料庫
- 資料庫 schema 變更必須使用 Alembic migration
- Migration 檔案放在 `backend/migrations/versions/`
- 檔案命名格式：`00X_description.py`
- `docker/init.sql` 已停用，所有表格由 Alembic migration 管理
- 執行 migration：`cd backend && uv run alembic upgrade head`
- 直接查詢資料庫：`docker exec ching-tech-os-db psql -U ching_tech -d ching_tech_os -c "SQL語句"`

### AI Logs 查詢
AI 對話記錄儲存在 `ai_logs` 表格（分區表）。常用查詢：

```bash
# 查詢最近 5 筆 AI logs（基本資訊）
docker exec ching-tech-os-db psql -U ching_tech -d ching_tech_os -c "SELECT id, context_type, model, success, duration_ms, created_at FROM ai_logs ORDER BY created_at DESC LIMIT 5"

# 查詢最近一筆的完整回應（raw_response 欄位）
docker exec ching-tech-os-db psql -U ching_tech -d ching_tech_os -c "SELECT raw_response FROM ai_logs ORDER BY created_at DESC LIMIT 1"

# 查詢失敗的請求
docker exec ching-tech-os-db psql -U ching_tech -d ching_tech_os -c "SELECT id, error_message, created_at FROM ai_logs WHERE success = false ORDER BY created_at DESC LIMIT 5"

# 查詢特定 context（如 Line 群組）
docker exec ching-tech-os-db psql -U ching_tech -d ching_tech_os -c "SELECT * FROM ai_logs WHERE context_type = 'line_group' ORDER BY created_at DESC LIMIT 5"
```

**重要欄位**：
- `raw_response`: AI 原始回應（注意：不是 `response_text`）
- `parsed_response`: 解析後的 JSON 結構
- `input_prompt`: 輸入的 prompt
- `context_type`: 來源類型（line_group, line_user, web 等）
- `allowed_tools`: 允許使用的工具列表

## 後端開發
- 使用 FastAPI + asyncpg
- Pydantic 資料模型放在 `models/` 目錄
- 業務邏輯放在 `services/` 目錄
- API 路由放在 `api/` 目錄
- 新增路由後記得在 `main.py` 註冊

### 服務日誌
後端以 systemd 服務運行，查看日誌使用：

```bash
# 查看最近 50 行日誌
journalctl -u ching-tech-os -n 50 --no-pager

# 即時追蹤日誌
journalctl -u ching-tech-os -f

# 查看特定時間範圍
journalctl -u ching-tech-os --since "10 minutes ago"

# 過濾特定關鍵字
journalctl -u ching-tech-os -n 100 --no-pager | grep -i "error"
```

## MCP 工具開發
MCP 工具定義在 `services/mcp_server.py`。

**重要**：MCP Server 是獨立執行的，不會經過 FastAPI 的啟動流程，因此：
- 需要資料庫操作時，**必須**先呼叫 `await ensure_db_connection()` 確保連線
- 參考現有的 `add_note`、`search_knowledge` 等工具的寫法

```python
@mcp.tool()
async def my_tool(param: str) -> str:
    await ensure_db_connection()  # 必須！確保資料庫連線
    # ... 資料庫操作 ...
```

**Prompt 更新**：新增 MCP 工具後，需要同步更新：
1. `bot/agents.py`（或 `linebot_agents.py`）- 程式碼中的 prompt 定義
2. 建立新的 migration 檔案更新資料庫中的 prompt
3. 執行 `uv run alembic upgrade head` 套用變更

## 前端開發
- 使用原生 JavaScript（無框架）
- 模組使用 IIFE 模式
- CSS/JS 檔案需在 `index.html` **和** `login.html` 引入（兩個頁面都需要）
- 桌面應用程式需在 `desktop.js` 的 `applications` 和 `openApp` 中註冊
- **不要**在 JS 或 CSS 檔案路徑後加 `?v=` 版本號（如 `script.js?v=123`），nginx 已設定正確的快取策略

### 圖示使用規則（重要）
**`getIcon()` 必須包在 `<span class="icon">` 裡面**，否則 SVG 大小和對齊會錯誤。

```javascript
// ❌ 錯誤：直接使用 getIcon()
`${getIcon('shield-edit')} 設定權限`

// ✅ 正確：包在 span.icon 裡面
`<span class="icon">${getIcon('shield-edit')}</span> 設定權限`
```

如果需要添加新圖示，在 `frontend/js/icons.js` 的 `Icons` 物件中新增 SVG。
圖示來源：[Material Design Icons](https://pictogrammers.com/library/mdi/)

## 子路徑部署（/ctos）注意事項

本專案支援部署在子路徑下（如 `https://ching-tech.ddns.net/ctos/`），由 `js/config.js` 統一處理。

### 運作原理
```
前端 JS           →  瀏覽器發送             →  nginx 代理        →  後端收到
/api/auth/login   →  /ctos/api/auth/login   →  去掉 /ctos/       →  /api/auth/login
```

- `config.js` 自動檢測路徑並設定 `window.API_BASE`
- `config.js` 覆寫 `fetch()`，自動為 `/api/` 開頭的請求加上 base path
- 後端程式碼**不需要任何修改**

### 需要手動處理的情況

**`fetch()` 呼叫**：自動處理，不需修改 ✅

**HTML 標籤的 `href` / `src` 屬性**：需要手動加 `API_BASE` ⚠️
```javascript
// ❌ 錯誤：不會被 config.js 攔截
`<a href="/api/files/${id}/download">下載</a>`
`<img src="/api/files/${id}/preview">`

// ✅ 正確：手動加上 API_BASE
`<a href="${window.API_BASE || ''}/api/files/${id}/download">下載</a>`
`<img src="${window.API_BASE || ''}/api/files/${id}/preview">`
```

**Socket.IO**：需要單獨處理（見 `socket-client.js`）
```javascript
const basePath = window.API_BASE || '';
const socketPath = basePath ? `${basePath}/socket.io/` : '/socket.io/';
socket = io(BACKEND_URL, { path: socketPath, ... });
```

**`window.open()`**：需要手動加 `API_BASE` ⚠️
```javascript
// ❌ 錯誤：直接使用 /api/... 路徑
window.open(`${API_BASE}/${id}/download`, '_blank');

// ✅ 正確：加上 window.API_BASE
const basePath = window.API_BASE || '';
window.open(`${basePath}${API_BASE}/${id}/download`, '_blank');
```

**`ImageViewerModule` / `TextViewerModule`**：自動處理，不需修改 ✅
```javascript
// 這些 viewer 會自動加上 base path，傳入 /api/... 開頭的路徑即可
ImageViewerModule.open(`/api/knowledge/attachments/${path}`);
TextViewerModule.open(`/api/knowledge/assets/${path}`, filename);
```

### 檢查清單
新增前端功能時，確認以下項目：
- [ ] 新的 JS 檔案已加入 `index.html` 和 `login.html`
- [ ] `<a href="/api/...">` 已加上 `${window.API_BASE || ''}`
- [ ] `<img src="/api/...">` 已加上 `${window.API_BASE || ''}`
- [ ] `window.open('/api/...')` 已加上 `${window.API_BASE || ''}`
- [ ] 其他 HTML 屬性中的 `/api/` 路徑已處理

## CSS 樣式注意事項

### CSS 變數命名規則（重要）
**撰寫 CSS 前，必須先查看 `frontend/css/main.css` 中的變數定義**，使用正確的變數名稱。

#### 命名慣例
- **文字顏色**：`--text-*`（如 `--text-primary`、`--text-secondary`）
- **背景顏色**：`--bg-*`（如 `--bg-surface`、`--bg-overlay`）
- **語義化顏色**：`--color-*`（如 `--color-primary`、`--color-success`）

常用變數對照：
| 用途 | 正確變數名稱 |
|------|-------------|
| 主要文字 | `--text-primary` |
| 次要文字 | `--text-secondary` |
| 靜音文字 | `--text-muted` |
| 主要顏色 | `--color-primary` |
| 主要顏色 hover | `--color-primary-hover` |
| 強調顏色 | `--color-accent` |
| 成功 | `--color-success` |
| 警告 | `--color-warning` |
| 錯誤 | `--color-error` |
| 背景 | `--color-background` |
| 表面背景 | `--bg-surface` |
| 深色表面 | `--bg-surface-dark` |
| 更深表面 | `--bg-surface-darker` |
| 遮罩 | `--bg-overlay-dark` |
| 邊框（輕） | `--border-light` |
| 邊框（中） | `--border-medium` |
| 邊框（強） | `--border-strong` |
| Modal 背景 | `--modal-bg` |
| Modal 邊框 | `--modal-border` |

**禁止**：
- 不要使用錯誤的變數名稱（如 `--color-text-primary`，應為 `--text-primary`）
- 不要硬編碼顏色值（如 `#1e1e2e`、`#4a9eff`）
- 不要使用 fallback 值（如 `var(--color-error, #e53935)`）

### 下拉選單（Select/Dropdown）樣式
**重要**：所有下拉選單必須同時為 `<select>` 和 `<option>` 元素定義樣式。
瀏覽器預設的 `<option>` 背景為白色，在深色主題下會造成顏色不協調。

範例：
```css
.xxx-filter-select {
  background: var(--bg-surface);
  color: var(--text-primary);
}

/* 重要：必須為 option 元素定義背景和文字顏色 */
.xxx-filter-select option {
  background-color: var(--color-background);
  color: var(--text-primary);
}
```

### 模態框（Modal）遮罩
- 模態框背景遮罩使用 `var(--bg-overlay-dark)` 變數
- 模態框內容區塊使用 `var(--modal-bg)` 變數
- 所有 overlay 類別應使用 CSS 變數，避免硬編碼 rgba 值

## 文件規範

### 文件架構
- `README.md` - 專案概覽、快速開始（保持簡潔）
- `docs/` - 所有詳細技術文件
- `openspec/` - 規格與變更管理

### 文件放置原則
- 詳細的技術設計文件放在 `docs/` 目錄
- **不要**在子目錄（如 `backend/`、`frontend/`）建立 README
- 功能規格使用 openspec 管理（`openspec/specs/`）

### docs/ 目錄結構
```
docs/
├── ai-agent-design.md       # AI Agent 架構設計
├── ai-management.md         # AI 管理系統
├── backend.md               # 後端開發指南、API 參考
├── database-design.md       # 資料庫設計
├── design-system.md         # CSS 設計系統
├── docker.md                # Docker 服務設定
├── file-manager.md          # 檔案管理器設計
├── frontend.md              # 前端開發指南
├── linebot.md               # Line Bot 整合
├── mcp-server.md            # MCP Server（AI 工具）
├── realtime.md              # Socket.IO 即時通訊
├── security.md              # 認證與安全
├── smb-nas-architecture.md  # SMB/NAS 架構
└── telegram-bot.md          # Telegram Bot 整合
```

### 文件更新時機
- 新增重大功能後更新 `README.md` 功能總覽
- 技術設計變更後更新對應的 `docs/*.md`
- API 變更後更新 `docs/backend.md`

## GitHub CLI 注意事項

### Projects (classic) 已棄用
`gh pr view` 等指令可能因 GitHub Projects (classic) 棄用而報錯：
```
GraphQL: Projects (classic) is being deprecated in favor of the new Projects experience
```
**解法**：加上 `--json` 參數指定需要的欄位，避免查詢已棄用的 projectCards：
```bash
# ❌ 會報錯
gh pr view 24

# ✅ 正確：指定欄位
gh pr view 24 --json title,body,state,url,reviews,comments
```
