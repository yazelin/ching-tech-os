"""Codex ACP compatibility layer。

修正 Generic client 的重複文字、HTTP MCP、terminal tool event 與 permission
identity 遺失問題；provider 業務邏輯留在 ``codex_agent.py``。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from typing import Any

from acp.client.connection import ClientSideConnection
from acp.schema import (
    AgentMessageChunk,
    AllowedOutcome,
    EnvVariable,
    HttpHeader,
    HttpMcpServer,
    Implementation,
    McpServerStdio,
    PermissionOption,
    RequestPermissionResponse,
    TextContentBlock,
    ToolCallProgress,
    ToolCallStart,
    ToolCallUpdate,
)
from claude_code_acp.acp_client import AcpClient as GenericAcpClient

logger = logging.getLogger(__name__)

MAX_ACP_FRAME_SIZE = 64 * 1024 * 1024
TERMINAL_TOOL_STATUSES = frozenset({"completed", "failed"})
_SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)((?:api[_-]?key|access[_-]?token|authorization)\s*[=:]\s*)[^\s,;]+"),
)


def _redact_diagnostics(value: str) -> str:
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(r"\1[REDACTED]", value)
    return value


def _as_plain_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(by_alias=True, exclude_none=True)
    raise ValueError("MCP server 設定必須是 dict 或 ACP schema object")


def to_acp_mcp_server(value: Any) -> McpServerStdio | HttpMcpServer:
    """轉換並完整保留 stdio 或 Streamable HTTP MCP 設定。"""
    config = _as_plain_mapping(value)
    server_type = str(config.get("type", "stdio")).strip().lower()
    name = str(config.get("name", "")).strip()
    if not name:
        raise ValueError("MCP server name 不得為空")

    if server_type == "http":
        raw_headers = config.get("headers") or {}
        if isinstance(raw_headers, list):
            header_pairs = [
                (item.get("name"), item.get("value"))
                for item in raw_headers
                if isinstance(item, dict)
            ]
        elif isinstance(raw_headers, dict):
            header_pairs = list(raw_headers.items())
        else:
            raise ValueError("HTTP MCP headers 格式無效")
        return HttpMcpServer(
            type="http",
            name=name,
            url=str(config.get("url", "")),
            headers=[
                HttpHeader(name=str(key), value=str(item_value))
                for key, item_value in header_pairs
                if key is not None and item_value is not None
            ],
        )

    if server_type != "stdio":
        raise ValueError(f"不支援的 MCP transport: {server_type}")
    raw_env = config.get("env") or {}
    if isinstance(raw_env, list):
        env_pairs = [
            (item.get("name"), item.get("value"))
            for item in raw_env
            if isinstance(item, dict)
        ]
    elif isinstance(raw_env, dict):
        env_pairs = list(raw_env.items())
    else:
        raise ValueError("stdio MCP env 格式無效")
    return McpServerStdio(
        name=name,
        command=str(config.get("command", "")),
        args=[str(item) for item in config.get("args", [])],
        env=[
            EnvVariable(name=str(key), value=str(item_value))
            for key, item_value in env_pairs
            if key is not None and item_value is not None
        ],
    )


def _reject_option_id(options: list[PermissionOption]) -> str:
    for option in options:
        if str(option.kind).startswith("reject"):
            return option.option_id
    return "reject"


class CodexAcpClient(GenericAcpClient):
    """針對 Codex 事件契約補強的 ACP client。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.input_tokens: int | None = None
        self.output_tokens: int | None = None
        self.model_name: str | None = None
        self._active_tool_identity: dict[str, tuple[str, dict[str, Any]]] = {}
        self._terminal_tool_ids: set[str] = set()
        self._stderr_tail = bytearray()
        self._stderr_task: asyncio.Task[None] | None = None
        self.stderr_max_bytes = 8192

    @property
    def stderr_tail(self) -> str:
        """只暴露有界、可替換解碼的診斷尾端。"""
        decoded = bytes(self._stderr_tail).decode("utf-8", errors="replace")
        return _redact_diagnostics(decoded)

    async def _drain_stderr(self) -> None:
        if self._process is None or self._process.stderr is None:
            return
        while chunk := await self._process.stderr.read(4096):
            self._stderr_tail.extend(chunk)
            overflow = len(self._stderr_tail) - self.stderr_max_bytes
            if overflow > 0:
                del self._stderr_tail[:overflow]

    def _create_client_handler(self):
        handler = super()._create_client_handler()
        generic_session_update = handler.session_update

        async def session_update(session_id: str, update: Any) -> None:
            if isinstance(update, AgentMessageChunk):
                content = getattr(update, "content", None)
                text = getattr(content, "text", None) if content is not None else None
                if text:
                    # ACP message chunk 是 ordered delta；重複文字也必須保留。
                    self._text_buffer += text
                    if self.events.on_text:
                        await self.events.on_text(text)
                return

            if isinstance(update, ToolCallStart):
                raw_input = update.raw_input if isinstance(update.raw_input, dict) else {}
                self._active_tool_identity[update.tool_call_id] = (
                    update.title or "",
                    dict(raw_input),
                )
                if self.events.on_tool_start:
                    await self.events.on_tool_start(
                        update.tool_call_id,
                        update.title or "",
                        dict(raw_input),
                    )
                if update.status in TERMINAL_TOOL_STATUSES:
                    await self._emit_terminal_tool_update(update)
                return

            if isinstance(update, ToolCallProgress):
                if update.title or isinstance(update.raw_input, dict):
                    old_title, old_input = self._active_tool_identity.get(
                        update.tool_call_id, ("", {})
                    )
                    self._active_tool_identity[update.tool_call_id] = (
                        update.title or old_title,
                        dict(update.raw_input) if isinstance(update.raw_input, dict) else old_input,
                    )
                if update.status in TERMINAL_TOOL_STATUSES:
                    await self._emit_terminal_tool_update(update)
                return

            await generic_session_update(session_id, update)

        async def request_permission(
            options: list[PermissionOption],
            session_id: str,
            tool_call: ToolCallUpdate,
            **_kwargs: Any,
        ) -> RequestPermissionResponse:
            del session_id
            title = tool_call.title or ""
            raw_input = (
                dict(tool_call.raw_input)
                if isinstance(tool_call.raw_input, dict)
                else {}
            )
            active = self._active_tool_identity.get(tool_call.tool_call_id)
            if active:
                active_title, active_input = active
                title = title or active_title
                raw_input = {**active_input, **raw_input}
            raw_input["_acp_tool_call_id"] = tool_call.tool_call_id

            selected_id = _reject_option_id(options)
            if self.events.on_permission:
                option_list = [
                    {
                        "id": option.option_id,
                        "name": option.name,
                        "kind": option.kind,
                        "_meta": option.field_meta,
                    }
                    for option in options
                ]
                selected_id = await self.events.on_permission(
                    title or "Unknown",
                    raw_input,
                    option_list,
                )
            return RequestPermissionResponse(
                outcome=AllowedOutcome(outcome="selected", option_id=selected_id)
            )

        handler.session_update = session_update
        handler.request_permission = request_permission
        return handler

    async def _emit_terminal_tool_update(self, update: Any) -> None:
        tool_id = update.tool_call_id
        if tool_id in self._terminal_tool_ids:
            return
        self._terminal_tool_ids.add(tool_id)
        raw_output = update.raw_output
        if update.content is not None:
            raw_output = (
                update.content
                if raw_output is None
                else {"raw_output": raw_output, "content": update.content}
            )
        if self.events.on_tool_end:
            await self.events.on_tool_end(
                tool_id,
                update.status or "",
                raw_output,
            )
        self._active_tool_identity.pop(tool_id, None)

    async def new_session(self) -> str:
        if not self._connection:
            raise RuntimeError("Not connected")
        mcp_servers = [to_acp_mcp_server(server) for server in self.mcp_servers]
        response = await self._connection.new_session(
            cwd=self.cwd,
            mcp_servers=mcp_servers,
        )
        self._session_id = response.session_id
        if self._pending_model:
            pending_model = self._pending_model
            self._pending_model = None
            await self._connection.set_session_model(
                model_id=pending_model,
                session_id=self._session_id,
            )
        return self._session_id

    async def prompt(self, text: str) -> str:
        if not self._connection:
            raise RuntimeError("Not connected")
        if not self._session_id:
            await self.new_session()
        self._text_buffer = ""
        self._terminal_tool_ids.clear()
        self.input_tokens = None
        self.output_tokens = None
        self.model_name = None
        try:
            response = await self._connection.prompt(
                prompt=[TextContentBlock(type="text", text=text)],
                session_id=self._session_id,
            )
            usage = getattr(response, "usage", None)
            if usage is not None:
                self.input_tokens = getattr(usage, "input_tokens", None)
                self.output_tokens = getattr(usage, "output_tokens", None)
            metadata = getattr(response, "field_meta", None) or {}
            if isinstance(metadata, dict):
                quota = metadata.get("quota") or {}
                model_usage = quota.get("model_usage") or []
                if isinstance(model_usage, list) and model_usage:
                    first = model_usage[0]
                    if isinstance(first, dict) and first.get("model"):
                        self.model_name = str(first["model"])
            if self.events.on_complete:
                await self.events.on_complete()
            return self._text_buffer
        except Exception as exc:
            if self.events.on_error:
                await self.events.on_error(exc)
            raise

    async def connect(self) -> None:
        if self._process is not None:
            return
        self._process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
            env=self.env,
            limit=MAX_ACP_FRAME_SIZE,
        )
        if self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("無法建立 Codex ACP subprocess pipes")
        self._stderr_tail.clear()
        self._stderr_task = asyncio.create_task(
            self._drain_stderr(), name="codex-acp-stderr"
        )
        self._connection = ClientSideConnection(
            to_client=self._create_client_handler(),
            input_stream=self._process.stdin,
            output_stream=self._process.stdout,
        )
        response = await self._connection.initialize(
            protocol_version=1,
            client_info=Implementation(
                name="ching-tech-os-codex-client",
                version="1.0.0",
            ),
        )
        logger.info("Codex ACP 已連線: %s", response.agent_info)
        self._initialized = True

    async def disconnect(self) -> None:
        process = self._process
        try:
            await super().disconnect()
        finally:
            stderr_task = self._stderr_task
            self._stderr_task = None
            if stderr_task is not None:
                if not stderr_task.done():
                    stderr_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await stderr_task
            if process is not None:
                for stream in (
                    getattr(process, "stdin", None),
                    getattr(process, "stdout", None),
                    getattr(process, "stderr", None),
                ):
                    transport = getattr(stream, "_transport", None)
                    if transport is not None:
                        transport.close()
                transport = getattr(process, "_transport", None)
                if transport is not None:
                    transport.close()
