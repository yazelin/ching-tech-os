"""Telegram Bot 事件處理

Phase 1：接收文字訊息並 echo 回覆。
"""

import logging

from telegram import Update

from .adapter import TelegramBotAdapter

logger = logging.getLogger("bot_telegram.handler")


async def handle_update(update: Update, adapter: TelegramBotAdapter) -> None:
    """處理 Telegram Update 事件

    Phase 1 只處理文字訊息，做 echo 回覆。
    """
    if not update.message:
        logger.debug(f"跳過非訊息 Update: {update.update_id}")
        return

    message = update.message
    chat_id = str(message.chat_id)

    # 記錄訊息資訊
    user = message.from_user
    user_name = user.full_name if user else "未知"
    logger.info(
        f"收到 Telegram 訊息: chat_id={chat_id}, "
        f"user={user_name}, type={'text' if message.text else 'other'}"
    )

    # Phase 1：只處理文字訊息，echo 回覆
    if message.text:
        reply_text = f"[Echo] {message.text}"
        try:
            await adapter.send_text(
                chat_id,
                reply_text,
                reply_to=str(message.message_id),
            )
            logger.info(f"已回覆 echo 訊息至 chat_id={chat_id}")
        except Exception as e:
            logger.error(f"回覆訊息失敗: {e}")
    else:
        logger.debug(f"跳過非文字訊息 (chat_id={chat_id})")
