<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# 專案開發規則

## 語言
- 使用繁體中文回應
- 程式碼註解使用繁體中文

## 資料庫
- 資料庫 schema 變更必須使用 Alembic migration
- Migration 檔案放在 `backend/migrations/versions/`
- 檔案命名格式：`00X_description.py`
- 不要直接修改 `docker/init.sql`（僅用於初始化基本表）
- 執行 migration：`cd backend && uv run alembic upgrade head`

## 後端開發
- 使用 FastAPI + asyncpg
- Pydantic 資料模型放在 `models/` 目錄
- 業務邏輯放在 `services/` 目錄
- API 路由放在 `api/` 目錄
- 新增路由後記得在 `main.py` 註冊

## 前端開發
- 使用原生 JavaScript（無框架）
- 模組使用 IIFE 模式
- CSS/JS 檔案需在 `index.html` **和** `login.html` 引入（兩個頁面都需要）
- 桌面應用程式需在 `desktop.js` 的 `applications` 和 `openApp` 中註冊

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

### 檢查清單
新增前端功能時，確認以下項目：
- [ ] 新的 JS 檔案已加入 `index.html` 和 `login.html`
- [ ] `<a href="/api/...">` 已加上 `${window.API_BASE || ''}`
- [ ] `<img src="/api/...">` 已加上 `${window.API_BASE || ''}`
- [ ] 其他 HTML 屬性中的 `/api/` 路徑已處理

## CSS 樣式注意事項

### 下拉選單（Select/Dropdown）樣式
**重要**：所有下拉選單必須同時為 `<select>` 和 `<option>` 元素定義樣式。
瀏覽器預設的 `<option>` 背景為白色，在深色主題下會造成顏色不協調。

範例：
```css
.xxx-filter-select {
  background: var(--bg-surface);
  color: var(--text-primary);
  /* ... 其他樣式 */
}

/* 重要：必須為 option 元素定義背景和文字顏色 */
.xxx-filter-select option {
  background-color: var(--color-background);
  color: var(--color-text-primary);
}
```

### 模態框（Modal）遮罩
- 模態框背景遮罩使用 `var(--bg-overlay-dark)` 變數
- 模態框內容區塊需使用不透明的背景色（如 `#1e1e2e`），不要使用半透明的 `var(--bg-surface)`
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
├── backend.md          # 後端開發指南、API 參考
├── database-design.md  # 資料庫設計
├── ai-agent-design.md  # AI Agent 架構設計
├── smb-nas-architecture.md  # SMB/NAS 架構
└── file-manager.md     # 檔案管理器設計
```

### 文件更新時機
- 新增重大功能後更新 `README.md` 功能總覽
- 技術設計變更後更新對應的 `docs/*.md`
- API 變更後更新 `docs/backend.md`