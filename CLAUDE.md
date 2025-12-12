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
- CSS/JS 檔案需在 `index.html` 引入
- 桌面應用程式需在 `desktop.js` 的 `applications` 和 `openApp` 中註冊

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