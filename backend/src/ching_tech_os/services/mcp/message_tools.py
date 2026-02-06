"""訊息相關 MCP 工具

包含：summarize_chat, get_message_attachments
"""

from datetime import datetime, timedelta
from uuid import UUID

from .server import mcp, logger, ensure_db_connection, to_taipei_time
from ...database import get_connection


@mcp.tool()
async def summarize_chat(
    line_group_id: str,
    hours: int = 24,
    max_messages: int = 50,
) -> str:
    """
    取得 Line 群組聊天記錄，供 AI 摘要使用

    Args:
        line_group_id: Line 群組的內部 UUID
        hours: 取得最近幾小時的訊息，預設 24
        max_messages: 最大訊息數量，預設 50
    """
    await ensure_db_connection()

    async with get_connection() as conn:
        # 計算時間範圍
        since = datetime.now() - timedelta(hours=hours)

        # 取得訊息
        rows = await conn.fetch(
            """
            SELECT m.content, m.created_at, m.message_type,
                   u.display_name as user_name
            FROM bot_messages m
            LEFT JOIN bot_users u ON m.bot_user_id = u.id
            WHERE m.bot_group_id = $1
              AND m.created_at >= $2
              AND m.message_type = 'text'
              AND m.content IS NOT NULL
            ORDER BY m.created_at ASC
            LIMIT $3
            """,
            UUID(line_group_id),
            since,
            max_messages,
        )

        if not rows:
            return f"過去 {hours} 小時內沒有文字訊息"

        # 取得群組名稱
        group = await conn.fetchrow(
            "SELECT name FROM bot_groups WHERE id = $1",
            UUID(line_group_id),
        )
        group_name = group["name"] if group else "未知群組"

        # 格式化訊息
        messages = [f"【{group_name}】過去 {hours} 小時的聊天記錄（共 {len(rows)} 則）：\n"]
        for row in rows:
            created_at_taipei = to_taipei_time(row["created_at"])
            time_str = created_at_taipei.strftime("%H:%M")
            user = row["user_name"] or "未知用戶"
            messages.append(f"[{time_str}] {user}: {row['content']}")

        return "\n".join(messages)


@mcp.tool()
async def get_message_attachments(
    line_user_id: str | None = None,
    line_group_id: str | None = None,
    days: int = 7,
    file_type: str | None = None,
    limit: int = 20,
) -> str:
    """
    查詢對話中的附件（圖片、檔案等），用於將附件加入知識庫

    Args:
        line_user_id: Line 用戶 ID（個人聊天時使用）
        line_group_id: Line 群組的內部 UUID
        days: 查詢最近幾天的附件，預設 7 天，可根據用戶描述調整
        file_type: 檔案類型過濾（image, file, video, audio），不填則查詢全部
        limit: 最大回傳數量，預設 20
    """
    await ensure_db_connection()

    if not line_user_id and not line_group_id:
        return "請提供 line_user_id 或 line_group_id"

    async with get_connection() as conn:
        # 計算時間範圍
        since = datetime.now() - timedelta(days=days)

        # 建立查詢條件
        conditions = ["m.created_at >= $1"]
        params: list = [since]
        param_idx = 2

        if line_group_id:
            conditions.append(f"m.bot_group_id = ${param_idx}")
            params.append(UUID(line_group_id))
            param_idx += 1
        elif line_user_id:
            # 個人聊天：查詢該用戶的訊息且不在群組中
            conditions.append(f"u.platform_user_id = ${param_idx}")
            params.append(line_user_id)
            param_idx += 1
            conditions.append("m.bot_group_id IS NULL")

        if file_type:
            conditions.append(f"f.file_type = ${param_idx}")
            params.append(file_type)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        # 查詢附件
        rows = await conn.fetch(
            f"""
            SELECT f.id, f.file_type, f.file_name, f.file_size, f.nas_path,
                   f.created_at, u.display_name as user_name
            FROM bot_files f
            JOIN bot_messages m ON f.message_id = m.id
            LEFT JOIN bot_users u ON m.bot_user_id = u.id
            WHERE {where_clause}
              AND f.nas_path IS NOT NULL
            ORDER BY f.created_at DESC
            LIMIT {limit}
            """,
            *params,
        )

        if not rows:
            type_hint = f"（類型：{file_type}）" if file_type else ""
            return f"最近 {days} 天內沒有找到附件{type_hint}"

        # 格式化結果
        type_names = {
            "image": "圖片",
            "file": "檔案",
            "video": "影片",
            "audio": "音訊",
        }

        output = [f"找到 {len(rows)} 個附件（最近 {days} 天）：\n"]
        for i, row in enumerate(rows, 1):
            type_name = type_names.get(row["file_type"], row["file_type"])
            created_at_taipei = to_taipei_time(row["created_at"])
            time_str = created_at_taipei.strftime("%Y-%m-%d %H:%M")
            user = row["user_name"] or "未知用戶"

            # 將相對路徑轉換為完整 URI 格式
            nas_path = row["nas_path"]
            if nas_path and not nas_path.startswith(("/", "ctos://", "shared://", "temp://")):
                # 相對路徑：加上 ctos://linebot/files/ 前綴
                nas_path = f"ctos://linebot/files/{nas_path}"

            output.append(f"{i}. [{type_name}] {time_str} - {user}")
            output.append(f"   NAS 路徑：{nas_path}")

            if row["file_name"]:
                output.append(f"   檔名：{row['file_name']}")
            if row["file_size"]:
                size_kb = row["file_size"] / 1024
                if size_kb >= 1024:
                    output.append(f"   大小：{size_kb / 1024:.1f} MB")
                else:
                    output.append(f"   大小：{size_kb:.1f} KB")
            output.append("")

        output.append("提示：使用 NAS 路徑作為 add_note_with_attachments 的 attachments 參數")

        return "\n".join(output)
