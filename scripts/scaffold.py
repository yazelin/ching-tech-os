#!/usr/bin/env python3
"""CTOS scaffold 產生器

產生內建 app / extends 模組 / AI Skill 的骨架檔案，並驗證 extends 模組的
contributes.yaml 宣告。只產生新檔案，不會修改任何既有檔案；需要手動接線的
步驟會在產生後印出清單。

用法：
    python scripts/scaffold.py app <app-id>
    python scripts/scaffold.py extends <module-name>
    python scripts/scaffold.py skill <skill-name> [--extends <module>]
    python scripts/scaffold.py validate

所有子命令都支援 --root 指定 repo 根目錄（預設為本腳本所在 repo 根目錄）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# validate 子命令需要 PyYAML（backend 環境已內建）；其他子命令不需要
try:
    import yaml
except ImportError:  # pragma: no cover - 取決於執行環境
    yaml = None

# 識別字規則：小寫字母/數字開頭結尾，中間可有 - 或 _
_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9_-]*[a-z0-9])?$")


# ============================================================
# 共用工具
# ============================================================


def default_root() -> Path:
    """預設 repo 根目錄 = 本腳本所在目錄的上一層（scripts/ 直屬 repo 根）"""
    return Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    """印出錯誤並以 exit code 1 結束"""
    print(f"錯誤：{message}", file=sys.stderr)
    raise SystemExit(1)


def validate_name(name: str, label: str) -> None:
    """驗證識別字格式（app-id / module-name / skill-name）"""
    if not _NAME_RE.match(name):
        fail(f"{label} 格式無效：{name!r}（僅允許小寫字母、數字、- 與 _，且頭尾須為字母或數字）")


def to_snake(name: str) -> str:
    """kebab-case 轉 snake_case（demo-widget -> demo_widget）"""
    return name.replace("-", "_")


def to_pascal(name: str) -> str:
    """kebab-case 轉 PascalCase（demo-widget -> DemoWidget）"""
    return "".join(part.capitalize() for part in re.split(r"[-_]", name) if part)


def render(template: str, mapping: dict[str, str]) -> str:
    """以 __KEY__ 佔位符替換產生檔案內容（避免與 JS/CSS 的大括號衝突）"""
    result = template
    for key, value in mapping.items():
        result = result.replace(f"__{key}__", value)
    return result


def write_files(files: dict[Path, str]) -> None:
    """寫入多個檔案；任一目標已存在時全部拒絕並 exit 1"""
    existing = [path for path in files if path.exists()]
    if existing:
        for path in existing:
            print(f"錯誤：目標檔案已存在，拒絕覆蓋：{path}", file=sys.stderr)
        raise SystemExit(1)
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"  已建立 {path}")


# ============================================================
# app 子命令：內建 app 骨架
# ============================================================

_API_TEMPLATE = '''"""__APP_ID__ API 路由

scaffold 產生的範本，請依實際需求修改。
"""

import logging

from fastapi import APIRouter, Depends

from ..models.auth import SessionData
from ..models.__SNAKE__ import __PASCAL__ItemListResponse
from ..services import __SNAKE__ as __SNAKE___service
from ..services.permissions import require_app_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/__APP_ID__", tags=["__APP_ID__"])


@router.get("/items", response_model=__PASCAL__ItemListResponse, summary="列出項目")
async def list_items(
    session: SessionData = Depends(require_app_permission("__APP_ID__")),
) -> __PASCAL__ItemListResponse:
    """範例端點：列出項目（請替換為實際業務邏輯）"""
    return await __SNAKE___service.list_items()
'''

_SERVICE_TEMPLATE = '''"""__APP_ID__ 服務層

scaffold 產生的範本，業務邏輯放這裡（API 路由保持薄層）。
"""

import logging

from ..models.__SNAKE__ import __PASCAL__Item, __PASCAL__ItemListResponse

logger = logging.getLogger(__name__)


async def list_items() -> __PASCAL__ItemListResponse:
    """範例：回傳項目列表（請替換為實際業務邏輯，如 DB 查詢）"""
    items = [__PASCAL__Item(id=1, name="範例項目")]
    return __PASCAL__ItemListResponse(items=items, total=len(items))
'''

_MODEL_TEMPLATE = '''"""__APP_ID__ 資料模型

scaffold 產生的範本，Pydantic 模型放這裡。
"""

from pydantic import BaseModel


class __PASCAL__Item(BaseModel):
    """範例項目"""

    id: int
    name: str


class __PASCAL__ItemListResponse(BaseModel):
    """項目列表回應"""

    items: list[__PASCAL__Item]
    total: int
'''

_JS_TEMPLATE = '''/**
 * ChingTech OS - __PASCAL__ Module
 * __APP_ID__ 桌面應用程式（scaffold 範本，請依需求修改）
 */

const __PASCAL__App = (function() {
  'use strict';

  let windowId = null;

  /**
   * 開啟視窗
   */
  function open() {
    // 已開啟則聚焦
    if (windowId && WindowModule.getWindowByAppId('__APP_ID__')) {
      WindowModule.focusWindow(windowId);
      return;
    }

    windowId = WindowModule.createWindow({
      title: '__APP_ID__',
      appId: '__APP_ID__',
      icon: 'mdi-application',
      width: 800,
      height: 600,
      content: `
        <div class="__APP_ID__-container">
          <div class="__APP_ID__-toolbar">
            <button class="__APP_ID__-refresh-btn">
              <span class="icon">${getIcon('mdi-refresh')}</span> 重新整理
            </button>
          </div>
          <div class="__APP_ID__-content">載入中...</div>
        </div>
      `,
      onClose: handleClose,
      onInit: handleInit
    });
  }

  /**
   * 視窗初始化
   * @param {HTMLElement} windowEl
   * @param {string} wId
   */
  function handleInit(windowEl, wId) {
    windowId = wId;

    const refreshBtn = windowEl.querySelector('.__APP_ID__-refresh-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => loadItems(windowEl));
    }

    loadItems(windowEl);
  }

  /**
   * 載入項目列表（fetch 會由 config.js 自動加上 API_BASE）
   * @param {HTMLElement} windowEl
   */
  async function loadItems(windowEl) {
    const content = windowEl.querySelector('.__APP_ID__-content');
    if (!content) return;
    content.textContent = '載入中...';
    try {
      const response = await fetch('/api/__APP_ID__/items');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      content.textContent = `共 ${data.total} 筆項目：` +
        data.items.map((item) => item.name).join('、');
    } catch (e) {
      content.textContent = '載入失敗，請稍後再試';
    }
  }

  /**
   * 視窗關閉
   */
  function handleClose() {
    windowId = null;
  }

  // Public API
  return {
    open
  };
})();
// 將模組掛載到 window，供 desktop.js lazy-loader 偵測
window.__PASCAL__App = __PASCAL__App;
'''

_CSS_TEMPLATE = '''/* ==========================================================================
   ChingTech OS - __PASCAL__ Styles（scaffold 範本，請依需求修改）
   ========================================================================== */

.__APP_ID__-container {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  color: var(--text-primary);
}

.__APP_ID__-toolbar {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  border-bottom: 1px solid var(--border-light);
  background: var(--bg-surface);
}

.__APP_ID__-refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: var(--text-primary);
  cursor: pointer;
}

.__APP_ID__-refresh-btn:hover {
  background: var(--color-primary-hover);
}

.__APP_ID__-content {
  flex: 1;
  padding: var(--spacing-md);
  overflow: auto;
  color: var(--text-secondary);
}
'''


def cmd_app(args: argparse.Namespace) -> None:
    """產生內建 app 骨架（5 個新檔案）並印出手動接線清單"""
    app_id = args.app_id
    validate_name(app_id, "app-id")
    root = args.root
    snake = to_snake(app_id)
    pascal = to_pascal(app_id)
    mapping = {"APP_ID": app_id, "SNAKE": snake, "PASCAL": pascal}

    files = {
        root / "backend" / "src" / "ching_tech_os" / "api" / f"{snake}.py":
            render(_API_TEMPLATE, mapping),
        root / "backend" / "src" / "ching_tech_os" / "services" / f"{snake}.py":
            render(_SERVICE_TEMPLATE, mapping),
        root / "backend" / "src" / "ching_tech_os" / "models" / f"{snake}.py":
            render(_MODEL_TEMPLATE, mapping),
        root / "frontend" / "js" / f"{app_id}.js":
            render(_JS_TEMPLATE, mapping),
        root / "frontend" / "css" / f"{app_id}.css":
            render(_CSS_TEMPLATE, mapping),
    }

    print(f"產生內建 app 骨架：{app_id}")
    write_files(files)

    print(f"""
接下來手動做（scaffold 不會改動既有檔案）：

1. backend/src/ching_tech_os/modules.py — BUILTIN_MODULES 加入 entry：

    "{app_id}": {{
        "id": "{app_id}",
        "source": "builtin",
        "routers": [{{"module": ".api.{snake}", "attr": "router"}}],
        "app_ids": ["{app_id}"],
        "app_manifest": [
            {{"id": "{app_id}", "name": "顯示名稱", "icon": "mdi-application"}},
        ],
        "permission_defaults": {{"{app_id}": True}},
        "permission_display_names": {{"{app_id}": "顯示名稱"}},
    }},

2. frontend/index.html — 引入 CSS（login.html 也需要此樣式時一併加入）：

    <link rel="stylesheet" href="css/{app_id}.css">

3. frontend/js/desktop.js — 註冊 app：
   - fallbackApplications 加入：

    {{ id: '{app_id}', name: '顯示名稱', icon: 'mdi-application' }},

   - fallbackAppLoaders 加入（lazy-loading 動態載入）：

    '{app_id}': {{ src: './js/{app_id}.js', globalName: '{pascal}App' }},

4. 權限預設值 — 上方 modules.py entry 的 permission_defaults / permission_display_names；
   default 設 False 表示預設關閉，需管理員逐一開通。

5. 資料庫 — 如需新表格，建立 backend/migrations/versions/0XX_add_{snake}_tables.py，
   再執行：cd backend && uv run alembic upgrade head

6. docs/module-index.md — 補上後端/前端模組地圖對照。
""")


# ============================================================
# extends 子命令：extends 模組骨架
# ============================================================

_CONTRIBUTES_TEMPLATE = '''# __MODULE__ 模組對主系統的貢獻宣告
# 主系統啟動時掃描 extends/*/contributes.yaml 自動整合
# 欄位規格詳見 docs/extends-module.md

# 模組 ID（對應 .env 的 ENABLED_MODULES；不設定則模組永遠啟用）
module_id: __MODULE__

# ── In-process MCP 工具 ──────────────────────────────────────
# 在主系統進程內執行的 MCP 工具，路徑相對於模組根目錄
# 適用：需要存取主系統 DB、知識庫、NAS 的業務模組
# mcp_tools: core/mcp_tools.py

# ── 外部 MCP Server ──────────────────────────────────────────
# 以獨立進程啟動的 MCP Server，透過 stdio 通訊
# 適用：串接外部系統 API、已有獨立 PyPI 套件、需要程序隔離
# mcp_servers:
#   __MODULE__:
#     command: uvx
#     args: [__MODULE__-mcp]

# ── 生命週期 ─────────────────────────────────────────────────
# 模組啟動/關閉時執行的函式（callable 為相對模組根目錄的 import 路徑）
# 適用：背景輪詢、快取預熱、連線池初始化；kwargs 支援 ${ENV_VAR} 替換
# lifespan:
#   startup:
#     callable: core.startup.start
#     kwargs:
#       interval: 30
#   shutdown:
#     callable: core.startup.stop

# ── API 路由 ─────────────────────────────────────────────────
# 註冊 FastAPI Router 到主系統（module 為 import 路徑，模組根目錄已在 sys.path）
# routers:
#   - module: my_router
#     attr: router
#     kwargs:
#       prefix: /api/__MODULE__
#       tags:
#         - __MODULE__
'''

_CORE_INIT_TEMPLATE = '''"""__MODULE__ 模組核心程式碼"""
'''

_MCP_TOOLS_TEMPLATE = '''"""__MODULE__ 模組 MCP 工具定義

啟用方式：在 contributes.yaml 取消註解 mcp_tools: core/mcp_tools.py。
主系統會自動以隔離的 package context 載入（支援 relative import）。
"""

from ching_tech_os.services.mcp.server import mcp, ensure_db_connection


@mcp.tool()
async def __SNAKE___example(param: str) -> str:
    """範例工具（請替換為實際功能說明，供 AI 理解用途）"""
    await ensure_db_connection()  # 存取 DB 前必須呼叫
    return f"__MODULE__ 範例結果：{param}"
'''

_EXTENDS_README_TEMPLATE = '''# __MODULE__

CTOS extends 模組（scaffold 產生的骨架，請補上實際說明）。

## 功能

- （待補）

## 結構

```
extends/__MODULE__/
├── contributes.yaml   # 模組能力宣告（mcp_tools / mcp_servers / lifespan / routers）
├── core/              # 核心程式碼
│   ├── __init__.py
│   └── mcp_tools.py   # MCP 工具範本（啟用前先在 contributes.yaml 取消註解）
└── skills/            # AI Skills（可用 scripts/scaffold.py skill <name> --extends __MODULE__ 產生）
```

開發規範見主專案 `docs/extends-module.md`。
'''


def cmd_extends(args: argparse.Namespace) -> None:
    """產生 extends 模組骨架"""
    module = args.module_name
    validate_name(module, "module-name")
    root = args.root
    module_dir = root / "extends" / module
    mapping = {"MODULE": module, "SNAKE": to_snake(module)}

    files = {
        module_dir / "contributes.yaml": render(_CONTRIBUTES_TEMPLATE, mapping),
        module_dir / "core" / "__init__.py": render(_CORE_INIT_TEMPLATE, mapping),
        module_dir / "core" / "mcp_tools.py": render(_MCP_TOOLS_TEMPLATE, mapping),
        module_dir / "README.md": render(_EXTENDS_README_TEMPLATE, mapping),
    }

    print(f"產生 extends 模組骨架：{module}")
    write_files(files)

    print(f"""
接下來手動做：

1. contributes.yaml 內四種貢獻（mcp_tools / mcp_servers / lifespan / routers）
   預設全註解，依需求取消註解並實作對應檔案。
2. 如為獨立 repo：gh repo create 後以 git submodule add 加入 extends/{module}。
3. 模組環境變數加入 .env 與 .env.example（命名慣例：{to_snake(module).upper()}_*）。
4. 如需 DB 表格，migration 放主系統 backend/migrations/versions/（Alembic 不掃描 extends）。
5. 驗證宣告：python scripts/scaffold.py validate
""")


# ============================================================
# skill 子命令：CTOS AI Skill 骨架
# ============================================================

_SKILL_MD_TEMPLATE = '''---
name: __SKILL__
description: __SKILL__ 功能說明（請修改為一句話描述，供 AI 判斷何時使用）
allowed-tools: mcp__ching-tech-os__run_skill_script
metadata:
  ctos:
    requires_app: null
    mcp_servers: ching-tech-os
---

【__SKILL__】
這裡是 AI 的 prompt 內容，描述如何使用這個 Skill 提供的工具（請修改）。

透過 `run_skill_script` 呼叫的腳本：

- `example`: 範例腳本（讀取 stdin JSON，輸出 JSON 到 stdout）
  · input: {"name": "世界"}
  · name: 問候對象（可選，預設 "世界"）
'''

_SKILL_SCRIPT_TEMPLATE = '''#!/usr/bin/env python3
"""範例腳本：讀取 stdin JSON 輸入，輸出 JSON 結果到 stdout（scaffold 範本）"""

import json
import sys


def main() -> int:
    # 解析 stdin JSON 物件（空輸入視為 {}）
    raw = sys.stdin.read().strip()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        print(json.dumps({"success": False, "error": "invalid_input: 無效的 JSON 輸入"}, ensure_ascii=False))
        return 1
    if not isinstance(payload, dict):
        print(json.dumps({"success": False, "error": "invalid_input: input 必須是 JSON 物件"}, ensure_ascii=False))
        return 1

    name = payload.get("name") or "世界"

    # 實際業務邏輯放這裡，結果輸出到 stdout
    print(json.dumps({
        "success": True,
        "output": f"你好，{name}",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def cmd_skill(args: argparse.Namespace) -> None:
    """產生 CTOS AI Skill 骨架（SKILL.md + scripts/）"""
    skill = args.skill_name
    validate_name(skill, "skill-name")
    root = args.root

    if args.extends:
        validate_name(args.extends, "extends 模組名稱")
        module_dir = root / "extends" / args.extends
        skill_dir = module_dir / "skills" / skill
        if not (module_dir / "contributes.yaml").exists():
            print(
                f"提醒：{module_dir / 'contributes.yaml'} 尚不存在，"
                f"可先執行 python scripts/scaffold.py extends {args.extends}"
            )
    else:
        skill_dir = root / "backend" / "src" / "ching_tech_os" / "skills" / skill

    mapping = {"SKILL": skill}
    files = {
        skill_dir / "SKILL.md": render(_SKILL_MD_TEMPLATE, mapping),
        skill_dir / "scripts" / "example.py": render(_SKILL_SCRIPT_TEMPLATE, mapping),
    }

    print(f"產生 Skill 骨架：{skill}")
    write_files(files)

    print("""
接下來手動做：

1. 修改 SKILL.md 的 description 與 prompt 內容；allowed-tools 列出此 Skill
   可使用的 MCP 工具（空格分隔）。
2. metadata.ctos.requires_app 如需綁定前端 App 權限，填入 app id。
3. scripts/ 下的腳本以 run_skill_script 呼叫：讀 stdin JSON、輸出 stdout。
4. 重啟服務後確認 SkillManager 有掃描到此 Skill。
""")


# ============================================================
# validate 子命令：驗證 extends/*/contributes.yaml
# ============================================================


def _module_file_exists(module_dir: Path, import_path: str) -> bool:
    """檢查 import 路徑對應的模組檔是否存在（相對模組根目錄）

    例：core.queue_cache -> core/queue_cache.py 或 core/queue_cache/__init__.py
    """
    rel = Path(*import_path.split("."))
    return (module_dir / rel.with_suffix(".py")).is_file() or (module_dir / rel / "__init__.py").is_file()


def _check_callable(module_dir: Path, callable_path: str, label: str, problems: list[str]) -> None:
    """檢查 lifespan callable 的模組檔存在（最後一段為函式名）"""
    parts = callable_path.split(".")
    if len(parts) < 2:
        problems.append(f"{label} callable 格式無效（需含模組路徑與函式名）：{callable_path}")
        return
    module_path = ".".join(parts[:-1])
    if not _module_file_exists(module_dir, module_path):
        problems.append(f"{label} callable 的模組檔不存在：{callable_path}（找不到 {module_path} 對應檔案）")


def _validate_module(contrib_path: Path, seen_ids: dict[str, str]) -> list[str]:
    """驗證單一 contributes.yaml，回傳問題清單"""
    module_dir = contrib_path.parent
    module_name = module_dir.name
    problems: list[str] = []

    try:
        config = yaml.safe_load(contrib_path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"YAML 解析失敗：{e}"]

    if not isinstance(config, dict):
        return ["contributes.yaml 不是 YAML 物件（mapping），主系統會略過此模組"]

    # module_id 唯一性
    module_id = config.get("module_id")
    if module_id is not None:
        if not isinstance(module_id, str) or not module_id:
            problems.append(f"module_id 必須是非空字串：{module_id!r}")
        elif module_id in seen_ids:
            problems.append(f"module_id 重複：{module_id}（已被 extends/{seen_ids[module_id]} 使用）")
        else:
            seen_ids[module_id] = module_name

    # mcp_tools：檔案路徑存在
    mcp_tools = config.get("mcp_tools")
    if mcp_tools is not None:
        if not isinstance(mcp_tools, str):
            problems.append(f"mcp_tools 必須是字串路徑：{mcp_tools!r}")
        elif not (module_dir / mcp_tools).is_file():
            problems.append(f"mcp_tools 檔案不存在：{mcp_tools}")

    # lifespan：startup/shutdown callable 的模組檔存在
    lifespan = config.get("lifespan")
    if lifespan is not None:
        if not isinstance(lifespan, dict):
            problems.append(f"lifespan 必須是物件：{lifespan!r}")
        else:
            for phase in ("startup", "shutdown"):
                cfg = lifespan.get(phase)
                if cfg is None:
                    continue
                if isinstance(cfg, dict):
                    callable_path = cfg.get("callable")
                    if not isinstance(callable_path, str) or not callable_path:
                        problems.append(f"lifespan.{phase} 缺少 callable 欄位")
                    else:
                        _check_callable(module_dir, callable_path, f"lifespan.{phase}", problems)
                elif isinstance(cfg, str):
                    # 主系統允許 shutdown 直接寫字串
                    _check_callable(module_dir, cfg, f"lifespan.{phase}", problems)
                else:
                    problems.append(f"lifespan.{phase} 格式無效：{cfg!r}")

    # routers：module 的模組檔存在
    routers = config.get("routers")
    if routers is not None:
        if not isinstance(routers, list):
            problems.append(f"routers 必須是清單：{routers!r}")
        else:
            for i, spec in enumerate(routers):
                if not isinstance(spec, dict):
                    problems.append(f"routers[{i}] 必須是物件：{spec!r}")
                    continue
                router_module = spec.get("module")
                if not isinstance(router_module, str) or not router_module:
                    problems.append(f"routers[{i}] 缺少 module 欄位")
                elif not _module_file_exists(module_dir, router_module):
                    problems.append(f"routers[{i}] 的模組檔不存在：{router_module}")

    # mcp_servers：每個 server 必須有 command 欄位
    mcp_servers = config.get("mcp_servers")
    if mcp_servers is not None:
        if not isinstance(mcp_servers, dict):
            problems.append(f"mcp_servers 必須是物件：{mcp_servers!r}")
        else:
            for server_name, spec in mcp_servers.items():
                if not isinstance(spec, dict):
                    problems.append(f"mcp_servers.{server_name} 必須是物件：{spec!r}")
                    continue
                command = spec.get("command")
                if not isinstance(command, str) or not command:
                    problems.append(f"mcp_servers.{server_name} 缺少 command 欄位")

    return problems


def cmd_validate(args: argparse.Namespace) -> None:
    """掃描 extends/*/contributes.yaml 並驗證宣告"""
    if yaml is None:
        fail(
            "驗證需要 PyYAML，請改用 backend 環境執行：\n"
            "  cd backend && uv run python ../scripts/scaffold.py validate"
        )

    root = args.root
    extends_root = root / "extends"
    if not extends_root.is_dir():
        fail(f"找不到 extends 目錄：{extends_root}")

    contrib_paths = sorted(extends_root.glob("*/contributes.yaml"))
    if not contrib_paths:
        print(f"extends 目錄下沒有任何 contributes.yaml：{extends_root}")
        return

    seen_ids: dict[str, str] = {}
    total_problems = 0
    for contrib_path in contrib_paths:
        module_name = contrib_path.parent.name
        problems = _validate_module(contrib_path, seen_ids)
        if problems:
            total_problems += len(problems)
            print(f"extends/{module_name}:")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print(f"extends/{module_name}: ok")

    if total_problems:
        print(f"\n驗證失敗：共 {total_problems} 個問題")
        raise SystemExit(1)
    print(f"\n驗證通過：{len(contrib_paths)} 個模組")


# ============================================================
# CLI 入口
# ============================================================


def build_parser() -> argparse.ArgumentParser:
    """建立 argparse 解析器"""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="repo 根目錄（預設為本腳本所在 repo 根）",
    )

    parser = argparse.ArgumentParser(
        prog="scaffold.py",
        description="CTOS scaffold 產生器：產生 app / extends / skill 骨架並驗證 contributes.yaml",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_app = sub.add_parser("app", parents=[common], help="產生內建 app 骨架（後端三層 + 前端 JS/CSS）")
    p_app.add_argument("app_id", metavar="app-id", help="app 識別字（kebab-case，如 demo-widget）")
    p_app.set_defaults(func=cmd_app)

    p_ext = sub.add_parser("extends", parents=[common], help="產生 extends 模組骨架")
    p_ext.add_argument("module_name", metavar="module-name", help="模組名稱（如 my-module）")
    p_ext.set_defaults(func=cmd_extends)

    p_skill = sub.add_parser("skill", parents=[common], help="產生 CTOS AI Skill 骨架")
    p_skill.add_argument("skill_name", metavar="skill-name", help="Skill 名稱（如 my-skill）")
    p_skill.add_argument("--extends", metavar="module", help="放到 extends/<module>/skills/ 下")
    p_skill.set_defaults(func=cmd_skill)

    p_val = sub.add_parser("validate", parents=[common], help="驗證 extends/*/contributes.yaml")
    p_val.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI 進入點"""
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        fail(f"--root 目錄不存在：{root}")
    args.root = root
    args.func(args)


if __name__ == "__main__":
    main()
