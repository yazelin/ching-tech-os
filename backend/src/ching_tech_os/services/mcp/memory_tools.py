"""記憶管理相關 MCP 工具

包含：add_memory, get_memories, update_memory, delete_memory
"""

from uuid import UUID

from .server import (
    mcp,
    logger,
    ensure_db_connection,
    resolve_bot_identity,
    to_taipei_time,
)
from ...database import get_connection


async def _resolve_bot_user_uuid(line_user_id: str | None):
    """platform_user_id → bot_users.id（找不到回 None）。"""
    if not line_user_id:
        return None
    from ..bot_line import get_line_user_record

    user_row = await get_line_user_record(line_user_id, "id")
    return user_row["id"] if user_row else None


async def _connected_memory_scope():
    """這次連線可以動的記憶範圍（issue #204）。

    `update_memory`／`delete_memory` 只吃 memory_id，沒有身分參數——換句話說
    任何拿得到（或猜得到）UUID 的人都能改別的群組／別人的記憶。有伺服器注入的
    連線身分時，SQL 一律加上對應的擁有者條件；沒有注入（目前是網頁聊天，
    見 `docs/mcp-tool-access-matrix.md` 的已知缺口）才維持原本的不限範圍行為。

    Returns:
        (bot_group_id, bot_user_uuid)：都是 None 表示沒有連線身分可用
    """
    group_id, platform_user_id = resolve_bot_identity(None, None)

    group_uuid = None
    if group_id:
        try:
            group_uuid = UUID(str(group_id))
        except ValueError:
            logger.warning("[memory] 注入的群組 id 格式錯誤，忽略：%s", group_id)

    bot_user_uuid = await _resolve_bot_user_uuid(platform_user_id)
    return group_uuid, bot_user_uuid


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

    # 身分一律以連線為準，模型宣稱別人的 id 無效（issue #204）
    line_group_id, line_user_id = resolve_bot_identity(line_group_id, line_user_id)

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
        bot_user_uuid = await _resolve_bot_user_uuid(line_user_id)
        if not bot_user_uuid:
            return "❌ 找不到用戶"

        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO bot_user_memories (bot_user_id, title, content)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                bot_user_uuid,
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

    # 身分一律以連線為準，模型宣稱別人的 id 無效（issue #204）
    line_group_id, line_user_id = resolve_bot_identity(line_group_id, line_user_id)

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
        bot_user_uuid = await _resolve_bot_user_uuid(line_user_id)
        if not bot_user_uuid:
            return "❌ 找不到用戶"

        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, content, is_active, created_at
                FROM bot_user_memories
                WHERE bot_user_id = $1
                ORDER BY created_at DESC
                """,
                bot_user_uuid,
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

    # 有連線身分就只能改自己這條連線底下的記憶（issue #204）
    group_uuid, bot_user_uuid = await _connected_memory_scope()
    scoped = group_uuid is not None or bot_user_uuid is not None

    async with get_connection() as conn:
        # 先嘗試更新群組記憶
        if group_uuid is not None or not scoped:
            group_params = list(params)
            group_where = ""
            if group_uuid is not None:
                group_where = f" AND bot_group_id = ${param_idx}"
                group_params.append(group_uuid)
            result = await conn.execute(
                f"UPDATE bot_group_memories SET {set_clause} WHERE id = $1{group_where}",
                *group_params,
            )
            if result == "UPDATE 1":
                return f"✅ 已更新群組記憶"

        # 再嘗試更新個人記憶
        if bot_user_uuid is not None or not scoped:
            user_params = list(params)
            user_where = ""
            if bot_user_uuid is not None:
                user_where = f" AND bot_user_id = ${param_idx}"
                user_params.append(bot_user_uuid)
            result = await conn.execute(
                f"UPDATE bot_user_memories SET {set_clause} WHERE id = $1{user_where}",
                *user_params,
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

    # 有連線身分就只能刪自己這條連線底下的記憶（issue #204）
    group_uuid, bot_user_uuid = await _connected_memory_scope()
    scoped = group_uuid is not None or bot_user_uuid is not None

    async with get_connection() as conn:
        # 先嘗試刪除群組記憶
        if group_uuid is not None or not scoped:
            if group_uuid is not None:
                result = await conn.execute(
                    "DELETE FROM bot_group_memories WHERE id = $1 AND bot_group_id = $2",
                    memory_uuid,
                    group_uuid,
                )
            else:
                result = await conn.execute(
                    "DELETE FROM bot_group_memories WHERE id = $1",
                    memory_uuid,
                )
            if result == "DELETE 1":
                return "✅ 已刪除群組記憶"

        # 再嘗試刪除個人記憶
        if bot_user_uuid is not None or not scoped:
            if bot_user_uuid is not None:
                result = await conn.execute(
                    "DELETE FROM bot_user_memories WHERE id = $1 AND bot_user_id = $2",
                    memory_uuid,
                    bot_user_uuid,
                )
            else:
                result = await conn.execute(
                    "DELETE FROM bot_user_memories WHERE id = $1",
                    memory_uuid,
                )
            if result == "DELETE 1":
                return "✅ 已刪除個人記憶"

        return "❌ 找不到指定的記憶"
