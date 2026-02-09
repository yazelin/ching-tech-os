# Spec: Skill ENV 管理

## Purpose
讓管理員在 UI 設定 skill 所需的環境變數（如 API Keys），支援加密儲存與 write-only 安全模式。

### Requirement: skill_env DB table
系統 SHALL 新增 `skill_env` table（Alembic migration）：
```sql
CREATE TABLE skill_env (
    id SERIAL PRIMARY KEY,
    scope VARCHAR(100) NOT NULL,    -- '_global' 或 skill slug
    key VARCHAR(255) NOT NULL,
    encrypted_value BYTEA NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(scope, key)
);
```

### Requirement: 加密
系統 SHALL 使用 `cryptography.fernet.Fernet` 加密 ENV values。
加密金鑰 SHALL 從環境變數 `CTOS_ENV_SECRET` 讀取。
若 `CTOS_ENV_SECRET` 未設定，系統 SHALL 在啟動時自動產生並寫入 `.env` 檔案，並 log warning。

### Requirement: ENV CRUD API
系統 SHALL 提供以下 admin-only API：

- `GET /api/skills/env` — 列出所有 scope 的 ENV keys（不含值，僅 key 列表 + mask）
- `GET /api/skills/{slug}/env` — 列出某 skill 的 ENV（key + mask）
- `PUT /api/skills/{slug}/env` — 設定 ENV（覆蓋寫入）
- `DELETE /api/skills/{slug}/env/{key}` — 刪除某個 ENV key
- `GET /api/skills/env/global` — 列出全域 ENV
- `PUT /api/skills/env/global` — 設定全域 ENV

#### Scenario: Write-only pattern
WHEN API 回傳 ENV 資訊
THEN value 欄位 SHALL 顯示為 mask（如 `GEMI****KEY`，取前 4 + 後 3 字元）
AND 完整值永遠不透過 API 回傳

#### Scenario: 設定 ENV
WHEN 管理員在 UI 填入 ENV 值並儲存
THEN 系統加密後寫入 DB
AND 舊值被覆蓋
AND 前端顯示更新成功 + mask 值

### Requirement: ENV 解析優先順序
Script Runner 注入 ENV 時 SHALL 按以下順序（後者優先）：
1. `os.environ`（系統環境變數）
2. `_global` scope（全域 skill env）
3. per-skill scope（該 skill 專用）

### Requirement: ENV Allowlist
Script Runner SHALL 改為 **allowlist 模式**：
- 只注入 skill 在 `metadata.openclaw.requires.env` 中宣告的 ENV keys
- 加上 SKILL_NAME, SKILL_DIR, SKILL_ASSETS_DIR 等系統 ENV
- 現有 `ENV_BLOCKLIST` 作為最後防線保留

#### Scenario: 未宣告的 ENV
WHEN skill 沒有在 metadata 中宣告 `requires.env`
THEN Script Runner 只注入系統 ENV（SKILL_NAME 等），不注入任何 user ENV
AND 現有 ENV_BLOCKLIST 仍然生效（雙重保護）

### Requirement: 前端 ENV 設定 UI
Skill 詳情頁 SHALL 新增「環境變數」section：
- 根據 SKILL.md `metadata.openclaw.requires.env` 自動列出必填/選填欄位
- 必填項顯示紅色星號
- 包含 KEY/SECRET/TOKEN 的欄位自動使用 password input
- 已設定的值顯示 mask + 「編輯」按鈕
- 未設定的必填項顯示 ⚠️ 提示

#### Scenario: 安裝後引導
WHEN 安裝的 skill 宣告了必填 ENV
THEN 安裝完成後自動開啟 ENV 設定 section
AND 顯示提示：「此 Skill 需要設定以下環境變數才能使用」

### Requirement: 依賴
系統 SHALL 在 `pyproject.toml` 新增 `cryptography` 依賴。
