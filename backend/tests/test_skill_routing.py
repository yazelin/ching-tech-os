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


async def _noop():
    pass


def _mock_ensure_db(monkeypatch):
    """Mock ensure_db_connection 避免 CI 無 DB 環境報錯，並放行 app 權限。

    `run_skill_script` 從 issue #210 起多一關 `check_mcp_tool_permission`
    （對到 ai-assistant）。這份檔案測的是 skill 路由，所以把那一關放行；
    未綁定自檢 `require_bound_user` 不受影響，仍然會擋。
    """
    monkeypatch.setattr(skill_script_tools, "ensure_db_connection", _noop)

    async def _allow(_tool_name, _ctos_user_id):
        return True, ""

    monkeypatch.setattr(skill_script_tools, "check_mcp_tool_permission", _allow)


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
        async def get_skills_for_user(self, _app_permissions, **_kw):
            return [script_skill]

        async def get_script_fallback_map(self, _skill_name):
            return {"create_share_link": "create_share_link"}

        async def get_required_mcp_servers(self, _app_permissions, **_kw):
            return {"ching-tech-os"}

    monkeypatch.setattr(bot_agents, "get_skill_manager", lambda: FakeSkillManager(), raising=False)
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
    """script 執行失敗時，依 mapping fallback 到 MCP，且忽略腳本內偽冒的 ctos_user_id。"""

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
                "output": '{"normalized_input":{"resource_type":"knowledge","resource_id":"kb-001","expires_in":"24h","ctos_user_id":999}}',
                "error": "fallback_required",
                "duration_ms": 12,
            }

    async def fake_execute_tool(tool_name: str, arguments: dict) -> str:
        assert tool_name == "create_share_link"
        assert arguments["resource_id"] == "kb-001"
        assert arguments["ctos_user_id"] == 123
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
    _mock_ensure_db(monkeypatch)

    raw = await skill_script_tools.run_skill_script(
        skill="share-links",
        script="create_share_link",
        input='{"resource_type":"knowledge","resource_id":"kb-001"}',
        ctos_user_id=123,
    )
    payload = json.loads(raw)
    assert payload["success"] is True
    assert payload["output"] == "share-link-created"
    assert payload["route"]["fallback_used"] is True
    assert payload["route"]["fallback_tool"] == "create_share_link"


@pytest.mark.asyncio
async def test_run_skill_script_invalid_input_no_fallback(monkeypatch):
    """腳本回報 invalid_input 時，不應 fallback 到 MCP tool。"""

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
                "output": '{"success":false,"error":"invalid_input: 缺少 resource_id"}',
                "error": "",
                "duration_ms": 8,
            }

    async def fake_execute_tool(_tool_name: str, _arguments: dict) -> str:
        pytest.fail("invalid_input 不應觸發 fallback")

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
    _mock_ensure_db(monkeypatch)

    raw = await skill_script_tools.run_skill_script(
        skill="share-links",
        script="create_share_link",
        input='{"resource_type":"knowledge"}',
        ctos_user_id=123,
    )
    payload = json.loads(raw)
    assert payload["success"] is False
    assert payload["route"]["fallback_used"] is False
    assert payload["route"]["fallback_tool"] is None
    assert payload["error"] == "invalid_input: 缺少 resource_id"
    assert payload["output"] == '{"success":false,"error":"invalid_input: 缺少 resource_id"}'


@pytest.mark.asyncio
async def test_run_skill_script_denies_unbound_even_when_default_enabled(monkeypatch):
    """issue #210：未綁定一律不得執行 skill script，即使 requires_app 預設開放。

    `run_skill_script` 等同讓對話端跑伺服器上的程式，所以進了
    `TOOLS_REQUIRE_BOUND_USER`——這條是上一版「預設開放就放行」的相反決定。
    """

    skill_obj = SimpleNamespace(
        name="secure-skill",
        requires_app="file-manager",
        metadata={"ctos": {}},
    )

    class FakeSkillManager:
        async def get_skill(self, _name):
            return skill_obj

        async def has_scripts(self, _name):
            return True

        async def get_script_path(self, _skill, _script):
            return Path("/tmp/fake.py")

        async def get_skill_dir(self, _name):
            return Path("/tmp/secure-skill")

        def get_skill_env_overrides(self, _skill):
            return {}

        async def get_script_fallback_map(self, _skill_name):
            return {}

    class FakeScriptRunner:
        def __init__(self, _skills_dir):
            pass

        async def execute_path(self, _script_path, _skill_name, input="", env_overrides=None):
            return {
                "success": True,
                "output": "ok",
                "error": "",
                "duration_ms": 3,
            }

    async def fake_create_log(_data):
        return {"id": "fake"}

    monkeypatch.setattr(
        "ching_tech_os.skills.script_runner.ScriptRunner",
        FakeScriptRunner,
    )
    monkeypatch.setattr(
        "ching_tech_os.skills.get_skill_manager",
        lambda: FakeSkillManager(),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.permissions.get_effective_app_permissions",
        lambda: {"file-manager": True},
    )
    monkeypatch.setattr(
        "ching_tech_os.services.ai_manager.create_log",
        fake_create_log,
    )
    _mock_ensure_db(monkeypatch)

    monkeypatch.delenv("CTOS_USER_ID", raising=False)

    raw = await skill_script_tools.run_skill_script(
        skill="secure-skill",
        script="read_secret",
        input="{}",
        ctos_user_id=None,
    )
    payload = json.loads(raw)
    assert payload["success"] is False
    from ching_tech_os.services import permissions as permissions_module

    assert payload["error"] == permissions_module.BOUND_USER_REQUIRED_MESSAGE

    # 已綁定照舊跑得動
    async def _admin_role(_uid):
        return {"role": "admin"}

    monkeypatch.setattr(
        "ching_tech_os.services.user.get_user_role_and_permissions", _admin_role
    )

    raw_bound = await skill_script_tools.run_skill_script(
        skill="secure-skill",
        script="read_secret",
        input="{}",
        ctos_user_id=1,
    )
    payload_bound = json.loads(raw_bound)
    assert payload_bound["success"] is True
    assert payload_bound["output"] == "ok"


@pytest.mark.asyncio
async def test_run_skill_script_denies_when_requires_app_disabled(monkeypatch):
    """requires_app 的 skill 若使用者沒有該 app 權限，一律拒絕。"""

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
    monkeypatch.setattr(
        "ching_tech_os.services.permissions.get_effective_app_permissions",
        lambda: {"file-manager": False},
    )
    _mock_ensure_db(monkeypatch)

    async def _user_without_file_manager(_uid):
        return {}

    monkeypatch.setattr(
        "ching_tech_os.services.permissions.get_user_app_permissions",
        _user_without_file_manager,
    )

    async def _role(_uid):
        return {"role": "user"}

    monkeypatch.setattr(
        "ching_tech_os.services.user.get_user_role_and_permissions", _role
    )

    raw = await skill_script_tools.run_skill_script(
        skill="secure-skill",
        script="read_secret",
        input="{}",
        ctos_user_id=1,
    )
    payload = json.loads(raw)
    assert payload["success"] is False
    assert "需要 file-manager 權限" in payload["error"]
