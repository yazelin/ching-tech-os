## Context

CTOS 目前所有功能模組在啟動時無條件載入：

- **main.py 第 18 行**：一條 import 同時載入全部 router（linebot_router、telegram_router、knowledge、nas...），任何一個的頂層 import 失敗就整個啟動爆炸
- **mcp/__init__.py**：8 個工具模組全部 `from . import xxx`，無條件註冊所有 MCP 工具
- **linebot_agents.py**：`LINEBOT_PERSONAL_PROMPT` 和 `LINEBOT_GROUP_PROMPT` 硬編碼了所有模組（ERPNext、NAS、知識庫、列印…）的完整工具說明，即使該模組未啟用
- **desktop.js**：15 個應用靜態宣告，前端只靠 `permissions.js` 隱藏無權限的 App，但 App 定義本身不可配置
- **scheduler.py**：所有排程任務無條件啟動（NAS 清理、訊息清理等），雖然個別任務有路徑不存在的防護

現有的「鬆耦合」基礎：
- `bot/agents.py` 的 `APP_PROMPT_MAPPING` 已將 prompt 按 app_id 分類
- `generate_tools_prompt()` 已按 `app_permissions` 動態組裝 prompt 片段
- `get_tools_for_user()` 已按權限過濾工具白名單
- `permissions.py` 的 `DEFAULT_APP_PERMISSIONS` 已定義各 App 的預設啟停狀態
- Telegram Bot 已有 token 空值跳過機制
- SkillHub 已有 `skillhub_enabled()` feature flag 模式
- Skill 系統已有 `SKILL.md` frontmatter 解析（`hub_meta.py`）、安裝/卸載、prompt 載入機制

也就是說：**prompt 層和工具白名單層已有按權限動態過濾的機制，但路由註冊、MCP 工具載入、排程、前端清單這四層完全是靜態的**。而 Skill 系統已具備擴充的基礎能力，但尚未發展為完整的模組擴充機制。

## Goals / Non-Goals

**Goals:**
- **統一模組與 Skill**：Skill 就是模組擴充系統（類似 VSCode Extension / Chrome Extension），安裝 Skill 即可擴充功能，不需修改程式碼
- 內建功能也用相同的模組描述格式，只是 `source: builtin`
- 每個模組可透過環境變數獨立啟用/停用
- 停用的模組：不載入 router、不載入 MCP 工具、不啟動排程任務、不出現在前端桌面、Prompt 中不出現工具說明
- 從 SkillHub 安裝帶有 `contributes` 宣告的 Skill → 自動出現在桌面、自動註冊 MCP 工具、自動加入 Prompt
- 現有部署零影響升級：預設啟用全部模組

**Non-Goals:**
- 不做多租戶（migration 003 已拆除，重建代價太高）
- 不做執行期動態啟停（只在啟動時讀取設定，不支援運行中切換模組）
- 不做前端品牌白牌化（獨立改動，不在本次範圍）
- 第一階段不支援 Skill 帶 FastAPI router（Skill 擴充透過 MCP 工具 + prompt + 前端 App，不擴充 REST API）

## Decisions

### Decision 1：Skill = 模組擴充系統，統一架構

**核心理念**：不另建「模組系統」，而是擴充現有 Skill 系統的能力，讓它成為完整的擴充機制。

類比：
| VSCode Extension | CTOS Skill |
|------------------|------------|
| `contributes.commands` | MCP 工具（現有） |
| `contributes.views` / `contributes.viewsContainers` | 前端 App（**新增**：`contributes.app`） |
| `contributes.configuration` | Prompt 片段（現有：`prompt_personal` / `prompt_group`） |
| `contributes.menus` | 工具白名單（現有：`allowed-tools`） |
| `package.json` | `SKILL.md` frontmatter |
| Extension Marketplace | SkillHub / ClawHub |
| Built-in extensions | `source: builtin` 的內建模組 |

**替代方案**：Skill 和模組分開管理（兩套 registry、兩套安裝機制）

**理由**：
- 分開會有兩套安裝、卸載、生命週期管理——複雜度翻倍
- Skill 已有完善的安裝/卸載/Hub 機制（`SkillManager`、`hub_meta.py`），再造一套是重複工作
- VSCode 和 Chrome 都是一套擴充系統，不區分「小擴充」和「大擴充」
- 現有的 4 個外部 Skill（base、file-manager、pdf-converter、share-links）已經證明 Skill 系統可以運作

### Decision 2：`contributes` — SKILL.md frontmatter 擴充格式

**選擇**：在 `SKILL.md` frontmatter 中新增 `contributes` 區塊，宣告 Skill 擴充了哪些系統能力。

#### 完整格式定義

```yaml
---
name: clinic-patient-portal
version: 1.0.0
description: 診所病人入口 — 掛號、衛教、問卷

# 現有欄位（不變）
allowed-tools:
  - mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    requires_app: patient-portal    # 需要此 app 權限才啟用
    mcp_servers: ching-tech-os

# 新增欄位
contributes:
  # 前端桌面應用（安裝後出現在桌面）
  app:
    id: patient-portal
    name: 病人入口
    icon: mdi-hospital
    # 前端 JS/CSS 由 Skill 目錄提供
    loader:
      src: frontend/patient-portal.js    # 相對於 Skill 目錄
      globalName: PatientPortalApp
    css: frontend/patient-portal.css     # 可選

  # 權限定義（自動加入 DEFAULT_APP_PERMISSIONS）
  permissions:
    patient-portal:
      default: true
      display_name: 病人入口

  # MCP 工具模組（可選，Python 檔案相對於 Skill 目錄）
  mcp_tools: mcp_tools.py

  # 排程任務（可選）
  scheduler:
    - fn: cleanup_expired_appointments
      trigger: cron
      hour: 3
---

# 以下是 prompt 區塊（現有機制，不變）
【病人入口】
- 掛號查詢：run_skill_script(skill="clinic-patient-portal", script="check_appointment", ...)
...
```

#### 各 `contributes` 欄位的生效機制

| 欄位 | 生效時機 | 機制 |
|------|---------|------|
| `app` | 系統啟動 | 加入 `/api/config/apps` 回傳的應用清單 |
| `app.loader` | 使用者點擊 App | `desktop.js` 動態載入 Skill 目錄下的 JS/CSS |
| `permissions` | 系統啟動 | 合併進 `DEFAULT_APP_PERMISSIONS` |
| `mcp_tools` | MCP Server 啟動 | 動態 import Skill 目錄下的 Python 模組 |
| `scheduler` | 系統啟動 | 動態註冊排程任務 |
| prompt 區塊 | AI 回應時 | 現有 SkillManager 機制，按 `requires_app` 過濾 |
| `allowed-tools` | AI 回應時 | 現有 SkillManager 機制，按權限過濾 |

### Decision 3：內建模組用同一格式描述

**選擇**：將現有 14 個內建功能也用 `ModuleInfo` 結構描述，集中定義在 `modules.py`。格式與 Skill 的 `contributes` 對齊，但多了 `router_path`（內建模組特有，Skill 不帶 router）。

```python
# modules.py

class ModuleInfo(TypedDict, total=False):
    id: str                     # 模組唯一識別
    source: str                 # "builtin" | "skill"

    # 後端（builtin 專用）
    router_path: str            # importlib 路徑
    router_attrs: list[str]     # router 物件名稱
    router_kwargs: list[dict]   # include_router 參數
    mcp_module: str             # MCP 工具模組路徑（內建）

    # 後端（skill 專用）
    mcp_tools_file: str         # Skill 目錄下的 MCP 工具 Python 檔

    # 共用
    app_manifest: list[dict]    # 前端 App [{id, name, icon, loader?, css?}]
    app_ids: list[str]          # 對應的權限 App ID
    scheduler_jobs: list[dict]  # 排程任務定義
    dependencies: list[str]     # 依賴的模組 ID
    lifespan_startup: str       # 啟動時呼叫的函式
    lifespan_shutdown: str      # 關閉時呼叫的函式
```

內建模組範例：

```python
BUILTIN_MODULES: dict[str, ModuleInfo] = {
    "core": {
        "id": "core",
        "source": "builtin",
        "router_path": ".api.auth",
        "router_attrs": ["router"],
        # core 永遠啟用，不能停用
    },
    "knowledge-base": {
        "id": "knowledge-base",
        "source": "builtin",
        "router_path": ".api.knowledge",
        "router_attrs": ["router"],
        "mcp_module": ".services.mcp.knowledge_tools",
        "app_ids": ["knowledge-base"],
        "app_manifest": [{"id": "knowledge-base", "name": "知識庫", "icon": "mdi-book-open-page-variant"}],
    },
    "line-bot": {
        "id": "line-bot",
        "source": "builtin",
        "router_path": ".api.linebot_router",
        "router_attrs": ["router", "line_router"],
        "router_kwargs": [{"prefix": "/api/bot"}, {"prefix": "/api/bot/line"}],
        "app_ids": ["linebot"],
        "app_manifest": [{"id": "linebot", "name": "Bot 管理", "icon": "mdi-message-text"}],
        "lifespan_startup": "ensure_default_linebot_agents",
    },
    "file-manager": {
        "id": "file-manager",
        "source": "builtin",
        "router_path": ".api.nas",
        "router_attrs": ["router"],
        "mcp_module": ".services.mcp.nas_tools",
        "scheduler_jobs": [
            {"fn": "cleanup_linebot_temp_files", "trigger": "interval", "hours": 1},
            {"fn": "cleanup_media_temp_folders", "trigger": "cron", "hour": 5},
        ],
        "app_ids": ["file-manager"],
        "app_manifest": [{"id": "file-manager", "name": "檔案管理", "icon": "mdi-folder"}],
    },
    "erpnext": {
        "id": "erpnext",
        "source": "builtin",
        # 無 router、無 mcp_module（ERPNext 是外部 MCP Server）
        # 只有 prompt 片段和工具白名單（透過現有 Skill 機制管理）
        "app_ids": ["project-management", "inventory-management"],
        "app_manifest": [{"id": "erpnext", "name": "ERPNext", "icon": "erpnext"}],
    },
    # ... 其餘模組
}
```

### Decision 4：合併 Registry 函式

**選擇**：`get_module_registry()` 合併內建模組 + 已安裝 Skill 的模組宣告。

```python
def get_module_registry() -> dict[str, ModuleInfo]:
    """取得完整模組 registry（內建 + Skill 擴充）"""
    registry = BUILTIN_MODULES.copy()

    try:
        from .skills import get_skill_manager
        sm = get_skill_manager()
        for skill in sm.get_all_skills():
            contributes = skill.metadata.get("contributes")
            if not contributes:
                continue
            module_id = contributes.get("app", {}).get("id") or skill.name
            if module_id in registry:
                logger.warning(f"Skill '{skill.name}' 的模組 ID '{module_id}' 與內建模組衝突，跳過")
                continue
            registry[module_id] = _skill_contributes_to_module_info(skill, contributes)
    except Exception:
        pass  # SkillManager 不可用時只回傳內建模組

    return registry
```

### Decision 5：`ENABLED_MODULES` 環境變數 + 預設全啟

**選擇**：`config.py` 新增 `enabled_modules` 設定。特殊值 `"*"`（預設）代表啟用全部。

```python
# config.py
enabled_modules: str = _get_env("ENABLED_MODULES", "*")
```

```python
# modules.py
def is_module_enabled(module_id: str) -> bool:
    if module_id == "core":
        return True
    enabled = settings.enabled_modules
    if enabled == "*":
        return True
    return module_id in {m.strip() for m in enabled.split(",")}
```

**理由**：
- 預設 `"*"` 確保現有部署零影響
- 診所場景：`ENABLED_MODULES=core,knowledge-base,ai-agent,line-bot`
- Skill 安裝的模組預設啟用（安裝即生效），除非被 `ENABLED_MODULES` 白名單排除
- `ENABLED_MODULES=*` 時，所有 Skill 模組也自動啟用

### Decision 6：用 `importlib` 延遲載入，解決頂層 import 爆炸

**選擇**：`main.py` 的路由註冊改為遍歷 registry，用 `importlib` 動態載入。

**目前的問題**：
```python
# main.py 第 18 行 — 觸發所有 router 的頂層 import
from .api import auth, knowledge, ..., linebot_router, telegram_router, ...
```
`linebot_router.py` 頂層 `from linebot.v3.webhooks import ...`，套件不裝就 ImportError。

**改後**：
```python
import importlib

for module_id, info in get_module_registry().items():
    if not is_module_enabled(module_id):
        continue
    if "router_path" not in info:
        continue  # Skill 模組沒有 router
    try:
        mod = importlib.import_module(info["router_path"], package=__package__)
        for i, attr in enumerate(info["router_attrs"]):
            kwargs = info.get("router_kwargs", [{}] * len(info["router_attrs"]))[i]
            app.include_router(getattr(mod, attr), **kwargs)
    except ImportError as e:
        logger.warning(f"模組 {module_id} 載入失敗（可能缺少套件）: {e}")
```

### Decision 7：MCP 工具條件載入 — 內建 + Skill 統一處理

**選擇**：`services/mcp/__init__.py` 改為動態載入。內建模組走 `mcp_module` 路徑，Skill 模組走 `mcp_tools_file` 檔案路徑。

```python
# mcp/__init__.py
import importlib

# 永遠載入的 core 工具
from . import memory_tools   # noqa: F401
from . import message_tools  # noqa: F401

# 內建模組條件載入
for module_id, info in get_module_registry().items():
    if not is_module_enabled(module_id):
        continue
    if info.get("source") == "builtin" and "mcp_module" in info:
        try:
            importlib.import_module(info["mcp_module"], package="ching_tech_os")
        except ImportError as e:
            logger.warning(f"MCP 工具模組 {module_id} 載入失敗: {e}")
    elif info.get("source") == "skill" and "mcp_tools_file" in info:
        # Skill 的 MCP 工具從外部檔案載入
        _load_skill_mcp_tools(info["mcp_tools_file"])
```

### Decision 8：前端應用清單 — 後端 API 提供，支援 Skill 擴充的 App

**選擇**：新增 `/api/config/apps` 端點，遍歷啟用模組的 `app_manifest`，回傳完整的應用清單。

```json
// GET /api/config/apps
[
  { "id": "knowledge-base", "name": "知識庫", "icon": "mdi-book-open-page-variant" },
  { "id": "ai-assistant", "name": "AI 助手", "icon": "mdi-robot" },
  { "id": "patient-portal", "name": "病人入口", "icon": "mdi-hospital",
    "loader": { "src": "/api/skills/clinic-patient-portal/frontend/patient-portal.js",
                "globalName": "PatientPortalApp" },
    "css": "/api/skills/clinic-patient-portal/frontend/patient-portal.css" }
]
```

`desktop.js` 改為：
1. 啟動時 fetch `/api/config/apps`
2. 內建 App 走現有的 `appLoaders` 映射（已載入的 JS）
3. Skill App 有 `loader` 欄位 → 動態載入 Skill 提供的 JS/CSS
4. API 失敗時 fallback 到靜態清單（graceful degradation）

### Decision 9：Prompt 與工具白名單 — 利用現有機制連動

**選擇**：不另做 prompt 模組化。停用模組時，其 `app_id` 從可用權限中移除，`generate_tools_prompt()` 和 `get_tools_for_user()` 現有邏輯自動跳過。

```python
def get_effective_app_permissions() -> dict[str, bool]:
    """取得有效的 App 權限（排除停用模組）"""
    perms = DEFAULT_APP_PERMISSIONS.copy()
    for module_id, info in get_module_registry().items():
        if not is_module_enabled(module_id):
            for app_id in info.get("app_ids", []):
                perms.pop(app_id, None)
    return perms
```

Skill 的 prompt 片段（`SKILL.md` 的 markdown 區塊）已由 SkillManager 按 `requires_app` 過濾——模組停用 → app 權限不存在 → prompt 片段不載入 → 工具不出現在白名單。整條鏈已打通。

### Decision 10：Scheduler 條件排程

**選擇**：`scheduler.py` 的 `start_scheduler()` 遍歷啟用模組的 `scheduler_jobs`，動態註冊排程任務。

```python
def start_scheduler():
    # core 任務（永遠啟用）
    scheduler.add_job(cleanup_old_messages, CronTrigger(hour=3), ...)
    scheduler.add_job(create_next_month_partitions, CronTrigger(day=25, hour=4), ...)
    scheduler.add_job(cleanup_expired_share_links, IntervalTrigger(hours=1), ...)

    # 模組任務（依啟用狀態）
    for module_id, info in get_module_registry().items():
        if not is_module_enabled(module_id):
            continue
        for job in info.get("scheduler_jobs", []):
            _register_job(job)  # 解析 trigger 類型並註冊
```

## Risks / Trade-offs

**[Risk] 模組邊界切割不精確** → 功能可能跨模組（如 `prepare_file_message` 屬於 file-manager 但 Bot 會用）
→ Mitigation: 跨模組的通用工具歸入 `core`，只把純粹屬於特定功能的歸入該模組

**[Risk] `linebot_agents.py` 的硬編碼 Prompt 仍包含所有模組** → 首次部署會把完整 prompt 寫入 DB
→ Mitigation: 改為在 `ensure_default_linebot_agents()` 中呼叫 `generate_tools_prompt()` 動態產生種子值

**[Risk] 前端 `desktop.js` 改為 API 驅動後，API 失敗時桌面空白**
→ Mitigation: 保留 fallback 靜態清單，API 失敗時降級顯示

**[Risk] importlib 延遲載入可能隱藏 import 錯誤**
→ Mitigation: 載入失敗時 log warning 明確標示模組名稱；測試環境可設 strict mode

**[Risk] Skill 安裝的模組有品質問題** → MCP 工具有 bug 影響系統
→ Mitigation: Skill 模組載入用 `try/except`，失敗只 warning 不阻斷

**[Trade-off] Skill 第一階段不帶 router**
→ Skill 只能透過 MCP 工具擴充後端能力，不能新增 REST API。這簡化了安全模型（不需審查外部 router 的認證），但限制了 Skill 的能力上限。如果 Skill 需要自訂 API，可透過 MCP 工具作為中介，由 CTOS core 提供統一的 API 代理。

**[Trade-off] 統一 Skill 與模組意味著 SkillManager 成為核心依賴**
→ 如果 SkillManager 載入失敗，只有內建模組可用，Skill 擴充的模組全部不可用。這是可接受的降級行為。

## Migration Plan

### 階段一：內建模組可插拔（本次實作重點）
1. 建立 `modules.py`，定義 `BUILTIN_MODULES` 和 `is_module_enabled()`
2. `main.py` 路由改為 `importlib` 條件載入
3. `mcp/__init__.py` 改為條件載入
4. `scheduler.py` 改為條件排程
5. `config.py` 新增 `ENABLED_MODULES`
6. `/api/config/apps` 端點，前端改為動態載入
7. 現有部署不需任何設定變更（預設 `"*"`）

### 階段二：Skill contributes 擴充（後續迭代）
1. `hub_meta.py` 支援解析 `contributes` 區塊
2. `SkillManager` 安裝 Skill 時，將 `contributes` 寫入模組 registry
3. 前端 `desktop.js` 支援載入 Skill 提供的 JS/CSS
4. `mcp/__init__.py` 支援載入 Skill 的 `mcp_tools.py`
5. 排程器支援 Skill 宣告的排程任務

### Rollback
- 移除 `ENABLED_MODULES` 或設為 `"*"` → 恢復全模組載入
- 前端 API 失敗 → fallback 到靜態清單
- Skill 載入失敗 → 只有內建模組可用

## Open Questions

1. **`linebot_agents.py` 硬編碼 prompt 如何處理？**
   - 傾向在 `ensure_default_linebot_agents()` 中呼叫 `generate_tools_prompt()` 動態產生
   - 需確認啟動時 SkillManager 和 DB 是否已就緒（lifespan 順序）

2. **外部 MCP Server（ERPNext、nanobanana、printer）歸類？**
   - 選項 A：歸為 `BUILTIN_MODULES`（只有 prompt 片段和工具白名單，無 router/mcp_module）
   - 選項 B：改為 SkillHub 上的 Skill（用 `SKILL.md` 宣告 prompt 和工具）
   - 傾向 A（短期），長期遷移到 B

3. **`core` 模組的精確邊界？**
   - 明確 core：auth、user、session、database、health
   - 待決：`message_tools`、`memory_tools` 歸 core 還是獨立？
   - 待決：`ai_router`、`ai_management` 歸 `ai-agent` 模組？

4. **Skill 前端資源的 serve 方式？**
   - Skill 的 JS/CSS 放在 `~/SDD/skill/<name>/frontend/`
   - 需要一個 API 端點（如 `/api/skills/<name>/frontend/<file>`）來 serve 這些靜態檔案
   - 或在安裝時複製到 `frontend/js/skills/` 目錄
