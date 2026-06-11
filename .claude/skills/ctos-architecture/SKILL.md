---
name: ctos-architecture
description: CTOS（ching-tech-os）架構導覽與改動定位指南。當使用者要在 ching-tech-os 加新功能、新前端 App、新後端內建模組、extends 外部模組，或新增 CTOS AI Skill 時使用。提供「改哪一層」決策樹、內建 App 逐檔 checklist、contributes.yaml 四種貢獻規格，以及 CTOS AI Skill 與 Claude Code skill 的區分。
---

# CTOS 架構與功能擴充指南

CTOS 是 FastAPI + PostgreSQL（asyncpg + Alembic）+ 原生 JS（IIFE，無框架）的內部平台。
加功能前先用下面的決策樹定位「要動哪一層」，再照對應 checklist 逐檔處理。
本 skill 只給骨架；**細節以 repo 內文件為準**，動手前先讀「必讀文件」一節列的檔案。

## 1. 決策樹：功能該放哪一層

```
這個需求是？
├─ 修改/擴充既有功能（加欄位、加端點、改 UI）
│   → 直接改既有模組。先查 docs/module-index.md 的
│     「常見修改場景速查」定位檔案，不要新開模組。
│
├─ 全新的平台功能，所有部署都該有（如知識庫、分享管理這類）
│   → 內建新 App：在 backend/src/ching_tech_os/modules.py 的
│     BUILTIN_MODULES 加 entry。見第 2 節 checklist。
│
├─ 需要獨立授權 / 獨立版控 / 客戶特定（如 his、law、erpnext）
│   → extends 外部模組：git submodule + contributes.yaml 宣告，
│     不修改主系統任何程式碼。見第 3 節。
│
└─ 要給 CTOS 的 AI（Bot / AI 助手）新能力（prompt + 工具 + 可選前端 App）
    → CTOS AI Skill：SKILL.md（frontmatter 含 metadata.ctos /
      contributes），由 SkillManager 掃描載入。見第 4 節。
```

判斷補充：

- 模組啟停由 `.env` 的 `ENABLED_MODULES` 控制（`*` 全開，或逗號分隔清單；`core` 永遠啟用）。`modules.py` 的 `is_module_enabled()` 是判斷點。
- extends 模組裡的工具有三種提供方式（in-process `mcp_tools` / 外部 `mcp_servers` / Skill Script），選擇矩陣在 `docs/extends-module.md` 的「三種工具提供方式的選擇」表格，別憑感覺選。

## 2. 內建新 App 逐檔 checklist

### 2.1 後端

- [ ] `backend/src/ching_tech_os/modules.py`：在 `BUILTIN_MODULES` 加 entry。欄位依 `ModuleInfo` TypedDict：
  - `id`（必填，模組 ID，同時是 `ENABLED_MODULES` 的 key）
  - `source: "builtin"`（必填）
  - `routers`：`RouterSpec` 清單，每筆 `{"module": ".api.xxx", "attr": "router", "kwargs": {...}}`，由 `main.py` 動態註冊
  - `mcp_module`：如 `".services.mcp.xxx_tools"`（有 MCP 工具才填）
  - `app_ids` + `app_manifest`：前端 App 清單，每個 app `{"id", "name", "icon"}`，會經 `/api/config/apps` 餵給前端
  - 視需求：`permission_defaults`、`permission_display_names`、`scheduler_jobs`、`lifespan_startup`
- [ ] `api/xxx.py`（路由）、`services/xxx.py`（業務邏輯）、`models/xxx.py`（Pydantic 模型）
- [ ] Migration：`backend/migrations/versions/00X_description.py`（schema 變更一律走 Alembic；`docker/init.sql` 已停用），套用：`cd backend && uv run alembic upgrade head`

### 2.2 前端

- [ ] `frontend/js/xxx.js`：IIFE 模組，需暴露 `open()`（desktop.js lazy-load 後以 `window[globalName].open()` 開啟）
- [ ] `frontend/css/xxx.css`：樣式。**先讀 `frontend/css/main.css` 的變數定義**，用 `--text-*` / `--bg-*` / `--color-*` 變數，禁止硬編碼色值與 fallback 值
- [ ] `frontend/js/desktop.js`：
  - `fallbackApplications` 加 `{ id, name, icon }`（API 失敗時的 fallback；正式清單來自 `/api/config/apps`，由 modules.py 的 `app_manifest` 生成）
  - `fallbackAppLoaders` 加 `{ src: './js/xxx.js', globalName: 'XxxApp' }`（lazy-load 查表）
- [ ] `frontend/index.html`（和 `login.html`）：引入 CSS。注意：僅靜態內建資源需引入；lazy-load 的 JS 由 desktop.js 動態注入，不需 `<script>` 標籤。路徑後**不要**加 `?v=` 版本號
- [ ] `frontend/js/icons.js`：如需新圖示，在 `Icons` 物件加 SVG（Material Design Icons）。使用時 `getIcon()` 必須包在 `<span class="icon">` 內

### 2.3 收尾

- [ ] `docs/module-index.md`：更新模組地圖（後端/前端對應表）
- [ ] 子路徑部署檢查：HTML 屬性裡的 `/api/...`（`href` / `src` / `window.open`）要加 `${window.API_BASE || ''}`，詳見 CLAUDE.md「子路徑部署」一節
- [ ] 版本號如要 bump，三處同步：`backend/pyproject.toml`、`src/ching_tech_os/__init__.py`、`main.py` 的 FastAPI `version`

## 3. extends 外部模組：contributes.yaml 四種貢獻

主系統啟動時掃描 `extends/*/contributes.yaml` 自動整合，模組**不需要也不應該**改主系統程式碼。`module_id` 對應 `ENABLED_MODULES`；不設定則永遠啟用。

### 3.1 四種貢獻的精確 YAML 規格

```yaml
module_id: my-module

# (1) in-process MCP 工具：路徑相對模組根目錄，
#     檔內用 @mcp.tool() 向主系統 FastMCP 註冊；
#     需 DB 時先 await ensure_db_connection()
mcp_tools: core/mcp_tools.py

# (2) 外部 MCP Server：獨立進程、stdio 通訊，
#     ${PROJECT_ROOT} 自動替換為專案根目錄
mcp_servers:
  server-name:
    command: bash
    args: ["-c", "set -a && source ${PROJECT_ROOT}/.env && set +a && uvx some-mcp"]

# (3) 生命週期：主系統啟動/關閉時執行，
#     callable 是相對模組根目錄的 import 路徑（sync/async 皆可），
#     kwargs 的 ${ENV_VAR} 自動替換環境變數
lifespan:
  startup:
    callable: core.some_module.start
    kwargs:
      param1: ${ENV_VAR}
      param2: 30
  shutdown:
    callable: core.some_module.stop

# (4) API 路由：把模組的 FastAPI Router 註冊進主系統，
#     module 是 import 路徑（模組根目錄已在 sys.path）
routers:
  - module: my_router
    attr: router
    kwargs:
      prefix: /api/my-module
      tags: [my-module]
```

### 3.2 現成範例模組對照表

| 模組 | 使用欄位 | 工具提供方式 | 參考重點 |
|------|---------|------------|---------|
| `extends/voice` | `module_id` + `lifespan` + `routers` | 主系統 in-process MCP 工具 | lifespan 預載 Whisper 模型；routers 掛 `/api/voice` TTS 下載 API |
| `extends/printer` | `module_id` + `mcp_servers` | 外部 MCP Server（`uvx printer-mcp`） | 最小 mcp_servers 範例 |
| `extends/his` | `module_id` + `lifespan`（含 `${CTHIS_DATA_PATH}` kwargs） | Skill Script（不用 in-process MCP） | lifespan 背景輪詢 DBF + `skills/*/SKILL.md` 帶前端 App 貢獻 |

另：`extends/law` 是 `module_id` + `mcp_tools`（in-process）的範例，見 `docs/extends-module.md` 的「現有模組參考」表。

注意：模組**根目錄**的 SKILL.md 只是說明文件，SkillManager 不掃描；會被載入的是 `extends/{module}/skills/{name}/SKILL.md`。

## 4. CTOS AI Skill 不是 Claude Code skill

兩者同名 SKILL.md，是**完全不同的東西**，別混：

| | CTOS AI Skill | Claude Code skill |
|---|---|---|
| 給誰用 | CTOS 平台內的 AI（Bot、AI 助手） | 開發者本機的 Claude Code |
| 位置 | `backend/.../skills/`、`extends/*/skills/{name}/`、外部 `~/SDD/external-skills/` | `.claude/skills/`（本檔就是一個） |
| 載入者 | CTOS 的 SkillManager | Claude Code CLI |

CTOS AI Skill 的 frontmatter（規格見 `docs/extends-module.md`）：

```yaml
---
name: skill-name
description: 一句話描述
allowed-tools: "tool_a tool_b"        # 空格分隔，控制此 Skill 可用哪些已註冊 MCP 工具
metadata:
  ctos:
    requires_app: app-id              # 需要的前端 App 權限（null = 不需要）
    mcp_servers: ""                   # 需要的外部 MCP Server（空格分隔）
  contributes:                        # 可選：向主系統貢獻前端 App / 權限
    app:
      id: app-id
      name: 顯示名稱
      icon: mdi-xxx
      loader:
        src: frontend/xxx-app.js      # 相對 skill 目錄，由 modules.py 轉成 /api/skills/... 路徑
        globalName: XxxApp
      css: frontend/xxx-app.css
    permissions:
      app-id:
        default: false
        display_name: 顯示名稱
---
```

分工：`contributes.yaml` 的 `mcp_tools` 負責**載入註冊**工具；SKILL.md 的 `allowed-tools` 負責控制 AI 在該情境**可以用哪些**。一個模組可有多個 Skill，各開放不同工具子集。實例參考 `extends/his/skills/his-integration/SKILL.md`（contributes.app + permissions 完整範例）。

## 5. 必讀文件指引

| 時機 | 讀什麼 |
|------|--------|
| 動任何功能前（定位檔案） | `docs/module-index.md` |
| 開發 extends 模組 / CTOS AI Skill | `docs/extends-module.md`（contributes.yaml 完整規格、Skill Script 模式、多租戶、驗證指令、常見問題） |
| 寫程式前的專案規範（migration、版本號三處同步、CSS 變數、子路徑部署、圖示規則） | 根目錄 `CLAUDE.md` |
| 測試與 CI 門檻 | `docs/testing-ci.md`、`.github/workflows/backend-tests.yml` |

本 skill 刻意精簡——上表文件才是單一事實來源，規格細節（完整欄位、錯誤排查）一律回到 repo 文件查證，不要憑本 skill 的摘要硬寫。
