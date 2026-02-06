"""Line Bot 客戶端"""

from linebot.v3 import WebhookParser
from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
)

from ...config import settings


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


async def get_messaging_api() -> AsyncMessagingApi:
    """取得 Messaging API 客戶端

    Returns:
        AsyncMessagingApi 客戶端
    """
    config = get_line_config()
    api_client = AsyncApiClient(config)
    return AsyncMessagingApi(api_client)
