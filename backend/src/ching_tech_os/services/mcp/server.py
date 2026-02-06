"""MCP Server 核心模組

FastMCP 實例和共用輔助函數。
"""

import logging
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP

from ...database import get_connection, init_db_pool

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
        ctos_user_id: CTOS 用戶 ID（None 表示未關聯帳號）

    Returns:
        (allowed, error_message): allowed=True 表示允許，False 表示拒絕並回傳錯誤訊息
    """
    from ..permissions import (
        check_tool_permission,
        TOOL_APP_MAPPING,
        APP_DISPLAY_NAMES,
        DEFAULT_APP_PERMISSIONS,
        is_tool_deprecated,
    )

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
        # 檢查預設權限是否允許
        if DEFAULT_APP_PERMISSIONS.get(required_app, False):
            return (True, "")
        app_name = APP_DISPLAY_NAMES.get(required_app, required_app)
        return (False, f"需要「{app_name}」功能權限才能使用此工具")

    # 查詢使用者角色和權限
    await ensure_db_connection()
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT role, preferences FROM users WHERE id = $1",
            ctos_user_id,
        )

    if not row:
        # 使用者不存在，使用預設權限
        if DEFAULT_APP_PERMISSIONS.get(required_app, False):
            return (True, "")
        app_name = APP_DISPLAY_NAMES.get(required_app, required_app)
        return (False, f"需要「{app_name}」功能權限才能使用此工具")

    role = row["role"] or "user"
    preferences = row["preferences"] or {}
    permissions = {"apps": preferences.get("permissions", {}).get("apps", {})}

    # 使用 check_tool_permission 檢查
    if check_tool_permission(tool_name, role, permissions):
        return (True, "")

    app_name = APP_DISPLAY_NAMES.get(required_app, required_app)
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
