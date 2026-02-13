"""bot.agents fallback 與例外流程測試。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import ching_tech_os.services.bot.agents as bot_agents


@pytest.mark.asyncio
async def test_normalize_and_route_state(monkeypatch: pytest.MonkeyPatch):
    assert bot_agents._normalize_ching_tool_name("create_share_link") == "mcp__ching-tech-os__create_share_link"
    assert bot_agents._normalize_ching_tool_name("mcp__erpnext__list_documents") == "mcp__erpnext__list_documents"

    class _SM:
        async def get_script_fallback_map(self, _name):
            return {"create_share_link": "create_share_link"}

    monkeypatch.setattr(bot_agents.settings, "skill_route_policy", "script-first")
    skills = [
        SimpleNamespace(name="no-script", scripts=[]),
        SimpleNamespace(name="scripted", scripts=["scripts/a.py"]),
    ]
    state = await bot_agents._calculate_tool_routing_state(_SM(), skills)
    assert state["has_script_skills"] is True
    assert state["script_skill_count"] == 1
    assert "mcp__ching-tech-os__create_share_link" in state["script_mcp_overlap"]
    assert state["suppressed_mcp_tools"] == state["script_mcp_overlap"]


@pytest.mark.asyncio
async def test_generate_tools_prompt_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(bot_agents, "_HAS_SKILL_MANAGER", False)
    monkeypatch.setattr(
        bot_agents,
        "_generate_script_tools_prompt",
        AsyncMock(return_value="【Script Tools】\nbase:\n  - run"),
    )
    result = await bot_agents.generate_tools_prompt({"project-management": True})
    assert "【對話附件管理】" in result
    assert "【專案管理】（使用 ERPNext）" in result
    assert "【Script Tools】" in result


@pytest.mark.asyncio
async def test_generate_tools_prompt_skill_manager_exception(monkeypatch: pytest.MonkeyPatch):
    warning = Mock()
    monkeypatch.setattr(bot_agents.logger, "warning", warning)
    monkeypatch.setattr(bot_agents, "_HAS_SKILL_MANAGER", True)

    class _SM:
        async def generate_tools_prompt(self, _permissions, _is_group):
            raise RuntimeError("boom")

    monkeypatch.setattr(bot_agents, "get_skill_manager", lambda: _SM())
    monkeypatch.setattr(
        bot_agents,
        "_generate_script_tools_prompt",
        AsyncMock(return_value=""),
    )

    result = await bot_agents.generate_tools_prompt({})
    assert "【對話附件管理】" in result
    warning.assert_called_once()


@pytest.mark.asyncio
async def test_generate_script_tools_prompt_paths(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(bot_agents, "_HAS_SKILL_MANAGER", False)
    assert await bot_agents._generate_script_tools_prompt({}) == ""

    monkeypatch.setattr(bot_agents, "_HAS_SKILL_MANAGER", True)

    class _SM:
        async def get_skills_for_user(self, _permissions):
            return [
                SimpleNamespace(name="none-script", scripts=[]),
                SimpleNamespace(name="empty-info", scripts=["scripts/a.py"]),
                SimpleNamespace(name="runner", scripts=["scripts/run.py"]),
            ]

        async def get_scripts_info(self, skill_name: str):
            if skill_name == "empty-info":
                return []
            return [{"name": "run", "description": None}]

    monkeypatch.setattr(bot_agents, "get_skill_manager", lambda: _SM())
    prompt = await bot_agents._generate_script_tools_prompt({})
    assert "runner" in prompt
    assert 'run_skill_script(skill="runner"' in prompt
    assert "執行 runner 的腳本 run" in prompt


@pytest.mark.asyncio
async def test_generate_script_tools_prompt_exception(monkeypatch: pytest.MonkeyPatch):
    warning = Mock()
    monkeypatch.setattr(bot_agents.logger, "warning", warning)
    monkeypatch.setattr(bot_agents, "_HAS_SKILL_MANAGER", True)

    class _SM:
        async def get_skills_for_user(self, _permissions):
            raise ValueError("bad")

    monkeypatch.setattr(bot_agents, "get_skill_manager", lambda: _SM())
    assert await bot_agents._generate_script_tools_prompt({}) == ""
    warning.assert_called_once()


def test_generate_usage_tips_with_file_manager():
    tips = bot_agents.generate_usage_tips_prompt({"file-manager": True})
    assert "search_nas_files" in tips


@pytest.mark.asyncio
async def test_get_tools_for_user_fallback(monkeypatch: pytest.MonkeyPatch):
    warning = Mock()
    monkeypatch.setattr(bot_agents.logger, "warning", warning)
    monkeypatch.setattr(bot_agents, "_HAS_SKILL_MANAGER", True)

    class _SM:
        async def get_skills_for_user(self, _permissions):
            raise RuntimeError("oops")

    monkeypatch.setattr(bot_agents, "get_skill_manager", lambda: _SM())
    tools = await bot_agents.get_tools_for_user({"project-management": True})
    assert "Read" in tools
    assert "mcp__erpnext__list_documents" in tools
    warning.assert_called_once()


@pytest.mark.asyncio
async def test_get_tool_routing_paths(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(bot_agents, "_HAS_SKILL_MANAGER", False)
    route = await bot_agents.get_tool_routing_for_user({})
    assert route["has_script_skills"] is False

    warning = Mock()
    monkeypatch.setattr(bot_agents.logger, "warning", warning)
    monkeypatch.setattr(bot_agents, "_HAS_SKILL_MANAGER", True)

    class _SM:
        async def get_skills_for_user(self, _permissions):
            raise RuntimeError("oops")

    monkeypatch.setattr(bot_agents, "get_skill_manager", lambda: _SM())
    route2 = await bot_agents.get_tool_routing_for_user({})
    assert route2["has_script_skills"] is False
    warning.assert_called_once()


@pytest.mark.asyncio
async def test_get_mcp_servers_for_user_paths(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(bot_agents, "_HAS_SKILL_MANAGER", True)

    class _SM:
        async def get_skills_for_user(self, _permissions):
            return [SimpleNamespace(name="runner", scripts=["scripts/run.py"])]

        async def get_required_mcp_servers(self, _permissions):
            return {"erpnext"}

    monkeypatch.setattr(bot_agents, "get_skill_manager", lambda: _SM())
    servers = await bot_agents.get_mcp_servers_for_user({})
    assert servers == {"erpnext", "ching-tech-os"}

    class _SMEmpty:
        async def get_skills_for_user(self, _permissions):
            return [SimpleNamespace(name="no-script", scripts=[])]

        async def get_required_mcp_servers(self, _permissions):
            return set()

    monkeypatch.setattr(bot_agents, "get_skill_manager", lambda: _SMEmpty())
    assert await bot_agents.get_mcp_servers_for_user({}) is None

    warning = Mock()
    monkeypatch.setattr(bot_agents.logger, "warning", warning)

    class _SMError:
        async def get_skills_for_user(self, _permissions):
            raise RuntimeError("oops")

    monkeypatch.setattr(bot_agents, "get_skill_manager", lambda: _SMError())
    assert await bot_agents.get_mcp_servers_for_user({}) is None
    warning.assert_called_once()
