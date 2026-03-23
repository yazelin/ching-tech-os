"""測試 bot/command_handlers.py 未覆蓋的部分"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from ching_tech_os.services.bot.command_handlers import (
    _format_agent_tools,
    get_welcome_message,
    _handle_help,
    _handle_agent_restricted,
    DEFAULT_WELCOME_MESSAGE,
)
from ching_tech_os.services.bot.commands import CommandContext


# ============================================
# _format_agent_tools
# ============================================


class TestFormatAgentTools:
    def test_no_tools(self):
        assert _format_agent_tools({}) == ""
        assert _format_agent_tools({"tools": None}) == ""
        assert _format_agent_tools({"tools": []}) == ""

    def test_json_string_tools(self):
        agent = {"tools": '["search_knowledge", "WebSearch"]'}
        result = _format_agent_tools(agent)
        assert "知識庫" in result
        assert "網路搜尋" in result
        assert result.startswith("｜")

    def test_list_tools(self):
        agent = {"tools": ["read_document", "unknown_tool"]}
        result = _format_agent_tools(agent)
        assert "文件讀取" in result
        assert "unknown_tool" in result

    def test_invalid_json_string(self):
        agent = {"tools": "not json"}
        assert _format_agent_tools(agent) == ""

    def test_empty_list(self):
        agent = {"tools": "[]"}
        assert _format_agent_tools(agent) == ""


# ============================================
# get_welcome_message
# ============================================


_AM = "ching_tech_os.services.ai_manager"


class TestGetWelcomeMessage:
    @pytest.mark.asyncio
    async def test_default_message(self):
        """無自訂 agent 時回傳預設"""
        with patch(f"{_AM}.get_agent_by_name", new_callable=AsyncMock, return_value=None):
            result = await get_welcome_message()
            assert result == DEFAULT_WELCOME_MESSAGE

    @pytest.mark.asyncio
    async def test_custom_message(self):
        """有自訂 welcome_message"""
        agent = {"settings": {"welcome_message": "自訂歡迎"}}
        with patch(f"{_AM}.get_agent_by_name", new_callable=AsyncMock, return_value=agent):
            result = await get_welcome_message()
            assert result == "自訂歡迎"

    @pytest.mark.asyncio
    async def test_exception_fallback(self):
        """讀取失敗 fallback"""
        with patch(f"{_AM}.get_agent_by_name", new_callable=AsyncMock, side_effect=Exception("err")):
            result = await get_welcome_message()
            assert result == DEFAULT_WELCOME_MESSAGE

    @pytest.mark.asyncio
    async def test_no_settings(self):
        """agent 存在但無 settings"""
        agent = {"settings": None}
        with patch(f"{_AM}.get_agent_by_name", new_callable=AsyncMock, return_value=agent):
            result = await get_welcome_message()
            assert result == DEFAULT_WELCOME_MESSAGE


# ============================================
# _handle_help
# ============================================


class TestHandleHelp:
    @pytest.mark.asyncio
    async def test_basic_help(self):
        """基本 help 輸出"""
        ctx = MagicMock(spec=CommandContext)
        ctx.platform_type = "line"
        ctx.is_admin = False

        with patch(
            "ching_tech_os.services.bot.command_handlers.router"
        ) as mock_router:
            mock_cmd = MagicMock()
            mock_cmd.enabled = True
            mock_cmd.platforms = {"line", "telegram"}
            mock_cmd.require_admin = False
            mock_cmd.name = "help"
            mock_cmd.description = "查看說明"
            mock_cmd.aliases = ["說明"]

            mock_router._commands = {"help": mock_cmd, "說明": mock_cmd}

            result = await _handle_help(ctx)
            assert "CTOS Bot 使用說明" in result
            assert "/help" in result

    @pytest.mark.asyncio
    async def test_admin_commands_hidden(self):
        """非管理員看不到管理員指令"""
        ctx = MagicMock(spec=CommandContext)
        ctx.platform_type = "line"
        ctx.is_admin = False

        admin_cmd = MagicMock()
        admin_cmd.enabled = True
        admin_cmd.platforms = {"line"}
        admin_cmd.require_admin = True
        admin_cmd.name = "debug"
        admin_cmd.description = "系統診斷"
        admin_cmd.aliases = []

        with patch(
            "ching_tech_os.services.bot.command_handlers.router"
        ) as mock_router:
            mock_router._commands = {"debug": admin_cmd}
            result = await _handle_help(ctx)
            assert "/debug" not in result


# ============================================
# _handle_agent_restricted
# ============================================

_LA = "ching_tech_os.services.linebot_agents"


class TestHandleAgentRestricted:
    @pytest.mark.asyncio
    async def test_not_group(self):
        """非群組回傳提示"""
        ctx = MagicMock(spec=CommandContext)
        ctx.is_group = False
        ctx.group_id = None
        result = await _handle_agent_restricted(ctx, "")
        assert "僅在群組中" in result

    @pytest.mark.asyncio
    async def test_reset(self):
        """重置受限 Agent"""
        ctx = MagicMock(spec=CommandContext)
        ctx.is_group = True
        ctx.group_id = "group-123"

        with patch(f"{_AM}.get_selectable_agents", new_callable=AsyncMock, return_value=[]):
            with patch(f"{_LA}.set_group_restricted_agent", new_callable=AsyncMock):
                result = await _handle_agent_restricted(ctx, "reset")
                assert "重置" in result

    @pytest.mark.asyncio
    async def test_show_status_no_selectable(self):
        """顯示狀態（無可切換 Agent）"""
        ctx = MagicMock(spec=CommandContext)
        ctx.is_group = True
        ctx.group_id = "group-123"

        with patch(f"{_AM}.get_selectable_agents", new_callable=AsyncMock, return_value=[]):
            with patch(f"{_LA}.get_group_restricted_agent_id", new_callable=AsyncMock, return_value=None):
                result = await _handle_agent_restricted(ctx, "")
                assert "受限模式" in result
                assert "沒有可切換" in result

    @pytest.mark.asyncio
    async def test_switch_by_number(self):
        """用編號切換"""
        ctx = MagicMock(spec=CommandContext)
        ctx.is_group = True
        ctx.group_id = "group-123"

        agent_id = uuid4()
        selectable = [
            {"id": agent_id, "name": "agent-1", "display_name": "Agent 一號"}
        ]

        with patch(f"{_AM}.get_selectable_agents", new_callable=AsyncMock, return_value=selectable):
            with patch(f"{_LA}.get_group_restricted_agent_id", new_callable=AsyncMock, return_value=None):
                with patch(f"{_LA}.set_group_restricted_agent", new_callable=AsyncMock):
                    result = await _handle_agent_restricted(ctx, "1")
                    assert "Agent 一號" in result

    @pytest.mark.asyncio
    async def test_switch_by_number_out_of_range(self):
        """編號超出範圍"""
        ctx = MagicMock(spec=CommandContext)
        ctx.is_group = True
        ctx.group_id = "group-123"

        with patch(f"{_AM}.get_selectable_agents", new_callable=AsyncMock, return_value=[]):
            with patch(f"{_LA}.get_group_restricted_agent_id", new_callable=AsyncMock, return_value=None):
                result = await _handle_agent_restricted(ctx, "5")
                assert "超出範圍" in result

    @pytest.mark.asyncio
    async def test_switch_by_name_not_found(self):
        """名稱找不到"""
        ctx = MagicMock(spec=CommandContext)
        ctx.is_group = True
        ctx.group_id = "group-123"

        with patch(f"{_AM}.get_selectable_agents", new_callable=AsyncMock, return_value=[]):
            with patch(f"{_AM}.get_agent_by_name", new_callable=AsyncMock, return_value=None):
                with patch(f"{_LA}.get_group_restricted_agent_id", new_callable=AsyncMock, return_value=None):
                    result = await _handle_agent_restricted(ctx, "unknown")
                    assert "找不到" in result

    @pytest.mark.asyncio
    async def test_switch_by_name_not_selectable(self):
        """Agent 存在但不可選"""
        ctx = MagicMock(spec=CommandContext)
        ctx.is_group = True
        ctx.group_id = "group-123"

        with patch(f"{_AM}.get_selectable_agents", new_callable=AsyncMock, return_value=[]):
            with patch(f"{_AM}.get_agent_by_name", new_callable=AsyncMock, return_value={"name": "private"}):
                with patch(f"{_LA}.get_group_restricted_agent_id", new_callable=AsyncMock, return_value=None):
                    result = await _handle_agent_restricted(ctx, "private")
                    assert "不可切換" in result
