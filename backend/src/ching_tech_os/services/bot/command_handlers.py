"""內建指令 handler

註冊所有內建的斜線指令到 CommandRouter。
"""

from __future__ import annotations

import logging

from .commands import CommandContext, SlashCommand, router
from ..bot_line.trigger import reset_conversation

logger = logging.getLogger(__name__)


async def _handle_reset(ctx: CommandContext) -> str | None:
    """重置對話歷史"""
    if ctx.is_group:
        return None  # 群組靜默忽略

    await reset_conversation(ctx.platform_user_id)
    return "已清除對話歷史，開始新對話！有什麼可以幫你的嗎？"


def register_builtin_commands() -> None:
    """註冊所有內建指令"""

    # /reset 指令（包含所有別名）
    router.register(
        SlashCommand(
            name="reset",
            aliases=["新對話", "新对话", "清除對話", "清除对话", "忘記", "忘记"],
            handler=_handle_reset,
            require_bound=False,  # 受限模式用戶也可以重置
            require_admin=False,
            private_only=True,
        )
    )

    # /debug 指令（後續 task 7 實作 handler）
    # 此處先預留，handler 在 task 7 中實作

    logger.info(f"已註冊 {len(set(router._commands.values()))} 個內建指令")
