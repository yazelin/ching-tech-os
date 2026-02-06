"""測試 LineBotAdapter

測試對象：services/bot_line/adapter.py
驗證 LineBotAdapter 正確實作 BotAdapter Protocol。

用法：
    cd backend
    uv run pytest tests/test_bot_line_adapter.py -v
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ching_tech_os.services.bot.adapter import BotAdapter
from ching_tech_os.services.bot_line.adapter import LineBotAdapter

# patch 目標是 linebot 模組（adapter 內部用 lazy import）
LINEBOT = "ching_tech_os.services.linebot"


# ============================================================
# Protocol 相容性測試
# ============================================================

class TestLineBotAdapterProtocol:
    def test_platform_type(self):
        adapter = LineBotAdapter()
        assert adapter.platform_type == "line"

    def test_is_bot_adapter(self):
        """LineBotAdapter 應該符合 BotAdapter Protocol"""
        adapter = LineBotAdapter()
        assert isinstance(adapter, BotAdapter)

    def test_no_tenant_id(self):
        """租戶功能已移除，LineBotAdapter 不再需要 tenant_id"""
        adapter = LineBotAdapter()
        # 確認不會有 tenant_id 屬性錯誤
        assert adapter.platform_type == "line"


# ============================================================
# send_text 測試
# ============================================================

class TestSendText:
    @pytest.mark.asyncio
    async def test_send_text_success(self):
        adapter = LineBotAdapter()
        with patch(
            f"{LINEBOT}.push_text",
            new_callable=AsyncMock,
            return_value=("msg123", None),
        ) as mock_push:
            result = await adapter.send_text("U123", "hello")
            assert result.message_id == "msg123"
            assert result.platform_type == "line"
            mock_push.assert_called_once_with("U123", "hello")

    @pytest.mark.asyncio
    async def test_send_text_error(self):
        adapter = LineBotAdapter()
        with patch(
            f"{LINEBOT}.push_text",
            new_callable=AsyncMock,
            return_value=(None, "發送失敗"),
        ):
            result = await adapter.send_text("U123", "hello")
            assert result.message_id == ""

    @pytest.mark.asyncio
    async def test_send_text_with_mention(self):
        adapter = LineBotAdapter()
        mock_msg = MagicMock()
        with patch(
            f"{LINEBOT}.create_text_message_with_mention",
            return_value=mock_msg,
        ) as mock_create, patch(
            f"{LINEBOT}.push_messages",
            new_callable=AsyncMock,
            return_value=(["msg456"], None),
        ) as mock_push:
            result = await adapter.send_text("C123", "hi", mention_user_id="U999")
            assert result.message_id == "msg456"
            mock_create.assert_called_once_with("hi", "U999")
            mock_push.assert_called_once()


# ============================================================
# send_image 測試
# ============================================================

class TestSendImage:
    @pytest.mark.asyncio
    async def test_send_image_success(self):
        adapter = LineBotAdapter()
        with patch(
            f"{LINEBOT}.push_image",
            new_callable=AsyncMock,
            return_value=("img123", None),
        ):
            result = await adapter.send_image("U123", "https://img.com/a.jpg")
            assert result.message_id == "img123"

    @pytest.mark.asyncio
    async def test_send_image_with_preview(self):
        adapter = LineBotAdapter()
        with patch(
            f"{LINEBOT}.push_image",
            new_callable=AsyncMock,
            return_value=("img456", None),
        ) as mock_push:
            await adapter.send_image(
                "U123", "https://img.com/full.jpg",
                preview_url="https://img.com/thumb.jpg",
            )
            mock_push.assert_called_once_with(
                "U123", "https://img.com/full.jpg",
                preview_url="https://img.com/thumb.jpg",
            )


# ============================================================
# send_file 測試
# ============================================================

class TestSendFile:
    @pytest.mark.asyncio
    async def test_send_file_as_text_link(self):
        adapter = LineBotAdapter()
        with patch(
            f"{LINEBOT}.push_text",
            new_callable=AsyncMock,
            return_value=("file123", None),
        ) as mock_push:
            result = await adapter.send_file(
                "U123", "https://file.com/doc.pdf", "doc.pdf",
                file_size="2MB",
            )
            assert result.message_id == "file123"
            call_args = mock_push.call_args
            assert "doc.pdf" in call_args[0][1]
            assert "2MB" in call_args[0][1]
