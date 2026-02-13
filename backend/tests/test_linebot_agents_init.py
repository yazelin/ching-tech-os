"""linebot_agents 初始化流程測試。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import ching_tech_os.services.linebot_agents as linebot_agents


@pytest.mark.asyncio
async def test_get_linebot_agent(monkeypatch: pytest.MonkeyPatch):
    get_agent = AsyncMock(return_value={"name": "x"})
    monkeypatch.setattr(linebot_agents.ai_manager, "get_agent_by_name", get_agent)

    await linebot_agents.get_linebot_agent(is_group=False)
    await linebot_agents.get_linebot_agent(is_group=True)

    assert get_agent.await_args_list[0].args[0] == linebot_agents.AGENT_LINEBOT_PERSONAL
    assert get_agent.await_args_list[1].args[0] == linebot_agents.AGENT_LINEBOT_GROUP


@pytest.mark.asyncio
async def test_ensure_default_linebot_agents_skip_existing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        linebot_agents.ai_manager,
        "get_agent_by_name",
        AsyncMock(return_value={"id": 1}),
    )
    create_prompt = AsyncMock()
    create_agent = AsyncMock()
    monkeypatch.setattr(linebot_agents.ai_manager, "create_prompt", create_prompt)
    monkeypatch.setattr(linebot_agents.ai_manager, "create_agent", create_agent)

    await linebot_agents.ensure_default_linebot_agents()

    create_prompt.assert_not_awaited()
    create_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_default_linebot_agents_create_prompt_and_agent(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        linebot_agents.ai_manager,
        "get_agent_by_name",
        AsyncMock(side_effect=[None, None]),
    )
    monkeypatch.setattr(
        linebot_agents.ai_manager,
        "get_prompt_by_name",
        AsyncMock(side_effect=[None, {"id": "00000000-0000-0000-0000-000000000099"}]),
    )
    monkeypatch.setattr(
        linebot_agents.ai_manager,
        "create_prompt",
        AsyncMock(return_value={"id": "00000000-0000-0000-0000-000000000011"}),
    )
    create_agent = AsyncMock()
    monkeypatch.setattr(linebot_agents.ai_manager, "create_agent", create_agent)

    await linebot_agents.ensure_default_linebot_agents()

    assert linebot_agents.ai_manager.create_prompt.await_count == 1
    assert create_agent.await_count == 2
    first_agent_payload = create_agent.await_args_list[0].args[0]
    second_agent_payload = create_agent.await_args_list[1].args[0]
    assert str(first_agent_payload.system_prompt_id) == "00000000-0000-0000-0000-000000000011"
    assert str(second_agent_payload.system_prompt_id) == "00000000-0000-0000-0000-000000000099"
