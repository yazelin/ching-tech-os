"""記憶管理相關 MCP 工具

包含：add_memory, get_memories, update_memory, delete_memory
"""

from uuid import UUID

from .server import mcp, logger, ensure_db_connection, to_taipei_time
from ...database import get_connection


@mcp.tool()
async def add_memory(
    content: str,
    title: str | None = None,
    line_group_id: str | None = None,
    line_user_id: str | None = None,
) -> str:
    """
    新增記憶

    Args:
        content: 記憶內容（必填）
        title: 記憶標題（方便識別），若未提供系統會自動產生
        line_group_id: Line 群組的內部 UUID（群組對話時使用，從對話識別取得）
        line_user_id: Line 用戶 ID（個人對話時使用，從對話識別取得）
    """
    await ensure_db_connection()

    # 自動產生標題（取 content 前 20 字）
    if not title:
        title = content[:20] + ("..." if len(content) > 20 else "")

    if line_group_id:
        # 群組記憶
        try:
            group_uuid = UUID(line_group_id)
        except ValueError:
            return "❌ 群組 ID 格式錯誤"

        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO bot_group_memories (bot_group_id, title, content)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                group_uuid,
                title,
                content,
            )
            return f"✅ 已新增群組記憶：{title}\n記憶 ID：{row['id']}"

    elif line_user_id:
        # 個人記憶：需要查詢用戶的內部 UUID
        from ..linebot import get_line_user_record
        user_row = await get_line_user_record(line_user_id, "id")
        if not user_row:
            return "❌ 找不到用戶"

        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO bot_user_memories (bot_user_id, title, content)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                user_row["id"],
                title,
                content,
            )
            return f"✅ 已新增個人記憶：{title}\n記憶 ID：{row['id']}"
    else:
        return "❌ 請提供 line_group_id 或 line_user_id"


@mcp.tool()
async def get_memories(
    line_group_id: str | None = None,
    line_user_id: str | None = None,
) -> str:
    """
    查詢記憶

    Args:
        line_group_id: Line 群組的內部 UUID（群組對話時使用，從對話識別取得）
        line_user_id: Line 用戶 ID（個人對話時使用，從對話識別取得）
    """
    await ensure_db_connection()

    if line_group_id:
        # 群組記憶
        try:
            group_uuid = UUID(line_group_id)
        except ValueError:
            return "❌ 群組 ID 格式錯誤"

        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, content, is_active, created_at
                FROM bot_group_memories
                WHERE bot_group_id = $1
                ORDER BY created_at DESC
                """,
                group_uuid,
            )

            if not rows:
                return "目前沒有設定任何記憶"

            result = "📝 **群組記憶列表**\n\n"
            for row in rows:
                status = "✅" if row["is_active"] else "❌"
                created = to_taipei_time(row["created_at"]).strftime("%Y-%m-%d %H:%M")
                result += f"**{row['title']}** {status}\n"
                result += f"ID: `{row['id']}`\n"
                result += f"內容: {row['content'][:100]}{'...' if len(row['content']) > 100 else ''}\n"
                result += f"建立時間: {created}\n\n"
            return result

    elif line_user_id:
        # 個人記憶
        from ..linebot import get_line_user_record
        user_row = await get_line_user_record(line_user_id, "id")
        if not user_row:
            return "❌ 找不到用戶"

        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, content, is_active, created_at
                FROM bot_user_memories
                WHERE bot_user_id = $1
                ORDER BY created_at DESC
                """,
                user_row["id"],
            )

        if not rows:
            return "目前沒有設定任何記憶"

        result = "📝 **個人記憶列表**\n\n"
        for row in rows:
            status = "✅" if row["is_active"] else "❌"
            created = to_taipei_time(row["created_at"]).strftime("%Y-%m-%d %H:%M")
            result += f"**{row['title']}** {status}\n"
            result += f"ID: `{row['id']}`\n"
            result += f"內容: {row['content'][:100]}{'...' if len(row['content']) > 100 else ''}\n"
            result += f"建立時間: {created}\n\n"
        return result
    else:
        return "❌ 請提供 line_group_id 或 line_user_id"


@mcp.tool()
async def update_memory(
    memory_id: str,
    title: str | None = None,
    content: str | None = None,
    is_active: bool | None = None,
) -> str:
    """
    更新記憶

    Args:
        memory_id: 記憶 UUID（必填）
        title: 新標題
        content: 新內容
        is_active: 是否啟用（true/false）
    """
    await ensure_db_connection()

    try:
        memory_uuid = UUID(memory_id)
    except ValueError:
        return "❌ 記憶 ID 格式錯誤"

    # 建構更新欄位
    update_fields = []
    params = [memory_uuid]
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
        return "❌ 請提供要更新的欄位（title、content 或 is_active）"

    update_fields.append("updated_at = NOW()")
    set_clause = ", ".join(update_fields)

    async with get_connection() as conn:
        # 先嘗試更新群組記憶
        result = await conn.execute(
            f"UPDATE bot_group_memories SET {set_clause} WHERE id = $1",
            *params,
        )
        if result == "UPDATE 1":
            return f"✅ 已更新群組記憶"

        # 再嘗試更新個人記憶
        result = await conn.execute(
            f"UPDATE bot_user_memories SET {set_clause} WHERE id = $1",
            *params,
        )
        if result == "UPDATE 1":
            return f"✅ 已更新個人記憶"

        return "❌ 找不到指定的記憶"


@mcp.tool()
async def delete_memory(memory_id: str) -> str:
    """
    刪除記憶

    Args:
        memory_id: 記憶 UUID（必填）
    """
    await ensure_db_connection()

    try:
        memory_uuid = UUID(memory_id)
    except ValueError:
        return "❌ 記憶 ID 格式錯誤"

    async with get_connection() as conn:
        # 先嘗試刪除群組記憶
        result = await conn.execute(
            "DELETE FROM bot_group_memories WHERE id = $1",
            memory_uuid,
        )
        if result == "DELETE 1":
            return "✅ 已刪除群組記憶"

        # 再嘗試刪除個人記憶
        result = await conn.execute(
            "DELETE FROM bot_user_memories WHERE id = $1",
            memory_uuid,
        )
        if result == "DELETE 1":
            return "✅ 已刪除個人記憶"

        return "❌ 找不到指定的記憶"
