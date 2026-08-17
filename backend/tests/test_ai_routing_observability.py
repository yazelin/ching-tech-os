"""AI 路由可觀測性測試（7.1–7.4）。

驗證 response routing metadata、structured route log 與敏感資訊防護。
"""

from __future__ import annotations

import json
import logging

import pytest

from ching_tech_os.config import settings
from ching_tech_os.services import ai_router as ai_router_service
from ching_tech_os.services.ai_provider import AIResponse, attach_routing_metadata


class FakeClaudeProvider:
    provider_name = "claude"

    def __init__(self, response: AIResponse, *, ready: bool = True) -> None:
        self.response = response
        self.ready = ready
        self.kwargs: dict | None = None

    async def is_ready(self) -> bool:
        return self.ready

    async def call(self, **kwargs) -> AIResponse:
        self.kwargs = kwargs
        return self.response


@pytest.fixture
def fake_claude_router(monkeypatch: pytest.MonkeyPatch) -> FakeClaudeProvider:
    provider = FakeClaudeProvider(
        AIResponse(success=True, message="hi", actual_model="claude-sonnet-4-5")
    )
    router = ai_router_service.ProviderRouter({"claude": provider})
    monkeypatch.setattr(ai_router_service, "_provider_router", router)
    monkeypatch.setattr(settings, "ai_provider_mode", "claude")
    return provider


# ── 7.1 response metadata ────────────────────────────────────


def test_routing_metadata_fields() -> None:
    response = AIResponse(
        success=True,
        message="ok",
        provider="codex",
        actual_model="gpt-test",
        route_reason="usage_threshold",
        requested_role="sonnet",
        provider_started=True,
        usage_snapshot={"state": "fresh", "utilization": 0.91},
    )
    assert response.routing_metadata() == {
        "provider": "codex",
        "requested_role": "sonnet",
        "actual_model": "gpt-test",
        "route_reason": "usage_threshold",
        "provider_started": True,
        "usage_snapshot": {"state": "fresh", "utilization": 0.91},
    }


@pytest.mark.asyncio
async def test_call_ai_sets_requested_role(fake_claude_router: FakeClaudeProvider) -> None:
    response = await ai_router_service.call_ai(prompt="hi", model="opus")
    assert response.requested_role == "opus"
    assert response.provider == "claude"
    assert response.route_reason == "forced_claude"
    # requested role 不影響傳給 provider 的 model kwarg
    assert fake_claude_router.kwargs is not None
    assert fake_claude_router.kwargs["model"] == "opus"


# ── 7.2 parsed_response helper 與 structured log ─────────────


def test_attach_routing_metadata_creates_and_merges() -> None:
    response = AIResponse(
        success=True, message="ok", provider="claude", requested_role="sonnet"
    )
    created = attach_routing_metadata(None, response)
    assert created["routing"]["provider"] == "claude"

    existing = {"tool_calls": [{"name": "search_knowledge"}]}
    merged = attach_routing_metadata(existing, response)
    assert merged["tool_calls"] == [{"name": "search_knowledge"}]
    assert merged["routing"]["requested_role"] == "sonnet"
    # 不改動呼叫端原本的 dict
    assert "routing" not in existing


@pytest.mark.asyncio
async def test_call_ai_logs_route_without_secrets(
    fake_claude_router: FakeClaudeProvider, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="ching_tech_os.services.ai_router"):
        await ai_router_service.call_ai(
            prompt="hi",
            model="sonnet",
            extra_mcp_env={"API_KEY": "sk-super-secret-value"},
        )
    route_logs = [
        record.getMessage()
        for record in caplog.records
        if "ai_route" in record.getMessage()
    ]
    assert route_logs, "call_ai 必須輸出 ai_route structured log"
    line = route_logs[0]
    assert "provider=claude" in line
    assert "route_reason=forced_claude" in line
    assert "requested_role=sonnet" in line
    assert "actual_model=claude-sonnet-4-5" in line
    assert "provider_latency_ms=" in line
    assert "sk-super-secret-value" not in caplog.text


@pytest.mark.asyncio
async def test_call_ai_logs_provider_unavailable(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    provider = FakeClaudeProvider(AIResponse(success=True, message=""), ready=False)
    router = ai_router_service.ProviderRouter({"claude": provider})
    monkeypatch.setattr(ai_router_service, "_provider_router", router)
    monkeypatch.setattr(settings, "ai_provider_mode", "claude")

    with caplog.at_level(logging.WARNING, logger="ching_tech_os.services.ai_router"):
        with pytest.raises(ai_router_service.ProviderUnavailableError):
            await ai_router_service.call_ai(
                prompt="機密內容不得進 log",
                extra_mcp_env={"TOKEN": "sk-unavailable-secret"},
            )
    assert any("ai_route" in record.getMessage() for record in caplog.records)
    assert "sk-unavailable-secret" not in caplog.text
    assert "機密內容不得進 log" not in caplog.text


@pytest.mark.asyncio
async def test_call_ai_metadata_json_serializable(
    fake_claude_router: FakeClaudeProvider,
) -> None:
    response = await ai_router_service.call_ai(prompt="hi")
    payload = attach_routing_metadata({"tool_calls": []}, response)
    # parsed_response 必須可直接 JSON 序列化寫入 ai_logs
    json.dumps(payload)
