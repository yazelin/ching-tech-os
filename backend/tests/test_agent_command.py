"""/agent 指令測試"""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from ching_tech_os.services.bot.commands import CommandContext
from ching_tech_os.services.bot.command_handlers import _handle_agent


def _make_ctx(**kwargs) -> CommandContext:
    """建立測試用 CommandContext"""
    defaults = {
        "platform_type": "line",
        "platform_user_id": "U123",
        "bot_user_id": "bot-user-uuid",
        "ctos_user_id": 1,
        "is_admin": True,
        "is_group": False,
        "group_id": None,
        "reply_token": "token-123",
        "raw_args": "",
    }
    defaults.update(kwargs)
    return CommandContext(**defaults)


AGENT_A_ID = uuid4()
AGENT_B_ID = uuid4()

SELECTABLE_AGENTS = [
    {"id": AGENT_A_ID, "name": "demo-agent", "display_name": "展示助理", "description": "", "model": "claude-haiku"},
    {"id": AGENT_B_ID, "name": "jfmskin-edu", "display_name": "杰膚美衛教助理", "description": "", "model": "claude-haiku"},
]


@pytest.fixture(autouse=True)
def mock_deps():
    """模擬所有外部依賴

    _handle_agent 內部使用 lazy import（from .. import ai_manager），
    所以需要 patch services 模組層級的 ai_manager。
    """
    with (
        patch("ching_tech_os.services.ai_manager.get_selectable_agents", new_callable=AsyncMock) as mock_selectable,
        patch("ching_tech_os.services.ai_manager.get_agent", new_callable=AsyncMock) as mock_get_agent,
        patch("ching_tech_os.services.ai_manager.get_agent_by_name", new_callable=AsyncMock) as mock_get_by_name,
        patch("ching_tech_os.services.linebot_agents.get_group_active_agent_id", new_callable=AsyncMock) as mock_get_group,
        patch("ching_tech_os.services.linebot_agents.get_user_active_agent_id", new_callable=AsyncMock) as mock_get_user,
        patch("ching_tech_os.services.linebot_agents.set_group_active_agent", new_callable=AsyncMock) as mock_set_group,
        patch("ching_tech_os.services.linebot_agents.set_user_active_agent", new_callable=AsyncMock) as mock_set_user,
    ):
        mock_selectable.return_value = SELECTABLE_AGENTS
        mock_get_agent.return_value = None
        mock_get_by_name.return_value = None
        mock_get_group.return_value = None
        mock_get_user.return_value = None
        yield {
            "get_selectable": mock_selectable,
            "get_agent": mock_get_agent,
            "get_by_name": mock_get_by_name,
            "get_group": mock_get_group,
            "get_user": mock_get_user,
            "set_group": mock_set_group,
            "set_user": mock_set_user,
        }


class TestAgentListCommand:
    """無參數顯示清單"""

    @pytest.mark.asyncio
    async def test_show_list_with_default_agent(self):
        ctx = _make_ctx(raw_args="")
        result = await _handle_agent(ctx)
        assert "目前 Agent：預設" in result
        assert "1. demo-agent" in result
        assert "2. jfmskin-edu" in result
        assert "杰膚美衛教助理" in result

    @pytest.mark.asyncio
    async def test_show_list_with_custom_agent(self, mock_deps):
        mock_deps["get_user"].return_value = str(AGENT_A_ID)
        mock_deps["get_agent"].return_value = {
            "name": "demo-agent",
            "display_name": "展示助理",
        }
        ctx = _make_ctx(raw_args="")
        result = await _handle_agent(ctx)
        assert "demo-agent" in result
        assert "展示助理" in result

    @pytest.mark.asyncio
    async def test_show_list_empty(self, mock_deps):
        mock_deps["get_selectable"].return_value = []
        ctx = _make_ctx(raw_args="")
        result = await _handle_agent(ctx)
        assert "沒有可切換的 Agent" in result


class TestAgentSwitchByName:
    """名稱切換"""

    @pytest.mark.asyncio
    async def test_switch_by_name(self, mock_deps):
        ctx = _make_ctx(raw_args="jfmskin-edu")
        result = await _handle_agent(ctx)
        assert "已切換到 杰膚美衛教助理" in result
        mock_deps["set_user"].assert_called_once_with("bot-user-uuid", str(AGENT_B_ID))

    @pytest.mark.asyncio
    async def test_switch_by_name_in_group(self, mock_deps):
        ctx = _make_ctx(raw_args="demo-agent", is_group=True, group_id="group-uuid")
        result = await _handle_agent(ctx)
        assert "已切換到 展示助理" in result
        mock_deps["set_group"].assert_called_once_with("group-uuid", str(AGENT_A_ID))

    @pytest.mark.asyncio
    async def test_switch_nonexistent_agent(self):
        ctx = _make_ctx(raw_args="not-exist")
        result = await _handle_agent(ctx)
        assert "找不到 Agent: not-exist" in result

    @pytest.mark.asyncio
    async def test_switch_non_selectable_agent(self, mock_deps):
        mock_deps["get_by_name"].return_value = {"name": "linebot-personal"}
        ctx = _make_ctx(raw_args="linebot-personal")
        result = await _handle_agent(ctx)
        assert "不可切換" in result


class TestAgentSwitchByNumber:
    """編號切換"""

    @pytest.mark.asyncio
    async def test_switch_by_number(self, mock_deps):
        ctx = _make_ctx(raw_args="1")
        result = await _handle_agent(ctx)
        assert "已切換到 展示助理" in result
        mock_deps["set_user"].assert_called_once_with("bot-user-uuid", str(AGENT_A_ID))

    @pytest.mark.asyncio
    async def test_switch_by_number_second(self, mock_deps):
        ctx = _make_ctx(raw_args="2")
        result = await _handle_agent(ctx)
        assert "已切換到 杰膚美衛教助理" in result

    @pytest.mark.asyncio
    async def test_switch_by_number_out_of_range(self):
        ctx = _make_ctx(raw_args="99")
        result = await _handle_agent(ctx)
        assert "超出範圍" in result

    @pytest.mark.asyncio
    async def test_switch_by_number_zero(self):
        ctx = _make_ctx(raw_args="0")
        result = await _handle_agent(ctx)
        assert "超出範圍" in result


class TestAgentReset:
    """重置"""

    @pytest.mark.asyncio
    async def test_reset_personal(self, mock_deps):
        ctx = _make_ctx(raw_args="reset")
        result = await _handle_agent(ctx)
        assert "已恢復預設 Agent" in result
        mock_deps["set_user"].assert_called_once_with("bot-user-uuid", None)

    @pytest.mark.asyncio
    async def test_reset_group(self, mock_deps):
        ctx = _make_ctx(raw_args="reset", is_group=True, group_id="group-uuid")
        result = await _handle_agent(ctx)
        assert "已恢復預設 Agent" in result
        mock_deps["set_group"].assert_called_once_with("group-uuid", None)

    @pytest.mark.asyncio
    async def test_reset_case_insensitive(self, mock_deps):
        ctx = _make_ctx(raw_args="Reset")
        result = await _handle_agent(ctx)
        assert "已恢復預設 Agent" in result


class TestGetLinebotAgentOverride:
    """Agent 路由覆蓋"""

    @pytest.mark.asyncio
    async def test_default_agent_when_no_preference(self):
        """無偏好時使用預設 Agent"""
        from ching_tech_os.services.linebot_agents import get_linebot_agent

        with (
            patch("ching_tech_os.services.linebot_agents.get_user_active_agent_id", new_callable=AsyncMock, return_value=None),
            patch("ching_tech_os.services.linebot_agents.ai_manager") as mock_mgr,
        ):
            mock_mgr.get_agent_by_name = AsyncMock(return_value={"name": "linebot-personal", "model": "claude-sonnet"})
            result = await get_linebot_agent(is_group=False, bot_user_id="user-1")
            assert result["name"] == "linebot-personal"

    @pytest.mark.asyncio
    async def test_override_agent_when_preference_set(self):
        """有偏好時使用偏好 Agent"""
        from ching_tech_os.services.linebot_agents import get_linebot_agent

        agent_id = str(uuid4())
        override_agent = {"id": agent_id, "name": "custom-agent", "is_active": True, "model": "claude-haiku"}

        with (
            patch("ching_tech_os.services.linebot_agents.get_group_active_agent_id", new_callable=AsyncMock, return_value=agent_id),
            patch("ching_tech_os.services.linebot_agents.ai_manager") as mock_mgr,
        ):
            mock_mgr.get_agent = AsyncMock(return_value=override_agent)
            result = await get_linebot_agent(is_group=True, bot_group_id="group-1")
            assert result["name"] == "custom-agent"

    @pytest.mark.asyncio
    async def test_fallback_when_preference_agent_deleted(self):
        """偏好 Agent 被刪除時 fallback 到預設"""
        from ching_tech_os.services.linebot_agents import get_linebot_agent

        with (
            patch("ching_tech_os.services.linebot_agents.get_user_active_agent_id", new_callable=AsyncMock, return_value=str(uuid4())),
            patch("ching_tech_os.services.linebot_agents.ai_manager") as mock_mgr,
        ):
            mock_mgr.get_agent = AsyncMock(return_value=None)
            mock_mgr.get_agent_by_name = AsyncMock(return_value={"name": "linebot-personal", "model": "claude-sonnet"})
            result = await get_linebot_agent(is_group=False, bot_user_id="user-1")
            assert result["name"] == "linebot-personal"
