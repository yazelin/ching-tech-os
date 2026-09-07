"""MCP 工具身分注入：ctos_user_id 由伺服器端環境變數決定，不靠模型帶參數。"""

from __future__ import annotations

import pytest

from ching_tech_os.services.mcp import server


def test_env_wins_over_param(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CTOS_USER_ID", "7")
    assert server.resolve_ctos_user_id(None) == 7
    assert server.resolve_ctos_user_id(3) == 7  # 模型填別人的 ID 無效


def test_param_used_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CTOS_USER_ID", raising=False)
    assert server.resolve_ctos_user_id(3) == 3
    assert server.resolve_ctos_user_id(None) is None  # 未綁定維持匿名


@pytest.mark.asyncio
async def test_tool_decorator_injects_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    @server.mcp.tool(name="_identity_probe_for_test")
    async def probe(query: str, ctos_user_id: int | None = None) -> str:
        return f"{query}:{ctos_user_id}"

    @server.mcp.tool(name="_no_identity_probe_for_test")
    async def plain(query: str) -> str:
        return query

    monkeypatch.setenv("CTOS_USER_ID", "42")
    assert await probe("q") == "q:42"  # 模型沒帶
    assert await probe("q", ctos_user_id=9) == "q:42"  # 模型帶錯
    assert await probe("q", 9) == "q:42"  # 位置參數也一樣
    assert await plain("q") == "q"

    monkeypatch.delenv("CTOS_USER_ID", raising=False)
    assert await probe("q") == "q:None"
    assert await probe("q", ctos_user_id=9) == "q:9"

    # 透過 FastMCP 呼叫也會經過同一層
    monkeypatch.setenv("CTOS_USER_ID", "42")
    contents, _ = await server.mcp.call_tool("_identity_probe_for_test", {"query": "q"})
    assert contents[0].text == "q:42"
