"""Bot 斜線指令路由系統

可擴充的指令框架，支援 Line/Telegram 共用。
指令在 AI 處理流程之前攔截處理。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


@dataclass
class CommandContext:
    """指令執行上下文"""

    platform_type: str  # "line" | "telegram"
    platform_user_id: str  # Line user ID 或 Telegram user ID
    bot_user_id: str | None  # bot_users.id (UUID)
    ctos_user_id: int | None  # CTOS 帳號 ID（None = 未綁定）
    is_admin: bool  # 是否為管理員
    is_group: bool  # 是否為群組對話
    group_id: str | None  # 群組 ID（群組對話時）
    reply_token: str | None  # Line reply token（Line 平台時）
    raw_args: str  # 指令後的參數文字


@dataclass
class SlashCommand:
    """斜線指令定義"""

    name: str  # 指令名稱（如 "debug"）
    aliases: list[str] = field(default_factory=list)  # 別名
    handler: Callable[[CommandContext], Coroutine[Any, Any, str | None]] = field(
        default=None  # type: ignore — 註冊時必須提供 handler
    )
    require_bound: bool = False  # 是否要求已綁定 CTOS 帳號
    require_admin: bool = False  # 是否要求管理員
    private_only: bool = False  # 是否僅限個人對話
    platforms: set[str] = field(default_factory=lambda: {"line", "telegram"})


class CommandRouter:
    """斜線指令路由器"""

    def __init__(self) -> None:
        # key = 正規化後的指令名稱（不含 /），value = SlashCommand
        self._commands: dict[str, SlashCommand] = {}

    def register(self, command: SlashCommand) -> None:
        """註冊指令"""
        key = command.name.lower()
        self._commands[key] = command
        for alias in command.aliases:
            self._commands[alias.lower()] = command

    def parse(self, content: str) -> tuple[SlashCommand, str] | None:
        """解析訊息，回傳 (command, args) 或 None

        僅匹配以 / 開頭的訊息。
        """
        text = content.strip()
        if not text.startswith("/"):
            return None

        # 分離指令名稱和參數
        parts = text[1:].split(None, 1)  # 去掉 /，以第一個空白分割
        if not parts:
            return None

        cmd_name = parts[0].lower()
        # 處理 Telegram 的 /command@botname 格式
        if "@" in cmd_name:
            cmd_name = cmd_name.split("@")[0]

        args = parts[1] if len(parts) > 1 else ""

        command = self._commands.get(cmd_name)
        if command is None:
            return None

        return (command, args)

    async def dispatch(
        self, command: SlashCommand, args: str, context: CommandContext
    ) -> str | None:
        """執行指令，包含權限檢查

        回傳值：
        - str: 回覆文字
        - None: 靜默處理（不回覆）
        """
        # 平台檢查
        if context.platform_type not in command.platforms:
            return None  # 不支援的平台，視為一般訊息

        # 群組限制
        if command.private_only and context.is_group:
            return None  # 靜默忽略

        # 綁定檢查
        if command.require_bound and context.ctos_user_id is None:
            return "請先綁定 CTOS 帳號才能使用此指令"

        # 管理員檢查
        if command.require_admin and not context.is_admin:
            return "此指令僅限管理員使用"

        # 設定參數
        context.raw_args = args

        if command.handler is None:
            logger.error(f"指令 /{command.name} 未設定 handler")
            return "指令設定錯誤，請聯繫管理員"

        try:
            return await command.handler(context)
        except Exception:
            logger.exception(f"指令 /{command.name} 執行失敗")
            return "指令執行時發生錯誤，請稍後再試"


# 全域路由器實例
router = CommandRouter()
