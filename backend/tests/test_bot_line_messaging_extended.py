"""測試 bot_line/messaging.py 未覆蓋的部分"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ching_tech_os.services.bot_line.messaging import (
    create_text_message_with_mention,
    _parse_line_error,
)


class TestCreateTextMessageWithMention:
    def test_without_mention(self):
        """不帶 mention"""
        from linebot.v3.messaging.models import TextMessage
        msg = create_text_message_with_mention("你好")
        assert isinstance(msg, TextMessage)
        assert msg.text == "你好"

    def test_with_mention(self):
        """帶 mention"""
        msg = create_text_message_with_mention("你好", mention_user_id="U12345")
        assert "你好" in msg.text


class TestParseLineError:
    def test_limit_error(self):
        assert "上限" in _parse_line_error(Exception("Monthly limit exceeded"))

    def test_quota_error(self):
        assert "上限" in _parse_line_error(Exception("exceeded quota"))

    def test_rate_limit(self):
        result = _parse_line_error(Exception("429 Too Many Requests"))
        assert "頻率" in result

    def test_too_many(self):
        result = _parse_line_error(Exception("too many requests"))
        assert "頻率" in result

    def test_forbidden(self):
        result = _parse_line_error(Exception("403 Forbidden"))
        assert "權限" in result

    def test_user_blocked(self):
        result = _parse_line_error(Exception("400 user not found"))
        assert "封鎖" in result or "不存在" in result

    def test_image_url_error(self):
        result = _parse_line_error(Exception("Invalid image url"))
        assert "圖片" in result

    def test_generic(self):
        result = _parse_line_error(Exception("Something unknown happened"))
        assert "發送失敗" in result
