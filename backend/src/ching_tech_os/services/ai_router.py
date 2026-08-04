"""Provider-neutral AI 呼叫旁路。

目前固定委派 Claude；usage routing、canary 與 Codex provider 尚未接入。
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..config import AI_PROVIDER_MODES, settings
from .ai_provider import AIProvider, AIResponse, DEFAULT_TIMEOUT, ToolNotifyCallback
from .claude_agent import call_claude

logger = logging.getLogger(__name__)


class ProviderUnavailableError(RuntimeError):
    """選定的 provider 與允許的 pre-start fallback 都不可用。"""


@dataclass(frozen=True)
class ProviderDecision:
    """單次請求在任何 provider 執行前固定的路由決策。"""

    provider_name: str
    route_reason: str
    fallback_provider: str | None = None
    fallback_reason: str | None = None

    def __post_init__(self) -> None:
        provider_name = self.provider_name.strip().lower()
        route_reason = self.route_reason.strip().lower()
        fallback_provider = (
            self.fallback_provider.strip().lower()
            if self.fallback_provider
            else None
        )
        fallback_reason = (
            self.fallback_reason.strip().lower()
            if self.fallback_reason
            else None
        )
        if not provider_name or not route_reason:
            raise ValueError("provider_name 與 route_reason 不得為空")
        if fallback_provider == provider_name:
            raise ValueError("fallback provider 不得與主要 provider 相同")
        object.__setattr__(self, "provider_name", provider_name)
        object.__setattr__(self, "route_reason", route_reason)
        object.__setattr__(self, "fallback_provider", fallback_provider)
        object.__setattr__(self, "fallback_reason", fallback_reason)


class ProviderRouter:
    """先完成 readiness，再以 sticky provider 執行單次請求。"""

    def __init__(self, providers: Mapping[str, AIProvider]) -> None:
        normalized: dict[str, AIProvider] = {}
        for name, provider in providers.items():
            normalized_name = str(name).strip().lower()
            if not normalized_name:
                raise ValueError("provider registry 名稱不得為空")
            provider_name = str(provider.provider_name).strip().lower()
            if provider_name != normalized_name:
                raise ValueError("provider registry key 與 provider_name 不一致")
            normalized[normalized_name] = provider
        self._providers = normalized

    async def _get_ready_provider(self, provider_name: str) -> AIProvider | None:
        provider = self._providers.get(provider_name)
        if provider is None:
            return None
        try:
            ready = await provider.is_ready()
        except Exception:
            # readiness error 可能含敏感診斷，這裡只記 provider 名稱。
            logger.warning("AI provider %s readiness check 失敗", provider_name)
            return None
        return provider if ready else None

    async def execute(
        self,
        decision: ProviderDecision,
        **provider_kwargs: Any,
    ) -> AIResponse:
        """依既定決策執行；只允許在 provider call 前 fallback。"""
        provider = await self._get_ready_provider(decision.provider_name)
        selected_name = decision.provider_name
        route_reason = decision.route_reason

        if provider is None and decision.fallback_provider:
            selected_name = decision.fallback_provider
            provider = await self._get_ready_provider(selected_name)
            route_reason = decision.fallback_reason or decision.route_reason

        if provider is None:
            raise ProviderUnavailableError(
                f"AI provider unavailable: {selected_name}"
            )

        # 進入 provider.call 後視為已跨越 router 的執行邊界；任何結果或例外
        # 都直接回傳/拋出，不再查詢或呼叫 fallback provider。
        response = await provider.call(**provider_kwargs)
        response.provider = selected_name
        response.route_reason = route_reason
        return response


class _ClaudeProvider:
    """將現有 call_claude 包成 provider-neutral adapter。"""

    provider_name = "claude"

    async def is_ready(self) -> bool:
        return True

    async def call(self, **provider_kwargs: Any) -> AIResponse:
        return await call_claude(**provider_kwargs)


_provider_router = ProviderRouter({"claude": _ClaudeProvider()})


@dataclass(frozen=True)
class RoutingContext:
    """只供 router 判斷的可信上下文，不得傳入模型或 provider。"""

    context_type: str
    agent_name: str | None = None

    def __post_init__(self) -> None:
        normalized_context = self.context_type.strip().lower()
        if not normalized_context:
            raise ValueError("routing context_type 不得為空")
        normalized_agent = self.agent_name.strip().lower() if self.agent_name else None
        object.__setattr__(self, "context_type", normalized_context)
        object.__setattr__(self, "agent_name", normalized_agent or None)


def is_canary_allowed(
    routing_context: RoutingContext | None,
    *,
    allowed_contexts: frozenset[str],
    allowed_agents: frozenset[str],
) -> bool:
    """以 context 或 Agent exact match 判斷是否進入 canary scope。"""
    if routing_context is None:
        return False

    normalized_contexts = {
        str(value).strip().lower() for value in allowed_contexts if str(value).strip()
    }
    normalized_agents = {
        str(value).strip().lower() for value in allowed_agents if str(value).strip()
    }
    if routing_context.context_type in normalized_contexts:
        return True
    return bool(
        routing_context.agent_name
        and routing_context.agent_name in normalized_agents
    )


def _claude_route_reason(routing_context: RoutingContext | None) -> str:
    """在 Codex/usage 尚未接入前，產生安全且可觀測的 Claude 路由原因。"""
    mode = str(settings.ai_provider_mode).strip().lower()
    if mode not in AI_PROVIDER_MODES:
        return "invalid_mode"
    if mode == "claude":
        return "forced_claude"
    if mode == "codex":
        return "codex_unready"
    if not is_canary_allowed(
        routing_context,
        allowed_contexts=settings.ai_provider_canary_contexts,
        allowed_agents=settings.ai_provider_canary_agents,
    ):
        return "canary_not_allowed"
    return "usage_unknown"


def _safe_claude_decision(routing_context: RoutingContext | None) -> ProviderDecision:
    """Codex/usage 尚未接入時，所有 mode 都建立固定 Claude 決策。"""
    return ProviderDecision(
        provider_name="claude",
        route_reason=_claude_route_reason(routing_context),
    )


async def call_ai(
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
    routing_context: RoutingContext | None = None,
) -> AIResponse:
    """以 provider-neutral 介面呼叫 AI，目前永遠固定使用 Claude。

    ``routing_context`` 只保留給未來 router 判斷，不會傳入 prompt 或 provider。
    """
    decision = _safe_claude_decision(routing_context)
    return await _provider_router.execute(
        decision,
        prompt=prompt,
        model=model,
        history=history,
        system_prompt=system_prompt,
        timeout=timeout,
        tools=tools,
        tool_call_limits=tool_call_limits,
        on_tool_start=on_tool_start,
        on_tool_end=on_tool_end,
        required_mcp_servers=required_mcp_servers,
        ctos_user_id=ctos_user_id,
        extra_mcp_env=extra_mcp_env,
    )
