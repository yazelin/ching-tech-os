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