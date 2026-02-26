"""Bot 斜線指令路由框架測試"""

import pytest

from ching_tech_os.services.bot.commands import (
    CommandContext,
    CommandRouter,
    SlashCommand,
)


def _make_ctx(**kwargs) -> CommandContext:
    """建立測試用 CommandContext"""
    defaults = {
        "platform_type": "line",
        "platform_user_id": "U123",
        "bot_user_id": "bot-user-uuid",
        "ctos_user_id": 1,
        "is_admin": False,
        "is_group": False,
        "group_id": None,
        "reply_token": "token-123",
        "raw_args": "",
    }
    defaults.update(kwargs)
    return CommandContext(**defaults)


@pytest.fixture
def router():
    return CommandRouter()


@pytest.fixture
def echo_handler():
    """簡單的 echo handler"""
    async def handler(ctx: CommandContext) -> str:
        return f"echo: {ctx.raw_args}" if ctx.raw_args else "echo"
    return handler


class TestCommandRouterParse:
    """測試指令解析"""

    def test_parse_simple_command(self, router, echo_handler):
        router.register(SlashCommand(name="test", handler=echo_handler))
        result = router.parse("/test")
        assert result is not None
        cmd, args = result
        assert cmd.name == "test"
        assert args == ""

    def test_parse_command_with_args(self, router, echo_handler):
        router.register(SlashCommand(name="debug", handler=echo_handler))
        result = router.parse("/debug 系統有問題")
        assert result is not None
        cmd, args = result
        assert cmd.name == "debug"
        assert args == "系統有問題"

    def test_parse_case_insensitive(self, router, echo_handler):
        router.register(SlashCommand(name="reset", handler=echo_handler))
        result = router.parse("/Reset")
        assert result is not None
        assert result[0].name == "reset"

    def test_parse_alias(self, router, echo_handler):
        router.register(SlashCommand(
            name="reset",
            aliases=["新對話", "忘記"],
            handler=echo_handler,
        ))
        result = router.parse("/新對話")
        assert result is not None
        assert result[0].name == "reset"

    def test_parse_unknown_command_returns_none(self, router):
        result = router.parse("/unknown")
        assert result is None

    def test_parse_non_command_returns_none(self, router, echo_handler):
        router.register(SlashCommand(name="test", handler=echo_handler))
        assert router.parse("hello") is None
        assert router.parse("") is None
        assert router.parse("test") is None

    def test_parse_telegram_bot_mention_format(self, router, echo_handler):
        """Telegram 的 /command@botname 格式"""
        router.register(SlashCommand(name="reset", handler=echo_handler))
        result = router.parse("/reset@mybot")
        assert result is not None
        assert result[0].name == "reset"


class TestCommandRouterDispatch:
    """測試指令分發和權限檢查"""

    @pytest.mark.asyncio
    async def test_dispatch_basic(self, router, echo_handler):
        router.register(SlashCommand(name="test", handler=echo_handler))
        ctx = _make_ctx()
        result = await router.dispatch(
            router._commands["test"], "", ctx
        )
        assert result == "echo"

    @pytest.mark.asyncio
    async def test_dispatch_with_args(self, router, echo_handler):
        router.register(SlashCommand(name="test", handler=echo_handler))
        ctx = _make_ctx()
        result = await router.dispatch(
            router._commands["test"], "hello world", ctx
        )
        assert result == "echo: hello world"

    @pytest.mark.asyncio
    async def test_require_bound_rejects_unbound(self, router, echo_handler):
        """未綁定用戶執行需綁定的指令"""
        router.register(SlashCommand(
            name="test", handler=echo_handler, require_bound=True,
        ))
        ctx = _make_ctx(ctos_user_id=None)
        result = await router.dispatch(
            router._commands["test"], "", ctx
        )
        assert "綁定" in result

    @pytest.mark.asyncio
    async def test_require_bound_allows_bound(self, router, echo_handler):
        """已綁定用戶可執行需綁定的指令"""
        router.register(SlashCommand(
            name="test", handler=echo_handler, require_bound=True,
        ))
        ctx = _make_ctx(ctos_user_id=1)
        result = await router.dispatch(
            router._commands["test"], "", ctx
        )
        assert result == "echo"

    @pytest.mark.asyncio
    async def test_require_admin_rejects_non_admin(self, router, echo_handler):
        """非管理員執行管理員指令"""
        router.register(SlashCommand(
            name="test", handler=echo_handler, require_admin=True,
        ))
        ctx = _make_ctx(is_admin=False)
        result = await router.dispatch(
            router._commands["test"], "", ctx
        )
        assert "管理員" in result

    @pytest.mark.asyncio
    async def test_require_admin_allows_admin(self, router, echo_handler):
        """管理員可執行管理員指令"""
        router.register(SlashCommand(
            name="test", handler=echo_handler, require_admin=True,
        ))
        ctx = _make_ctx(is_admin=True)
        result = await router.dispatch(
            router._commands["test"], "", ctx
        )
        assert result == "echo"

    @pytest.mark.asyncio
    async def test_private_only_ignores_group(self, router, echo_handler):
        """群組中執行僅限個人的指令"""
        router.register(SlashCommand(
            name="test", handler=echo_handler, private_only=True,
        ))
        ctx = _make_ctx(is_group=True)
        result = await router.dispatch(
            router._commands["test"], "", ctx
        )
        assert result is None  # 靜默忽略

    @pytest.mark.asyncio
    async def test_platform_mismatch_returns_none(self, router, echo_handler):
        """不支援的平台"""
        router.register(SlashCommand(
            name="test", handler=echo_handler, platforms={"telegram"},
        ))
        ctx = _make_ctx(platform_type="line")
        result = await router.dispatch(
            router._commands["test"], "", ctx
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_handler_exception_returns_error(self, router):
        """handler 拋出例外時回覆錯誤訊息"""
        async def bad_handler(ctx):
            raise RuntimeError("test error")

        router.register(SlashCommand(name="test", handler=bad_handler))
        ctx = _make_ctx()
        result = await router.dispatch(
            router._commands["test"], "", ctx
        )
        assert "錯誤" in result
