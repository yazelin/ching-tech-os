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
_BOT_IDENTITY_MARKERS = (
    "resolve_bot_identity(",
    "_connected_memory_scope(",
    "resolve_conversation_scope(",
)

_DOC_HEADER = """# MCP 工具存取矩陣

> 本檔由 `backend/scripts/gen_tool_access_matrix.py` 從程式內省產生，**不要手改**。
> 改了工具或權限 registry 之後重跑一次；
> `backend/tests/test_mcp_tool_access_matrix.py` 會比對逐字相同，漂移就紅。

## 共同根因

這套權限設計假設呼叫者是已綁定的自己人，但 bot 對外開放，未綁定者一路走得進來。
下面這些 issue 都是同一個根因的不同出口：

| Issue | 出口 | 狀態 |
|-------|------|------|
| #201 | 未綁定者可查專案／往來對象／物料／NAS 檔案（app 預設開放） | 已修（PR #206，`APPS_REQUIRE_BOUND_USER`） |
| #207 | 未綁定者可用 `add_note`／`add_note_with_attachments` 寫進全域知識庫 | 已修（工具內部自檢 `TOOLS_REQUIRE_BOUND_USER`） |
| #204 | 記憶工具直接吃模型帶的 `line_group_id`／`line_user_id`，可冒充別的群組／別人 | 已修（`resolve_bot_identity`，伺服器注入優先） |
| #205 | 分享工具（`create_share_link`／`share_knowledge_attachment`）可把任何知識條目／NAS 檔案變成公開連結 | 已修（`share-manager` 進 `APPS_REQUIRE_BOUND_USER` ＋ `share.check_resource_access()`） |
| #209 | 知識庫／NAS／訊息工具還吃模型帶的 `line_group_id`／`line_user_id`，可寫進別的專案範圍、把檔案推到別的群組、讀別的群組的對話 | 已修（`resolve_bot_identity()` ＋ 讀對話類走 `resolve_conversation_scope()`） |
| #210 | 十幾支工具連 `check_mcp_tool_permission()` 都沒呼叫，`TOOL_APP_MAPPING` 只是裝飾 | 已修（逐支對到 app，或登記進 `TOOLS_INTENTIONALLY_OPEN` 並寫明理由） |

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
  `check_mcp_tool_permission` 都沒呼叫，app 對應只是裝飾（issue #210 之後應該是空的）；
  `是（登記開放）` 表示這支工具登記在 `permissions.TOOLS_INTENTIONALLY_OPEN`，
  是刻意對未綁定者開放的基礎功能，理由列在表格下方。
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
        TOOL_APP_MAPPING,
        TOOLS_INTENTIONALLY_OPEN,
        TOOLS_REQUIRE_BOUND_USER,
        WRITE_TOOLS,
        get_app_display_names,
        get_effective_app_permissions,
    )

    app_display_names = get_app_display_names()

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
            app_cell = f"`{app_id}`（{app_display_names.get(app_id, app_id)}）"

    if name in TOOLS_INTENTIONALLY_OPEN and checks_permission:
        # 「登記開放」與「有做 app 權限檢查」是兩個相反的決定。靜靜標成開放，
        # 矩陣就會謊報這支工具不受權限保護（或反過來），所以直接爆掉。
        raise ValueError(
            f"{name} 同時登記在 TOOLS_INTENTIONALLY_OPEN 又呼叫了權限檢查："
            "兩者只能擇一，請從 registry 拿掉或移除工具裡的檢查"
        )

    if name in TOOLS_REQUIRE_BOUND_USER:
        unbound = "否（工具自檢）"
    elif name in TOOLS_INTENTIONALLY_OPEN:
        unbound = "是（登記開放）"
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


def _render_intentionally_open() -> list[str]:
    """有意對未綁定開放的工具：理由直接抄 registry，矩陣不另寫一套說法。"""
    from ching_tech_os.services.permissions import TOOLS_INTENTIONALLY_OPEN

    lines = ["## 有意對未綁定開放的工具（issue #210）", ""]
    lines.append(
        "來源：`services/permissions.py` 的 `TOOLS_INTENTIONALLY_OPEN`。"
        "這裡列的是「看過、決定要開」，不是「還沒看」——"
        "沒登記又沒呼叫 `check_mcp_tool_permission()` 的工具，矩陣測試會紅。"
    )
    lines.append("")
    lines.append("| 工具 | 理由 |")
    lines.append("|------|------|")
    for name, reason in sorted(TOOLS_INTENTIONALLY_OPEN.items()):
        lines.append(f"| `{name}` | {reason} |")
    lines.append("")
    return lines


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

    lines = ["## 已知缺口", ""]

    if unchecked:
        lines.append(
            f"**沒有工具層權限檢查、也沒登記開放的 {len(unchecked)} 支**："
            f"{names(unchecked)}。"
            "這些工具連 `check_mcp_tool_permission()` 都沒呼叫，"
            "`TOOL_APP_MAPPING` 的對應只是裝飾，未綁定者只要模型肯呼叫就跑得動。"
        )
    else:
        lines.append(
            "**沒有工具層權限檢查、也沒登記開放的工具**：無（issue #210）。"
            "每一支不呼叫 `check_mcp_tool_permission()` 的工具都登記在 "
            "`TOOLS_INTENTIONALLY_OPEN`，理由見上一節。"
        )
    lines.append("")

    if unmapped_modules:
        lines.append(
            f"**完全不在 `TOOL_APP_MAPPING` 的模組（{len(unmapped_modules)} 個）**："
            + "、".join(f"`{m}`" for m in unmapped_modules)
            + "。新增工具沒登錄 registry 就等於不檢查，預設是開的。"
        )
    else:
        lines.append(
            "**完全不在 `TOOL_APP_MAPPING` 的模組**：無。"
            "但新增工具沒登錄 registry 還是等於不檢查，預設是開的——"
            "加工具時要一起決定。"
        )
    lines.append("")

    lines.append(
        f"**未綁定可呼叫又會寫入／送出的 {len(unbound_writes)} 支**："
        f"{names(unbound_writes_open)} 沒有 app 權限這一關"
        "（都登記在 `TOOLS_INTENTIONALLY_OPEN`：記憶靠注入身分分範圍，"
        "其餘只寫得到 `/tmp` 暫存區）；"
        f"{names(unbound_writes_guarded)} 還有條目層級 `_check_item_access()` 擋著，"
        "未綁定實際上寫不進去。"
    )
    lines.append("")

    if model_param:
        lines.append(
            f"**bot 身分還是模型說了算的 {len(model_param)} 支**："
            f"{names(model_param)}。"
            "這些工具收 `line_group_id`／`line_user_id` 但沒接 `resolve_bot_identity()`，"
            "已綁定的使用者可以宣稱別的群組，把筆記寫進別的專案範圍或讀到別的群組的訊息附件。"
        )
    else:
        lines.append(
            "**bot 身分還是模型說了算的工具**：無（issue #209）。"
            "收 `line_group_id`／`line_user_id` 的工具都先過 `resolve_bot_identity()`，"
            "**有注入時**（LINE／Telegram）模型帶的 id 一律被覆蓋。"
            "讀群組對話／附件的兩支再多一層 `resolve_conversation_scope()`："
            "沒有 bot 注入時要有 `ctos_user_id` 且與該群組有既有關聯才放行。"
            "網頁聊天的 `CTOS_USER_ID` 自 issue #231 起由 `api/ai.py` 從 session 注入，"
            "所以這一關在網頁端拿到的是伺服器驗過的身分，不是模型帶的值"
            "（見下方「網頁聊天的身分注入」）。"
        )
    lines.append("")
    lines.append(
        "**`send_nas_file` 的 `telegram_chat_id` 不在注入範圍**（issue #232）："
        "`build_bot_mcp_env()` 注入的是 `CTOS_BOT_GROUP_ID`／`CTOS_BOT_USER_ID`／"
        "`CTOS_BOT_PLATFORM`，Telegram 的 chat id 本身仍由模型參數決定。"
        "跨平台那一半已經擋掉（連線不是 Telegram 對話時模型帶的 chat id 一律忽略），"
        "剩下的是 Telegram 對話裡模型仍可指定同平台的別的 chat id。"
    )
    lines.append("")
    lines.append(
        "**網頁聊天的身分注入**（issue #231 已修）：`api/ai.py` 的 Socket.IO "
        "`ai_chat_event`／`compress_chat` 走 `call_ai()` 時帶 "
        "`ctos_user_id=session.user_id`，值取自進入事件時重新驗過的 session，"
        "不從 request body 也不從模型參數取；`call_ai()` 把它變成 MCP 子行程的 "
        "`CTOS_USER_ID`，`resolve_ctos_user_id()` 只認這個環境變數，"
        "模型在工具參數裡宣稱別人的 id 不算數。"
        "bot 專屬的 `CTOS_BOT_PLATFORM`／`CTOS_BOT_GROUP_ID`／`CTOS_BOT_USER_ID` "
        "不注入網頁端（網頁聊天沒有對應的對話身分）。"
        "剩下的是記憶工具：`add_memory`／`get_memories`／`update_memory`／"
        "`delete_memory` 的範圍是 bot 對話身分，網頁端沒有可注入的值，"
        "仍然吃模型帶的 `line_group_id`／`line_user_id`，不在 issue #231 的範圍內。"
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
    lines.extend(_render_intentionally_open())
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
