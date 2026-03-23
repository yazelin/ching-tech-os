"""測試 bot_line/webhook.py 未覆蓋的分支"""

import pytest
from unittest.mock import patch

from ching_tech_os.services.bot_line.webhook import (
    verify_signature,
    verify_webhook_signature,
)


class TestVerifyWebhookSignature:
    @pytest.mark.asyncio
    async def test_valid_signature(self):
        """簽章正確時回傳 (True, None, None)"""
        with patch(
            "ching_tech_os.services.bot_line.webhook.verify_signature",
            return_value=True,
        ):
            result = await verify_webhook_signature(b"body", "sig")
            assert result == (True, None, None)

    @pytest.mark.asyncio
    async def test_invalid_signature(self):
        """簽章錯誤時回傳 (False, None, None)"""
        with patch(
            "ching_tech_os.services.bot_line.webhook.verify_signature",
            return_value=False,
        ):
            result = await verify_webhook_signature(b"body", "bad-sig")
            assert result == (False, None, None)


class TestVerifySignature:
    def test_no_secret(self):
        """secret 未設定"""
        with patch(
            "ching_tech_os.services.bot_line.webhook.settings"
        ) as mock_settings:
            mock_settings.line_channel_secret = ""
            assert verify_signature(b"body", "sig", channel_secret="") is False

    def test_correct_signature(self):
        """正確的簽章"""
        import hashlib, hmac, base64

        secret = "test-secret"
        body = b"test-body"
        h = hmac.new(secret.encode(), body, hashlib.sha256).digest()
        sig = base64.b64encode(h).decode()
        assert verify_signature(body, sig, channel_secret=secret) is True

    def test_incorrect_signature(self):
        """錯誤的簽章"""
        assert verify_signature(b"body", "wrong", channel_secret="secret") is False
