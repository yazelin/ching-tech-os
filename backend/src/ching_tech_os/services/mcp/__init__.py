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
from . import codex_image_tools  # noqa: F401

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


def load_extends_mcp_tools(tools_map: dict[str, str]) -> None:
    """載入 extends 模組的 in-process MCP 工具。

    由 main.py 的 _start_extends_modules() 呼叫，
    傳入從 contributes.yaml 的 mcp_tools 欄位收集到的路徑。

    extends 模組的 mcp_tools.py 通常放在 core/ 子目錄下，
    使用 relative import（如 from .services import ...）。
    此函式會自動設定 package context 讓 relative import 正確解析。

    Args:
        tools_map: {module_name: absolute_file_path}
    """
    from pathlib import Path

    for module_name, file_path in tools_map.items():
        try:
            tools_path = Path(file_path)
            # 推算 package：如果路徑是 .../extends/law/core/mcp_tools.py，
            # 則 package 是 core（相對於 extends/law/）
            parent_dir = tools_path.parent  # e.g. .../extends/law/core
            pkg_name = f"_extends_{module_name}_{parent_dir.name}"

            # 註冊 parent 為 package（支援 relative import）
            if pkg_name not in sys.modules:
                pkg_spec = importlib.util.spec_from_file_location(
                    pkg_name,
                    str(parent_dir / "__init__.py"),
                    submodule_search_locations=[str(parent_dir)],
                )
                if pkg_spec and pkg_spec.loader:
                    pkg_mod = importlib.util.module_from_spec(pkg_spec)
                    sys.modules[pkg_name] = pkg_mod
                    pkg_spec.loader.exec_module(pkg_mod)

                    # 註冊 sub-packages（掃描子目錄中含 __init__.py 的）
                    for sub_dir in sorted(parent_dir.iterdir()):
                        if sub_dir.is_dir() and (sub_dir / "__init__.py").exists():
                            sub_pkg = f"{pkg_name}.{sub_dir.name}"
                            if sub_pkg in sys.modules:
                                continue
                            sub_spec = importlib.util.spec_from_file_location(
                                sub_pkg,
                                str(sub_dir / "__init__.py"),
                                submodule_search_locations=[str(sub_dir)],
                            )
                            if sub_spec and sub_spec.loader:
                                sub_mod = importlib.util.module_from_spec(sub_spec)
                                sys.modules[sub_pkg] = sub_mod
                                sub_spec.loader.exec_module(sub_mod)

                                # 再往下一層（如 services/legal_search/）
                                for subsub_dir in sorted(sub_dir.iterdir()):
                                    if subsub_dir.is_dir() and (subsub_dir / "__init__.py").exists():
                                        subsub_pkg = f"{sub_pkg}.{subsub_dir.name}"
                                        if subsub_pkg in sys.modules:
                                            continue
                                        ss_spec = importlib.util.spec_from_file_location(
                                            subsub_pkg,
                                            str(subsub_dir / "__init__.py"),
                                            submodule_search_locations=[str(subsub_dir)],
                                        )
                                        if ss_spec and ss_spec.loader:
                                            ss_mod = importlib.util.module_from_spec(ss_spec)
                                            sys.modules[subsub_pkg] = ss_mod
                                            ss_spec.loader.exec_module(ss_mod)

            # 載入 mcp_tools.py 本身
            mod_name = f"{pkg_name}.mcp_tools"
            spec = importlib.util.spec_from_file_location(mod_name, file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"無法建立 spec: {file_path}")
            mod = importlib.util.module_from_spec(spec)
            mod.__package__ = pkg_name
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)

            logger.info("extends/%s MCP 工具已載入", module_name)
        except Exception as e:
            logger.warning("extends/%s MCP 工具載入失敗: %s", module_name, e)


# voice MCP 工具：無條件載入（MCP server 是獨立進程，voice_bridge 可能不可用）
# 工具內部會在呼叫時才檢查 voice 模組是否可用
try:
    from . import voice_tools  # noqa: F401
    logger.info("voice MCP 工具已載入")
except Exception as e:
    logger.debug("voice MCP 工具未載入: %s", e)

# web MCP 工具：無條件載入（提供 browse_webpage 瀏覽器擷取功能）
try:
    from . import web_tools  # noqa: F401
    logger.info("web MCP 工具已載入")
except Exception as e:
    logger.debug("web MCP 工具未載入: %s", e)


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
