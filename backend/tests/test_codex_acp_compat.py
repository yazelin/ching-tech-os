"""Codex ACP compatibility layer 的協定 fixture 測試。"""

from __future__ import annotations

import json
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from acp.schema import (
    AgentMessageChunk,
    HttpMcpServer,
    McpServerStdio,
    PermissionOption,
    TextContentBlock,
    ToolCallProgress,
    ToolCallStart,
    ToolCallUpdate,
)

from ching_tech_os.services.codex_acp import (
    CodexAcpClient,
    _redact_diagnostics,
    to_acp_mcp_server,
)


def test_runtime_versions_are_exactly_pinned() -> None:
    project_root = Path(__file__).parents[2]
    package = json.loads((project_root / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((project_root / "package-lock.json").read_text(encoding="utf-8"))

    assert package["dependencies"]["@agentclientprotocol/codex-acp"] == "1.1.9"
    assert package["dependencies"]["@openai/codex"] == "0.146.0"
    assert lock["packages"]["node_modules/@agentclientprotocol/codex-acp"]["version"] == "1.1.9"
    assert lock["packages"]["node_modules/@openai/codex"]["version"] == "0.146.0"

    fixture = json.loads(
        (
            Path(__file__).parent
            / "fixtures/codex_acp_compatibility_1_1_9.json"
        ).read_text(encoding="utf-8")
    )
    assert fixture["versions"]["codex_acp"] == "1.1.9"
    assert fixture["versions"]["codex_cli"] == "0.146.0"
    assert all(fixture["validated"].values())


def test_stderr_diagnostics_are_bounded_and_redacted() -> None:
    client = CodexAcpClient()
    client.stderr_max_bytes = 24
    client._stderr_tail.extend(b"prefix Bearer very-secret")
    overflow = len(client._stderr_tail) - client.stderr_max_bytes
    del client._stderr_tail[:max(0, overflow)]

    assert len(client._stderr_tail) <= 24
    assert "very-secret" not in client.stderr_tail
    assert "[REDACTED]" in client.stderr_tail
    assert "token-value" not in _redact_diagnostics("access_token=token-value")


@pytest.mark.asyncio
async def test_stderr_reader_keeps_only_bounded_tail() -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(b"old-data " + b"x" * 30)
    reader.feed_data(b" Bearer newest-secret")
    reader.feed_eof()
    client = CodexAcpClient()
    client.stderr_max_bytes = 32
    client._process = SimpleNamespace(stderr=reader)

    await client._drain_stderr()

    assert len(client._stderr_tail) == 32
    assert "old-data" not in client.stderr_tail
    assert "newest-secret" not in client.stderr_tail


def test_mcp_conversion_preserves_stdio_and_http_fields() -> None:
    stdio = to_acp_mcp_server(
        {
            "name": "ching-tech-os",
            "type": "stdio",
            "command": "uv",
            "args": ["run", "python", "-m", "ching_tech_os.mcp_cli"],
            "env": {"CTOS_USER_ID": "42"},
        }
    )
    http = to_acp_mcp_server(
        {
            "name": "github",
            "type": "http",
            "url": "https://api.githubcopilot.com/mcp/",
            "headers": {"Authorization": "Bearer secret-placeholder"},
        }
    )

    assert isinstance(stdio, McpServerStdio)
    assert stdio.command == "uv"
    assert stdio.args[-1] == "ching_tech_os.mcp_cli"
    assert [(item.name, item.value) for item in stdio.env] == [("CTOS_USER_ID", "42")]
    assert isinstance(http, HttpMcpServer)
    assert http.url == "https://api.githubcopilot.com/mcp/"
    assert [(item.name, item.value) for item in http.headers] == [
        ("Authorization", "Bearer secret-placeholder")
    ]


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"name": "x", "type": "sse"},
        {"name": "x", "type": "http", "headers": "invalid"},
        {"name": "x", "type": "stdio", "env": "invalid"},
    ],
)
def test_mcp_conversion_fails_closed_for_invalid_config(config: dict) -> None:
    with pytest.raises(ValueError):
        to_acp_mcp_server(config)


@pytest.mark.asyncio
async def test_message_chunks_preserve_repeated_text() -> None:
    client = CodexAcpClient()
    received: list[str] = []

    @client.on_text
    async def on_text(text: str) -> None:
        received.append(text)

    handler = client._create_client_handler()
    for text in ("echo ", "echo ", "done"):
        await handler.session_update(
            "session-1",
            AgentMessageChunk(
                sessionUpdate="agent_message_chunk",
                content=TextContentBlock(type="text", text=text),
            ),
        )

    assert client._text_buffer == "echo echo done"
    assert received == ["echo ", "echo ", "done"]


@pytest.mark.asyncio
async def test_tool_progress_is_deduplicated_and_permission_keeps_identity() -> None:
    client = CodexAcpClient()
    starts: list[tuple] = []
    ends: list[tuple] = []
    permissions: list[tuple] = []

    @client.on_tool_start
    async def on_start(*args) -> None:
        starts.append(args)

    @client.on_tool_end
    async def on_end(*args) -> None:
        ends.append(args)

    @client.on_permission
    async def on_permission(title: str, raw_input: dict, options: list[dict]) -> str:
        permissions.append((title, raw_input, options))
        return "reject_once"

    handler = client._create_client_handler()
    await handler.session_update(
        "session-1",
        ToolCallStart(
            sessionUpdate="tool_call",
            toolCallId="tool-1",
            title="mcp.ching-tech-os.search_knowledge",
            kind="execute",
            status="in_progress",
            rawInput={
                "server": "ching-tech-os",
                "tool": "search_knowledge",
                "arguments": {"query": "安全測試"},
            },
        ),
    )
    response = await handler.request_permission(
        options=[
            PermissionOption(optionId="allow_once", name="Allow", kind="allow_once"),
            PermissionOption(optionId="reject_once", name="Reject", kind="reject_once"),
        ],
        session_id="session-1",
        tool_call=ToolCallUpdate(
            toolCallId="tool-1",
            status="pending",
        ),
    )
    for status in ("in_progress", "completed", "completed"):
        await handler.session_update(
            "session-1",
            ToolCallProgress(
                sessionUpdate="tool_call_update",
                toolCallId="tool-1",
                status=status,
                rawOutput={"ok": True} if status == "completed" else None,
            ),
        )

    assert starts == [
        (
            "tool-1",
            "mcp.ching-tech-os.search_knowledge",
            {
                "server": "ching-tech-os",
                "tool": "search_knowledge",
                "arguments": {"query": "安全測試"},
            },
        )
    ]
    assert permissions[0][0] == "mcp.ching-tech-os.search_knowledge"
    assert permissions[0][1]["server"] == "ching-tech-os"
    assert permissions[0][1]["tool"] == "search_knowledge"
    assert permissions[0][1]["_acp_tool_call_id"] == "tool-1"
    assert response.outcome.option_id == "reject_once"
    assert ends == [("tool-1", "completed", {"ok": True})]


@pytest.mark.asyncio
async def test_permission_defaults_to_reject_without_handler() -> None:
    client = CodexAcpClient()
    handler = client._create_client_handler()

    response = await handler.request_permission(
        options=[
            PermissionOption(optionId="allow_once", name="Allow", kind="allow_once"),
            PermissionOption(optionId="deny", name="Deny", kind="reject_once"),
        ],
        session_id="session-1",
        tool_call=ToolCallUpdate(toolCallId="unknown", status="pending"),
    )

    assert response.outcome.option_id == "deny"


@pytest.mark.asyncio
async def test_new_session_passes_both_mcp_transports_and_pending_model() -> None:
    connection = SimpleNamespace(
        new_session=AsyncMock(return_value=SimpleNamespace(session_id="session-1")),
        set_session_model=AsyncMock(),
    )
    client = CodexAcpClient(
        cwd="/tmp/safe-workspace",
        mcp_servers=[
            {"name": "local", "command": "python", "args": ["server.py"]},
            {"name": "remote", "type": "http", "url": "https://example.test/mcp", "headers": {}},
        ],
    )
    client._connection = connection
    await client.set_model("gpt-test")

    session_id = await client.new_session()

    assert session_id == "session-1"
    passed = connection.new_session.await_args.kwargs["mcp_servers"]
    assert isinstance(passed[0], McpServerStdio)
    assert isinstance(passed[1], HttpMcpServer)
    connection.set_session_model.assert_awaited_once_with(
        model_id="gpt-test",
        session_id="session-1",
    )


@pytest.mark.asyncio
async def test_prompt_retains_token_model_metadata_and_cancel() -> None:
    client = CodexAcpClient()

    async def prompt(**_kwargs):
        client._text_buffer = "repeat repeat"
        return SimpleNamespace(
            usage=SimpleNamespace(input_tokens=12, output_tokens=5),
            field_meta={"quota": {"model_usage": [{"model": "gpt-test"}]}},
        )

    connection = SimpleNamespace(
        prompt=AsyncMock(side_effect=prompt),
        cancel=AsyncMock(),
    )
    client._connection = connection
    client._session_id = "session-1"

    result = await client.prompt("只讀測試")
    await client.cancel()

    assert result == "repeat repeat"
    assert client.input_tokens == 12
    assert client.output_tokens == 5
    assert client.model_name == "gpt-test"
    connection.cancel.assert_awaited_once_with(session_id="session-1")
