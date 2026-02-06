#!/usr/bin/env python
"""MCP Server CLI 入口點

供 Claude Code CLI 使用：
  uv run python -m ching_tech_os.mcp_cli
"""

from ching_tech_os.services.mcp import mcp

if __name__ == "__main__":
    mcp.run()
