"""Line Bot 用戶管理"""

import logging
from uuid import UUID

from ...database import get_connection
from .client import get_messaging_api

logger = logging.getLogger("linebot")


async def get_line_user_record(
    line_user_id: str,
    columns: str = "*",
) -> dict | None:
    """查詢 bot_users 表的記錄

    Args:
        line_user_id: Line 用戶 ID
        columns: 要查詢的欄位（預設 "*"）

    Returns:
        bot_users 表的記錄，若找不到則回傳 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"SELECT {columns} FROM bot_users WHERE platform_user_id = $1",
            line_user_id,
        )
        return dict(row) if row else None


async def get_or_create_user(
    line_user_id: str,
    profile: dict | None = None,
    is_friend: bool | None = None,
) -> UUID:
    """取得或建立 Line 用戶，回傳內部 UUID

    Args:
        line_user_id: Line 用戶 ID
        profile: 用戶資料（displayName, pictureUrl, statusMessage）
        is_friend: 是否為好友（僅在建立新用戶時使用）
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM bot_users WHERE platform_user_id = $1",
            line_user_id,
        )
        if row:
            # 用戶已存在，更新 profile 資訊（如果有）
            if profile:
                await conn.execute(
                    """
                    UPDATE bot_users
                    SET display_name = COALESCE($2, display_name),
                        picture_url = COALESCE($3, picture_url),
                        status_message = COALESCE($4, status_message),
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    row["id"],
                    profile.get("displayName"),
                    profile.get("pictureUrl"),
                    profile.get("statusMessage"),
                )
            return row["id"]

        # 用戶不存在，建立新記錄
        row = await conn.fetchrow(
            """
            INSERT INTO bot_users (platform_user_id, display_name, picture_url, status_message, is_friend)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            line_user_id,
            profile.get("displayName") if profile else None,
            profile.get("pictureUrl") if profile else None,
            profile.get("statusMessage") if profile else None,
            is_friend if is_friend is not None else False,
        )
        return row["id"]


async def update_user_friend_status(
    line_user_id: str,
    is_friend: bool,
) -> bool:
    """更新用戶的好友狀態

    Args:
        line_user_id: Line 用戶 ID
        is_friend: 是否為好友

    Returns:
        是否更新成功
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE bot_users
            SET is_friend = $2, updated_at = NOW()
            WHERE platform_user_id = $1
            """,
            line_user_id,
            is_friend,
        )
        return result == "UPDATE 1"


async def get_user_profile(line_user_id: str) -> dict | None:
    """從 Line API 取得用戶 profile（個人對話用）

    注意：此 API 只能取得與 Bot 有好友關係的用戶資料。
    群組訊息請使用 get_group_member_profile()。

    Args:
        line_user_id: Line 用戶 ID
    """
    try:
        api = await get_messaging_api()
        profile = await api.get_profile(line_user_id)
        return {
            "displayName": profile.display_name,
            "pictureUrl": profile.picture_url,
            "statusMessage": profile.status_message,
        }
    except Exception as e:
        logger.warning(f"無法取得用戶 profile: {e}")
        return None


async def get_group_member_profile(
    line_group_id: str,
    line_user_id: str,
) -> dict | None:
    """從 Line API 取得群組成員 profile

    此 API 可取得群組內任何成員的資料，不需要好友關係。

    Args:
        line_group_id: Line 群組 ID
        line_user_id: Line 用戶 ID

    Returns:
        包含 displayName、pictureUrl 的字典，失敗回傳 None
    """
    try:
        api = await get_messaging_api()
        profile = await api.get_group_member_profile(line_group_id, line_user_id)
        return {
            "displayName": profile.display_name,
            "pictureUrl": profile.picture_url,
        }
    except Exception as e:
        logger.warning(f"無法取得群組成員 profile: {e}")
        return None
