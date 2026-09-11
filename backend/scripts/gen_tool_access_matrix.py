#!/usr/bin/env python3
"""產生 MCP 工具存取矩陣（docs/mcp-tool-access-matrix.md）。

矩陣的每一欄都從程式內省而來，不是手寫的：
- app：`services/permissions.py` 的 `TOOL_APP_MAPPING`
- 未綁定可否呼叫：`APPS_REQUIRE_BOUND_USER` ＋ app 預設權限
  （`get_effective_app_permissions()`）＋ 工具內部的未綁定自檢
  （`TOOLS_REQUIRE_BOUND_USER`）＋ 工具原始碼裡到底有沒有呼叫
  `check_mcp_tool_permission`
- 是否寫入：`WRITE_TOOLS` registry
- 身分來源：工具簽章（`ctos_user_id`／`line_group_id`／`line_user_id`）

用法：
    uv run python scripts/gen_tool_access_matrix.py            # 寫入 docs/
    uv run python scripts/gen_tool_access_matrix.py --stdout   # 印到 stdout
    uv run python scripts/gen_tool_access_matrix.py --check    # 有漂移就 exit 1
"""

from __future__ import annotations

import argparse
import inspect
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DOC_PATH = REPO_ROOT / "docs" / "mcp-tool-access-matrix.md"

# 這份矩陣只描述 repo 內的 MCP 工具；Skill／extends 動態載入的工具依機器設定而異，
# 放進來會讓「重新產生要逐字相同」的測試變成看環境臉色。
IN_REPO_MODULE_PREFIX = "ching_tech_os.services.mcp."

# 工具原始碼裡代表「有做工具層權限檢查」的呼叫
_PERMISSION_CALL_MARKERS = ("check_mcp_tool_permission", "_guard(")

# 工具原始碼裡代表「bot 身分由伺服器注入」的呼叫
_BOT_IDENTITY_MARKERS = ("resolve_bot_identity(", "_connected_memory_scope(")

_DOC_HEADER = """# MCP 工具存取矩陣

> 本檔由 `backend/scripts/gen_tool_access_matrix.py` 從程式內省產生，**不要手改**。
> 改了工具或權限 registry 之後重跑一次；
> `backend/tests/test_mcp_tool_access_matrix.py` 會比對逐字相同，漂移就紅。

## 共同根因

這套權限設計假設呼叫者是已綁定的自己人，但 bot 對外開放，未綁定者一路走得進來。
四個 issue 都是同一個根因的不同出口：

| Issue | 出口 | 狀態 |
|-------|------|------|
| #201 | 未綁定者可查專案／往來對象／物料／NAS 檔案（app 預設開放） | 已修（PR #206，`APPS_REQUIRE_BOUND_USER`） |
| #207 | 未綁定者可用 `add_note`／`add_note_with_attachments` 寫進全域知識庫 | 已修（工具內部自檢 `TOOLS_REQUIRE_BOUND_USER`） |
| #204 | 記憶工具直接吃模型帶的 `line_group_id`／`line_user_id`，可冒充別的群組／別人 | 已修（`resolve_bot_identity`，伺服器注入優先） |
| #205 | 分享工具（`create_share_link`／`share_knowledge_attachment`）可把任何知識條目／NAS 檔案變成公開連結 | 已修（`share-manager` 進 `APPS_REQUIRE_BOUND_USER` ＋ `share.check_resource_access()`） |

四道關卡各擋不同的東西，缺一不可：

1. **app 權限**（`check_mcp_tool_permission`）：擋「這個人有沒有這個功能」。
2. **條目層級**（知識庫的 `_check_item_access`、記憶的擁有者條件）：擋「這一筆是不是你的」。
3. **工具內部自檢**（`require_bound_user`）：擋「憑空建立新資料」——沒有既有條目可比對的寫入。
4. **資源存取檢查**（`share.check_resource_access`）：擋「把讀不到的東西送出去」——
   建立公開連結前，knowledge 走 `check_knowledge_permission_async(..., action="read")`、
   nas_file 走帶 `source_permissions` 的 `validate_nas_file_path()`，與讀取工具同一條路。

## 欄位說明

- **App 權限**：`TOOL_APP_MAPPING` 的對應。`—（無需權限）` 表示 registry 明確標成
  不需要特定權限；`—（未登錄）` 表示這支工具根本不在 registry 裡，等同不檢查。
- **未綁定可呼叫**：LINE／Telegram 使用者沒有綁定 CTOS 帳號（`ctos_user_id is None`）時的結果。
  `否` 表示被擋在工具層；`是` 表示 app 權限這一關放行——知識庫工具還有條目層級
  （`_check_item_access`）在後面擋：未綁定只讀得到 `scope=global` 且 `is_public`
  的條目，對既有條目的寫入一律拒絕。`是（未檢查）` 表示這支工具連
  `check_mcp_tool_permission` 都沒呼叫，app 對應只是裝飾。
- **寫入**：會建立／修改／刪除資料，或產生檔案、對外送出內容。
- **身分來源**：`ctos_user_id` ＝ 伺服器用 `CTOS_USER_ID` 環境變數注入（`mcp.tool`
  包裝層強制，模型帶什麼都會被覆蓋）；`bot 身分（注入）` ＝ 走 `resolve_bot_identity()`，
  以 `CTOS_BOT_GROUP_ID`／`CTOS_BOT_USER_ID` 為準；`bot 身分（模型參數）` ＝ 工具收
  `line_group_id`／`line_user_id` 但還沒接上注入，模型帶進來的值會被採用（殘留風險，
  見下方「已知缺口」）；`無` ＝ 工具不帶身分。

"""


def _load_tools():
    """載入 repo 內的 MCP 工具並回傳 {tool_name: Tool}。"""
    # 讓結果不受本機 .env／呼叫端環境影響：硬設成全部啟用。
    # 用 setdefault 不夠——`ENABLED_MODULES=knowledge` 之類的值會讓
    # `get_effective_app_permissions()` 少掉被停用模組的 app，矩陣就跟著漂。
    os.environ["ENABLED_MODULES"] = "*"
    sys.path.insert(0, str(BACKEND_DIR / "src"))

    import importlib

    from ching_tech_os.services.mcp import mcp  # noqa: E402

    # 明確載入 repo 內的每一個工具模組（有些平常只在模組啟用時才載入）
    for path in sorted((BACKEND_DIR / "src/ching_tech_os/services/mcp").glob("*_tools.py")):
        try:
            importlib.import_module(f"ching_tech_os.services.mcp.{path.stem}")
        except Exception as exc:  # pragma: no cover - 只在環境壞掉時發生
            print(f"警告：載入 {path.stem} 失敗：{exc}", file=sys.stderr)

    return {
        name: tool
        for name, tool in mcp._tool_manager._tools.items()
        if tool.fn.__module__.startswith(IN_REPO_MODULE_PREFIX)
    }


def _tool_source(fn) -> str:
    try:
        return inspect.getsource(inspect.unwrap(fn))
    except (OSError, TypeError):  # pragma: no cover - 動態產生的函式才會走到
        return ""


def _classify(name: str, tool) -> dict:
    from ching_tech_os.services.permissions import (
        APPS_REQUIRE_BOUND_USER,
        APP_DISPLAY_NAMES,
        TOOL_APP_MAPPING,
        TOOLS_REQUIRE_BOUND_USER,
        WRITE_TOOLS,
        get_effective_app_permissions,
    )

    fn = inspect.unwrap(tool.fn)
    params = inspect.signature(fn).parameters
    source = _tool_source(tool.fn)
    checks_permission = any(marker in source for marker in _PERMISSION_CALL_MARKERS)

    if name not in TOOL_APP_MAPPING:
        app_cell = "—（未登錄）"
        app_id = None
    else:
        app_id = TOOL_APP_MAPPING[name]
        if app_id is None:
            app_cell = "—（無需權限）"
        else:
            app_cell = f"`{app_id}`（{APP_DISPLAY_NAMES.get(app_id, app_id)}）"

    if name in TOOLS_REQUIRE_BOUND_USER:
        unbound = "否（工具自檢）"
    elif not checks_permission:
        unbound = "是（未檢查）"
    elif app_id is None:
        unbound = "是"
    elif app_id in APPS_REQUIRE_BOUND_USER:
        unbound = "否（需綁定）"
    elif get_effective_app_permissions().get(app_id, False):
        unbound = "是"
    else:
        unbound = "否（需權限）"

    identity = []
    if "ctos_user_id" in params:
        identity.append("`ctos_user_id`")
    injects_bot_identity = any(
        marker in source for marker in _BOT_IDENTITY_MARKERS
    )
    takes_bot_params = "line_group_id" in params or "line_user_id" in params
    if injects_bot_identity:
        identity.append("bot 身分（注入）")
    elif takes_bot_params:
        identity.append("bot 身分（模型參數）")
    identity_cell = " ＋ ".join(identity) if identity else "無"

    return {
        "name": name,
        "module": fn.__module__.rsplit(".", 1)[-1],
        "app": app_cell,
        "unbound": unbound,
        "write": "是" if name in WRITE_TOOLS else "否",
        "identity": identity_cell,
    }


def _render_gaps(rows: list[dict]) -> list[str]:
    """已知缺口一節：由表格資料算出來，不手寫（手寫的清單三個月後就是假的）。"""

    def names(selected: list[dict]) -> str:
        return "、".join(f"`{r['name']}`" for r in selected)

    unchecked = [r for r in rows if r["unbound"] == "是（未檢查）"]
    model_param = [r for r in rows if "模型參數" in r["identity"]]
    unbound_writes = [
        r for r in rows if r["unbound"].startswith("是") and r["write"] == "是"
    ]
    unbound_writes_guarded = [
        r for r in unbound_writes if r["module"] == "knowledge_tools"
    ]
    unbound_writes_open = [
        r for r in unbound_writes if r["module"] != "knowledge_tools"
    ]
    unmapped_modules = sorted({r["module"] for r in rows if "未登錄" in r["app"]})

    lines = ["## 已知缺口（本次未修）", ""]

    lines.append(
        f"**沒有工具層權限檢查的 {len(unchecked)} 支**："
        f"{names(unchecked)}。"
        "這些工具連 `check_mcp_tool_permission()` 都沒呼叫，"
        "`TOOL_APP_MAPPING` 的對應只是裝飾，未綁定者只要模型肯呼叫就跑得動。"
        "目前尚未有對應 issue。"
    )
    lines.append("")
    lines.append(
        f"**完全不在 `TOOL_APP_MAPPING` 的模組（{len(unmapped_modules)} 個）**："
        + "、".join(f"`{m}`" for m in unmapped_modules)
        + "。新增工具沒登錄 registry 就等於不檢查，預設是開的。"
    )
    lines.append("")
    lines.append(
        f"**未綁定可呼叫又會寫入／送出的 {len(unbound_writes)} 支**："
        f"{names(unbound_writes_open)} 沒有第二道關卡"
        "（例如 `prepare_print_file` 會把檔案送進印表機佇列）；"
        f"{names(unbound_writes_guarded)} 還有條目層級 `_check_item_access()` 擋著，"
        "未綁定實際上寫不進去。"
    )
    lines.append("")
    lines.append(
        f"**bot 身分還是模型說了算的 {len(model_param)} 支**："
        f"{names(model_param)}。"
        "這些工具收 `line_group_id`／`line_user_id` 但沒接 `resolve_bot_identity()`，"
        "已綁定的使用者可以宣稱別的群組，把筆記寫進別的專案範圍或讀到別的群組的訊息附件。"
        "修法與 #204 相同，不在這支 PR 的範圍。"
    )
    lines.append("")
    lines.append(
        "**網頁聊天不注入身分**：`api/ai.py` 的 Socket.IO `ai_message` 走 "
        "`call_ai()` 時沒有帶 `ctos_user_id` 也沒有帶 `extra_mcp_env`（雖然 "
        "session 裡就有 `user_id`），那條路會起一個沒有任何身分環境變數的 MCP 子行程："
        "工具的 `ctos_user_id` 由模型參數決定、記憶工具吃模型帶的 id、"
        "`update_memory`／`delete_memory` 沒有擁有者範圍。"
        "進 socket 之前有 session 認證，所以不是匿名者能打的路，"
        "但同一個登入者可以指定別人的 id。"
    )
    lines.append("")
    return lines


def render() -> str:
    tools = _load_tools()
    rows = [_classify(name, tool) for name, tool in tools.items()]
    rows.sort(key=lambda r: (r["module"], r["name"]))

    total = len(rows)
    unbound_ok = sum(1 for r in rows if r["unbound"].startswith("是"))
    writes = sum(1 for r in rows if r["write"] == "是")

    lines = [_DOC_HEADER.rstrip("\n"), ""]
    lines.append(
        f"共 {total} 支工具：未綁定可呼叫 {unbound_ok} 支、寫入類 {writes} 支。"
    )
    lines.append("")
    lines.append("| 工具 | 模組 | App 權限 | 未綁定可呼叫 | 寫入 | 身分來源 |")
    lines.append("|------|------|----------|--------------|------|----------|")
    for row in rows:
        lines.append(
            f"| `{row['name']}` | `{row['module']}` | {row['app']} "
            f"| {row['unbound']} | {row['write']} | {row['identity']} |"
        )
    lines.append("")
    lines.extend(_render_gaps(rows))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="產生 MCP 工具存取矩陣")
    parser.add_argument("--stdout", action="store_true", help="印到 stdout，不寫檔")
    parser.add_argument("--check", action="store_true", help="比對現有檔案，有漂移回傳 1")
    args = parser.parse_args()

    content = render()

    if args.stdout:
        sys.stdout.write(content)
        return 0

    if args.check:
        current = DOC_PATH.read_text(encoding="utf-8") if DOC_PATH.exists() else ""
        if current != content:
            print(f"{DOC_PATH} 與程式內省結果不同，請重跑產生器", file=sys.stderr)
            return 1
        return 0

    DOC_PATH.write_text(content, encoding="utf-8")
    print(f"已寫入 {DOC_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
