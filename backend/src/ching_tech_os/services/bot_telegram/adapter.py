"""Telegram Bot Adapter — 實作 BotAdapter / EditableMessageAdapter / ProgressNotifier

使用 python-telegram-bot 庫與 Telegram Bot API 互動。
"""

import logging
from typing import Any

from telegram import Bot

from ..bot.adapter import SentMessage

logger = logging.getLogger("bot_telegram.adapter")


class TelegramBotAdapter:
    """Telegram Bot 的 BotAdapter 實作

    同時實作 EditableMessageAdapter 和 ProgressNotifier Protocol。

    用法：
        adapter = TelegramBotAdapter(token="BOT_TOKEN")
        msg = await adapter.send_text("123456", "你好")
    """

    platform_type: str = "telegram"

    def __init__(self, token: str):
        self.bot = Bot(token=token)

    # === BotAdapter ===

    async def send_text(
        self,
        target: str,
        text: str,
        *,
        reply_to: str | None = None,
        mention_user_id: str | None = None,
    ) -> SentMessage:
        """發送文字訊息"""
        kwargs: dict[str, Any] = {
            "chat_id": target,
            "text": text,
        }
        if reply_to:
            kwargs["reply_to_message_id"] = int(reply_to)

        msg = await self.bot.send_message(**kwargs)
        return SentMessage(message_id=str(msg.message_id), platform_type="telegram")

    async def send_image(
        self,
        target: str,
        image_url: str,
        *,
        reply_to: str | None = None,
        preview_url: str | None = None,
    ) -> SentMessage:
        """發送圖片訊息"""
        kwargs: dict[str, Any] = {
            "chat_id": target,
            "photo": image_url,
        }
        if reply_to:
            kwargs["reply_to_message_id"] = int(reply_to)

        msg = await self.bot.send_photo(**kwargs)
        return SentMessage(message_id=str(msg.message_id), platform_type="telegram")

    async def send_file(
        self,
        target: str,
        file_url: str,
        file_name: str,
        *,
        reply_to: str | None = None,
        file_size: str | None = None,
    ) -> SentMessage:
        """發送檔案訊息"""
        kwargs: dict[str, Any] = {
            "chat_id": target,
            "document": file_url,
            "filename": file_name,
        }
        if reply_to:
            kwargs["reply_to_message_id"] = int(reply_to)

        msg = await self.bot.send_document(**kwargs)
        return SentMessage(message_id=str(msg.message_id), platform_type="telegram")

    async def send_messages(
        self,
        target: str,
        messages: list[Any],
        *,
        reply_to: str | None = None,
    ) -> list[SentMessage]:
        """批次發送多則訊息（逐一發送）"""
        results = []
        for text in messages:
            if isinstance(text, str):
                sent = await self.send_text(target, text, reply_to=reply_to)
                results.append(sent)
        return results

    # === EditableMessageAdapter ===

    async def edit_message(
        self,
        target: str,
        message_id: str,
        new_text: str,
    ) -> None:
        """編輯已發送的訊息"""
        await self.bot.edit_message_text(
            chat_id=target,
            message_id=int(message_id),
            text=new_text,
        )

    async def delete_message(
        self,
        target: str,
        message_id: str,
    ) -> None:
        """刪除已發送的訊息"""
        await self.bot.delete_message(
            chat_id=target,
            message_id=int(message_id),
        )

    # === ProgressNotifier ===

    async def send_progress(
        self,
        target: str,
        text: str,
    ) -> SentMessage:
        """發送進度通知訊息"""
        return await self.send_text(target, text)

    async def update_progress(
        self,
        target: str,
        message_id: str,
        text: str,
    ) -> None:
        """更新進度通知內容"""
        await self.edit_message(target, message_id, text)

    async def finish_progress(
        self,
        target: str,
        message_id: str,
    ) -> None:
        """完成進度通知（刪除訊息）"""
        try:
            await self.delete_message(target, message_id)
        except Exception as e:
            logger.debug(f"刪除進度通知失敗（可能已過期）: {e}")
