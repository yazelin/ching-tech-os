"""Codex ACP smoke 專用的單一唯讀 MCP 工具。"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP


mcp = FastMCP(
    "ctos-readonly-smoke",
    host="127.0.0.1",
    port=int(os.getenv("CTOS_SMOKE_MCP_PORT", "8765")),
    stateless_http=True,
)


@mcp.tool()
def read_only_marker(value: str) -> str:
    """原樣回傳 marker，不讀寫任何系統或外部資料。"""
    return value


if __name__ == "__main__":
    transport = os.getenv("CTOS_SMOKE_MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
