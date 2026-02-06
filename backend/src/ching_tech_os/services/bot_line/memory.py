"""Line Bot 記憶管理服務"""

import logging
from uuid import UUID

from ...database import get_connection

logger = logging.getLogger("linebot")


async def list_group_memories(line_group_id: UUID) -> tuple[list[dict], int]:
    """取得群組記憶列表

    Args:
        line_group_id: 群組內部 UUID

    Returns:
        (記憶列表, 總數)
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT m.*, u.display_name as created_by_name
            FROM bot_group_memories m
            LEFT JOIN bot_users u ON m.created_by = u.id
            WHERE m.bot_group_id = $1
            ORDER BY m.created_at DESC
            """,
            line_group_id,
        )
        return [dict(row) for row in rows], len(rows)


async def list_user_memories(line_user_id: UUID) -> tuple[list[dict], int]:
    """取得個人記憶列表

    Args:
        line_user_id: 用戶內部 UUID

    Returns:
        (記憶列表, 總數)
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM bot_user_memories
            WHERE bot_user_id = $1
            ORDER BY created_at DESC
            """,
            line_user_id,
        )
        return [dict(row) for row in rows], len(rows)


async def create_group_memory(
    line_group_id: UUID,
    title: str,
    content: str,
    created_by: UUID | None = None,
) -> dict:
    """建立群組記憶

    Args:
        line_group_id: 群組內部 UUID
        title: 記憶標題
        content: 記憶內容
        created_by: 建立者（Line 用戶 UUID）

    Returns:
        建立的記憶資料
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO bot_group_memories (bot_group_id, title, content, created_by)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            line_group_id,
            title,
            content,
            created_by,
        )
        result = dict(row)

        # 取得建立者名稱
        if created_by:
            user_row = await conn.fetchrow(
                "SELECT display_name FROM bot_users WHERE id = $1",
                created_by,
            )
            if user_row:
                result["created_by_name"] = user_row["display_name"]

        logger.info(f"已建立群組記憶: group={line_group_id}, title={title}")
        return result


async def create_user_memory(
    line_user_id: UUID,
    title: str,
    content: str,
) -> dict:
    """建立個人記憶

    Args:
        line_user_id: 用戶內部 UUID
        title: 記憶標題
        content: 記憶內容

    Returns:
        建立的記憶資料
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO bot_user_memories (bot_user_id, title, content)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            line_user_id,
            title,
            content,
        )
        logger.info(f"已建立個人記憶: user={line_user_id}, title={title}")
        return dict(row)


async def update_memory(
    memory_id: UUID,
    title: str | None = None,
    content: str | None = None,
    is_active: bool | None = None,
) -> dict | None:
    """更新記憶（群組或個人）

    會先嘗試在 bot_group_memories 找，找不到再找 bot_user_memories。

    Args:
        memory_id: 記憶 UUID
        title: 新標題（可選）
        content: 新內容（可選）
        is_active: 新啟用狀態（可選）

    Returns:
        更新後的記憶資料，找不到回傳 None
    """
    async with get_connection() as conn:
        # 先嘗試更新群組記憶
        update_fields = []
        params = [memory_id]
        param_idx = 2

        if title is not None:
            update_fields.append(f"title = ${param_idx}")
            params.append(title)
            param_idx += 1
        if content is not None:
            update_fields.append(f"content = ${param_idx}")
            params.append(content)
            param_idx += 1
        if is_active is not None:
            update_fields.append(f"is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1

        if not update_fields:
            # 沒有要更新的欄位，直接查詢回傳
            row = await conn.fetchrow(
                """
                SELECT m.*, u.display_name as created_by_name
                FROM bot_group_memories m
                LEFT JOIN bot_users u ON m.created_by = u.id
                WHERE m.id = $1
                """,
                memory_id,
            )
            if row:
                return dict(row)
            row = await conn.fetchrow(
                "SELECT * FROM bot_user_memories WHERE id = $1",
                memory_id,
            )
            return dict(row) if row else None

        update_fields.append("updated_at = NOW()")
        set_clause = ", ".join(update_fields)

        # 嘗試更新群組記憶
        row = await conn.fetchrow(
            f"""
            UPDATE bot_group_memories
            SET {set_clause}
            WHERE id = $1
            RETURNING *
            """,
            *params,
        )

        if row:
            result = dict(row)
            # 取得建立者名稱
            if result.get("created_by"):
                user_row = await conn.fetchrow(
                    "SELECT display_name FROM bot_users WHERE id = $1",
                    result["created_by"],
                )
                if user_row:
                    result["created_by_name"] = user_row["display_name"]
            logger.info(f"已更新群組記憶: {memory_id}")
            return result

        # 嘗試更新個人記憶
        row = await conn.fetchrow(
            f"""
            UPDATE bot_user_memories
            SET {set_clause}
            WHERE id = $1
            RETURNING *
            """,
            *params,
        )

        if row:
            logger.info(f"已更新個人記憶: {memory_id}")
            return dict(row)

        return None


async def delete_memory(memory_id: UUID) -> bool:
    """刪除記憶（群組或個人）

    會先嘗試在 bot_group_memories 刪除，找不到再找 bot_user_memories。

    Args:
        memory_id: 記憶 UUID

    Returns:
        是否成功刪除
    """
    async with get_connection() as conn:
        # 先嘗試刪除群組記憶
        result = await conn.execute(
            "DELETE FROM bot_group_memories WHERE id = $1",
            memory_id,
        )
        if result == "DELETE 1":
            logger.info(f"已刪除群組記憶: {memory_id}")
            return True

        # 嘗試刪除個人記憶
        result = await conn.execute(
            "DELETE FROM bot_user_memories WHERE id = $1",
            memory_id,
        )
        if result == "DELETE 1":
            logger.info(f"已刪除個人記憶: {memory_id}")
            return True

        return False


async def get_line_user_by_ctos_user(ctos_user_id: int) -> dict | None:
    """透過 CTOS 用戶 ID 取得對應的 Line 用戶

    Args:
        ctos_user_id: CTOS 用戶 ID

    Returns:
        Line 用戶資料，找不到回傳 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM bot_users WHERE user_id = $1",
            ctos_user_id,
        )
        return dict(row) if row else None


async def get_active_group_memories(line_group_id: UUID) -> list[dict]:
    """取得群組的所有啟用記憶

    Args:
        line_group_id: 群組內部 UUID

    Returns:
        啟用的記憶列表
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT content
            FROM bot_group_memories
            WHERE bot_group_id = $1 AND is_active = true
            ORDER BY created_at ASC
            """,
            line_group_id,
        )
        return [dict(row) for row in rows]


async def get_active_user_memories(line_user_id: UUID) -> list[dict]:
    """取得用戶的所有啟用記憶

    Args:
        line_user_id: 用戶內部 UUID

    Returns:
        啟用的記憶列表
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT content
            FROM bot_user_memories
            WHERE bot_user_id = $1 AND is_active = true
            ORDER BY created_at ASC
            """,
            line_user_id,
        )
        return [dict(row) for row in rows]
