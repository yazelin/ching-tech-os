## 1. 模組 Registry 與啟停基礎

- [x] 1.1 新增 `modules.py`，定義 `ModuleInfo`、`BUILTIN_MODULES`、`get_module_registry()` 與衝突處理
- [x] 1.2 在 `config.py` 新增 `ENABLED_MODULES`（預設 `*`）並實作 `is_module_enabled()`（`core` 永遠啟用）
- [x] 1.3 實作 `get_effective_app_permissions()`，停用模組時移除對應 `app_id`

## 2. 後端條件載入（Router / MCP / Scheduler）

- [x] 2.1 改寫 `main.py` 路由註冊為依 registry 動態 `importlib` 載入，移除頂層全量 router import
- [x] 2.2 實作模組 `lifespan_startup` 條件初始化，只執行啟用模組的啟動邏輯
- [x] 2.3 改寫 `services/mcp/__init__.py` 為條件載入：core 工具永遠載入、內建模組依 `mcp_module` 載入、Skill 依 `mcp_tools` 載入
- [x] 2.4 改寫 `scheduler.py` 為條件註冊排程：core 任務固定註冊、模組任務依啟停狀態註冊

## 3. Skill contributes 與模組整合

- [x] 3.1 擴充 `hub_meta.py` 解析 `SKILL.md` 的 `contributes` 區塊並做必要欄位驗證
- [x] 3.2 在 SkillManager 載入/安裝/卸載流程整合 `contributes`，讓 `get_module_registry()` 可合併 Skill 模組
- [x] 3.3 新增 Skill 前端資源 API：`GET /api/skills/{skill_name}/frontend/{file_path}`，含路徑穿越防護與 404 處理
- [x] 3.4 更新 Skills 管理 API 回傳 `has_module` 等必要欄位，並確保 reload/install/uninstall 會同步模組狀態

## 4. 前端桌面動態 App 清單與載入

- [x] 4.1 新增 `/api/config/apps` 端點，回傳啟用模組的 `app_manifest`（含可選 `loader`、`css`）
- [x] 4.2 修改 `desktop.js`：登入後改為呼叫 `/api/config/apps`，並保留 API 失敗時靜態清單 fallback
- [x] 4.3 在桌面渲染套用使用者權限過濾（管理員看全部啟用 App），拒絕無權限開啟並提示
- [x] 4.4 實作 Skill App 動態載入流程（先 CSS 後 JS），並確保子路徑部署 URL 正確

## 5. Bot Prompt 與工具白名單連動

- [x] 5.1 調整 Agent prompt 組裝，改為使用 `generate_tools_prompt(app_permissions)` 並自動排除停用模組片段
- [x] 5.2 調整 `get_tools_for_user()` 與各平台 handler，移除硬編碼工具清單並依權限動態產生
- [x] 5.3 實作 script 優先、`SKILL_SCRIPT_FALLBACK_ENABLED=true` 時允許回退到 MCP 工具

## 6. 驗證與回歸測試

- [x] 6.1 補齊後端測試：模組啟停、條件 router/MCP/scheduler、`/api/config/apps` 行為
- [x] 6.2 補齊 Skill contributes 測試：frontmatter 解析、欄位驗證、模組衝突、前端資源路徑防護
- [x] 6.3 執行 `cd backend && uv run pytest` 與 `npm run build`，確認變更不破壞既有流程
