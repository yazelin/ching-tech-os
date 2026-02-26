"""Bot 統一指令系統測試

測試 /start、/help 指令、指令啟用停用開關、動態指令列表。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ching_tech_os.services.bot.commands import CommandContext, CommandRouter, SlashCommand


# ============================================================
# CommandRouter enabled 過濾測試
# ============================================================


def _make_ctx(platform: str = "line", is_admin: bool = False) -> CommandContext:
    return CommandContext(
        platform_type=platform,
        platform_user_id="test-user",
        bot_user_id=None,
        ctos_user_id=None,
        is_admin=is_admin,
        is_group=False,
        group_id=None,
        reply_token=None,
        raw_args="",
    )


class TestCommandRouterEnabled:
    """6.1 測試 CommandRouter.parse() 跳過 enabled=False 的指令"""

    def test_enabled_command_matches(self):
        router = CommandRouter()
        cmd = SlashCommand(name="test", handler=AsyncMock(), enabled=True)
        router.register(cmd)
        result = router.parse("/test")
        assert result is not None
        assert result[0] is cmd

    def test_disabled_command_not_matched(self):
        router = CommandRouter()
        cmd = SlashCommand(name="test", handler=AsyncMock(), enabled=False)
        router.register(cmd)
        result = router.parse("/test")
        assert result is None

    def test_disabled_alias_not_matched(self):
        router = CommandRouter()
        cmd = SlashCommand(name="test", aliases=["別名"], handler=AsyncMock(), enabled=False)
        router.register(cmd)
        assert router.parse("/test") is None
        assert router.parse("/別名") is None

    def test_mixed_enabled_disabled(self):
        router = CommandRouter()
        enabled_cmd = SlashCommand(name="a", handler=AsyncMock(), enabled=True)
        disabled_cmd = SlashCommand(name="b", handler=AsyncMock(), enabled=False)
        router.register(enabled_cmd)
        router.register(disabled_cmd)
        assert router.parse("/a") is not None
        assert router.parse("/b") is None


# ============================================================
# /help 動態指令列表測試
# ============================================================


class TestHandleHelp:
    """6.2 測試 _handle_help() 根據角色過濾指令列表"""

    @pytest.mark.asyncio
    async def test_help_filters_admin_commands(self):
        from ching_tech_os.services.bot.command_handlers import _handle_help

        # 確保指令已註冊
        from ching_tech_os.services.bot.command_handlers import register_builtin_commands
        register_builtin_commands()

        # 一般用戶
        ctx = _make_ctx(is_admin=False)
        result = await _handle_help(ctx)
        assert result is not None
        assert "/start" in result
        assert "/help" in result
        assert "/reset" in result
        # 非管理員不應看到 /debug
        assert "/debug" not in result

    @pytest.mark.asyncio
    async def test_help_shows_admin_commands_for_admin(self):
        from ching_tech_os.services.bot.command_handlers import _handle_help

        from ching_tech_os.services.bot.command_handlers import register_builtin_commands
        register_builtin_commands()

        # 管理員
        ctx = _make_ctx(is_admin=True)
        result = await _handle_help(ctx)
        assert result is not None
        assert "/debug" in result
        assert "（管理員）" in result

    @pytest.mark.asyncio
    async def test_help_skips_disabled_commands(self):
        from ching_tech_os.services.bot.command_handlers import _handle_help
        from ching_tech_os.services.bot.commands import router

        # 停用 /start
        for cmd in router._commands.values():
            if cmd.name == "start":
                cmd.enabled = False
                break

        ctx = _make_ctx()
        result = await _handle_help(ctx)
        assert "/start" not in result

        # 恢復
        for cmd in router._commands.values():
            if cmd.name == "start":
                cmd.enabled = True
                break


# ============================================================
# BOT_CMD_DISABLED 設定項測試
# ============================================================


class TestBotCmdDisabled:
    """6.3 測試 BOT_CMD_DISABLED 設定項正確解析"""

    def test_empty_env(self):
        """空字串不停用任何指令"""
        with patch.dict("os.environ", {"BOT_CMD_DISABLED": ""}):
            from ching_tech_os.config import _get_env
            result = [s.strip().lower() for s in _get_env("BOT_CMD_DISABLED", "").split(",") if s.strip()]
            assert result == []

    def test_single_command(self):
        with patch.dict("os.environ", {"BOT_CMD_DISABLED": "debug"}):
            from ching_tech_os.config import _get_env
            result = [s.strip().lower() for s in _get_env("BOT_CMD_DISABLED", "").split(",") if s.strip()]
            assert result == ["debug"]

    def test_multiple_commands_case_insensitive(self):
        with patch.dict("os.environ", {"BOT_CMD_DISABLED": "Debug, START "}):
            from ching_tech_os.config import _get_env
            result = [s.strip().lower() for s in _get_env("BOT_CMD_DISABLED", "").split(",") if s.strip()]
            assert result == ["debug", "start"]


# ============================================================
# /start 和 /help 跨平台一致性測試
# ============================================================


class TestStartHelpConsistency:
    """6.4 測試 /start 和 /help 在 LINE 和 Telegram 回覆一致"""

    @pytest.mark.asyncio
    async def test_start_returns_same_for_both_platforms(self):
        from ching_tech_os.services.bot.command_handlers import _handle_start

        line_ctx = _make_ctx(platform="line")
        tg_ctx = _make_ctx(platform="telegram")
        line_result = await _handle_start(line_ctx)
        tg_result = await _handle_start(tg_ctx)
        assert line_result == tg_result
        assert "CTOS Bot" in line_result

    @pytest.mark.asyncio
    async def test_help_structure_consistent(self):
        from ching_tech_os.services.bot.command_handlers import _handle_help, register_builtin_commands
        register_builtin_commands()

        line_ctx = _make_ctx(platform="line")
        tg_ctx = _make_ctx(platform="telegram")
        line_result = await _handle_help(line_ctx)
        tg_result = await _handle_help(tg_ctx)
        # 兩平台都支援所有指令，結果應相同
        assert line_result == tg_result


# ============================================================
# Telegram 移除寫死邏輯驗證
# ============================================================


class TestTelegramNoHardcoded:
    """6.5 驗證 Telegram 移除寫死邏輯後 /start、/help 仍正常運作"""

    def test_no_start_message_constant(self):
        """確認 START_MESSAGE 已從 handler 移除"""
        from ching_tech_os.services.bot_telegram import handler
        assert not hasattr(handler, "START_MESSAGE")

    def test_no_help_message_constant(self):
        """確認 HELP_MESSAGE 已從 handler 移除"""
        from ching_tech_os.services.bot_telegram import handler
        assert not hasattr(handler, "HELP_MESSAGE")
