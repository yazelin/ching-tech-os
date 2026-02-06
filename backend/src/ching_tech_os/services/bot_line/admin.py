"""Line Bot 管理查詢功能"""

import logging
from uuid import UUID

from ...database import get_connection

logger = logging.getLogger("linebot")


async def list_groups(
    is_active: bool | None = None,
    project_id: UUID | None = None,
    platform_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """列出群組

    Args:
        is_active: 是否活躍過濾
        project_id: 專案 ID 過濾
        platform_type: 平台類型過濾（line, telegram）
        limit: 最大數量
        offset: 偏移量
    """
    async with get_connection() as conn:
        # 建構查詢條件
        conditions: list[str] = []
        params: list = []
        param_idx = 1

        if is_active is not None:
            conditions.append(f"g.is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1

        if project_id is not None:
            conditions.append(f"g.project_id = ${param_idx}")
            params.append(project_id)
            param_idx += 1

        if platform_type is not None:
            conditions.append(f"g.platform_type = ${param_idx}")
            params.append(platform_type)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 查詢總數
        count_query = f"SELECT COUNT(*) FROM bot_groups g WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params)

        # 查詢列表
        query = f"""
            SELECT g.*
            FROM bot_groups g
            WHERE {where_clause}
            ORDER BY g.updated_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows], total


async def list_messages(
    line_group_id: UUID | None = None,
    line_user_id: UUID | None = None,
    platform_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """列出訊息

    Args:
        line_group_id: 群組 UUID 過濾
        line_user_id: 用戶 UUID 過濾
        platform_type: 平台類型過濾（line, telegram）
        limit: 最大數量
        offset: 偏移量
    """
    async with get_connection() as conn:
        conditions: list[str] = []
        params: list = []
        param_idx = 1

        if line_group_id is not None:
            conditions.append(f"m.bot_group_id = ${param_idx}")
            params.append(line_group_id)
            param_idx += 1
        else:
            # 如果沒指定群組，預設查個人訊息
            conditions.append("m.bot_group_id IS NULL")

        if line_user_id is not None:
            conditions.append(f"m.bot_user_id = ${param_idx}")
            params.append(line_user_id)
            param_idx += 1

        if platform_type is not None:
            conditions.append(f"m.platform_type = ${param_idx}")
            params.append(platform_type)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 查詢總數
        count_query = f"SELECT COUNT(*) FROM bot_messages m WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params)

        # 查詢列表（包含用戶資訊）
        query = f"""
            SELECT m.*, u.display_name as user_display_name, u.picture_url as user_picture_url
            FROM bot_messages m
            LEFT JOIN bot_users u ON m.bot_user_id = u.id
            WHERE {where_clause}
            ORDER BY m.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows], total


async def list_users(
    platform_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """列出用戶

    Args:
        platform_type: 平台類型過濾（line, telegram）
        limit: 最大數量
        offset: 偏移量
    """
    async with get_connection() as conn:
        conditions: list[str] = []
        params: list = []
        param_idx = 1

        if platform_type is not None:
            conditions.append(f"platform_type = ${param_idx}")
            params.append(platform_type)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM bot_users WHERE {where_clause}",
            *params,
        )
        params.extend([limit, offset])
        rows = await conn.fetch(
            f"""
            SELECT * FROM bot_users
            WHERE {where_clause}
            ORDER BY updated_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """,
            *params,
        )
        return [dict(row) for row in rows], total


async def get_group_by_id(
    group_id: UUID,
) -> dict | None:
    """取得群組詳情

    Args:
        group_id: 群組 UUID
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM bot_groups WHERE id = $1",
            group_id,
        )
        return dict(row) if row else None


async def get_user_by_id(
    user_id: UUID,
) -> dict | None:
    """取得用戶詳情

    Args:
        user_id: 用戶 UUID
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM bot_users WHERE id = $1",
            user_id,
        )
        return dict(row) if row else None


async def bind_group_to_project(
    group_id: UUID,
    project_id: UUID,
) -> bool:
    """綁定群組到專案

    Args:
        group_id: 群組 UUID
        project_id: 專案 UUID
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE bot_groups
            SET project_id = $2, updated_at = NOW()
            WHERE id = $1
            """,
            group_id,
            project_id,
        )
        return result == "UPDATE 1"


async def unbind_group_from_project(
    group_id: UUID,
) -> bool:
    """解除群組與專案的綁定

    Args:
        group_id: 群組 UUID
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE bot_groups
            SET project_id = NULL, updated_at = NOW()
            WHERE id = $1
            """,
            group_id,
        )
        return result == "UPDATE 1"


async def delete_group(
    group_id: UUID,
) -> dict | None:
    """刪除群組及其相關資料

    Args:
        group_id: 群組 UUID

    Returns:
        刪除結果（含訊息數量）或 None（群組不存在）
    """
    async with get_connection() as conn:
        # 先查詢群組是否存在及訊息數量
        row = await conn.fetchrow(
            """
            SELECT g.id, g.name,
                   (SELECT COUNT(*) FROM bot_messages WHERE bot_group_id = g.id) as message_count
            FROM bot_groups g
            WHERE g.id = $1
            """,
            group_id,
        )

        if not row:
            return None

        group_name = row["name"] or "未命名群組"
        message_count = row["message_count"]

        # 刪除群組（訊息和檔案記錄會級聯刪除）
        await conn.execute(
            "DELETE FROM bot_groups WHERE id = $1",
            group_id,
        )

        return {
            "group_id": str(group_id),
            "group_name": group_name,
            "deleted_messages": message_count,
        }


async def update_group_settings(
    group_id: UUID,
    allow_ai_response: bool,
) -> bool:
    """
    更新群組設定

    Args:
        group_id: 群組 UUID
        allow_ai_response: 是否允許 AI 回應

    Returns:
        是否成功更新
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE bot_groups
            SET allow_ai_response = $2, updated_at = NOW()
            WHERE id = $1
            """,
            group_id,
            allow_ai_response,
        )
        return result == "UPDATE 1"


async def list_users_with_binding(
    platform_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """列出用戶（包含 CTOS 綁定資訊）

    Args:
        platform_type: 平台類型過濾（line, telegram）
        limit: 最大數量
        offset: 偏移量
    """
    async with get_connection() as conn:
        conditions: list[str] = []
        params: list = []
        param_idx = 1

        if platform_type is not None:
            conditions.append(f"lu.platform_type = ${param_idx}")
            params.append(platform_type)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM bot_users lu WHERE {where_clause}",
            *params,
        )
        params.extend([limit, offset])
        rows = await conn.fetch(
            f"""
            SELECT lu.*, u.username as bound_username, u.display_name as bound_display_name
            FROM bot_users lu
            LEFT JOIN users u ON lu.user_id = u.id
            WHERE {where_clause}
            ORDER BY lu.updated_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """,
            *params,
        )
        return [dict(row) for row in rows], total
