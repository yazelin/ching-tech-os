# feature-modules Specification

## Purpose
TBD - created by syncing change multi-industry-flexibility. Update Purpose after archive.
## Requirements

### Requirement: Module Registry
系統 SHALL 維護一個模組 registry，描述所有可用的功能模組（內建 + Skill 擴充）。每個模組 SHALL 包含 id、source、router 資訊、MCP 工具模組、前端 App 定義、排程任務、權限 App ID 等 metadata。

#### Scenario: 內建模組定義
- **WHEN** 系統啟動
- **THEN** `BUILTIN_MODULES` dict SHALL 包含所有內建功能模組的 `ModuleInfo` 定義

#### Scenario: 合併 Registry
- **WHEN** 呼叫 `get_module_registry()`
- **THEN** SHALL 回傳內建模組 + 已安裝 Skill 模組的合併 registry
- **THEN** Skill 模組 ID 與內建模組衝突時 SHALL log warning 並跳過該 Skill

#### Scenario: SkillManager 不可用
- **WHEN** SkillManager 載入失敗
- **THEN** `get_module_registry()` SHALL 只回傳內建模組，不 raise exception

### Requirement: Module Enable/Disable
系統 SHALL 透過 `ENABLED_MODULES` 環境變數控制哪些模組啟用。

#### Scenario: 預設全部啟用
- **WHEN** `ENABLED_MODULES` 未設定或設為 `"*"`
- **THEN** 所有模組（內建 + Skill）SHALL 視為啟用

#### Scenario: 白名單模式
- **WHEN** `ENABLED_MODULES` 設為逗號分隔的模組 ID（如 `"core,knowledge-base,ai-agent,line-bot"`）
- **THEN** 只有列出的模組 SHALL 視為啟用，其餘 SHALL 視為停用

#### Scenario: Core 永遠啟用
- **WHEN** 任何 `ENABLED_MODULES` 設定
- **THEN** `core` 模組 SHALL 永遠啟用，即使未列在白名單中

#### Scenario: is_module_enabled 查詢
- **WHEN** 呼叫 `is_module_enabled(module_id)`
- **THEN** SHALL 回傳該模組是否啟用的 boolean 值

### Requirement: Conditional Router Registration
系統 SHALL 只為啟用的模組註冊 FastAPI router。

#### Scenario: 啟用模組載入 router
- **WHEN** 模組啟用且 `ModuleInfo` 包含 `router_path`
- **THEN** SHALL 使用 `importlib.import_module()` 載入該模組的 router 並呼叫 `app.include_router()`

#### Scenario: 停用模組不載入
- **WHEN** 模組停用
- **THEN** SHALL 不載入其 router，對應的 API 端點 SHALL 回傳 404

#### Scenario: 套件缺失 graceful 降級
- **WHEN** 模組啟用但其 Python 套件未安裝（如 `line-bot-sdk`）
- **THEN** `importlib` 載入 SHALL catch `ImportError`，log warning，跳過該模組
- **THEN** 系統其他模組 SHALL 正常運行

### Requirement: Conditional MCP Tool Loading
系統 SHALL 只為啟用模組載入 MCP 工具。

#### Scenario: 啟用模組的 MCP 工具載入
- **WHEN** 模組啟用且 `ModuleInfo` 包含 `mcp_module`
- **THEN** SHALL 動態 import 該 MCP 工具子模組，工具註冊到 FastMCP server

#### Scenario: 停用模組的 MCP 工具不載入
- **WHEN** 模組停用
- **THEN** 其 MCP 工具子模組 SHALL 不被 import，工具不出現在 MCP server

#### Scenario: Core MCP 工具永遠載入
- **WHEN** 系統啟動
- **THEN** `memory_tools` 和 `message_tools` SHALL 永遠載入，不受模組啟停影響

### Requirement: Conditional Scheduler Jobs
系統 SHALL 只為啟用模組註冊排程任務。

#### Scenario: 啟用模組的排程任務註冊
- **WHEN** 模組啟用且 `ModuleInfo` 包含 `scheduler_jobs`
- **THEN** SHALL 註冊對應的排程任務到 APScheduler

#### Scenario: 停用模組的排程任務不註冊
- **WHEN** 模組停用
- **THEN** 其排程任務 SHALL 不註冊，不執行

#### Scenario: Core 排程任務永遠啟用
- **WHEN** 系統啟動
- **THEN** `cleanup_old_messages`、`create_next_month_partitions`、`cleanup_expired_share_links` SHALL 永遠註冊

### Requirement: Effective App Permissions
系統 SHALL 自動排除停用模組的 App 權限，使 Prompt 和工具白名單連動。

#### Scenario: 停用模組的 app_id 被移除
- **WHEN** 模組停用
- **THEN** 其 `app_ids` SHALL 從 `DEFAULT_APP_PERMISSIONS` 中移除
- **THEN** `generate_tools_prompt()` SHALL 不包含該模組的工具說明
- **THEN** `get_tools_for_user()` SHALL 不回傳該模組的工具

#### Scenario: 啟用模組的 app_id 保留
- **WHEN** 模組啟用
- **THEN** 其 `app_ids` SHALL 保留在權限系統中，行為與目前相同

### Requirement: Apps Config API
系統 SHALL 提供 `/api/config/apps` 端點，回傳啟用模組的前端應用清單。

#### Scenario: 回傳啟用模組的應用清單
- **WHEN** GET `/api/config/apps`
- **THEN** SHALL 回傳所有啟用模組的 `app_manifest` 合併清單
- **THEN** 每個項目 SHALL 包含 `id`、`name`、`icon` 欄位

#### Scenario: Skill 擴充的 App 包含 loader
- **WHEN** 啟用的 Skill 模組有 `contributes.app.loader` 定義
- **THEN** 回傳的項目 SHALL 額外包含 `loader`（JS 路徑）和 `css`（CSS 路徑）欄位

#### Scenario: 停用模組的 App 不回傳
- **WHEN** 模組停用
- **THEN** 其 App SHALL 不出現在回傳清單中
