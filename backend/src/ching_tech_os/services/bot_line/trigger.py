"""Line Bot AI 觸發判斷與對話管理"""

import logging
from uuid import UUID

from ...config import settings
from ...database import get_connection

logger = logging.getLogger("linebot")


def should_trigger_ai(
    message_content: str,
    is_group: bool,
    is_reply_to_bot: bool = False,
) -> bool:
    """
    判斷是否應該觸發 AI 處理

    規則：
    - 個人對話：所有訊息都觸發
    - 群組對話：訊息包含 @bot_name 或回覆機器人訊息時觸發
    """
    if not is_group:
        # 個人對話：全部觸發
        return True

    # 群組對話：檢查是否回覆機器人訊息
    if is_reply_to_bot:
        return True

    # 群組對話：檢查是否被 @ 提及
    content_lower = message_content.lower()

    # 檢查配置的所有觸發名稱
    for name in settings.line_bot_trigger_names:
        if f"@{name.lower()}" in content_lower:
            return True

    return False


async def is_bot_message(line_message_id: str) -> bool:
    """
    檢查訊息是否為機器人發送的

    Args:
        line_message_id: Line 訊息 ID

    Returns:
        True 如果是機器人發送的訊息
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT is_from_bot FROM bot_messages WHERE message_id = $1",
            line_message_id,
        )
        if row:
            return row["is_from_bot"] is True
        return False


async def reset_conversation(
    line_user_id: str,
) -> bool:
    """重置用戶的對話歷史

    設定 conversation_reset_at 為當前時間，
    之後查詢對話歷史時會忽略這個時間之前的訊息。

    Args:
        line_user_id: Line 用戶 ID

    Returns:
        是否成功
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE bot_users
            SET conversation_reset_at = NOW()
            WHERE platform_user_id = $1
            """,
            line_user_id,
        )
        success = result == "UPDATE 1"
        if success:
            logger.info(f"已重置對話歷史: {line_user_id}")
        return success


def is_reset_command(content: str) -> bool:
    """檢查訊息是否為重置對話指令

    Args:
        content: 訊息內容

    Returns:
        是否為重置指令
    """
    reset_commands = [
        "/新對話",
        "/新对话",
        "/reset",
        "/清除對話",
        "/清除对话",
        "/忘記",
        "/忘记",
    ]
    return content.strip().lower() in [cmd.lower() for cmd in reset_commands]
