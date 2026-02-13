"""Skill 路由與 external-first 測試。"""

import json
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from ching_tech_os.config import settings as app_settings
from ching_tech_os.skills import SkillManager
from ching_tech_os.services.bot import agents as bot_agents
from ching_tech_os.services.mcp import skill_script_tools


def _write_skill(path: Path, description: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(
        (
            "---\n"
            f"name: {path.name}\n"
            f"description: {description}\n"
            "allowed-tools: Read\n"
            "metadata:\n"
            "  ctos:\n"
            "    requires_app: null\n"
            "    mcp_servers: ching-tech-os\n"
            "---\n\n"
            f"{description}\n"
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_skill_manager_external_first_override(tmp_path, monkeypatch):
    """同名 skill 應由 external root 覆蓋 native。"""
    native_root = tmp_path / "native"
    external_root = tmp_path / "external"
    _write_skill(native_root / "demo", "native-skill")
    _write_skill(external_root / "demo", "external-skill")

    monkeypatch.setattr(
        "ching_tech_os.skills.seed_external.ensure_seed_skills",
        lambda _root: None,
    )

    sm = SkillManager(skills_dir=native_root, external_skills_dir=external_root)
    skill = await sm.get_skill("demo")
    assert skill is not None
    assert skill.description == "external-skill"
    assert skill.source == "external"

    skill_dir = await sm.get_skill_dir("demo")
    assert skill_dir == external_root / "demo"


@pytest.mark.asyncio
async def test_script_first_suppresses_overlap_tools(monkeypatch):
    """script-first 模式會抑制重疊 MCP tool 並保留 run_skill_script。"""
    script_skill = SimpleNamespace(
        name="share-links",
        allowed_tools=["mcp__ching-tech-os__create_share_link"],
        scripts=["scripts/create_share_link.py"],
    )

    class FakeSkillManager:
        async def get_skills_for_user(self, _app_permissions):
            return [script_skill]

        async def get_script_fallback_map(self, _skill_name):
            return {"create_share_link": "create_share_link"}

        async def get_required_mcp_servers(self, _app_permissions):
            return {"ching-tech-os"}

    monkeypatch.setattr(bot_agents, "get_skill_manager", lambda: FakeSkillManager())
    monkeypatch.setattr(bot_agents, "_HAS_SKILL_MANAGER", True)
    monkeypatch.setattr(bot_agents.settings, "skill_route_policy", "script-first")

    tools = await bot_agents.get_tools_for_user({})
    assert "mcp__ching-tech-os__run_skill_script" in tools
    assert "mcp__ching-tech-os__create_share_link" not in tools

    routing = await bot_agents.get_tool_routing_for_user({})
    assert routing["policy"] == "script-first"
    assert routing["script_skill_count"] == 1
    assert "mcp__ching-tech-os__create_share_link" in routing["suppressed_mcp_tools"]


@pytest.mark.asyncio
async def test_run_skill_script_fallback_to_mcp(monkeypatch):
    """script 執行失敗時，依 mapping fallback 到 MCP tool。"""

    skill_obj = SimpleNamespace(
        name="share-links",
        requires_app=None,
        metadata={
            "ctos": {
                "script_mcp_fallback": {"create_share_link": "create_share_link"},
            }
        },
    )

    class FakeSkillManager:
        async def get_skill(self, _name):
            return skill_obj

        async def has_scripts(self, _name):
            return True

        async def get_script_path(self, _skill, _script):
            return Path("/tmp/fake.py")

        async def get_skill_dir(self, _name):
            return Path("/tmp/share-links")

        def get_skill_env_overrides(self, _skill):
            return {}

        async def get_script_fallback_map(self, _skill_name):
            return {"create_share_link": "create_share_link"}

    class FakeScriptRunner:
        def __init__(self, _skills_dir):
            pass

        async def execute_path(self, _script_path, _skill_name, input="", env_overrides=None):
            return {
                "success": False,
                "output": '{"normalized_input":{"resource_type":"knowledge","resource_id":"kb-001","expires_in":"24h"}}',
                "error": "fallback_required",
                "duration_ms": 12,
            }

    async def fake_execute_tool(tool_name: str, arguments: dict) -> str:
        assert tool_name == "create_share_link"
        assert arguments["resource_id"] == "kb-001"
        return "share-link-created"

    async def fake_create_log(_data):
        return {"id": "fake"}

    monkeypatch.setattr(
        "ching_tech_os.skills.script_runner.ScriptRunner",
        FakeScriptRunner,
    )
    mcp_server_module = importlib.import_module("ching_tech_os.services.mcp.server")
    monkeypatch.setattr(mcp_server_module, "execute_tool", fake_execute_tool)
    monkeypatch.setattr(
        "ching_tech_os.services.ai_manager.create_log",
        fake_create_log,
    )
    monkeypatch.setattr(
        "ching_tech_os.skills.get_skill_manager",
        lambda: FakeSkillManager(),
    )
    monkeypatch.setattr(app_settings, "skill_script_fallback_enabled", True)
    monkeypatch.setattr(app_settings, "skill_route_policy", "script-first")

    raw = await skill_script_tools.run_skill_script(
        skill="share-links",
        script="create_share_link",
        input='{"resource_type":"knowledge","resource_id":"kb-001"}',
    )
    payload = json.loads(raw)
    assert payload["success"] is True
    assert payload["output"] == "share-link-created"
    assert payload["route"]["fallback_used"] is True
    assert payload["route"]["fallback_tool"] == "create_share_link"


@pytest.mark.asyncio
async def test_run_skill_script_denies_when_requires_app_without_user_id(monkeypatch):
    """requires_app 的 skill 若缺少 ctos_user_id，應直接拒絕。"""

    skill_obj = SimpleNamespace(
        name="secure-skill",
        requires_app="file-manager",
        metadata={"ctos": {}},
    )

    class FakeSkillManager:
        async def get_skill(self, _name):
            return skill_obj

    monkeypatch.setattr(
        "ching_tech_os.skills.get_skill_manager",
        lambda: FakeSkillManager(),
    )

    raw = await skill_script_tools.run_skill_script(
        skill="secure-skill",
        script="read_secret",
        input="{}",
        ctos_user_id=None,
    )
    payload = json.loads(raw)
    assert payload["success"] is False
    assert "缺少使用者身分" in payload["error"]
