"""Line Bot 客戶端"""

import logging

from linebot.v3 import WebhookParser
from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
)

from ...config import settings

logger = logging.getLogger(__name__)

# 共用的 AsyncApiClient 單例，避免每次呼叫都建立新的 aiohttp session
_shared_api_client: AsyncApiClient | None = None


def get_line_config(access_token: str | None = None) -> Configuration:
    """取得 Line API 設定

    Args:
        access_token: 指定的 access token，不指定則使用環境變數
    """
    token = access_token or settings.line_channel_access_token
    return Configuration(access_token=token)


def get_webhook_parser(channel_secret: str | None = None) -> WebhookParser:
    """取得 Webhook 解析器

    Args:
        channel_secret: 指定的 channel secret，不指定則使用環境變數
    """
    secret = channel_secret or settings.line_channel_secret
    return WebhookParser(secret)


def _get_shared_api_client() -> AsyncApiClient:
    """取得共用的 AsyncApiClient 單例"""
    global _shared_api_client
    if _shared_api_client is None:
        config = get_line_config()
        _shared_api_client = AsyncApiClient(config)
    return _shared_api_client


async def get_messaging_api() -> AsyncMessagingApi:
    """取得 Messaging API 客戶端（共用單例，避免 aiohttp session 洩漏）

    Returns:
        AsyncMessagingApi 客戶端
    """
    api_client = _get_shared_api_client()
    return AsyncMessagingApi(api_client)


async def close_line_client() -> None:
    """關閉共用的 Line API 客戶端，應在應用程式關閉時呼叫"""
    global _shared_api_client
    if _shared_api_client is not None:
        try:
            await _shared_api_client.close()
        except Exception as e:
            logger.warning(f"關閉 Line API 客戶端失敗: {e}")
        _shared_api_client = None
