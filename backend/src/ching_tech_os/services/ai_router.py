"""Provider-neutral AI 呼叫旁路。"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..config import AI_PROVIDER_MODES, settings
from .ai_provider import AIProvider, AIResponse, DEFAULT_TIMEOUT, ToolNotifyCallback
from .claude_agent import call_claude
from .claude_usage import UsageSnapshot, claude_usage_monitor
from .codex_agent import call_codex, codex_provider

logger = logging.getLogger(__name__)


class ProviderUnavailableError(RuntimeError):
    """選定的 provider 與允許的 pre-start fallback 都不可用。"""


# 首批 canary 只允許唯讀工具進 Codex（spec：副作用工具 MUST NOT 暴露給 Codex）。
# 以動詞前綴 fail closed：不在名單內的一律移除，寧可少工具也不放行副作用。
_CODEX_READONLY_TOOL_PREFIXES = ("search_", "get_", "read_", "list_", "find_")


def filter_codex_readonly_tools(
    tools: list[str] | None,
    extra_allowlist: frozenset[str] = frozenset(),
) -> list[str] | None:
    """回傳只含唯讀 MCP 工具的清單；非 canonical 名稱或非唯讀動詞一律移除。

    ``extra_allowlist`` 為 per-context 明確放行的 canonical 工具名（fail-closed：
    只有完全相符才放行，預設空集合時行為與純唯讀規則完全相同）。
    """
    if tools is None:
        return None
    filtered: list[str] = []
    for tool in tools:
        normalized = str(tool).strip().lower()
        if not normalized.startswith("mcp__"):
            continue
        _server, separator, tool_name = normalized[5:].partition("__")
        if not separator:
            continue
        if tool_name.startswith(_CODEX_READONLY_TOOL_PREFIXES) or normalized in extra_allowlist:
            filtered.append(tool)
    # allowlist 語意為「保證此 context 下 Codex 可用」：即使被上游（如 script-first
    # 路由）從清單隱藏，也補回來——MCP server 本就提供這些工具，只是權限未開
    normalized_filtered = {str(t).strip().lower() for t in filtered}
    for tool in sorted(extra_allowlist):
        if tool not in normalized_filtered:
            filtered.append(tool)
    return filtered


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
        *,
        codex_extra_tools: frozenset[str] = frozenset(),
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

        # 首批 canary：副作用工具不得暴露給 Codex；過濾必須在 provider
        # 選定之後做，pre-start fallback 回 Claude 時才能保有完整工具。
        if selected_name == "codex":
            original_tools = provider_kwargs.get("tools")
            filtered_tools = filter_codex_readonly_tools(
                original_tools, extra_allowlist=codex_extra_tools
            )
            removed = len(original_tools or []) - len(filtered_tools or [])
            if removed:
                logger.info(
                    "ai_route codex_readonly_filter removed=%d kept=%d",
                    removed,
                    len(filtered_tools or []),
                )
            provider_kwargs["tools"] = filtered_tools

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


class _CodexProvider:
    """保留可 monkeypatch 的 call_codex 邊界並委派 readiness。"""

    provider_name = "codex"

    async def is_ready(self) -> bool:
        return await codex_provider.is_ready()

    async def call(self, **provider_kwargs: Any) -> AIResponse:
        return await call_codex(**provider_kwargs)


_provider_router = ProviderRouter(
    {"claude": _ClaudeProvider(), "codex": _CodexProvider()}
)


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


class UsageRoutingPolicy:
    """以 90%/85% hysteresis 維持單一穩定 provider 狀態。"""

    def __init__(self, *, switch_threshold: float, recovery_threshold: float) -> None:
        if not 0 <= recovery_threshold < switch_threshold <= 1:
            raise ValueError("usage thresholds 必須符合 0 <= recovery < switch <= 1")
        self.switch_threshold = switch_threshold
        self.recovery_threshold = recovery_threshold
        self._stable_provider = "claude"
        self._lock = threading.Lock()

    def select(self, snapshot: UsageSnapshot) -> tuple[str, str]:
        with self._lock:
            if snapshot.state == "unknown":
                self._stable_provider = "claude"
                return "claude", "usage_unknown"
            if snapshot.state == "error" or snapshot.utilization is None:
                self._stable_provider = "claude"
                return "claude", "usage_error"
            if snapshot.state == "stale":
                return self._stable_provider, "usage_stale"

            if snapshot.utilization >= self.switch_threshold:
                self._stable_provider = "codex"
                return "codex", "usage_threshold"
            if snapshot.utilization < self.recovery_threshold:
                reason = (
                    "usage_recovered"
                    if self._stable_provider == "codex"
                    else "usage_below_threshold"
                )
                self._stable_provider = "claude"
                return "claude", reason
            return self._stable_provider, "usage_hysteresis"


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


def select_provider_decision(
    *,
    mode: str,
    routing_context: RoutingContext | None,
    usage_snapshot: UsageSnapshot | None,
    policy: UsageRoutingPolicy,
    allowed_contexts: frozenset[str],
    allowed_agents: frozenset[str],
) -> ProviderDecision:
    """在 provider 執行前，以設定、canary 與快照建立單次決策。"""
    mode = str(mode).strip().lower()
    if mode not in AI_PROVIDER_MODES:
        return ProviderDecision("claude", "invalid_mode")
    if mode == "claude":
        return ProviderDecision("claude", "forced_claude")
    if mode == "codex":
        return ProviderDecision(
            "codex",
            "forced_codex",
            fallback_provider="claude",
            fallback_reason="codex_unready",
        )
    if not is_canary_allowed(
        routing_context,
        allowed_contexts=allowed_contexts,
        allowed_agents=allowed_agents,
    ):
        return ProviderDecision("claude", "canary_not_allowed")

    selected, reason = policy.select(usage_snapshot or UsageSnapshot())
    if selected == "codex":
        return ProviderDecision(
            "codex",
            reason,
            fallback_provider="claude",
            fallback_reason="codex_unready",
        )
    return ProviderDecision("claude", reason)


async def provider_status() -> dict[str, Any]:
    """Provider readiness、circuit 與 usage 快照的安全彙總，供 admin 觀測。

    輸出不得包含 credentials、token 或原始錯誤內容。
    """
    return {
        "mode": str(settings.ai_provider_mode).strip().lower(),
        "providers": {
            "claude": {"ready": True},
            "codex": await codex_provider.status(),
        },
        "usage": claude_usage_monitor.snapshot().as_metadata(),
    }


_usage_policy = UsageRoutingPolicy(
    switch_threshold=settings.claude_usage_switch_threshold,
    recovery_threshold=settings.claude_usage_recovery_threshold,
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
    """以 provider-neutral 介面呼叫 AI。

    ``routing_context`` 只保留給未來 router 判斷，不會傳入 prompt 或 provider。
    """
    mode = str(settings.ai_provider_mode).strip().lower()
    usage_snapshot = claude_usage_monitor.snapshot() if mode == "auto" else None
    decision = select_provider_decision(
        mode=mode,
        routing_context=routing_context,
        usage_snapshot=usage_snapshot,
        policy=_usage_policy,
        allowed_contexts=settings.ai_provider_canary_contexts,
        allowed_agents=settings.ai_provider_canary_agents,
    )
    # per-context 額外工具 allowlist（預設空 = 純唯讀 fail-closed）
    codex_extra_tools: frozenset[str] = frozenset()
    if routing_context is not None:
        codex_extra_tools = settings.codex_context_tool_allowlist.get(
            routing_context.context_type, frozenset()
        )

    started = time.monotonic()
    try:
        response = await _provider_router.execute(
            decision,
            codex_extra_tools=codex_extra_tools,
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
    except ProviderUnavailableError:
        # 只記路由決策，不記 prompt 或任何 provider kwargs
        logger.warning(
            "ai_route unavailable mode=%s provider=%s route_reason=%s",
            mode,
            decision.provider_name,
            decision.route_reason,
        )
        raise
    response.requested_role = str(model)
    if usage_snapshot is not None:
        response.usage_snapshot = usage_snapshot.as_metadata()
    # Claude 請求成功代表 OAuth token 剛被刷新；usage 快照若已退化，
    # 立刻非同步補一次 refresh（零成本、不阻塞、single-flight）
    if mode == "auto" and response.success and response.provider == "claude":
        claude_usage_monitor.nudge_after_success()
    logger.info(
        "ai_route provider=%s route_reason=%s context=%s requested_role=%s "
        "actual_model=%s success=%s provider_latency_ms=%d tool_calls=%d",
        response.provider,
        response.route_reason,
        routing_context.context_type if routing_context else "none",
        response.requested_role,
        response.actual_model,
        response.success,
        int((time.monotonic() - started) * 1000),
        len(response.tool_calls),
    )
    return response
