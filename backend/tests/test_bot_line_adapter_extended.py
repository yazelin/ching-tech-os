"""測試 bot_line/adapter.py 未覆蓋的方法"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ching_tech_os.services.bot_line.adapter import LineBotAdapter as LineAdapter
from ching_tech_os.services.bot.adapter import SentMessage


class TestLineAdapterSendText:
    @pytest.mark.asyncio
    async def test_send_text_with_mention(self):
        """帶 mention 的文字訊息"""
        adapter = LineAdapter()
        with patch(
            "ching_tech_os.services.linebot.push_messages",
            new_callable=AsyncMock,
            return_value=(["msg-1"], None),
        ):
            with patch(
                "ching_tech_os.services.linebot.create_text_message_with_mention",
                return_value=MagicMock(),
            ):
                result = await adapter.send_text("U123", "hello", mention_user_id="U456")
                assert isinstance(result, SentMessage)
                assert result.platform_type == "line"

    @pytest.mark.asyncio
    async def test_send_text_error(self):
        """發送失敗"""
        adapter = LineAdapter()
        with patch(
            "ching_tech_os.services.linebot.push_text",
            new_callable=AsyncMock,
            return_value=(None, "API error"),
        ):
            result = await adapter.send_text("U123", "hello")
            assert result.message_id == ""


class TestLineAdapterSendImage:
    @pytest.mark.asyncio
    async def test_send_image_success(self):
        adapter = LineAdapter()
        with patch(
            "ching_tech_os.services.linebot.push_image",
            new_callable=AsyncMock,
            return_value=("img-1", None),
        ):
            result = await adapter.send_image("U123", "https://img.jpg")
            assert result.message_id == "img-1"

    @pytest.mark.asyncio
    async def test_send_image_error(self):
        adapter = LineAdapter()
        with patch(
            "ching_tech_os.services.linebot.push_image",
            new_callable=AsyncMock,
            return_value=(None, "failed"),
        ):
            result = await adapter.send_image("U123", "https://img.jpg")
            assert result.message_id == ""


class TestLineAdapterSendFile:
    @pytest.mark.asyncio
    async def test_send_file_success(self):
        adapter = LineAdapter()
        with patch(
            "ching_tech_os.services.linebot.push_text",
            new_callable=AsyncMock,
            return_value=("file-1", None),
        ):
            result = await adapter.send_file("U123", "https://file.pdf", "doc.pdf", file_size="2MB")
            assert result.message_id == "file-1"

    @pytest.mark.asyncio
    async def test_send_file_error(self):
        adapter = LineAdapter()
        with patch(
            "ching_tech_os.services.linebot.push_text",
            new_callable=AsyncMock,
            return_value=(None, "error"),
        ):
            result = await adapter.send_file("U123", "https://file.pdf", "doc.pdf")
            assert result.message_id == ""


class TestLineAdapterSendMessages:
    @pytest.mark.asyncio
    async def test_send_messages_success(self):
        adapter = LineAdapter()
        with patch(
            "ching_tech_os.services.linebot.push_messages",
            new_callable=AsyncMock,
            return_value=(["m1", "m2"], None),
        ):
            result = await adapter.send_messages("U123", [MagicMock(), MagicMock()])
            assert len(result) == 2
            assert all(isinstance(r, SentMessage) for r in result)

    @pytest.mark.asyncio
    async def test_send_messages_error(self):
        adapter = LineAdapter()
        with patch(
            "ching_tech_os.services.linebot.push_messages",
            new_callable=AsyncMock,
            return_value=([], "error"),
        ):
            result = await adapter.send_messages("U123", [MagicMock()])
            assert result == []


class TestLineAdapterReply:
    @pytest.mark.asyncio
    async def test_reply_text(self):
        adapter = LineAdapter()
        with patch(
            "ching_tech_os.services.linebot.reply_text",
            new_callable=AsyncMock,
            return_value="reply-1",
        ):
            result = await adapter.reply_text("token-123", "reply")
            assert result.message_id == "reply-1"

    @pytest.mark.asyncio
    async def test_reply_messages(self):
        adapter = LineAdapter()
        with patch(
            "ching_tech_os.services.linebot.reply_messages",
            new_callable=AsyncMock,
            return_value=["rm1", "rm2"],
        ):
            result = await adapter.reply_messages("token-123", [MagicMock()])
            assert len(result) == 2
