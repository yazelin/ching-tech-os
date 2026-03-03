"""主動推送通知服務

在背景任務完成後，依平台設定決定是否主動推送結果給發起者。

預設行為：
- Line：預設關閉（bot_settings 無記錄時不推送）
- Telegram：預設開啟（bot_settings 無記錄時仍推送）
"""

import logging

from ..database import get_connection

logger = logging.getLogger(__name__)

# 各平台缺少設定時的預設值
_PLATFORM_DEFAULT: dict[str, bool] = {
    "line": False,
    "telegram": True,
}


async def _is_push_enabled(platform: str) -> bool:
    """從 bot_settings 讀取平台的主動推送開關，缺值時依預設值處理"""
    try:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM bot_settings WHERE platform = $1 AND key = 'proactive_push_enabled'",
                platform,
            )
        if row is None:
            return _PLATFORM_DEFAULT.get(platform, False)
        return row["value"].lower() == "true"
    except Exception:
        logger.warning(f"讀取 {platform} 主動推送設定失敗，使用預設值", exc_info=True)
        return _PLATFORM_DEFAULT.get(platform, False)


async def notify_job_complete(
    platform: str,
    platform_user_id: str,
    is_group: bool,
    group_id: str | None,
    message: str,
) -> None:
    """背景任務完成後推送通知

    Args:
        platform: 平台名稱（"line" 或 "telegram"）
        platform_user_id: Line user ID 或 Telegram user chat_id
        is_group: 是否為群組對話
        group_id: 群組 ID（群組對話時使用），個人對話為 None
        message: 推送訊息內容
    """
    if not await _is_push_enabled(platform):
        logger.debug(f"{platform} 主動推送未啟用，跳過通知")
        return

    target = group_id if is_group and group_id else platform_user_id
    if not target:
        logger.warning("無法推送：target 為空")
        return

    try:
        if platform == "line":
            await _push_line(target, message)
        elif platform == "telegram":
            await _push_telegram(target, message)
        else:
            logger.warning(f"不支援的平台: {platform}")
    except Exception:
        logger.warning(f"主動推送失敗（{platform} → {target}），靜默處理", exc_info=True)


async def _push_line(to: str, message: str) -> None:
    """透過 Line Push API 發送訊息"""
    from .bot_line.messaging import push_text
    _msg_id, error = await push_text(to, message)
    if error:
        logger.warning(f"Line push 失敗: {error}")


async def _push_telegram(chat_id: str, message: str) -> None:
    """透過 Telegram Bot API 發送訊息"""
    from .bot_settings import get_bot_credentials
    from .bot_telegram.adapter import TelegramBotAdapter

    credentials = await get_bot_credentials("telegram")
    token = credentials.get("bot_token", "")
    if not token:
        logger.warning("Telegram bot_token 未設定，無法推送")
        return

    adapter = TelegramBotAdapter(token=token)
    await adapter.send_text(chat_id, message)
