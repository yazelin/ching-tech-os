"""Line Bot 訊息儲存"""

import logging
from uuid import UUID

from ...database import get_connection
from .user_manager import (
    get_or_create_user,
    get_user_profile,
    get_group_member_profile,
)
from .group_manager import get_or_create_group, get_group_profile

logger = logging.getLogger("linebot")


async def save_message(
    message_id: str,
    line_user_id: str,
    line_group_id: str | None,
    message_type: str,
    content: str | None,
    reply_token: str | None = None,
    is_from_bot: bool = False,
) -> UUID:
    """儲存訊息到資料庫，回傳訊息 UUID

    Args:
        message_id: Line 訊息 ID
        line_user_id: Line 用戶 ID
        line_group_id: Line 群組 ID（群組訊息時使用）
        message_type: 訊息類型（text, image, video, audio, file）
        content: 訊息內容
        reply_token: Line 回覆 token
        is_from_bot: 是否為 Bot 發送的訊息
    """
    # 取得或建立用戶
    # 群組訊息使用 get_group_member_profile（可取得非好友用戶資料）
    # 個人對話使用 get_user_profile（用戶必定與 Bot 有好友關係）
    user_profile = None
    is_friend = None  # 預設不設定，讓 get_or_create_user 決定
    if not is_from_bot:
        if line_group_id:
            user_profile = await get_group_member_profile(line_group_id, line_user_id)
            is_friend = False  # 群組成員預設為非好友
        else:
            user_profile = await get_user_profile(line_user_id)
            is_friend = True  # 個人對話必定是好友
    user_uuid = await get_or_create_user(line_user_id, user_profile, is_friend)

    # 取得或建立群組（如果是群組訊息）
    group_uuid = None
    if line_group_id:
        group_profile = await get_group_profile(line_group_id)
        group_uuid = await get_or_create_group(line_group_id, group_profile)

    # 儲存訊息
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO bot_messages (
                message_id, bot_user_id, bot_group_id,
                message_type, content, reply_token, is_from_bot
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            message_id,
            user_uuid,
            group_uuid,
            message_type,
            content,
            reply_token,
            is_from_bot,
        )
        logger.info(f"儲存訊息: {message_id} (type={message_type})")
        return row["id"]


async def mark_message_ai_processed(message_uuid: UUID) -> None:
    """標記訊息已經過 AI 處理"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE bot_messages SET ai_processed = true WHERE id = $1",
            message_uuid,
        )


async def get_or_create_bot_user(_: UUID | str | None = None) -> UUID:
    """取得或建立 Bot 用戶，回傳用戶 UUID

    由於 line_user_id 有全域唯一約束，Bot 用戶在全系統只會有一個。
    此函數會優先查詢全域 Bot 用戶，如果已存在則返回現有用戶。
    """
    bot_line_id = "BOT_CHINGTECH"

    async with get_connection() as conn:
        # 先查詢全域是否有 Bot 用戶（platform_user_id 有全域唯一約束）
        row = await conn.fetchrow(
            "SELECT id FROM bot_users WHERE platform_user_id = $1",
            bot_line_id,
        )
        if row:
            # 確保 Bot 用戶的 is_friend 為 false 且名稱正確
            await conn.execute(
                """
                UPDATE bot_users
                SET is_friend = false, display_name = 'ChingTech AI (Bot)'
                WHERE id = $1
                """,
                row["id"],
            )
            return row["id"]

        # 建立 Bot 用戶（is_friend = false）
        row = await conn.fetchrow(
            """
            INSERT INTO bot_users (platform_user_id, display_name, is_friend)
            VALUES ($1, $2, false)
            RETURNING id
            """,
            bot_line_id,
            "ChingTech AI (Bot)",
        )
        logger.info("已建立 Bot 用戶")
        return row["id"]


async def save_bot_response(
    group_uuid: UUID | None,
    content: str,
    responding_to_line_user_id: str | None = None,
    line_message_id: str | None = None,
) -> UUID:
    """儲存 Bot 回應訊息到資料庫

    Args:
        group_uuid: 群組內部 UUID（個人對話為 None）
        content: 回應內容
        responding_to_line_user_id: 回應的對象用戶 Line ID（個人對話用）
        line_message_id: Line 回傳的訊息 ID（用於回覆觸發）

    Returns:
        訊息 UUID
    """
    import uuid as uuid_module

    # 使用 Line 回傳的 message_id，或產生唯一的 ID
    message_id = line_message_id or f"bot_{uuid_module.uuid4().hex[:16]}"

    # 決定使用哪個用戶 ID
    if group_uuid:
        # 群組對話：使用 Bot 用戶 ID
        user_uuid = await get_or_create_bot_user()
    elif responding_to_line_user_id:
        # 個人對話：使用對話對象的用戶 ID（這樣查詢歷史時可以一起取得）
        user_uuid = await get_or_create_user(responding_to_line_user_id, None)
    else:
        # Fallback：使用 Bot 用戶 ID
        user_uuid = await get_or_create_bot_user()

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO bot_messages (
                message_id, bot_user_id, bot_group_id,
                message_type, content, is_from_bot
            )
            VALUES ($1, $2, $3, 'text', $4, true)
            RETURNING id
            """,
            message_id,
            user_uuid,
            group_uuid,
            content,
        )
        logger.info(f"儲存 Bot 回應: {message_id}")
        return row["id"]


async def get_message_content_by_line_message_id(line_message_id: str) -> dict | None:
    """根據 Line message_id 取得訊息內容

    Args:
        line_message_id: Line 訊息 ID

    Returns:
        dict with content, message_type, display_name, is_from_bot or None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT m.content, m.message_type, m.is_from_bot,
                   u.display_name
            FROM bot_messages m
            JOIN bot_users u ON m.bot_user_id = u.id
            WHERE m.message_id = $1
            """,
            line_message_id,
        )
        return dict(row) if row else None
