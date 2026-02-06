"""MCP Server 模組

將 FastMCP 工具按領域拆分為子模組：
- server: FastMCP 實例和共用輔助函數
- knowledge_tools: 知識庫相關工具
- message_tools: 訊息相關工具
- nas_tools: NAS 檔案相關工具
- share_tools: 分享連結相關工具
- memory_tools: 記憶管理相關工具
- media_tools: 媒體處理相關工具
- presentation_tools: 簡報/文件生成、列印相關工具

匯入所有子模組以觸發 @mcp.tool() 註冊。
"""

# 匯入共用元件
from .server import (
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

# 匯入所有工具子模組以觸發 @mcp.tool() 註冊
from . import knowledge_tools  # noqa: F401
from . import message_tools  # noqa: F401
from . import nas_tools  # noqa: F401
from . import share_tools  # noqa: F401
from . import memory_tools  # noqa: F401
from . import media_tools  # noqa: F401
from . import presentation_tools  # noqa: F401

__all__ = [
    # FastMCP 實例
    "mcp",
    # 工具存取介面
    "get_mcp_tools",
    "get_mcp_tool_names",
    "execute_tool",
    # CLI
    "run_cli",
    # 共用輔助函數（供其他模組使用）
    "ensure_db_connection",
    "check_mcp_tool_permission",
    "check_project_member_permission",
    "to_taipei_time",
    "TAIPEI_TZ",
]
