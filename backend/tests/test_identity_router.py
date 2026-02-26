"""身份分流路由器單元測試"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ching_tech_os.services.bot.identity_router import (
    UnboundRouteResult,
    route_unbound,
    get_unbound_policy,
    handle_restricted_mode,
    BINDING_PROMPT_LINE,
    BINDING_PROMPT_TELEGRAM,
)


# ============================================================
# route_unbound() 測試
# ============================================================


class TestRouteUnbound:
    """測試 route_unbound() 分流邏輯"""

    def test_reject_policy_line_private(self):
        """reject 策略 + Line 個人對話 → 回覆綁定提示"""
        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "reject"
            result = route_unbound(platform_type="line", is_group=False)
            assert result.action == "reject"
            assert result.reply_text == BINDING_PROMPT_LINE

    def test_reject_policy_telegram_private(self):
        """reject 策略 + Telegram 個人對話 → 回覆 Telegram 綁定提示"""
        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "reject"
            result = route_unbound(platform_type="telegram", is_group=False)
            assert result.action == "reject"
            assert result.reply_text == BINDING_PROMPT_TELEGRAM

    def test_reject_policy_group_silent(self):
        """reject 策略 + 群組 → 靜默忽略"""
        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "reject"
            result = route_unbound(platform_type="line", is_group=True)
            assert result.action == "silent"
            assert result.reply_text is None

    def test_restricted_policy_private(self):
        """restricted 策略 + 個人對話 → 走受限模式"""
        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "restricted"
            result = route_unbound(platform_type="line", is_group=False)
            assert result.action == "restricted"
            assert result.reply_text is None

    def test_restricted_policy_group_still_silent(self):
        """restricted 策略 + 群組 → 仍靜默忽略（群組不受策略影響）"""
        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "restricted"
            result = route_unbound(platform_type="telegram", is_group=True)
            assert result.action == "silent"

    def test_default_policy_fallback(self):
        """未設定/無效策略 → 預設 reject"""
        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "invalid_value"
            result = route_unbound(platform_type="line", is_group=False)
            assert result.action == "reject"

    def test_empty_policy_fallback(self):
        """空字串策略 → 預設 reject"""
        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = ""
            result = route_unbound(platform_type="line", is_group=False)
            assert result.action == "reject"


# ============================================================
# get_unbound_policy() 測試
# ============================================================


class TestGetUnboundPolicy:
    """測試 get_unbound_policy()"""

    def test_reject(self):
        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "reject"
            assert get_unbound_policy() == "reject"

    def test_restricted(self):
        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "restricted"
            assert get_unbound_policy() == "restricted"

    def test_case_insensitive(self):
        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "RESTRICTED"
            assert get_unbound_policy() == "restricted"

    def test_whitespace_trimmed(self):
        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "  reject  "
            assert get_unbound_policy() == "reject"


# ============================================================
# handle_restricted_mode() 測試
# ============================================================


def _rate_limit_patches():
    """建立 rate limiter mock patches（避免 DB 連線）"""
    return (
        patch(
            "ching_tech_os.services.bot.rate_limiter.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None),
        ),
        patch(
            "ching_tech_os.services.bot.rate_limiter.record_usage",
            new_callable=AsyncMock,
        ),
    )


class TestHandleRestrictedMode:
    """測試受限模式 AI 流程"""

    @pytest.mark.asyncio
    async def test_agent_not_found(self):
        """bot-restricted Agent 不存在 → 回傳錯誤訊息"""
        rl, ru = _rate_limit_patches()
        with (
            rl,
            ru,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id="uuid-123",
                is_group=False,
            )
            assert result == "系統設定錯誤，請聯繫管理員。"

    @pytest.mark.asyncio
    async def test_agent_no_prompt(self):
        """bot-restricted Agent 無 system_prompt → 回傳錯誤"""
        rl, ru = _rate_limit_patches()
        with (
            rl,
            ru,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value={"system_prompt": None, "tools": []},
            ),
        ):
            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id="uuid-123",
                is_group=False,
            )
            assert result == "系統設定錯誤，請聯繫管理員。"

    @pytest.mark.asyncio
    async def test_successful_restricted_flow(self):
        """成功的受限模式 AI 流程"""
        mock_response = MagicMock()
        mock_response.tool_calls = []
        rl, ru = _rate_limit_patches()

        with (
            rl,
            ru,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value={
                    "system_prompt": {"content": "你是 AI 助理"},
                    "tools": ["search_knowledge"],
                },
            ),
            patch(
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
            patch(
                "ching_tech_os.services.linebot_ai.build_system_prompt",
                new_callable=AsyncMock,
                return_value="test prompt",
            ),
            patch(
                "ching_tech_os.services.linebot_ai.get_conversation_context",
                new_callable=AsyncMock,
                return_value=([], [], []),
            ),
            patch(
                "ching_tech_os.services.mcp.get_mcp_tool_names",
                new_callable=AsyncMock,
                return_value=["search_knowledge", "get_knowledge_item"],
            ),
            patch(
                "ching_tech_os.services.linebot_agents.get_mcp_servers_for_user",
                new_callable=AsyncMock,
                return_value=set(),
            ),
            patch(
                "ching_tech_os.services.bot.ai.parse_ai_response",
                return_value={"text": "你好！有什麼可以幫你的？"},
            ),
        ):
            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id="uuid-123",
                is_group=False,
            )
            assert result == "你好！有什麼可以幫你的？"

    @pytest.mark.asyncio
    async def test_file_message_filtered(self):
        """受限模式過濾 FILE_MESSAGE 標記"""
        mock_response = MagicMock()
        mock_response.tool_calls = []
        rl, ru = _rate_limit_patches()

        with (
            rl,
            ru,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value={
                    "system_prompt": {"content": "你是 AI 助理"},
                    "tools": ["search_knowledge"],
                },
            ),
            patch(
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
            patch(
                "ching_tech_os.services.linebot_ai.build_system_prompt",
                new_callable=AsyncMock,
                return_value="test prompt",
            ),
            patch(
                "ching_tech_os.services.linebot_ai.get_conversation_context",
                new_callable=AsyncMock,
                return_value=([], [], []),
            ),
            patch(
                "ching_tech_os.services.mcp.get_mcp_tool_names",
                new_callable=AsyncMock,
                return_value=["search_knowledge"],
            ),
            patch(
                "ching_tech_os.services.linebot_agents.get_mcp_servers_for_user",
                new_callable=AsyncMock,
                return_value=set(),
            ),
            patch(
                "ching_tech_os.services.bot.ai.parse_ai_response",
                return_value={
                    "text": "這是結果 [FILE_MESSAGE:path/to/file] 完畢"
                },
            ),
        ):
            result = await handle_restricted_mode(
                content="查詢",
                platform_user_id="U123",
                bot_user_id="uuid-123",
                is_group=False,
            )
            assert "[FILE_MESSAGE:" not in result
            assert "這是結果" in result
            assert "完畢" in result

    @pytest.mark.asyncio
    async def test_empty_response_fallback(self):
        """空回應 → 預設訊息"""
        mock_response = MagicMock()
        mock_response.tool_calls = []
        rl, ru = _rate_limit_patches()

        with (
            rl,
            ru,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value={
                    "system_prompt": {"content": "你是 AI 助理"},
                    "tools": [],
                },
            ),
            patch(
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
            patch(
                "ching_tech_os.services.linebot_ai.build_system_prompt",
                new_callable=AsyncMock,
                return_value="test prompt",
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
                return_value={"text": ""},
            ),
        ):
            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id="uuid-123",
                is_group=False,
            )
            assert result == "抱歉，我目前無法回答您的問題。"
