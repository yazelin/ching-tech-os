"""Bot /debug 指令測試"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ching_tech_os.services.bot.commands import CommandContext, CommandRouter, SlashCommand
from ching_tech_os.services.bot.command_handlers import _handle_debug


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


class TestDebugCommand:
    """測試 /debug 指令"""

    @pytest.mark.asyncio
    async def test_debug_agent_not_found(self):
        """bot-debug Agent 不存在 → 回傳錯誤"""
        with patch(
            "ching_tech_os.services.ai_manager.get_agent_by_name",
            new_callable=AsyncMock,
            return_value=None,
        ):
            ctx = _make_ctx(is_admin=True, raw_args="")
            result = await _handle_debug(ctx)
            assert "bot-debug Agent 不存在" in result

    @pytest.mark.asyncio
    async def test_debug_no_prompt(self):
        """Agent 無 system_prompt → 回傳錯誤"""
        with patch(
            "ching_tech_os.services.ai_manager.get_agent_by_name",
            new_callable=AsyncMock,
            return_value={"system_prompt": None, "tools": []},
        ):
            ctx = _make_ctx(is_admin=True)
            result = await _handle_debug(ctx)
            assert "缺少 system_prompt" in result

    @pytest.mark.asyncio
    async def test_debug_successful(self):
        """成功的 debug 流程"""
        mock_response = MagicMock()
        mock_response.tool_calls = []

        with (
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value={
                    "system_prompt": {"content": "你是系統診斷助理"},
                    "tools": ["run_skill_script"],
                },
            ),
            patch(
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
            patch(
                "ching_tech_os.services.bot.ai.parse_ai_response",
                return_value=("系統狀態正常，無異常。", []),
            ),
        ):
            ctx = _make_ctx(is_admin=True, raw_args="系統有什麼問題嗎")
            result = await _handle_debug(ctx)
            assert result == "系統狀態正常，無異常。"

    @pytest.mark.asyncio
    async def test_debug_default_prompt(self):
        """無問題描述時使用預設 prompt"""
        mock_response = MagicMock()
        mock_response.tool_calls = []

        with (
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value={
                    "system_prompt": {"content": "你是系統診斷助理"},
                    "tools": ["run_skill_script"],
                },
            ),
            patch(
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
                return_value=mock_response,
            ) as mock_call,
            patch(
                "ching_tech_os.services.bot.ai.parse_ai_response",
                return_value=("健檢結果正常", []),
            ),
        ):
            ctx = _make_ctx(is_admin=True, raw_args="")
            result = await _handle_debug(ctx)
            assert result == "健檢結果正常"
            # 檢查呼叫 call_claude 時的 prompt 包含預設文字
            call_args = mock_call.call_args
            assert "check-system-health" in call_args.kwargs.get("prompt", "")

    @pytest.mark.asyncio
    async def test_debug_call_failure(self):
        """AI 呼叫失敗 → 回傳錯誤"""
        with (
            patch(
                "ching_tech_os.services.ai_manager.get_agent_by_name",
                new_callable=AsyncMock,
                return_value={
                    "system_prompt": {"content": "你是系統診斷助理"},
                    "tools": ["run_skill_script"],
                },
            ),
            patch(
                "ching_tech_os.services.claude_agent.call_claude",
                new_callable=AsyncMock,
                side_effect=Exception("timeout"),
            ),
        ):
            ctx = _make_ctx(is_admin=True, raw_args="問題？")
            result = await _handle_debug(ctx)
            assert "診斷執行失敗" in result


class TestDebugCommandRouting:
    """測試 /debug 指令路由（權限檢查）"""

    def test_debug_registered(self):
        """/debug 指令已註冊"""
        router = CommandRouter()
        router.register(
            SlashCommand(
                name="debug",
                aliases=["診斷"],
                handler=_handle_debug,
                require_bound=True,
                require_admin=True,
                private_only=True,
            )
        )
        parsed = router.parse("/debug 查詢日誌")
        assert parsed is not None
        cmd, args = parsed
        assert cmd.name == "debug"
        assert args == "查詢日誌"

    @pytest.mark.asyncio
    async def test_non_admin_rejected(self):
        """非管理員 → 拒絕"""
        router = CommandRouter()
        router.register(
            SlashCommand(
                name="debug",
                handler=_handle_debug,
                require_bound=True,
                require_admin=True,
                private_only=True,
            )
        )
        parsed = router.parse("/debug")
        assert parsed is not None
        cmd, args = parsed
        ctx = _make_ctx(is_admin=False)
        result = await router.dispatch(cmd, args, ctx)
        assert "管理員" in result

    @pytest.mark.asyncio
    async def test_unbound_rejected(self):
        """未綁定用戶 → 拒絕"""
        router = CommandRouter()
        router.register(
            SlashCommand(
                name="debug",
                handler=_handle_debug,
                require_bound=True,
                require_admin=True,
                private_only=True,
            )
        )
        parsed = router.parse("/debug")
        assert parsed is not None
        cmd, args = parsed
        ctx = _make_ctx(ctos_user_id=None, is_admin=False)
        result = await router.dispatch(cmd, args, ctx)
        assert "綁定" in result

    @pytest.mark.asyncio
    async def test_group_silently_ignored(self):
        """群組中 → 靜默忽略"""
        router = CommandRouter()
        router.register(
            SlashCommand(
                name="debug",
                handler=_handle_debug,
                require_bound=True,
                require_admin=True,
                private_only=True,
            )
        )
        parsed = router.parse("/debug")
        assert parsed is not None
        cmd, args = parsed
        ctx = _make_ctx(is_group=True, is_admin=True)
        result = await router.dispatch(cmd, args, ctx)
        assert result is None  # 靜默忽略

    def test_alias_parse(self):
        """別名 /診斷 可解析"""
        router = CommandRouter()
        router.register(
            SlashCommand(
                name="debug",
                aliases=["診斷", "diag"],
                handler=_handle_debug,
                require_bound=True,
                require_admin=True,
                private_only=True,
            )
        )
        parsed = router.parse("/診斷")
        assert parsed is not None
        cmd, args = parsed
        assert cmd.name == "debug"
