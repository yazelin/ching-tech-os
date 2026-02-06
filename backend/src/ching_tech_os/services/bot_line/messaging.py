"""Line Bot 訊息發送"""

import logging

from linebot.v3.messaging import (
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    TextMessageV2,
    ImageMessage,
    MentionSubstitutionObject,
    UserMentionTarget,
)

from .client import get_messaging_api
from .constants import MENTION_KEY, MENTION_PLACEHOLDER

logger = logging.getLogger("linebot")


async def reply_text(
    reply_token: str,
    text: str,
) -> str | None:
    """回覆文字訊息

    Args:
        reply_token: Line 回覆 token
        text: 回覆內容

    Returns:
        Line 訊息 ID，如果失敗則為 None
    """
    try:
        api = await get_messaging_api()
        response = await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )
        logger.info(f"回覆訊息: {text[:50]}...")
        # 取得 Line 回傳的訊息 ID
        if response and response.sent_messages:
            return response.sent_messages[0].id
        return None
    except Exception as e:
        logger.error(f"回覆訊息失敗: {e}")
        return None


def create_text_message_with_mention(
    text: str,
    mention_user_id: str | None = None,
) -> TextMessage | TextMessageV2:
    """建立文字訊息，可選擇 mention 特定用戶

    Args:
        text: 訊息文字
        mention_user_id: 要 mention 的 Line 用戶 ID（如 U1234567890abcdef）

    Returns:
        TextMessage 或 TextMessageV2（帶 mention）
    """
    if mention_user_id:
        # 使用 TextMessageV2 + mention
        # {user} 是佔位符，會被替換為 @用戶名稱
        return TextMessageV2(
            text=MENTION_PLACEHOLDER + text,
            substitution={
                MENTION_KEY: MentionSubstitutionObject(
                    mentionee=UserMentionTarget(userId=mention_user_id)
                )
            },
        )
    else:
        # 一般的 TextMessage
        return TextMessage(text=text)


async def reply_messages(
    reply_token: str,
    messages: list[TextMessage | TextMessageV2 | ImageMessage],
) -> list[str]:
    """回覆多則訊息（文字 + 圖片混合）

    Args:
        reply_token: Line 回覆 token
        messages: 訊息列表（TextMessage 或 ImageMessage，最多 5 則）

    Returns:
        發送成功的訊息 ID 列表
    """
    if not messages:
        return []

    # Line 限制每次最多 5 則訊息
    messages_to_send = messages[:5]

    try:
        api = await get_messaging_api()
        response = await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages_to_send,
            )
        )

        # 記錄發送內容
        msg_types = [type(m).__name__ for m in messages_to_send]
        logger.info(f"回覆多則訊息: {msg_types}")

        if response and response.sent_messages:
            return [m.id for m in response.sent_messages]
        return []
    except Exception as e:
        logger.error(f"回覆多則訊息失敗: {e}")
        raise  # 往上拋出讓呼叫端處理 fallback


def _parse_line_error(error: Exception) -> str:
    """解析 Line API 錯誤訊息"""
    error_str = str(error).lower()

    # 額度相關
    if "limit" in error_str or "quota" in error_str:
        return "已達本月推播上限"
    # 頻率限制
    if "429" in error_str or "too many" in error_str or "rate" in error_str:
        return "發送頻率過高，請稍後再試"
    # 權限問題
    if "403" in error_str or "forbidden" in error_str:
        return "沒有推播權限"
    # 用戶封鎖或不存在
    if "400" in error_str and ("user" in error_str or "not found" in error_str):
        return "用戶已封鎖機器人或不存在"
    # 圖片 URL 問題
    if "url" in error_str or "image" in error_str:
        return "圖片網址無法存取"
    # 其他
    return f"發送失敗：{error}"


async def push_text(
    to: str,
    text: str,
) -> tuple[str | None, str | None]:
    """主動推送文字訊息

    Args:
        to: 目標 ID（Line 用戶 ID 或群組 ID）
        text: 訊息內容

    Returns:
        (Line 訊息 ID, 錯誤訊息)，成功時錯誤訊息為 None
    """
    try:
        api = await get_messaging_api()
        response = await api.push_message(
            PushMessageRequest(
                to=to,
                messages=[TextMessage(text=text)],
            )
        )
        logger.info(f"推送訊息到 {to}: {text[:50]}...")
        if response and response.sent_messages:
            return response.sent_messages[0].id, None
        return None, "未知錯誤：無回應"
    except Exception as e:
        logger.error(f"推送訊息失敗: {e}")
        return None, _parse_line_error(e)


async def push_image(
    to: str,
    image_url: str,
    preview_url: str | None = None,
) -> tuple[str | None, str | None]:
    """主動推送圖片訊息

    Args:
        to: 目標 ID（Line 用戶 ID 或群組 ID）
        image_url: 圖片 URL（必須是 HTTPS）
        preview_url: 預覽圖 URL（可選，預設使用 image_url）

    Returns:
        (Line 訊息 ID, 錯誤訊息)，成功時錯誤訊息為 None
    """
    try:
        api = await get_messaging_api()
        response = await api.push_message(
            PushMessageRequest(
                to=to,
                messages=[ImageMessage(
                    original_content_url=image_url,
                    preview_image_url=preview_url or image_url,
                )],
            )
        )
        logger.info(f"推送圖片到 {to}: {image_url}")
        if response and response.sent_messages:
            return response.sent_messages[0].id, None
        return None, "未知錯誤：無回應"
    except Exception as e:
        logger.error(f"推送圖片失敗: {e}")
        return None, _parse_line_error(e)


async def push_messages(
    to: str,
    messages: list[TextMessage | ImageMessage],
) -> tuple[list[str], str | None]:
    """主動推送多則訊息（最多 5 則）

    Line API 支援單次請求發送多則訊息，可減少 API 呼叫次數。
    超過 5 則時會自動分批發送。

    Args:
        to: 目標 ID（Line 用戶 ID 或群組 ID）
        messages: 訊息列表（TextMessage 或 ImageMessage）

    Returns:
        (Line 訊息 ID 列表, 錯誤訊息)，成功時錯誤訊息為 None
    """
    if not messages:
        return [], None

    MAX_MESSAGES_PER_REQUEST = 5
    sent_message_ids: list[str] = []
    last_error: str | None = None

    try:
        api = await get_messaging_api()

        # 分批發送（每批最多 5 則）
        for i in range(0, len(messages), MAX_MESSAGES_PER_REQUEST):
            batch = messages[i:i + MAX_MESSAGES_PER_REQUEST]

            response = await api.push_message(
                PushMessageRequest(
                    to=to,
                    messages=batch,
                )
            )

            if response and response.sent_messages:
                for msg in response.sent_messages:
                    sent_message_ids.append(msg.id)

            logger.info(f"推送 {len(batch)} 則訊息到 {to}")

        return sent_message_ids, None

    except Exception as e:
        logger.error(f"推送多則訊息失敗: {e}")
        last_error = _parse_line_error(e)
        # 如果部分成功，仍回傳已發送的 ID
        if sent_message_ids:
            return sent_message_ids, f"部分訊息發送失敗: {last_error}"
        return [], last_error
