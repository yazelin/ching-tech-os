"""Provider-neutral AI 契約與固定 Claude 旁路測試。"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from ching_tech_os import config
from ching_tech_os.services import ai_provider, ai_router, claude_agent, claude_usage


class _FakeProvider:
    def __init__(
        self,
        provider_name: str,
        *,
        ready: bool = True,
        readiness_error: Exception | None = None,
        response: ai_provider.AIResponse | None = None,
        call_error: Exception | None = None,
    ) -> None:
        self.provider_name = provider_name
        self.ready = ready
        self.readiness_error = readiness_error
        self.response = response or ai_provider.AIResponse(
            success=True,
            message=f"{provider_name} 回覆",
            provider=provider_name,
            provider_started=True,
        )
        self.call_error = call_error
        self.readiness_count = 0
        self.call_count = 0
        self.received_kwargs: dict = {}

    async def is_ready(self) -> bool:
        self.readiness_count += 1
        if self.readiness_error:
            raise self.readiness_error
        return self.ready

    async def call(self, **kwargs):
        self.call_count += 1
        self.received_kwargs = kwargs
        if self.call_error:
            raise self.call_error
        return self.response


def test_provider_types_keep_claude_alias_compatible(provider_contract_spec) -> None:
    assert claude_agent.ClaudeResponse is ai_provider.AIResponse
    assert claude_agent.ToolCall is ai_provider.ToolCall

    response = claude_agent.ClaudeResponse(success=True, message="相容回覆")
    assert response.provider == "unknown"
    assert response.actual_model is None
    assert response.route_reason is None
    assert response.provider_started is False
    assert response.usage_snapshot is None
    assert provider_contract_spec.response_fields <= set(vars(response))
    assert provider_contract_spec.routing_metadata_fields <= set(vars(response))


def test_call_ai_signature_extends_claude_contract(provider_contract_spec) -> None:
    request_fields = set(inspect.signature(ai_router.call_ai).parameters)
    assert request_fields == provider_contract_spec.ai_request_fields


def test_ai_provider_protocol_is_runtime_checkable() -> None:
    class _FakeProvider:
        provider_name = "fake"

        async def is_ready(self) -> bool:
            return True

        async def call(self, **_kwargs):
            return ai_provider.AIResponse(success=True, message="ok")

    assert isinstance(_FakeProvider(), ai_provider.AIProvider)


def test_provider_decision_normalizes_and_rejects_ambiguous_fallback() -> None:
    decision = ai_router.ProviderDecision(
        provider_name=" Codex ",
        route_reason=" Forced_Codex ",
        fallback_provider=" Claude ",
        fallback_reason=" Codex_Unready ",
    )
    assert decision.provider_name == "codex"
    assert decision.route_reason == "forced_codex"
    assert decision.fallback_provider == "claude"
    assert decision.fallback_reason == "codex_unready"

    with pytest.raises(ValueError, match="不得為空"):
        ai_router.ProviderDecision(provider_name=" ", route_reason="forced_codex")
    with pytest.raises(ValueError, match="不得與主要 provider 相同"):
        ai_router.ProviderDecision(
            provider_name="claude",
            route_reason="forced_claude",
            fallback_provider="CLAUDE",
        )


def test_provider_registry_rejects_empty_or_mismatched_names() -> None:
    claude = _FakeProvider("claude")
    with pytest.raises(ValueError, match="名稱不得為空"):
        ai_router.ProviderRouter({" ": claude})
    with pytest.raises(ValueError, match="不一致"):
        ai_router.ProviderRouter({"codex": claude})


def test_provider_mode_env_validation_falls_back_to_claude(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    allowed = frozenset({"claude", "codex", "auto"})

    monkeypatch.delenv("TEST_AI_PROVIDER_MODE", raising=False)
    assert config._get_env_choice("TEST_AI_PROVIDER_MODE", "claude", allowed) == "claude"

    monkeypatch.setenv("TEST_AI_PROVIDER_MODE", " AUTO ")
    assert config._get_env_choice("TEST_AI_PROVIDER_MODE", "claude", allowed) == "auto"

    caplog.set_level("ERROR", logger=config.__name__)
    monkeypatch.setenv("TEST_AI_PROVIDER_MODE", "invalid-provider")
    assert config._get_env_choice("TEST_AI_PROVIDER_MODE", "claude", allowed) == "claude"
    assert "TEST_AI_PROVIDER_MODE" in caplog.text
    assert "使用安全預設值 claude" in caplog.text

    monkeypatch.setenv(
        "TEST_AI_PROVIDER_CANARY",
        " Internal_Admin, internal_test,INTERNAL_ADMIN,, ",
    )
    assert config._get_env_lower_set("TEST_AI_PROVIDER_CANARY") == {
        "internal_admin",
        "internal_test",
    }


def test_numeric_env_helpers_validate_without_changing_existing_int_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_EXISTING_INT", "42")
    assert config._get_env_int("TEST_EXISTING_INT", 7) == 42
    monkeypatch.setenv("TEST_EXISTING_INT", "invalid")
    assert config._get_env_int("TEST_EXISTING_INT", 7) == 7

    monkeypatch.setenv("TEST_BOUNDED_FLOAT", "0.9")
    assert config._get_env_float_bounded(
        "TEST_BOUNDED_FLOAT", 0.5, minimum=0.0, maximum=1.0
    ) == 0.9
    monkeypatch.setenv("TEST_BOUNDED_FLOAT", "1.1")
    assert config._get_env_float_bounded(
        "TEST_BOUNDED_FLOAT", 0.5, minimum=0.0, maximum=1.0
    ) == 0.5

    monkeypatch.setenv("TEST_BOUNDED_INT", "60")
    assert config._get_env_int_bounded(
        "TEST_BOUNDED_INT", 30, minimum=5, maximum=300
    ) == 60
    monkeypatch.setenv("TEST_BOUNDED_INT", "oops")
    assert config._get_env_int_bounded(
        "TEST_BOUNDED_INT", 30, minimum=5, maximum=300
    ) == 30


def test_routing_context_normalizes_and_validates_values() -> None:
    context = ai_router.RoutingContext(
        context_type=" Internal_Admin ",
        agent_name=" Test-Agent ",
    )
    assert context.context_type == "internal_admin"
    assert context.agent_name == "test-agent"

    with pytest.raises(ValueError, match="context_type"):
        ai_router.RoutingContext(context_type="   ")


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        (ai_router.RoutingContext(context_type="internal_admin"), True),
        (ai_router.RoutingContext(context_type="web", agent_name="test-agent"), True),
        (ai_router.RoutingContext(context_type="web", agent_name="normal-agent"), False),
        (ai_router.RoutingContext(context_type="web", agent_name="test-agent-copy"), False),
        (None, False),
    ],
)
def test_canary_allowlist_matches_context_or_agent(context, expected: bool) -> None:
    assert ai_router.is_canary_allowed(
        context,
        allowed_contexts=frozenset({"internal_admin", "internal_test"}),
        allowed_agents=frozenset({"test-agent"}),
    ) is expected


@pytest.mark.asyncio
async def test_call_ai_forced_claude_forwards_all_provider_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = ai_provider.AIResponse(
        success=True,
        message="Claude 回覆",
        provider="claude",
        route_reason="direct_claude",
        provider_started=True,
    )
    call_claude = AsyncMock(return_value=response)
    monkeypatch.setattr(ai_router, "call_claude", call_claude)
    monkeypatch.setattr(ai_router.settings, "ai_provider_mode", "claude")

    on_start = AsyncMock()
    on_end = AsyncMock()
    result = await ai_router.call_ai(
        prompt="最新問題",
        model="claude-opus",
        history=[{"role": "user", "content": "先前問題"}],
        system_prompt="系統提示",
        timeout=45,
        tools=["search_knowledge"],
        tool_call_limits={"search_knowledge": 1},
        on_tool_start=on_start,
        on_tool_end=on_end,
        required_mcp_servers={"ching-tech-os"},
        ctos_user_id=123,
        extra_mcp_env={"CTOS_GROUP_ID": "group-1"},
        routing_context=ai_router.RoutingContext(
            context_type="internal_test",
            agent_name="test-agent",
        ),
    )

    assert result is response
    assert result.provider == "claude"
    assert result.route_reason == "forced_claude"
    call_claude.assert_awaited_once_with(
        prompt="最新問題",
        model="claude-opus",
        history=[{"role": "user", "content": "先前問題"}],
        system_prompt="系統提示",
        timeout=45,
        tools=["search_knowledge"],
        tool_call_limits={"search_knowledge": 1},
        on_tool_start=on_start,
        on_tool_end=on_end,
        required_mcp_servers={"ching-tech-os"},
        ctos_user_id=123,
        extra_mcp_env={"CTOS_GROUP_ID": "group-1"},
    )


@pytest.mark.asyncio
async def test_call_ai_does_not_retry_after_claude_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_claude = AsyncMock(side_effect=RuntimeError("provider failed"))
    monkeypatch.setattr(ai_router, "call_claude", call_claude)

    with pytest.raises(RuntimeError, match="provider failed"):
        await ai_router.call_ai(prompt="不要重送")

    assert call_claude.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "routing_context", "expected_reason"),
    [
        ("claude", None, "forced_claude"),
        ("codex", None, "codex_unready"),
        ("invalid-provider", None, "invalid_mode"),
        (
            "auto",
            ai_router.RoutingContext(context_type="web", agent_name="normal-agent"),
            "canary_not_allowed",
        ),
        (
            "auto",
            ai_router.RoutingContext(context_type="internal_test"),
            "usage_unknown",
        ),
    ],
)
async def test_call_ai_modes_remain_safely_on_claude_without_codex_provider(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    routing_context,
    expected_reason: str,
) -> None:
    response = ai_provider.AIResponse(success=True, message="安全回覆")
    call_claude = AsyncMock(return_value=response)
    monkeypatch.setattr(ai_router, "call_claude", call_claude)
    monkeypatch.setattr(ai_router.settings, "ai_provider_mode", mode)
    monkeypatch.setattr(
        ai_router.settings,
        "ai_provider_canary_contexts",
        frozenset({"internal_admin", "internal_test"}),
    )
    monkeypatch.setattr(
        ai_router.settings,
        "ai_provider_canary_agents",
        frozenset({"test-agent"}),
    )

    result = await ai_router.call_ai(
        prompt="安全模式測試",
        routing_context=routing_context,
    )

    assert result.provider == "claude"
    assert result.route_reason == expected_reason
    call_claude.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "readiness_error",
    [None, RuntimeError("preflight failed")],
)
async def test_provider_router_falls_back_only_when_primary_is_unready(
    readiness_error: Exception | None,
) -> None:
    codex = _FakeProvider(
        "codex",
        ready=False,
        readiness_error=readiness_error,
    )
    claude = _FakeProvider("claude")
    router = ai_router.ProviderRouter({"codex": codex, "claude": claude})
    decision = ai_router.ProviderDecision(
        provider_name="codex",
        route_reason="forced_codex",
        fallback_provider="claude",
        fallback_reason="codex_unready",
    )

    result = await router.execute(decision, prompt="唯讀測試")

    assert result.provider == "claude"
    assert result.route_reason == "codex_unready"
    assert codex.readiness_count == 1
    assert codex.call_count == 0
    assert claude.readiness_count == 1
    assert claude.call_count == 1
    assert claude.received_kwargs == {"prompt": "唯讀測試"}


@pytest.mark.asyncio
async def test_provider_router_treats_missing_primary_as_pre_start_unready() -> None:
    claude = _FakeProvider("claude")
    router = ai_router.ProviderRouter({"claude": claude})
    decision = ai_router.ProviderDecision(
        provider_name="codex",
        route_reason="forced_codex",
        fallback_provider="claude",
        fallback_reason="codex_unready",
    )

    result = await router.execute(decision, prompt="adapter 尚未安裝")

    assert result.provider == "claude"
    assert result.route_reason == "codex_unready"
    assert claude.readiness_count == 1
    assert claude.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_started", [False, True])
async def test_provider_router_keeps_selection_sticky_after_call_begins(
    provider_started: bool,
) -> None:
    codex_response = ai_provider.AIResponse(
        success=False,
        message="部分內容",
        error="provider failed",
        provider="codex",
        provider_started=provider_started,
    )
    codex = _FakeProvider("codex", response=codex_response)
    claude = _FakeProvider("claude")
    router = ai_router.ProviderRouter({"codex": codex, "claude": claude})
    decision = ai_router.ProviderDecision(
        provider_name="codex",
        route_reason="forced_codex",
        fallback_provider="claude",
        fallback_reason="codex_unready",
    )

    result = await router.execute(decision, prompt="不可重送")

    assert result is codex_response
    assert result.provider == "codex"
    assert result.route_reason == "forced_codex"
    assert codex.call_count == 1
    assert claude.readiness_count == 0
    assert claude.call_count == 0


@pytest.mark.asyncio
async def test_provider_router_does_not_retry_call_exception() -> None:
    codex = _FakeProvider(
        "codex",
        call_error=RuntimeError("execution failed"),
    )
    claude = _FakeProvider("claude")
    router = ai_router.ProviderRouter({"codex": codex, "claude": claude})
    decision = ai_router.ProviderDecision(
        provider_name="codex",
        route_reason="forced_codex",
        fallback_provider="claude",
        fallback_reason="codex_unready",
    )

    with pytest.raises(RuntimeError, match="execution failed"):
        await router.execute(decision, prompt="不可重送")

    assert codex.call_count == 1
    assert claude.readiness_count == 0
    assert claude.call_count == 0


@pytest.mark.asyncio
async def test_provider_router_fails_when_fallback_is_also_unready() -> None:
    codex = _FakeProvider("codex", ready=False)
    claude = _FakeProvider("claude", ready=False)
    router = ai_router.ProviderRouter({"codex": codex, "claude": claude})
    decision = ai_router.ProviderDecision(
        provider_name="codex",
        route_reason="forced_codex",
        fallback_provider="claude",
        fallback_reason="codex_unready",
    )

    with pytest.raises(ai_router.ProviderUnavailableError, match="claude"):
        await router.execute(decision, prompt="無可用 provider")

    assert codex.call_count == 0
    assert claude.call_count == 0


def _usage_snapshot(state: str, utilization: float | None) -> claude_usage.UsageSnapshot:
    now = datetime(2026, 8, 4, tzinfo=UTC)
    return claude_usage.UsageSnapshot(
        state=state,
        utilization=utilization,
        five_hour=utilization,
        seven_day=utilization,
        fetched_at=now if utilization is not None else None,
        last_attempt_at=now if state != "unknown" else None,
    )


def test_usage_policy_applies_90_85_hysteresis() -> None:
    policy = ai_router.UsageRoutingPolicy(switch_threshold=0.90, recovery_threshold=0.85)

    assert policy.select(_usage_snapshot("fresh", 0.849)) == ("claude", "usage_below_threshold")
    assert policy.select(_usage_snapshot("fresh", 0.899)) == ("claude", "usage_hysteresis")
    assert policy.select(_usage_snapshot("fresh", 0.90)) == ("codex", "usage_threshold")
    assert policy.select(_usage_snapshot("fresh", 0.85)) == ("codex", "usage_hysteresis")
    assert policy.select(_usage_snapshot("fresh", 0.849)) == ("claude", "usage_recovered")

    with pytest.raises(ValueError, match="thresholds"):
        ai_router.UsageRoutingPolicy(switch_threshold=0.85, recovery_threshold=0.90)


def test_usage_policy_handles_unknown_stale_and_error_safely() -> None:
    policy = ai_router.UsageRoutingPolicy(switch_threshold=0.90, recovery_threshold=0.85)

    assert policy.select(_usage_snapshot("unknown", None)) == ("claude", "usage_unknown")
    assert policy.select(_usage_snapshot("fresh", 0.95))[0] == "codex"
    assert policy.select(_usage_snapshot("stale", 0.95)) == ("codex", "usage_stale")
    assert policy.select(_usage_snapshot("error", 0.95)) == ("claude", "usage_error")
    assert policy.select(_usage_snapshot("stale", 0.95)) == ("claude", "usage_stale")


def test_auto_route_decision_requires_canary_and_attaches_safe_fallback() -> None:
    policy = ai_router.UsageRoutingPolicy(switch_threshold=0.90, recovery_threshold=0.85)
    canary = ai_router.RoutingContext(context_type="internal_test")

    denied = ai_router.select_provider_decision(
        mode="auto",
        routing_context=ai_router.RoutingContext(context_type="web"),
        usage_snapshot=_usage_snapshot("fresh", 0.95),
        policy=policy,
        allowed_contexts=frozenset({"internal_test"}),
        allowed_agents=frozenset(),
    )
    assert denied.provider_name == "claude"
    assert denied.route_reason == "canary_not_allowed"

    selected = ai_router.select_provider_decision(
        mode="auto",
        routing_context=canary,
        usage_snapshot=_usage_snapshot("fresh", 0.95),
        policy=policy,
        allowed_contexts=frozenset({"internal_test"}),
        allowed_agents=frozenset(),
    )
    assert selected.provider_name == "codex"
    assert selected.route_reason == "usage_threshold"
    assert selected.fallback_provider == "claude"
    assert selected.fallback_reason == "codex_unready"
