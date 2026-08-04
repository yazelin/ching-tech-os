"""AI provider 共用契約。

此模組只定義 provider-neutral 型別與 Protocol，不負責選擇或啟動 provider。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


ToolNotifyCallback = Callable[[str, dict], Awaitable[None]]
DEFAULT_TIMEOUT = 180


@dataclass
class ToolCall:
    """Provider-neutral 工具呼叫紀錄。"""

    id: str
    name: str
    input: dict
    output: str | None = None


@dataclass
class AIResponse:
    """所有 AI provider 共用的回應格式。"""

    success: bool
    message: str
    error: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    tool_timings: list[dict] = field(default_factory=list)
    provider: str = "unknown"
    actual_model: str | None = None
    route_reason: str | None = None
    provider_started: bool = False
    usage_snapshot: dict[str, Any] | None = None


@runtime_checkable
class AIProvider(Protocol):
    """Claude 與未來 Codex adapter 必須實作的 provider 契約。"""

    provider_name: str

    async def is_ready(self) -> bool:
        """在尚未建立 session 前檢查 provider 是否可接受請求。"""
        ...

    async def call(
        self,
        prompt: str,
        model: str = "sonnet",
        history: list[dict] | None = None,
        system_prompt: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        tools: list[str] | None = None,
        tool_call_limits: dict[str, int] | None = None,
        on_tool_start: ToolNotifyCallback | None = None,
        on_tool_end: ToolNotifyCallback | None = None,
        required_mcp_servers: set[str] | None = None,
        ctos_user_id: int | None = None,
        extra_mcp_env: dict[str, str] | None = None,
    ) -> AIResponse:
        """執行單次 provider request。"""
        ...
