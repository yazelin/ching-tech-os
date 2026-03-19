"""黑名單機制測試"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from ching_tech_os.services.bot.identity_router import handle_restricted_mode


class TestIsUserBlocked:
    """封鎖狀態檢查"""

    @pytest.mark.asyncio
    async def test_blocked_user_returns_none(self):
        """封鎖用戶 → 靜默忽略（return None）"""
        with (
            patch(
                "ching_tech_os.services.bot_line.admin.is_user_blocked",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "ching_tech_os.services.bot.identity_router.settings"
            ) as mock_settings,
        ):
            mock_settings.bot_unbound_user_policy = "restricted"

            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id=str(uuid4()),
                is_group=False,
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_unblocked_user_proceeds(self):
        """未封鎖用戶 → 正常進入 AI 流程"""
        agent = {
            "name": "bot-restricted",
            "model": "haiku",
            "system_prompt": {"content": "你是 AI"},
            "tools": [],
            "id": str(uuid4()),
            "settings": {},
        }

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.message = "你好！"
        mock_response.input_tokens = None
        mock_response.output_tokens = None
        mock_response.tool_calls = []

        with (
            patch(
                "ching_tech_os.services.bot_line.admin.is_user_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "ching_tech_os.services.bot.identity_router.settings"
            ) as mock_settings,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value=agent,
            ),
            patch(
                "ching_tech_os.services.linebot_agents.get_restricted_agent",
                new_callable=AsyncMock,
                return_value=agent,
            ),
            patch(
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
            patch(
                "ching_tech_os.services.linebot_ai.build_system_prompt",
                new_callable=AsyncMock,
                return_value="prompt",
            ),
            patch(
                "ching_tech_os.services.linebot_ai.get_conversation_context",
                new_callable=AsyncMock,
                return_value=([], [], []),
            ),
            patch(
                "ching_tech_os.services.mcp.get_mcp_tool_names",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "ching_tech_os.services.linebot_agents.get_mcp_servers_for_user",
                new_callable=AsyncMock,
                return_value=set(),
            ),
            patch(
                "ching_tech_os.services.bot.ai.parse_ai_response",
                return_value=("你好！", [], []),
            ),
            patch(
                "ching_tech_os.services.bot.rate_limiter.check_and_increment",
                new_callable=AsyncMock,
                return_value=(True, None),
            ),
        ):
            mock_settings.bot_unbound_user_policy = "restricted"
            mock_settings.bot_restricted_model = "haiku"
            mock_settings.bot_rate_limit_enabled = True

            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id=str(uuid4()),
                is_group=False,
            )

            assert result is not None
            assert "你好" in result

    @pytest.mark.asyncio
    async def test_no_bot_user_id_skips_check(self):
        """bot_user_id 為 None → 跳過封鎖檢查"""
        agent = {
            "name": "bot-restricted",
            "model": "haiku",
            "system_prompt": {"content": "你是 AI"},
            "tools": [],
            "id": str(uuid4()),
            "settings": {},
        }

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.message = "OK"
        mock_response.input_tokens = None
        mock_response.output_tokens = None
        mock_response.tool_calls = []

        with (
            patch(
                "ching_tech_os.services.bot_line.admin.is_user_blocked",
                new_callable=AsyncMock,
            ) as mock_check,
            patch(
                "ching_tech_os.services.bot.identity_router.settings"
            ) as mock_settings,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value=agent,
            ),
            patch(
                "ching_tech_os.services.linebot_agents.get_restricted_agent",
                new_callable=AsyncMock,
                return_value=agent,
            ),
            patch(
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
            patch(
                "ching_tech_os.services.linebot_ai.build_system_prompt",
                new_callable=AsyncMock,
                return_value="prompt",
            ),
            patch(
                "ching_tech_os.services.linebot_ai.get_conversation_context",
                new_callable=AsyncMock,
                return_value=([], [], []),
            ),
            patch(
                "ching_tech_os.services.mcp.get_mcp_tool_names",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "ching_tech_os.services.linebot_agents.get_mcp_servers_for_user",
                new_callable=AsyncMock,
                return_value=set(),
            ),
            patch(
                "ching_tech_os.services.bot.ai.parse_ai_response",
                return_value=("OK", [], []),
            ),
        ):
            mock_settings.bot_unbound_user_policy = "restricted"
            mock_settings.bot_restricted_model = "haiku"
            mock_settings.bot_rate_limit_enabled = False

            await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id=None,
                is_group=False,
            )

            mock_check.assert_not_called()
