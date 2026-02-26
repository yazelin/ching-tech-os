"""身份分流路由器單元測試"""

import contextlib

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ching_tech_os.services.bot.identity_router import (
    UnboundRouteResult,
    route_unbound,
    get_unbound_policy,
    handle_restricted_mode,
    _get_restricted_setting,
    BINDING_PROMPT_LINE,
    BINDING_PROMPT_TELEGRAM,
)


# ============================================================
# _get_restricted_setting() 測試
# ============================================================


class TestGetRestrictedSetting:
    """測試 _get_restricted_setting() helper"""

    def test_agent_none_returns_default(self):
        """agent 為 None → 回傳 default"""
        assert _get_restricted_setting(None, "welcome_message", "預設") == "預設"

    def test_no_settings_key_returns_default(self):
        """agent 無 settings 欄位 → 回傳 default"""
        agent = {"settings": None}
        assert _get_restricted_setting(agent, "disclaimer", "預設") == "預設"

    def test_empty_value_returns_default(self):
        """settings 中 key 值為空字串 → 回傳 default"""
        agent = {"settings": {"disclaimer": ""}}
        assert _get_restricted_setting(agent, "disclaimer", "預設免責") == "預設免責"

    def test_custom_value_returned(self):
        """settings 有自訂值 → 回傳自訂值"""
        agent = {"settings": {"disclaimer": "\n\n※ 此回覆僅供參考"}}
        assert _get_restricted_setting(agent, "disclaimer", "預設") == "\n\n※ 此回覆僅供參考"

    def test_missing_key_returns_default(self):
        """settings 中不存在的 key → 回傳 default"""
        agent = {"settings": {"other_key": "value"}}
        assert _get_restricted_setting(agent, "disclaimer", "預設") == "預設"


# ============================================================
# route_unbound() 測試
# ============================================================


class TestRouteUnbound:
    """測試 route_unbound() 分流邏輯"""

    @pytest.mark.asyncio
    async def test_reject_policy_line_private(self):
        """reject 策略 + Line 個人對話 → 回覆綁定提示"""
        with (
            patch(
                "ching_tech_os.services.bot.identity_router.settings"
            ) as mock_settings,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            mock_settings.bot_unbound_user_policy = "reject"
            result = await route_unbound(platform_type="line", is_group=False)
            assert result.action == "reject"
            assert result.reply_text == BINDING_PROMPT_LINE

    @pytest.mark.asyncio
    async def test_reject_policy_telegram_private(self):
        """reject 策略 + Telegram 個人對話 → 回覆 Telegram 綁定提示"""
        with (
            patch(
                "ching_tech_os.services.bot.identity_router.settings"
            ) as mock_settings,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            mock_settings.bot_unbound_user_policy = "reject"
            result = await route_unbound(platform_type="telegram", is_group=False)
            assert result.action == "reject"
            assert result.reply_text == BINDING_PROMPT_TELEGRAM

    @pytest.mark.asyncio
    async def test_reject_policy_group_silent(self):
        """reject 策略 + 群組 → 靜默忽略"""
        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "reject"
            result = await route_unbound(platform_type="line", is_group=True)
            assert result.action == "silent"
            assert result.reply_text is None

    @pytest.mark.asyncio
    async def test_restricted_policy_private(self):
        """restricted 策略 + 個人對話 → 走受限模式"""
        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "restricted"
            result = await route_unbound(platform_type="line", is_group=False)
            assert result.action == "restricted"
            assert result.reply_text is None

    @pytest.mark.asyncio
    async def test_restricted_policy_group_still_silent(self):
        """restricted 策略 + 群組 → 仍靜默忽略（群組不受策略影響）"""
        with patch(
            "ching_tech_os.services.bot.identity_router.settings"
        ) as mock_settings:
            mock_settings.bot_unbound_user_policy = "restricted"
            result = await route_unbound(platform_type="telegram", is_group=True)
            assert result.action == "silent"

    @pytest.mark.asyncio
    async def test_default_policy_fallback(self):
        """未設定/無效策略 → 預設 reject"""
        with (
            patch(
                "ching_tech_os.services.bot.identity_router.settings"
            ) as mock_settings,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            mock_settings.bot_unbound_user_policy = "invalid_value"
            result = await route_unbound(platform_type="line", is_group=False)
            assert result.action == "reject"

    @pytest.mark.asyncio
    async def test_empty_policy_fallback(self):
        """空字串策略 → 預設 reject"""
        with (
            patch(
                "ching_tech_os.services.bot.identity_router.settings"
            ) as mock_settings,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            mock_settings.bot_unbound_user_policy = ""
            result = await route_unbound(platform_type="line", is_group=False)
            assert result.action == "reject"

    @pytest.mark.asyncio
    async def test_reject_with_custom_binding_prompt(self):
        """reject 策略 + agent settings 有自訂 binding_prompt → 使用自訂文字"""
        custom_prompt = "請到我們的官網綁定帳號。"
        with (
            patch(
                "ching_tech_os.services.bot.identity_router.settings"
            ) as mock_settings,
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value={"settings": {"binding_prompt": custom_prompt}},
            ),
        ):
            mock_settings.bot_unbound_user_policy = "reject"
            result = await route_unbound(platform_type="line", is_group=False)
            assert result.action == "reject"
            assert result.reply_text == custom_prompt


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


def _make_agent(
    system_prompt="你是 AI 助理",
    tools=None,
    settings_data=None,
):
    """建立模擬 agent 字典"""
    agent = {
        "system_prompt": {"content": system_prompt} if system_prompt else None,
        "tools": tools or ["search_knowledge"],
    }
    if settings_data is not None:
        agent["settings"] = settings_data
    return agent


@contextlib.contextmanager
def _restricted_mode_patches(agent=None, ai_reply="你好！有什麼可以幫你的？"):
    """建立 handle_restricted_mode 的常用 mock patches"""
    mock_response = MagicMock()
    mock_response.tool_calls = []

    with (
        patch(
            "ching_tech_os.services.ai_manager.get_agent_by_name",
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
            return_value=(ai_reply, []),
        ),
    ):
        yield


class TestHandleRestrictedMode:
    """測試受限模式 AI 流程"""

    @pytest.mark.asyncio
    async def test_agent_not_found(self):
        """bot-restricted Agent 不存在 → 回傳錯誤訊息"""
        with patch(
            "ching_tech_os.services.ai_manager.get_agent_by_name",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id=None,
                is_group=False,
            )
            assert result == "系統設定錯誤，請聯繫管理員。"

    @pytest.mark.asyncio
    async def test_agent_no_prompt(self):
        """bot-restricted Agent 無 system_prompt → 回傳錯誤"""
        agent = _make_agent(system_prompt=None)
        with _restricted_mode_patches(agent=agent):
            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id=None,
                is_group=False,
            )
            assert result == "系統設定錯誤，請聯繫管理員。"

    @pytest.mark.asyncio
    async def test_successful_restricted_flow(self):
        """成功的受限模式 AI 流程"""
        agent = _make_agent()
        with _restricted_mode_patches(agent=agent):
            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id=None,
                is_group=False,
            )
            assert result == "你好！有什麼可以幫你的？"

    @pytest.mark.asyncio
    async def test_file_message_filtered(self):
        """受限模式過濾 FILE_MESSAGE 標記"""
        agent = _make_agent()
        with _restricted_mode_patches(
            agent=agent,
            ai_reply="這是結果 [FILE_MESSAGE:path/to/file] 完畢",
        ):
            result = await handle_restricted_mode(
                content="查詢",
                platform_user_id="U123",
                bot_user_id=None,
                is_group=False,
            )
            assert "[FILE_MESSAGE:" not in result
            assert "這是結果" in result
            assert "完畢" in result

    @pytest.mark.asyncio
    async def test_empty_response_fallback(self):
        """空回應 → 預設訊息"""
        agent = _make_agent(tools=[])
        with _restricted_mode_patches(agent=agent, ai_reply=""):
            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id=None,
                is_group=False,
            )
            assert result == "抱歉，我目前無法回答您的問題。"

    @pytest.mark.asyncio
    async def test_disclaimer_appended(self):
        """settings.disclaimer 有值 → 附加到回覆結尾"""
        agent = _make_agent(
            settings_data={"disclaimer": "\n\n※ 本回覆僅供參考，不構成醫療建議。"}
        )
        with _restricted_mode_patches(agent=agent, ai_reply="感冒建議多休息。"):
            result = await handle_restricted_mode(
                content="感冒怎麼辦",
                platform_user_id="U123",
                bot_user_id=None,
                is_group=False,
            )
            assert result == "感冒建議多休息。\n\n※ 本回覆僅供參考，不構成醫療建議。"

    @pytest.mark.asyncio
    async def test_disclaimer_empty_not_appended(self):
        """settings.disclaimer 為空字串 → 不附加"""
        agent = _make_agent(settings_data={"disclaimer": ""})
        with _restricted_mode_patches(agent=agent, ai_reply="你好！"):
            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id=None,
                is_group=False,
            )
            assert result == "你好！"

    @pytest.mark.asyncio
    async def test_custom_error_message(self):
        """AI 呼叫失敗 + settings.error_message 有值 → 使用自訂錯誤訊息"""
        agent = _make_agent(
            settings_data={"error_message": "系統忙碌中，請稍後再試。"}
        )
        with (
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value=agent,
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
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
                side_effect=Exception("AI 失敗"),
            ),
        ):
            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id=None,
                is_group=False,
            )
            assert result == "系統忙碌中，請稍後再試。"

    @pytest.mark.asyncio
    async def test_default_error_message_when_not_configured(self):
        """AI 呼叫失敗 + 無自訂 error_message → 使用預設"""
        agent = _make_agent()
        with (
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value=agent,
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
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
                side_effect=Exception("AI 失敗"),
            ),
        ):
            result = await handle_restricted_mode(
                content="你好",
                platform_user_id="U123",
                bot_user_id=None,
                is_group=False,
            )
            assert result == "抱歉，處理您的訊息時發生錯誤，請稍後再試。"
