"""Line Bot 群組管理"""

import logging
from uuid import UUID

from ...database import get_connection
from .client import get_messaging_api

logger = logging.getLogger("linebot")


async def get_or_create_group(
    line_group_id: str,
    profile: dict | None = None,
) -> UUID:
    """取得或建立 Line 群組，回傳內部 UUID

    Args:
        line_group_id: Line 群組 ID
        profile: 群組資料（groupName, pictureUrl, memberCount）
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM bot_groups WHERE platform_group_id = $1",
            line_group_id,
        )
        if row:
            # 群組已存在，更新 profile 資訊（如果有）
            if profile:
                await conn.execute(
                    """
                    UPDATE bot_groups
                    SET name = COALESCE($2, name),
                        picture_url = COALESCE($3, picture_url),
                        member_count = COALESCE($4, member_count),
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    row["id"],
                    profile.get("groupName"),
                    profile.get("pictureUrl"),
                    profile.get("memberCount"),
                )
            return row["id"]

        # 群組不存在，建立新群組
        row = await conn.fetchrow(
            """
            INSERT INTO bot_groups (platform_group_id, name, picture_url, member_count)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            line_group_id,
            profile.get("groupName") if profile else None,
            profile.get("pictureUrl") if profile else None,
            profile.get("memberCount") if profile else 0,
        )
        return row["id"]


async def get_group_profile(
    line_group_id: str,
) -> dict | None:
    """從 Line API 取得群組 profile

    Args:
        line_group_id: Line 群組 ID
    """
    try:
        api = await get_messaging_api()
        summary = await api.get_group_summary(line_group_id)
        member_count_response = await api.get_group_member_count(line_group_id)
        return {
            "groupName": summary.group_name,
            "pictureUrl": summary.picture_url,
            "memberCount": member_count_response.count,
        }
    except Exception as e:
        logger.warning(f"無法取得群組 profile: {e}")
        return None


async def handle_join_event(
    line_group_id: str,
) -> None:
    """處理加入群組事件（包含重新加入）

    Args:
        line_group_id: Line 群組 ID
    """
    profile = await get_group_profile(line_group_id)
    group_uuid = await get_or_create_group(line_group_id, profile)

    # 確保群組狀態為活躍（處理重新加入的情況）
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE bot_groups
            SET is_active = true,
                left_at = NULL,
                joined_at = COALESCE(
                    CASE WHEN is_active = false THEN NOW() ELSE joined_at END,
                    NOW()
                ),
                updated_at = NOW()
            WHERE id = $1
            """,
            group_uuid,
        )
    logger.info(f"Bot 加入群組: {line_group_id}")


async def handle_leave_event(
    line_group_id: str,
) -> None:
    """處理離開群組事件

    Args:
        line_group_id: Line 群組 ID
    """
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE bot_groups
            SET is_active = false, left_at = NOW(), updated_at = NOW()
            WHERE platform_group_id = $1
            """,
            line_group_id,
        )
    logger.info(f"Bot 離開群組: {line_group_id}")


async def get_line_group_external_id(
    group_uuid: UUID,
) -> str | None:
    """從內部 UUID 取得 Line 群組的外部 ID

    Args:
        group_uuid: 群組內部 UUID

    Returns:
        Line 群組 ID（外部），或 None（如果找不到）
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT platform_group_id FROM bot_groups WHERE id = $1",
            group_uuid,
        )
        return row["platform_group_id"] if row else None
