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
    requested_role: str | None = None
    provider_started: bool = False
    usage_snapshot: dict[str, Any] | None = None

    def routing_metadata(self) -> dict[str, Any]:
        """可直接寫入 structured log 與 ai_logs.parsed_response 的安全路由資訊。"""
        return {
            "provider": self.provider,
            "requested_role": self.requested_role,
            "actual_model": self.actual_model,
            "route_reason": self.route_reason,
            "provider_started": self.provider_started,
            "usage_snapshot": self.usage_snapshot,
        }


def attach_routing_metadata(
    parsed_response: dict[str, Any] | None, response: AIResponse
) -> dict[str, Any]:
    """將路由資訊併入 ai_logs 的 parsed_response；不改動呼叫端原本的 dict。"""
    merged = dict(parsed_response or {})
    merged["routing"] = response.routing_metadata()
    return merged


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
