"""Line Bot Adapter — 實作 BotAdapter Protocol

將 Line Messaging API 封裝為統一的 BotAdapter 介面，
讓核心 AI 處理流程可以透過平台無關的方式發送訊息。
"""

import logging

from ..bot.adapter import SentMessage

logger = logging.getLogger("bot_line.adapter")


class LineBotAdapter:
    """Line Bot 的 BotAdapter 實作

    透過委託給現有的 linebot.py 函式來實作 BotAdapter Protocol。
    未來可逐步將 linebot.py 的發送邏輯遷移到此處。

    用法：
        adapter = LineBotAdapter()
        msg = await adapter.send_text("C1234", "你好")
    """

    platform_type: str = "line"

    def __init__(self):
        pass

    async def send_text(
        self,
        target: str,
        text: str,
        *,
        reply_to: str | None = None,
        mention_user_id: str | None = None,
    ) -> SentMessage:
        """發送文字訊息

        Args:
            target: Line 用戶 ID 或群組 ID
            text: 訊息文字
            reply_to: 未使用（Line 不支援引用回覆）
            mention_user_id: 要 mention 的 Line 用戶 ID
        """
        # 使用向後相容匯出點，讓測試可穩定 patch `services.linebot.*`
        from ..linebot import (
            push_text,
            create_text_message_with_mention,
            push_messages,
        )

        if mention_user_id:
            # 使用 mention 版本
            msg = create_text_message_with_mention(text, mention_user_id)
            sent_ids, error = await push_messages(target, [msg])
            if error:
                logger.error(f"send_text 失敗: {error}")
                return SentMessage(message_id="", platform_type="line")
            msg_id = sent_ids[0] if sent_ids else ""
        else:
            msg_id, error = await push_text(target, text)
            if error:
                logger.error(f"send_text 失敗: {error}")
                return SentMessage(message_id="", platform_type="line")
            msg_id = msg_id or ""

        return SentMessage(message_id=msg_id, platform_type="line")

    async def send_image(
        self,
        target: str,
        image_url: str,
        *,
        reply_to: str | None = None,
        preview_url: str | None = None,
    ) -> SentMessage:
        """發送圖片訊息"""
        from ..linebot import push_image

        msg_id, error = await push_image(
            target, image_url,
            preview_url=preview_url,
        )
        if error:
            logger.error(f"send_image 失敗: {error}")
            return SentMessage(message_id="", platform_type="line")

        return SentMessage(message_id=msg_id or "", platform_type="line")

    async def send_file(
        self,
        target: str,
        file_url: str,
        file_name: str,
        *,
        reply_to: str | None = None,
        file_size: str | None = None,
    ) -> SentMessage:
        """發送檔案訊息

        Line 不支援直接發送檔案，改用文字訊息附帶連結。
        """
        from ..linebot import push_text

        # Line 沒有原生檔案訊息，用文字連結代替
        size_info = f"（{file_size}）" if file_size else ""
        text = f"📎 {file_name}{size_info}\n{file_url}"
        msg_id, error = await push_text(target, text)
        if error:
            logger.error(f"send_file 失敗: {error}")
            return SentMessage(message_id="", platform_type="line")

        return SentMessage(message_id=msg_id or "", platform_type="line")

    async def send_messages(
        self,
        target: str,
        messages: list,
        *,
        reply_to: str | None = None,
    ) -> list[SentMessage]:
        """批次發送多則訊息

        Args:
            target: Line 用戶 ID 或群組 ID
            messages: Line 原生訊息物件列表
            reply_to: 未使用
        """
        from ..linebot import push_messages as _push_messages

        sent_ids, error = await _push_messages(target, messages)
        if error:
            logger.error(f"send_messages 失敗: {error}")
            return []

        return [
            SentMessage(message_id=mid, platform_type="line")
            for mid in sent_ids
        ]

    async def reply_text(
        self,
        reply_token: str,
        text: str,
    ) -> SentMessage:
        """使用 reply token 回覆文字（Line 專屬，非 BotAdapter 介面）"""
        from ..linebot import reply_text as _reply_text

        msg_id = await _reply_text(reply_token, text)
        return SentMessage(message_id=msg_id or "", platform_type="line")

    async def reply_messages(
        self,
        reply_token: str,
        messages: list,
    ) -> list[SentMessage]:
        """使用 reply token 回覆多則訊息（Line 專屬，非 BotAdapter 介面）"""
        from ..linebot import reply_messages as _reply_messages

        sent_ids = await _reply_messages(reply_token, messages)
        return [
            SentMessage(message_id=mid, platform_type="line")
            for mid in sent_ids
        ]
