# Tasks: Skill 生態系統完善

## Phase 1: ClawHub REST API 替換

### Task 1.1: ClawHubClient class
- [ ] 建立 `services/clawhub_client.py`
- [ ] `httpx.AsyncClient` + base URL + timeout + no redirect
- [ ] `search()`, `get_skill()`, `get_versions()`, `download_zip()`
- [ ] `download_and_extract()` — ZIP 解壓 + zip slip 防護 + 大小限制 10MB
- [ ] `_write_meta()` — 寫入 `_meta.json`
- [ ] 單一實例（module-level 或 lru_cache）
- **檔案**: `backend/src/ching_tech_os/services/clawhub_client.py`

### Task 1.2: API 端點替換
- [ ] `hub_search` 改用 `ClawHubClient.search()`
- [ ] `hub_inspect` 改用 `ClawHubClient.get_skill()` + ZIP 內 SKILL.md
- [ ] `hub_install` 改用 `ClawHubClient.download_and_extract()`
- [ ] 移除 `_run_clawhub` helper 和 `_SEARCH_LINE_RE`
- [ ] 新增 `GET /api/skills/{name}/meta` — 回傳 _meta.json 資訊
- **檔案**: `backend/src/ching_tech_os/api/skills.py`

### Task 1.3: 前端搜尋卡片升級
- [ ] 搜尋結果顯示：author、version、summary、relativeTime
- [ ] 預覽面板顯示完整 metadata（owner avatar + handle、stats、changelog）
- [ ] 移除原本的 metadata inspect 邏輯（已內含於搜尋結果）
- **檔案**: `frontend/js/agent-settings.js`, `frontend/css/agent-settings.css`

### Task 1.4: 依賴與腳本
- [ ] `pyproject.toml` 新增 `httpx>=0.27`
- [ ] `install-service.sh` 中 clawhub CLI 安裝行加註解（保留備用）
- **檔案**: `backend/pyproject.toml`, `scripts/install-service.sh`

---

## Phase 2: Skill ENV 管理

### Task 2.1: DB table + Migration
- [ ] 建立 Alembic migration `00X_skill_env.py`
- [ ] `skill_env` table: id, scope, key, encrypted_value, created_at, updated_at, UNIQUE(scope, key)
- **檔案**: `backend/migrations/versions/00X_skill_env.py`

### Task 2.2: SkillEnvManager
- [ ] 建立 `services/skill_env.py`
- [ ] Fernet 加密（key 從 `CTOS_ENV_SECRET` 環境變數）
- [ ] 若 secret 未設定，啟動時自動生成 + log warning
- [ ] `list_env(scope)` — 回傳 key + mask
- [ ] `get_env(scope)` — 解密（server-side only）
- [ ] `set_env(scope, key, value)` — 加密寫入
- [ ] `delete_env(scope, key)`
- [ ] `resolve_env(slug, declared_keys)` — 合併 os.environ + global + per-skill，按 allowlist 過濾
- [ ] `mask_value(value)` — 靜態方法
- **檔案**: `backend/src/ching_tech_os/services/skill_env.py`

### Task 2.3: ENV API 端點
- [ ] `GET /api/skills/env/global` — 全域 ENV（key + mask）
- [ ] `PUT /api/skills/env/global` — 設定全域 ENV
- [ ] `GET /api/skills/{slug}/env` — 某 skill 的 ENV（key + mask）
- [ ] `PUT /api/skills/{slug}/env` — 設定 skill ENV
- [ ] `DELETE /api/skills/{slug}/env/{key}` — 刪除
- [ ] 全部 admin-only
- **檔案**: `backend/src/ching_tech_os/api/skills.py`

### Task 2.4: Script Runner ENV Allowlist
- [ ] `skill_script_tools.py` 中 ENV 注入改 allowlist 模式
- [ ] 只注入 skill 宣告的 `metadata.openclaw.requires.env` keys + 系統 ENV
- [ ] 保留 ENV_BLOCKLIST 作為最後防線
- [ ] 從 SkillEnvManager 解析 ENV（os.environ → global → per-skill）
- **檔案**: `backend/src/ching_tech_os/services/mcp/skill_script_tools.py`

### Task 2.5: 前端 ENV UI
- [ ] Skill 詳情頁新增「環境變數」section
- [ ] 從 skill metadata 讀取 required env 列表
- [ ] 必填項紅色星號、password input 自動偵測
- [ ] 已設定的值顯示 mask + 編輯按鈕
- [ ] 安裝後若有必填 ENV，自動展開 ENV section
- [ ] 全域 ENV 設定入口（skill 管理頁頂部）
- **檔案**: `frontend/js/agent-settings.js`, `frontend/css/agent-settings.css`

### Task 2.6: 依賴
- [ ] `pyproject.toml` 新增 `cryptography>=43.0`
- **檔案**: `backend/pyproject.toml`

---

## Phase 3: 權限模型改善

### Task 3.1: 信任等級
- [ ] SkillManager 新增 `get_trust_level(name)` — builtin/private/community
- [ ] 判定邏輯：無 _meta.json = builtin, owner 匹配 = private, 其他 = community
- [ ] API 回應中包含 trust_level 欄位
- **檔案**: `backend/src/ching_tech_os/skills/__init__.py`

### Task 3.2: 安裝預設權限
- [ ] ClawHub 安裝後預設 `requires_app: "admin"`
- [ ] 寫入 SKILL.md frontmatter（如果原本沒有或為空）
- **檔案**: `backend/src/ching_tech_os/api/skills.py`, `services/clawhub_client.py`

### Task 3.3: 狀態燈號
- [ ] SkillManager 新增 `get_skill_status(name)` — ok/warning/error
- [ ] 檢查：必填 ENV 是否齊全、requires_app 是否為預設值
- [ ] 前端 skill 列表顯示燈號圓點（CSS class）
- [ ] Hover tooltip 顯示缺什麼
- **檔案**: `backend/src/ching_tech_os/skills/__init__.py`, `frontend/js/agent-settings.js`, `frontend/css/agent-settings.css`

### Task 3.4: 內建 skill 權限補齊
- [ ] 7 個內建 skill 的 SKILL.md 補上正確的 `requires_app`
- [ ] base → "", ai-assistant → "", file-manager → "file_manager", inventory → "inventory", knowledge → "knowledge_base", project → "project"
- **檔案**: `skills/*/SKILL.md`

### Task 3.5: 前端權限引導
- [ ] 安裝完成後顯示權限設定引導（所有人/管理員/自訂）
- [ ] Skill 詳情頁可編輯 requires_app
- **檔案**: `frontend/js/agent-settings.js`

---

## Phase 4: Printer Skill 化

### Task 4.1: Printer SKILL.md
- [ ] 建立 `skills/printer/SKILL.md`
- [ ] `requires_app: "printer"`, `mcp_servers: "printer"`
- [ ] allowed-tools: print_document, list_printers, get_printer_status
- **檔案**: `skills/printer/SKILL.md`

### Task 4.2: MCP Server 宣告式啟動
- [ ] SkillManager 讀取 `metadata.ctos.mcp_servers`
- [ ] 與現有 MCP on-demand loading 整合
- [ ] 只在使用者有權限時載入
- **檔案**: `backend/src/ching_tech_os/skills/__init__.py`, `services/bot/agents.py`

### Task 4.3: 移除硬編碼
- [ ] 從 MCP server 硬編碼列表移除 printer
- [ ] 確保 printer 功能完全由 skill 機制控管
- **檔案**: `backend/src/ching_tech_os/services/mcp_server.py`, `services/bot/agents.py`

### Task 4.4: 測試（需公司環境）
- [ ] 測試列印功能正常
- [ ] 測試無 printer 權限的使用者看不到列印工具
- [ ] 測試 MCP server on-demand 載入/卸載
