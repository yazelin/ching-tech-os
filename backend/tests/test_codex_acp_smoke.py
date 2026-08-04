"""真實 Codex ACP 唯讀 smoke；預設跳過，需明確設定環境變數。"""

from __future__ import annotations

import asyncio
import json
import os
import socket
from pathlib import Path

import pytest

from ching_tech_os.services.codex_acp import CodexAcpClient


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_CODEX_ACP_SMOKE") != "1",
    reason="需明確設定 RUN_CODEX_ACP_SMOKE=1 才執行真實 Codex ACP smoke",
)

PROJECT_ROOT = Path(__file__).parents[2]
BACKEND_ROOT = Path(__file__).parents[1]
ADAPTER_BIN = PROJECT_ROOT / "node_modules/.bin/codex-acp"
CODEX_BIN = PROJECT_ROOT / "node_modules/.bin/codex"
MCP_FIXTURE = Path(__file__).parent / "fixtures/codex_readonly_mcp_server.py"


def _client_env(*, approval_policy: str = "never") -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "CODEX_PATH": str(CODEX_BIN),
            "INITIAL_AGENT_MODE": "read-only",
            "NO_BROWSER": "1",
            "CODEX_CONFIG": json.dumps(
                {
                    "features": {"multi_agent": False},
                    "sandbox_mode": "read-only",
                    "approval_policy": approval_policy,
                }
            ),
        }
    )
    return env


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _wait_for_port(port: int) -> None:
    for _ in range(100):
        try:
            _reader, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError:
            await asyncio.sleep(0.05)
            continue
        writer.close()
        await writer.wait_closed()
        return
    raise TimeoutError("本機 smoke HTTP MCP 未在期限內啟動")


@pytest.mark.asyncio
async def test_real_codex_acp_text_repeat_and_readonly_stdio_tool(tmp_path) -> None:
    client = CodexAcpClient(
        command=str(ADAPTER_BIN),
        cwd=str(tmp_path),
        env=_client_env(approval_policy="on-request"),
        mcp_servers=[
            {
                "name": "ctos-readonly-smoke",
                "type": "stdio",
                "command": str(BACKEND_ROOT / ".venv/bin/python"),
                "args": [str(MCP_FIXTURE)],
                "env": {},
            }
        ],
    )
    permission_identities: list[tuple[str, str]] = []
    tool_identities: list[tuple[str, str, str]] = []

    @client.on_tool_start
    async def on_tool_start(_tool_id: str, title: str, raw_input: dict) -> None:
        if title.startswith("mcp."):
            tool_identities.append(
                (
                    title,
                    str(raw_input.get("server", "")),
                    str(raw_input.get("tool", "")),
                )
            )

    @client.on_permission
    async def on_permission(_title: str, raw_input: dict, options: list[dict]) -> str:
        identity = (str(raw_input.get("server", "")), str(raw_input.get("tool", "")))
        permission_identities.append(identity)
        if identity == ("ctos-readonly-smoke", "read_only_marker"):
            for option in options:
                if str(option.get("kind", "")).startswith("allow"):
                    return str(option["id"])
        for option in options:
            if str(option.get("kind", "")).startswith("reject"):
                return str(option["id"])
        return "reject"

    try:
        await client.connect()
        await client.new_session()
        plain = await asyncio.wait_for(
            client.prompt("Reply with exactly: ACP_SMOKE_OK"),
            timeout=90,
        )
        repeated = await asyncio.wait_for(
            client.prompt("Reply with exactly: repeat repeat repeat"),
            timeout=90,
        )
        tool_result = await asyncio.wait_for(
            client.prompt(
                "Call read_only_marker exactly once with value ACP_TOOL_OK, "
                "then reply with the returned text only."
            ),
            timeout=120,
        )
    finally:
        await client.disconnect()

    assert "ACP_SMOKE_OK" in plain
    assert "repeat repeat repeat" in repeated
    assert "ACP_TOOL_OK" in tool_result
    assert tool_identities == [
        (
            "mcp.ctos-readonly-smoke.read_only_marker",
            "ctos-readonly-smoke",
            "read_only_marker",
        )
    ]
    assert permission_identities == [
        ("ctos-readonly-smoke", "read_only_marker")
    ]


@pytest.mark.asyncio
async def test_real_codex_acp_http_mcp_handshake(tmp_path) -> None:
    port = _free_port()
    server_env = dict(os.environ)
    server_env.update(
        {
            "CTOS_SMOKE_MCP_TRANSPORT": "streamable-http",
            "CTOS_SMOKE_MCP_PORT": str(port),
        }
    )
    server = await asyncio.create_subprocess_exec(
        str(BACKEND_ROOT / ".venv/bin/python"),
        str(MCP_FIXTURE),
        env=server_env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    client = CodexAcpClient(
        command=str(ADAPTER_BIN),
        cwd=str(tmp_path),
        env=_client_env(),
        mcp_servers=[
            {
                "name": "ctos-http-smoke",
                "type": "http",
                "url": f"http://127.0.0.1:{port}/mcp",
                "headers": {"X-CTOS-Smoke": "safe-marker"},
            }
        ],
    )
    try:
        await _wait_for_port(port)
        await client.connect()
        session_id = await asyncio.wait_for(client.new_session(), timeout=30)
        assert session_id
    finally:
        await client.disconnect()
        server.terminate()
        try:
            await asyncio.wait_for(server.wait(), timeout=5)
        except TimeoutError:
            server.kill()
            await server.wait()


@pytest.mark.asyncio
async def test_real_codex_acp_timeout_cancel_and_cleanup(tmp_path) -> None:
    client = CodexAcpClient(
        command=str(ADAPTER_BIN),
        cwd=str(tmp_path),
        env=_client_env(),
    )
    try:
        await client.connect()
        await client.new_session()
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(
                client.prompt("Analyze this empty workspace in detail."),
                timeout=0.001,
            )
        await client.cancel()
    finally:
        process = client._process
        await client.disconnect()

    assert process is not None
    assert process.returncode is not None
