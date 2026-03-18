# Extends 模組開發指南

> 本文件定義 `extends/` 子模組的開發規範，適用於所有外部模組（如 law、his、erpnext 等）。
> 開發新模組前請先閱讀本文件。

## 概述

`extends/` 目錄存放以 git submodule 形式管理的外部模組。每個模組可以獨立授權、版控、部署。主系統在啟動時自動掃描 `extends/*/contributes.yaml`，根據宣告內容整合模組功能。

**核心原則**：模組透過 `contributes.yaml` 宣告自己「提供什麼」，主系統負責載入和整合。模組不需要修改主系統的任何程式碼。

## 目錄結構慣例

```
extends/{module-name}/
├── contributes.yaml          # 必須 — 模組能力宣告
├── SKILL.md                  # 可選 — 模組級說明（僅供文件用途，不被 SkillManager 掃描）
├── README.md                 # 可選 — 模組說明
├── .gitignore                # 建議 — 排除 __pycache__
│
├── core/                     # 核心程式碼
│   ├── __init__.py
│   ├── mcp_tools.py          # MCP 工具定義（@mcp.tool() 註冊）
│   ├── models.py             # Pydantic 資料模型
│   ├── config.py             # 客戶設定載入
│   └── services/             # 業務邏輯
│       ├── __init__.py
│       └── xxx_service.py
│
├── skills/                   # CTOS Skills（AI 的 prompt 和工具權限）
│   └── {skill-name}/
│       └── SKILL.md          # 被 SkillManager 掃描的 Skill 定義
│
├── clients/                  # 多租戶客戶設定（可選）
│   ├── _template/
│   │   ├── config.yaml
│   │   ├── README.md
│   │   └── agents/
│   │       └── {agent-name}.md
│   └── {client-code}/
│       └── config.yaml
│
├── templates/                # 模板檔案（可選）
│
└── migrations/               # SQL 參考檔（可選，實際 migration 放主系統 Alembic）
```

### 重要：根目錄 SKILL.md vs skills/ 下的 SKILL.md

| 位置 | 用途 | 被掃描 |
|------|------|--------|
| `extends/{module}/SKILL.md` | 模組級說明文件，描述整體功能 | **否** — SkillManager 不掃描 |
| `extends/{module}/skills/{name}/SKILL.md` | AI Skill 定義（prompt + allowed-tools） | **是** — SkillManager 掃描載入 |

**不要**在根目錄 SKILL.md 的 `contributes.mcp_tools` 放 MCP 工具路徑 — 它不會被載入。MCP 工具載入由 `contributes.yaml` 的 `mcp_tools` 欄位控制。

## contributes.yaml 完整規格

`contributes.yaml` 是模組的能力宣告檔。所有欄位都是可選的，模組根據需求組合使用。

```yaml
# ============================================================
# contributes.yaml 完整欄位參考
# ============================================================

# 模組 ID（用於 ENABLED_MODULES 環境變數控制啟停）
# 如不設定，模組永遠啟用
module_id: my-module

# ── In-process MCP 工具 ──────────────────────────────────────
# 在主系統進程內執行的 MCP 工具
# 路徑相對於模組根目錄（extends/{module}/）
# 適用：需要存取主系統 DB、知識庫、NAS 的業務模組
mcp_tools: core/mcp_tools.py

# ── 外部 MCP Server ──────────────────────────────────────────
# 以獨立進程啟動的 MCP Server
# 適用：串接外部系統 API，不需要主系統 DB
mcp_servers:
  server-name:
    command: bash
    args: ["-c", "set -a && source ${PROJECT_ROOT}/.env && set +a && uvx some-mcp"]

# ── 生命週期 ─────────────────────────────────────────────────
# 模組啟動/關閉時執行的函式
# 適用：需要背景服務（輪詢、快取預熱、連線池初始化）
lifespan:
  startup:
    callable: core.some_module.start       # 相對 import 路徑
    kwargs:
      param1: ${ENV_VAR}                   # 支援 ${} 環境變數替換
      param2: 30
  shutdown:
    callable: core.some_module.stop

# ── API 路由 ─────────────────────────────────────────────────
# 註冊 FastAPI Router
# 適用：需要暴露 HTTP 端點（檔案下載、webhook 等）
routers:
  - module: my_router                      # Python 模組路徑
    attr: router                           # Router 物件名稱
    kwargs:
      prefix: /api/my-module
      tags: [my-module]
```

### 欄位詳細說明

#### `module_id`

```yaml
module_id: law
```

對應 `.env` 的 `ENABLED_MODULES` 環境變數。設定 `ENABLED_MODULES=*` 啟用全部，或明確列出要啟用的模組（逗號分隔）。如果不設定 `module_id`，模組永遠啟用。

#### `mcp_tools`（in-process MCP 工具）

```yaml
mcp_tools: core/mcp_tools.py
```

指向模組內的 Python 檔案，該檔案使用 `@mcp.tool()` 向主系統的 FastMCP 實例註冊工具。

**載入機制**：主系統的 `_start_extends_modules()` 在啟動時收集路徑，呼叫 `load_extends_mcp_tools()` 動態載入。自動建立隔離的 package context（`_extends_{module}_{dir}`），支援 relative import 且不會與其他模組衝突。

**mcp_tools.py 撰寫方式**：

```python
"""模組 MCP 工具定義"""

from ching_tech_os.services.mcp.server import mcp, ensure_db_connection
from .services import my_service    # relative import（自動解析）
from .models import MyModel

@mcp.tool()
async def my_tool(param: str) -> str:
    """工具說明（供 AI 理解用途）"""
    await ensure_db_connection()    # 存取 DB 前必須呼叫
    result = await my_service.do_something(param)
    return f"結果：{result}"
```

**注意事項**：
- 必須 `from ching_tech_os.services.mcp.server import mcp` 取得全域 MCP 實例
- 需要 DB 操作時必須先 `await ensure_db_connection()`
- 工具函式回傳 `str`（格式化文字供 AI 閱讀，不要回傳 JSON）
- relative import（`from .services import ...`）會自動解析，不需額外處理

#### `mcp_servers`（外部 MCP Server）

```yaml
mcp_servers:
  erpnext:
    command: bash
    args: ["-c", "set -a && source ${PROJECT_ROOT}/.env && set +a && uvx erpnext-mcp"]
```

啟動獨立進程作為 MCP Server，透過 stdio 通訊。`${PROJECT_ROOT}` 自動替換為專案根目錄。

**三種工具提供方式的選擇**：

| 條件 | 外部 MCP Server | in-process mcp_tools | Skill Script |
|------|---|---|---|
| 需要主系統 DB | ✗ | ✓ | ✗ |
| 串接外部 API | ✓ | ✓ | ✓ |
| 已有獨立 PyPI 套件 | ✓ | ✗ | ✗ |
| 需要程序隔離（穩定性） | ✓ | ✗ | ✓（獨立 process） |
| 效能敏感 | ✗ | ✓ | ✗ |
| 讀取本機檔案/快取 | ✗ | ✓ | ✓ |
| 不需改主系統程式碼 | ✓ | ✓ | ✓ |

#### Skill Script 模式

除了 MCP 工具外，extends 模組也可以透過 **Skill Script** 提供工具。AI 透過 `run_skill_script` 呼叫 `skills/{name}/scripts/*.py` 腳本。

```
skills/
└── my-skill/
    ├── SKILL.md          # Skill 定義（allowed-tools 包含 run_skill_script）
    └── scripts/
        ├── _common.py    # 共用工具函式
        └── my_query.py   # 工具腳本
```

**Script 接收 stdin 輸入（JSON），輸出結果到 stdout**。適用於不需要向 MCP Server 註冊工具、只需要 AI 透過 `run_skill_script` 呼叫的場景（如讀取本機快取資料、檔案處理）。

**何時用 Skill Script vs MCP 工具**：
- 工具需要被其他 MCP 客戶端（如 Claude Code CLI）直接呼叫 → 用 MCP 工具
- 工具只在 Bot AI 對話中使用、透過 `run_skill_script` 呼叫即可 → 用 Skill Script

#### `lifespan`（生命週期）

```yaml
lifespan:
  startup:
    callable: core.queue_cache.start_polling
    kwargs:
      dbf_base_path: ${CTHIS_DATA_PATH}
      interval: 30
  shutdown:
    callable: core.queue_cache.stop_polling
```

在主系統啟動/關閉時執行。`callable` 是相對於模組根目錄的 Python import 路徑（模組根目錄會自動加入 `sys.path`）。支援 sync 和 async 函式。`kwargs` 中的 `${ENV_VAR}` 會自動替換為環境變數值。

**適用場景**：背景輪詢（定期讀取外部資料）、快取預熱、連線池初始化。

#### `routers`（API 路由）

```yaml
routers:
  - module: tts_router
    attr: router
    kwargs:
      prefix: /api/voice
      tags: [voice]
```

將模組的 FastAPI Router 註冊到主系統。`module` 是 Python import 路徑（模組根目錄已在 `sys.path`）。

## Skills 開發

Skills 定義在 `skills/{skill-name}/SKILL.md`，由 SkillManager 自動掃描載入。

### SKILL.md 格式

```yaml
---
name: case-mgmt
description: 案件與當事人管理 — 建立案件、管理當事人、追蹤案件狀態
allowed-tools: "create_case get_case list_cases update_case"
metadata:
  ctos:
    requires_app: null          # 需要的前端 App 權限（null = 不需要）
    mcp_servers: ""             # 需要的外部 MCP Server 名稱
---

# Skill 標題

這裡是 AI 的 prompt 內容，描述如何使用這個 Skill 提供的工具。
```

**重要欄位**：
- `allowed-tools`：空格分隔的 MCP 工具名稱，控制此 Skill 可以使用哪些工具
- `metadata.ctos.requires_app`：如果設定，使用者需要有對應的 App 權限才能使用此 Skill
- `metadata.ctos.mcp_servers`：此 Skill 需要哪些外部 MCP Server（空格分隔）

### Skill 與 MCP 工具的關係

- `contributes.yaml` 的 `mcp_tools` 負責**載入和註冊**工具到 MCP Server
- `SKILL.md` 的 `allowed-tools` 負責控制 AI 在特定情境下**可以使用哪些**已註冊的工具
- 一個模組可以有多個 Skills，每個 Skill 開放不同的工具子集

## 資料庫 Migration

extends 模組如果需要 DB 表格，migration 放在**主系統**的 Alembic 目錄：

```
backend/migrations/versions/0XX_add_{module}_tables.py
```

模組內的 `migrations/` 目錄僅放 SQL 參考檔案供文件用途。

**原因**：主系統的 Alembic 不會掃描 extends 目錄下的 migration，而且 migration 的版本序列需要全域統一管理。

## 多租戶支援

如果模組需要支援多個客戶部署，使用 `clients/` 目錄：

```
clients/
├── _template/              # 新客戶範本
│   ├── config.yaml         # 設定範本
│   ├── README.md           # 部署檢查清單
│   └── agents/
│       └── assistant.md    # Agent prompt 範本
└── {client-code}/          # 各客戶獨立設定
    ├── config.yaml
    └── agents/
        └── assistant.md
```

透過環境變數選擇客戶：`{MODULE}_CLIENT=client-code`

設定載入邏輯放在 `core/config.py`：

```python
import os
from pathlib import Path

def get_config():
    client_code = os.environ.get("LAW_CLIENT", "")
    if not client_code:
        return DefaultConfig()
    config_path = Path(__file__).parent.parent / "clients" / client_code / "config.yaml"
    # ... 載入 config.yaml
```

## 環境變數慣例

模組相關的環境變數統一在 `.env` 中管理，命名慣例：

```bash
# 模組名稱大寫 + 底線
LAW_DATA_PATH=/mnt/nas/ctos/law/cases
LAW_CLIENT=firm-code

HIS_CLIENT=jfmskin
CTHIS_DATA_PATH=/mnt/nas/ctos/external-data/cthis-jfmskin/data
```

新增環境變數時，同步更新 `.env.example`。

## 現有模組參考

| 模組 | 類型 | 使用的 contributes.yaml 欄位 | 工具提供方式 | 說明 |
|------|------|------|------|------|
| **law** | git submodule | `module_id` + `mcp_tools` | in-process MCP 工具（12 個） | 律師事務所 AI 工作流 |
| **his** | git submodule | `module_id` + `lifespan` | Skill Script（5 個腳本） | 展望 HIS 整合，背景輪詢 DBF 資料 |
| **erpnext** | git submodule | `module_id` + `mcp_servers` | 外部 MCP Server | ERPNext ERP 整合 |
| **printer** | native | `module_id` + `mcp_servers` | 外部 MCP Server | 列印功能 |
| **voice** | native | `module_id` + `lifespan` + `routers` | 主系統 in-process MCP 工具 | 語音 STT/TTS |

## 開發新模組的步驟

### 1. 建立 Git Repo

```bash
gh repo create yazelin/ching-tech-{module} --private
```

### 2. 加入主專案為 Submodule

```bash
git submodule add https://github.com/yazelin/ching-tech-{module}.git extends/{module}
```

### 3. 建立 contributes.yaml

根據需求選填欄位：

```yaml
module_id: my-module
mcp_tools: core/mcp_tools.py     # 如果有 MCP 工具
```

### 4. 建立目錄結構

```bash
mkdir -p extends/{module}/core/services
mkdir -p extends/{module}/skills/{skill-name}
touch extends/{module}/core/__init__.py
touch extends/{module}/core/services/__init__.py
```

### 5. 實作 MCP 工具（如需要）

建立 `core/mcp_tools.py`：

```python
from ching_tech_os.services.mcp.server import mcp, ensure_db_connection

@mcp.tool()
async def my_tool(param: str) -> str:
    """工具說明"""
    await ensure_db_connection()
    # ... 業務邏輯
    return "結果"
```

### 6. 建立 Skills

建立 `skills/{name}/SKILL.md`，定義 AI 的 prompt 和允許的工具。

### 7. 建立 DB Migration（如需要）

在 `backend/migrations/versions/` 建立 Alembic migration 檔案。

### 8. 更新 .env.example

加入模組相關的環境變數說明。

### 9. 驗證

```bash
# 確認 contributes.yaml 被掃描
cd backend && uv run python -c "
from pathlib import Path
import yaml
for p in sorted(Path('../extends').glob('*/contributes.yaml')):
    print(f'{p.parent.name}: {yaml.safe_load(p.read_text())}')
"

# 確認 Skills 被載入
uv run python -c "
from ching_tech_os.skills import SkillManager
sm = SkillManager()
for s in sm.get_loaded_skills():
    if '{module}' in str(s.skill_dir):
        print(f'✓ {s.name} [{s.source}]')
"

# 確認 MCP 工具被載入（重啟服務後）
uv run python -c "
import asyncio
from ching_tech_os.services.mcp.server import mcp
async def test():
    tools = await mcp.list_tools()
    for t in tools:
        if 'my_tool' in t.name:
            print(f'✓ {t.name}')
asyncio.run(test())
"
```

## 常見問題

### MCP 工具沒有被載入

1. 確認 `contributes.yaml` 有 `mcp_tools` 欄位
2. 確認指向的檔案路徑存在（相對於模組根目錄）
3. 確認 `core/__init__.py` 存在
4. 重啟服務後查看 log：`journalctl -u ching-tech-os | grep "MCP 工具"`

### Relative import 失敗

`load_extends_mcp_tools()` 會自動建立隔離的 package context，支援最多 3 層子目錄的 relative import（如 `from .services.sub_module import ...`）。如果超過 3 層，需要手動在更深的子目錄建立 `__init__.py`。

### 與其他模組的 package 名稱衝突

不會衝突。每個模組的 package 以 `_extends_{module}_{dir}` 為前綴註冊到 `sys.modules`，完全隔離。例如 law 的 core 註冊為 `_extends_law_core`，his 的 core 註冊為 `_extends_his_core`。

### Skills 沒有被掃描到

確認目錄結構正確：`extends/{module}/skills/{skill-name}/SKILL.md`。SkillManager 只掃描 `extends/*/skills/*/SKILL.md`，不掃描根目錄的 SKILL.md。
