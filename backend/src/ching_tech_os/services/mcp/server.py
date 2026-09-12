"""MCP Server 核心模組

FastMCP 實例和共用輔助函數。
"""

import functools
import inspect
import logging
import os
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP

from ...database import get_connection, init_db_pool
from ...utils.jsonb import parse_json_dict

# 訊息常數集中在 permissions.py（與 BOUND_USER_REQUIRED_MESSAGE 放一起），
# 這裡 re-export 讓工具端沿用 `mcp_server.XXX` 的既有寫法。
from ..permissions import (  # noqa: F401
    BOT_GROUP_SCOPE_DENIED_MESSAGE,
    BOT_IDENTITY_REQUIRED_MESSAGE,
)

logger = logging.getLogger("mcp_server")

# 台北時區 (UTC+8)
TAIPEI_TZ = timezone(timedelta(hours=8))

# 知識庫「列出全部」的特殊查詢關鍵字
_LIST_ALL_KNOWLEDGE_QUERIES = {"*", "all", "全部", "列表", ""}


def to_taipei_time(dt: datetime) -> datetime:
    """將 datetime 轉換為台北時區"""
    if dt is None:
        return None
    # 如果是 naive datetime，假設為 UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TAIPEI_TZ)

# 建立 FastMCP Server 實例
mcp = FastMCP(
    "ching-tech-os",
    instructions="擎添工業 OS 的 AI 工具，可查詢專案、會議、成員等資訊。",
)


def _tool_with_identity(*deco_args, **deco_kwargs):
    """mcp.tool 的包裝：工具簽章有 ctos_user_id 就自動用 resolve_ctos_user_id 填。

    身分由伺服器端保證，不再依賴模型記得帶參數
    （bypassPermissions 模式下 on_tool_input_transform 不會被呼叫）。
    """
    register = _original_tool(*deco_args, **deco_kwargs)

    def decorator(fn):
        sig = inspect.signature(fn)
        if "ctos_user_id" not in sig.parameters:
            return register(fn)

        @functools.wraps(fn)
        async def with_identity(*args, **kwargs):
            bound = sig.bind_partial(*args, **kwargs)
            bound.arguments["ctos_user_id"] = resolve_ctos_user_id(
                bound.arguments.get("ctos_user_id")
            )
            return await fn(*bound.args, **bound.kwargs)

        return register(with_identity)

    return decorator


_original_tool = mcp.tool
mcp.tool = _tool_with_identity


# ============================================================
# 資料庫連線輔助函數
# ============================================================


async def ensure_db_connection():
    """確保資料庫連線池已初始化（懶初始化）"""
    from ...database import _pool
    if _pool is None:
        logger.info("初始化資料庫連線池...")
        await init_db_pool()


# ============================================================
# 使用者身份輔助函數
# ============================================================


def resolve_ctos_user_id(ctos_user_id: int | None) -> int | None:
    """解析 ctos_user_id：環境變數優先，只認伺服器驗過的身分。

    claude_agent 為每個 session 啟動 MCP 子行程時，會把該 LINE/Telegram
    使用者綁定的 ctos_user_id 放進 CTOS_USER_ID 環境變數。這是伺服器驗過的
    身分，模型在工具參數裡打什麼都不能覆蓋（防冒充）。

    環境變數不存在時才採用參數。實際上就是網頁聊天：`api/ai.py` 呼叫 `call_ai()`
    沒有帶 ctos_user_id 也沒有帶 extra_mcp_env（見 docs/mcp-tool-access-matrix.md
    的已知缺口）。`execute_tool()` 目前只有 MCP server 內部的 skill fallback 在用。
    """
    env_val = os.environ.get("CTOS_USER_ID")
    if env_val:
        try:
            return int(env_val)
        except ValueError:
            pass
    return ctos_user_id


def require_bound_user(tool_name: str, ctos_user_id: int | None) -> str | None:
    """工具層級的未綁定自檢（issue #207）。

    `check_mcp_tool_permission` 擋的是「app 權限」，`_check_item_access` 擋的是
    「既有條目」。`add_note` 這類「憑空建立條目」的工具兩者都套不上——未綁定者
    沒有帳號可歸屬，卻能把內容寫進全域知識庫。名單放在
    `permissions.TOOLS_REQUIRE_BOUND_USER`，同時是存取矩陣的來源。

    Args:
        tool_name: 工具名稱（不含 mcp__ching-tech-os__ 前綴）
        ctos_user_id: CTOS 用戶 ID（會先走 resolve_ctos_user_id 認伺服器身分）

    Returns:
        None 表示放行；否則回傳要給使用者的錯誤訊息
    """
    from ..permissions import BOUND_USER_REQUIRED_MESSAGE, TOOLS_REQUIRE_BOUND_USER

    if tool_name not in TOOLS_REQUIRE_BOUND_USER:
        return None
    if resolve_ctos_user_id(ctos_user_id) is not None:
        return None
    return BOUND_USER_REQUIRED_MESSAGE


def resolve_bot_identity(
    line_group_id: str | None,
    line_user_id: str | None,
) -> tuple[str | None, str | None]:
    """解析 bot 對話身分：伺服器注入優先，模型參數只在沒有注入時採用（issue #204）。

    與 `resolve_ctos_user_id` 同一套想法：bot 走 MCP 子行程時，呼叫端把這次
    對話的身分放進環境變數（`CTOS_BOT_GROUP_ID`／`CTOS_BOT_USER_ID`，群組沿用
    既有的 `CTOS_GROUP_ID`），模型在工具參數裡宣稱別人的 id 一律無效。

    模型「挑哪一種記憶」（群組 vs 個人）的意圖會保留，被換掉的只有 id 的值：
    - 模型只帶 group → 用注入的群組 id（沒有注入的群組 id 就退回個人身分）
    - 模型只帶 user → 用注入的個人 id
    - 兩個都帶或都沒帶 → 兩個都用注入值（工具本身是群組優先）

    環境變數都不存在時才採用參數——目前實際上就是網頁聊天（`api/ai.py` 呼叫
    `call_ai()` 沒有帶 `extra_mcp_env`），那條路的身分仍由模型參數決定，
    缺口記在 `docs/mcp-tool-access-matrix.md`。

    Args:
        line_group_id: 模型帶進來的群組 UUID（bot_groups.id）
        line_user_id: 模型帶進來的平台使用者 ID（bot_users.platform_user_id）

    Returns:
        (line_group_id, line_user_id)：實際要用的身分
    """
    env_group = os.environ.get("CTOS_BOT_GROUP_ID") or os.environ.get("CTOS_GROUP_ID")
    env_user = os.environ.get("CTOS_BOT_USER_ID")

    if not env_group and not env_user:
        return line_group_id, line_user_id

    if line_group_id and not line_user_id:
        resolved_group, resolved_user = env_group, None
    elif line_user_id and not line_group_id:
        resolved_group, resolved_user = None, env_user
    else:
        resolved_group, resolved_user = env_group, env_user

    # 模型指定的種類在這次連線不存在（例如個人對話卻要寫群組記憶）：退回連線身分
    if not resolved_group and not resolved_user:
        resolved_group, resolved_user = env_group, env_user

    if (line_group_id and line_group_id != resolved_group) or (
        line_user_id and line_user_id != resolved_user
    ):
        logger.warning("[memory] 模型帶入的 id 與連線身分不符，已改用連線身分")

    return resolved_group, resolved_user


def has_bot_identity_injection() -> bool:
    """這條 MCP 連線有沒有被注入 bot 對話身分。

    有注入＝呼叫端（LINE／Telegram）已經驗過是誰在講話，`resolve_bot_identity()`
    的回傳值就是可信的。沒有注入＝目前實際上就是網頁聊天（`api/ai.py` 呼叫
    `call_ai()` 沒有帶 `extra_mcp_env`），身分只能從 `ctos_user_id` 再驗一次。
    """
    return bool(
        os.environ.get("CTOS_BOT_GROUP_ID")
        or os.environ.get("CTOS_GROUP_ID")
        or os.environ.get("CTOS_BOT_USER_ID")
    )


async def _ctos_user_in_bot_group(ctos_user_id: int, line_group_id: str) -> bool:
    """這個 CTOS 使用者有沒有參與這個 bot 群組。

    沒有 bot_group_members 這張表，既有的關聯只有兩條：
    `bot_users.user_id`（綁定的 CTOS 帳號）與 `bot_messages`（誰在哪個群組發過話）。
    沿用同一條關聯：綁定的 bot 帳號在這個群組留過訊息才算參與。
    """
    from uuid import UUID as _UUID

    try:
        group_uuid = _UUID(str(line_group_id))
    except (ValueError, AttributeError):
        return False

    await ensure_db_connection()
    async with get_connection() as conn:
        row = await conn.fetchval(
            """
            SELECT 1
            FROM bot_messages m
            JOIN bot_users u ON m.bot_user_id = u.id
            WHERE m.bot_group_id = $1 AND u.user_id = $2
            LIMIT 1
            """,
            group_uuid,
            ctos_user_id,
        )
        return row is not None


async def _ctos_user_owns_bot_user(ctos_user_id: int, platform_user_id: str) -> bool:
    """這個平台使用者 ID 是不是這個 CTOS 使用者自己綁的。"""
    await ensure_db_connection()
    async with get_connection() as conn:
        row = await conn.fetchval(
            "SELECT 1 FROM bot_users WHERE platform_user_id = $1 AND user_id = $2 LIMIT 1",
            str(platform_user_id),
            ctos_user_id,
        )
        return row is not None


async def resolve_conversation_scope(
    line_group_id: str | None,
    line_user_id: str | None,
    ctos_user_id: int | None = None,
) -> tuple[str | None, str | None, str | None]:
    """讀群組對話／附件的身分解析（issue #209）。

    `resolve_bot_identity()` 只解決「有注入時模型不能宣稱別人」，但網頁聊天那條路
    沒有注入，模型帶什麼群組 id 就讀什麼群組——已登入的網頁使用者可以讀到任何群組的
    對話與附件。所以分兩段：

    1. 有注入 → 直接用注入值，模型參數一律忽略（與記憶工具同一套）。
    2. 沒有注入 → 要有伺服器認得的 `ctos_user_id`，而且指定的群組／個人身分
       必須跟這個 CTOS 帳號有既有關聯，否則拒絕。

    Returns:
        (line_group_id, line_user_id, error_message)：error 非 None 就是拒絕
    """
    resolved_group, resolved_user = resolve_bot_identity(line_group_id, line_user_id)

    if has_bot_identity_injection():
        return resolved_group, resolved_user, None

    uid = resolve_ctos_user_id(ctos_user_id)
    if uid is None:
        return None, None, BOT_IDENTITY_REQUIRED_MESSAGE

    if resolved_group and not await _ctos_user_in_bot_group(uid, resolved_group):
        return None, None, BOT_GROUP_SCOPE_DENIED_MESSAGE

    if resolved_user and not await _ctos_user_owns_bot_user(uid, resolved_user):
        return None, None, BOT_GROUP_SCOPE_DENIED_MESSAGE

    return resolved_group, resolved_user, None


def build_bot_mcp_env(
    line_group_id=None,
    line_user_id=None,
    agent_id=None,
    platform=None,
) -> dict[str, str]:
    """組 bot 對話要注入 MCP 子行程的身分環境變數（issue #204）。

    寫入端（`linebot_ai.py`／`bot_telegram/handler.py`／`bot/identity_router.py`）
    與讀取端（`resolve_bot_identity`）共用這一個函式，變數名稱只有這裡定義一次。

    Args:
        line_group_id: 群組的內部 UUID（bot_groups.id；個人對話為 None）
        line_user_id: 平台使用者 ID（bot_users.platform_user_id）
        agent_id: 這次對話使用的 Agent ID（語音設定用）
        platform: 這次對話的平台（`line`／`telegram`）。`send_nas_file` 用它判斷
            模型帶的 `telegram_chat_id` 算不算數——LINE 對話裡不算（issue #210 review）。

    Returns:
        要附加到 ching-tech-os MCP server 的環境變數
    """
    env: dict[str, str] = {}
    if platform:
        env["CTOS_BOT_PLATFORM"] = str(platform)
    if line_group_id:
        env["CTOS_BOT_GROUP_ID"] = str(line_group_id)
        # 語音設定（voice_tools）已經在用的名字，沿用同一個值避免兩套名字打架
        env["CTOS_GROUP_ID"] = str(line_group_id)
    if line_user_id:
        env["CTOS_BOT_USER_ID"] = str(line_user_id)
    if agent_id:
        env["CTOS_AGENT_ID"] = str(agent_id)
    return env


def resolve_bot_platform() -> str | None:
    """這條連線的平台（`line`／`telegram`），沒有注入就回 None。

    由 `build_bot_mcp_env(platform=...)` 寫進 `CTOS_BOT_PLATFORM`。
    """
    return os.environ.get("CTOS_BOT_PLATFORM") or None


def resolve_agent_allowed_shared_sources() -> list[str] | None:
    """從環境變數讀取 Agent 允許的 shared 來源列表。

    由 claude_agent.py 注入 AGENT_ALLOWED_SHARED_SOURCES 環境變數，
    用於限制受限 Agent 可搜尋的 NAS 來源範圍。

    Returns:
        允許的來源名稱列表，或 None（不限制）
    """
    import json as _json
    env_val = os.environ.get("AGENT_ALLOWED_SHARED_SOURCES")
    if not env_val:
        return None
    try:
        result = _json.loads(env_val)
        if isinstance(result, list):
            return [str(s) for s in result]
    except (ValueError, TypeError):
        pass
    return None


def resolve_agent_allowed_library_paths() -> list[str] | None:
    """從環境變數讀取 Agent 允許的 library 子路徑列表。

    由 claude_agent.py 注入 AGENT_ALLOWED_LIBRARY_PATHS 環境變數，
    用於限制受限 Agent 在 library 中可搜尋的路徑範圍。

    Returns:
        允許的 library 子路徑列表（相對於 library 根目錄），或 None（不限制）
    """
    import json as _json
    env_val = os.environ.get("AGENT_ALLOWED_LIBRARY_PATHS")
    if not env_val:
        return None
    try:
        result = _json.loads(env_val)
        if isinstance(result, list):
            return [str(s) for s in result]
    except (ValueError, TypeError):
        pass
    return None


# ============================================================
# 權限檢查輔助函數
# ============================================================


async def check_mcp_tool_permission(
    tool_name: str,
    ctos_user_id: int | None,
) -> tuple[bool, str]:
    """
    檢查使用者是否有權限使用 MCP 工具

    此函數用於 MCP 工具執行時的權限檢查，防止使用者繞過 prompt 過濾直接呼叫工具。

    Args:
        tool_name: 工具名稱（不含 mcp__ching-tech-os__ 前綴）
        ctos_user_id: CTOS 用戶 ID（None 表示未關聯帳號，會自動 fallback 環境變數）

    Returns:
        (allowed, error_message): allowed=True 表示允許，False 表示拒絕並回傳錯誤訊息
    """
    # bypassPermissions 模式下 AI 可能不傳 ctos_user_id，fallback 環境變數
    ctos_user_id = resolve_ctos_user_id(ctos_user_id)

    from ..permissions import (
        check_tool_permission,
        TOOL_APP_MAPPING,
        APPS_REQUIRE_BOUND_USER,
        BOUND_USER_REQUIRED_MESSAGE,
        get_app_display_names,
        get_effective_app_permissions,
        is_tool_deprecated,
    )
    effective_defaults = get_effective_app_permissions()
    app_display_names = get_app_display_names()

    # 檢查工具是否已停用（遷移至 ERPNext）
    is_deprecated, deprecated_message = is_tool_deprecated(tool_name)
    if is_deprecated:
        return (False, deprecated_message)

    # 不需要特定權限的工具，直接放行
    required_app = TOOL_APP_MAPPING.get(tool_name)
    if required_app is None:
        return (True, "")

    # 未關聯帳號的使用者，使用預設權限
    if ctos_user_id is None:
        # 這幾個 app 不管預設權限，未綁定一律拒絕（issue #201）
        if required_app in APPS_REQUIRE_BOUND_USER:
            return (False, BOUND_USER_REQUIRED_MESSAGE)
        # 檢查預設權限是否允許
        if effective_defaults.get(required_app, False):
            return (True, "")
        app_name = app_display_names.get(required_app, required_app)
        return (False, f"需要「{app_name}」功能權限才能使用此工具")

    # 查詢使用者角色和權限
    await ensure_db_connection()
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT role, preferences FROM users WHERE id = $1",
            ctos_user_id,
        )

    if not row:
        # 使用者不存在（等同未綁定），這幾個 app 一律拒絕（issue #201）
        if required_app in APPS_REQUIRE_BOUND_USER:
            return (False, BOUND_USER_REQUIRED_MESSAGE)
        # 其餘 app 使用預設權限
        if effective_defaults.get(required_app, False):
            return (True, "")
        app_name = app_display_names.get(required_app, required_app)
        return (False, f"需要「{app_name}」功能權限才能使用此工具")

    role = row["role"] or "user"
    # 舊資料的 preferences 可能是雙重編碼的字串或被串壞的陣列，一律轉成 dict
    preferences = parse_json_dict(row["preferences"])
    permissions = {"apps": preferences.get("permissions", {}).get("apps", {})}

    # 使用 check_tool_permission 檢查
    if check_tool_permission(tool_name, role, permissions):
        return (True, "")

    app_name = app_display_names.get(required_app, required_app)
    return (False, f"您沒有「{app_name}」功能權限，無法使用此工具")


async def check_project_member_permission(
    project_id: str,
    user_id: int,
) -> bool:
    """
    檢查用戶是否為專案成員

    Args:
        project_id: 專案 UUID 字串
        user_id: CTOS 用戶 ID

    Returns:
        True 表示用戶是專案成員，可以操作
    """
    from uuid import UUID as UUID_type
    await ensure_db_connection()
    async with get_connection() as conn:
        exists = await conn.fetchval(
            """
            SELECT 1 FROM project_members pm
            WHERE pm.project_id = $1 AND pm.user_id = $2
            """,
            UUID_type(project_id),
            user_id,
        )
        return exists is not None


# ============================================================
# 工具存取介面（供 Line Bot 和其他服務使用）
# ============================================================


async def get_mcp_tools() -> list[dict]:
    """
    取得 MCP 工具定義列表，格式符合 Claude API

    Returns:
        工具定義列表，可直接用於 Claude API 的 tools 參數
    """
    tools = await mcp.list_tools()
    return [
        {
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.inputSchema,
        }
        for tool in tools
    ]


async def get_mcp_tool_names(exclude_group_only: bool = False) -> list[str]:
    """
    取得 MCP 工具名稱列表，格式為 mcp__ching-tech-os__{tool_name}

    Args:
        exclude_group_only: 是否排除群組專用工具（如 summarize_chat）

    Returns:
        工具名稱列表，可用於 Claude API 的 tools 參數
    """
    # 群組專用工具
    group_only_tools = {"summarize_chat"}

    tools = await mcp.list_tools()
    tool_names = []

    for tool in tools:
        if exclude_group_only and tool.name in group_only_tools:
            continue
        tool_names.append(f"mcp__ching-tech-os__{tool.name}")

    return tool_names


async def execute_tool(tool_name: str, arguments: dict) -> str:
    """
    執行 MCP 工具

    Args:
        tool_name: 工具名稱
        arguments: 工具參數

    Returns:
        工具執行結果（文字）
    """
    try:
        result = await mcp.call_tool(tool_name, arguments)
        # result 是 (list[TextContent], dict) 的元組
        contents, _ = result
        if contents:
            return contents[0].text
        return "執行完成（無輸出）"
    except Exception as e:
        logger.error(f"執行工具 {tool_name} 失敗: {e}")
        return f"執行失敗：{str(e)}"


# ============================================================
# CLI 入口點（供 Claude Code 使用）
# ============================================================


def run_cli():
    """以 stdio 模式執行 MCP Server"""
    mcp.run()
