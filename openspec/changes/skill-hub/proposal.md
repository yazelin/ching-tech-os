## Why

CTOS 已完成 Agent Skills 開放標準相容（PR #45-47），但目前：

1. **無法從 UI 安裝新 skill** — 只能手動複製檔案到 skills 目錄
2. **無法搜尋 ClawHub 生態** — 25+ 平台共用的 skill marketplace 無法存取
3. **管理員無法編輯權限** — skill 的 `requires_app`、`allowed-tools`、`mcp_servers` 只能改檔案
4. **clawhub CLI 未納入部署** — install.sh 不包含 clawhub

## What Changes

### 1. 基礎設施：clawhub 納入安裝流程
- `install.sh` 加入 `npm install -g clawhub` 或 `pip install clawhub`
- 或改用 ClawHub HTTP API 直接下載（不依賴 CLI）

### 2. 後端：Skills CRUD API
- `POST /api/skills/search` — 搜尋 ClawHub marketplace
- `POST /api/skills/install` — 從 ClawHub 安裝 skill（呼叫 `import_openclaw_skill`）
- `PUT /api/skills/{name}` — 編輯 skill 的 CTOS 擴充欄位（requires_app、allowed-tools、mcp_servers）
- `DELETE /api/skills/{name}` — 移除已安裝的 skill
- `POST /api/skills/reload` — 重新載入所有 skills（不重啟服務）

### 3. 前端：Skills 管理介面升級
- **搜尋 tab**：搜尋 ClawHub，顯示搜尋結果（名稱、描述、版本、相似度），一鍵安裝
- **已安裝 tab**（現有）：顯示所有已載入 skill
- **Skill 詳情**：新增「編輯」按鈕，可修改：
  - `requires_app`（下拉選擇現有 app 或輸入新的）
  - `allowed-tools`（chip 列表，可新增/移除）
  - `mcp_servers`（chip 列表，可新增/移除）
- **來源標記**：顯示 skill 來源（native / openclaw / claude-code）
- **檔案瀏覽**：可查看 skill 的 references/、scripts/、assets/ 檔案內容

### 4. SkillManager 擴充
- `update_skill_metadata()` — 更新 CTOS 擴充欄位並寫回 SKILL.md
- `remove_skill()` — 刪除 skill 目錄
- `reload_skills()` — 清除 `_loaded` flag，重新掃描

## Capabilities

### New Capabilities

- **skill-marketplace**: 管理員可從 ClawHub 搜尋、預覽、安裝 Agent Skills
- **skill-permission-edit**: 管理員可編輯 skill 的權限（requires_app）和工具白名單（allowed-tools、mcp_servers）
- **skill-lifecycle**: 管理員可安裝、更新、移除 skill，並即時重載

### Modified Capabilities

- **ai-management**: Skills 管理介面從唯讀升級為完整 CRUD
- **bot-platform**: SkillManager 支援動態重載（不需重啟服務）
- **infrastructure**: install.sh 納入 clawhub 依賴

## Impact

### 安全性考量
- Skills 安裝/編輯/移除限定 `require_admin`
- 從 ClawHub 安裝的 skill 預設 `requires_app: null`、`allowed-tools` 為空，管理員需手動授權
- Skill name 驗證防止路徑穿越（已實作）
- 檔案讀取限定 references/scripts/assets/ 前綴（已實作）

### 向下相容
- 現有 7 個 native skill 不受影響
- 現有 API（GET /api/skills、GET /api/skills/{name}）不變
- 前端已安裝 tab 保持現有行為

## Implementation Phases

### Phase 1: 後端 API（CRUD + reload）
- `PUT /api/skills/{name}` 編輯 metadata.ctos
- `DELETE /api/skills/{name}` 移除
- `POST /api/skills/reload` 重載
- SkillManager 新增 `update_skill_metadata()`、`remove_skill()`

### Phase 2: ClawHub 整合
- 研究 ClawHub HTTP API 或 CLI 整合方式
- `POST /api/skills/search` 搜尋
- `POST /api/skills/install` 安裝

### Phase 3: 前端 UI
- 編輯 modal（requires_app + allowed-tools + mcp_servers）
- ClawHub 搜尋 tab
- 安裝/移除確認 dialog
- 檔案瀏覽 panel
