"""MCP Server 模組。"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys

# 匯入共用元件
from .server import (  # noqa: F401
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

# core 工具永遠載入
from . import memory_tools  # noqa: F401
from . import message_tools  # noqa: F401

logger = logging.getLogger(__name__)


def _load_skill_mcp_tools(module_id: str, file_path: str) -> None:
    """從 Skill 檔案載入 MCP 工具模組。"""

    module_name = f"ching_tech_os.dynamic_mcp.{module_id.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"無法建立 spec: {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)


def _load_enabled_mcp_tools() -> None:
    """依啟用模組動態載入 MCP 工具。"""
    from ...modules import get_module_registry, is_module_enabled

    for module_id, info in get_module_registry().items():
        if not is_module_enabled(module_id):
            continue

        if info.get("source") == "builtin":
            mcp_module = info.get("mcp_module")
            if not isinstance(mcp_module, str) or not mcp_module:
                continue
            try:
                if mcp_module.startswith("."):
                    importlib.import_module(mcp_module, package="ching_tech_os")
                else:
                    importlib.import_module(mcp_module)
            except Exception as e:
                logger.warning("MCP 工具模組載入失敗（%s）: %s", module_id, e)
            continue

        mcp_tools_file = info.get("mcp_tools_file")
        if isinstance(mcp_tools_file, str) and mcp_tools_file:
            try:
                _load_skill_mcp_tools(module_id, mcp_tools_file)
            except Exception as e:
                logger.warning("Skill MCP 工具載入失敗（%s）: %s", module_id, e)


_load_enabled_mcp_tools()


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
]
