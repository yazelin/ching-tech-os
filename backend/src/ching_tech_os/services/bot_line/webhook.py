"""Webhook 簽章驗證"""

import hashlib
import hmac
import base64
import logging

from ...config import settings

logger = logging.getLogger("linebot")


def verify_signature(body: bytes, signature: str, channel_secret: str | None = None) -> bool:
    """驗證 Line Webhook 簽章

    Args:
        body: 請求內容
        signature: X-Line-Signature header
        channel_secret: 指定的 channel secret，不指定則使用環境變數

    Returns:
        簽章是否正確
    """
    secret = channel_secret or settings.line_channel_secret
    if not secret:
        logger.warning("Line channel secret 未設定")
        return False

    hash_value = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected_signature = base64.b64encode(hash_value).decode("utf-8")

    return hmac.compare_digest(signature, expected_signature)


async def verify_webhook_signature(body: bytes, signature: str) -> tuple[bool, None, None]:
    """驗證 Webhook 簽章

    Args:
        body: 請求內容
        signature: X-Line-Signature header

    Returns:
        (是否驗證成功, None, None)
        - (True, None, None): 驗證成功
        - (False, None, None): 驗證失敗
    """
    if verify_signature(body, signature):
        logger.debug("Webhook 驗證成功")
        return True, None, None

    logger.warning("Webhook 簽章驗證失敗")
    return False, None, None
