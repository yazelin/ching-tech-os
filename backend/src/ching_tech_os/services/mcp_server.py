"""向後相容模組 — 請改用 services.mcp

此檔案僅用於過渡期，所有功能已遷移至 services/mcp/ 子模組。
新程式碼請直接 import from services.mcp。
"""

# Re-export 所有公開 API，保持向後相容
from .mcp import (
    mcp,
    get_mcp_tools,
    get_mcp_tool_names,
    execute_tool,
    run_cli,
    ensure_db_connection,
    check_mcp_tool_permission,
    check_project_member_permission,
    to_taipei_time,
    TAIPEI_TZ,
)

# Re-export 常用工具函式（供 lazy import 使用）
from .mcp.nas_tools import prepare_file_message  # noqa: F401

__all__ = [
    "mcp",
    "get_mcp_tools",
    "get_mcp_tool_names",
    "execute_tool",
    "run_cli",
    "ensure_db_connection",
    "check_mcp_tool_permission",
    "check_project_member_permission",
    "to_taipei_time",
    "TAIPEI_TZ",
    "prepare_file_message",
]
