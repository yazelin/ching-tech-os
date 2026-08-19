"""Provider-neutral pipeline 呼叫測試（add-codex-pipeline-parity 3.x）。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services import ai_pipelines
from ching_tech_os.services.ai_provider import AIResponse


@pytest.mark.asyncio
async def test_summarize_messages_parity_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """3.1：summary 走 call_ai，prompt 組合、model role 與 routing context 符合契約。"""
    monkeypatch.setattr(
        ai_pipelines, "get_prompt_content", AsyncMock(return_value="summary prompt")
    )
    call_ai_mock = AsyncMock(
        return_value=AIResponse(success=True, message="摘要完成", provider="claude")
    )
    monkeypatch.setattr(ai_pipelines, "call_ai", call_ai_mock)

    result = await ai_pipelines.summarize_messages(
        [
            {"role": "user", "content": "問題A"},
            {"role": "assistant", "content": "回答B"},
        ],
        timeout=12,
    )
    assert result.success is True
    kwargs = call_ai_mock.await_args.kwargs
    # 契約：對話逐行 role: content、model=haiku、summarizer 為 system prompt
    assert "user: 問題A" in kwargs["prompt"]
    assert "assistant: 回答B" in kwargs["prompt"]
    assert kwargs["model"] == "haiku"
    assert kwargs["system_prompt"] == "summary prompt"
    assert kwargs["timeout"] == 12
    # routing context 用 caller 事實；canary 由設定控制
    assert kwargs["routing_context"].context_type == "compress"


@pytest.mark.asyncio
async def test_summarize_messages_missing_prompt_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ai_pipelines, "get_prompt_content", AsyncMock(return_value=None)
    )
    call_ai_mock = AsyncMock()
    monkeypatch.setattr(ai_pipelines, "call_ai", call_ai_mock)

    result = await ai_pipelines.summarize_messages([{"role": "user", "content": "a"}])
    assert result.success is False
    assert "找不到 summarizer prompt" in (result.error or "")
    assert result.provider_started is False
    call_ai_mock.assert_not_awaited()
