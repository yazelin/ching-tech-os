"""訊息中心服務"""

import json
import math
from datetime import datetime, date
from typing import Any

from ..database import get_connection
from ..models.message import (
    MessageCreate,
    MessageFilter,
    MessageListItem,
    MessageListResponse,
    MessageResponse,
    MessageSeverity,
    MessageSource,
)


async def log_message(
    severity: MessageSeverity | str,
    source: MessageSource | str,
    title: str,
    content: str | None = None,
    metadata: dict[str, Any] | None = None,
    user_id: int | None = None,
    category: str | None = None,
    session_id: str | None = None,
) -> int:
    """記錄訊息

    Args:
        severity: 嚴重程度
        source: 來源分類
        title: 訊息標題
        content: 訊息內容
        metadata: 結構化附加資料
        user_id: 關聯使用者 ID
        category: 細分類
        session_id: 關聯 session ID

    Returns:
        新建訊息的 ID
    """
    # 轉換 enum 為字串
    if isinstance(severity, MessageSeverity):
        severity = severity.value
    if isinstance(source, MessageSource):
        source = source.value

    async with get_connection() as conn:
        result = await conn.fetchrow(
            """
            INSERT INTO messages (
                severity, source, title, content, metadata,
                user_id, category, session_id, partition_date
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, CURRENT_DATE)
            RETURNING id
            """,
            severity,
            source,
            title,
            content,
            json.dumps(metadata) if metadata else None,
            user_id,
            category,
            session_id,
        )
        return result["id"]


async def get_message(message_id: int) -> MessageResponse | None:
    """取得單一訊息詳情

    Args:
        message_id: 訊息 ID

    Returns:
        訊息資料或 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, created_at, severity, source, category,
                   title, content, metadata, user_id, session_id, is_read
            FROM messages
            WHERE id = $1
            """,
            message_id,
        )
        if row:
            return MessageResponse(
                id=row["id"],
                created_at=row["created_at"],
                severity=MessageSeverity(row["severity"]),
                source=MessageSource(row["source"]),
                category=row["category"],
                title=row["title"],
                content=row["content"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                user_id=row["user_id"],
                session_id=row["session_id"],
                is_read=row["is_read"],
            )
        return None


async def search_messages(filter: MessageFilter) -> MessageListResponse:
    """搜尋訊息

    Args:
        filter: 查詢條件

    Returns:
        訊息列表（含分頁資訊）
    """
    conditions = []
    params = []
    param_idx = 1

    # 嚴重程度過濾
    if filter.severity:
        placeholders = ", ".join(f"${param_idx + i}" for i in range(len(filter.severity)))
        conditions.append(f"severity IN ({placeholders})")
        params.extend(s.value for s in filter.severity)
        param_idx += len(filter.severity)

    # 來源過濾
    if filter.source:
        placeholders = ", ".join(f"${param_idx + i}" for i in range(len(filter.source)))
        conditions.append(f"source IN ({placeholders})")
        params.extend(s.value for s in filter.source)
        param_idx += len(filter.source)

    # 分類過濾
    if filter.category:
        conditions.append(f"category = ${param_idx}")
        params.append(filter.category)
        param_idx += 1

    # 使用者過濾
    if filter.user_id:
        conditions.append(f"user_id = ${param_idx}")
        params.append(filter.user_id)
        param_idx += 1

    # 日期範圍過濾
    if filter.start_date:
        conditions.append(f"created_at >= ${param_idx}")
        params.append(filter.start_date)
        param_idx += 1

    if filter.end_date:
        conditions.append(f"created_at <= ${param_idx}")
        params.append(filter.end_date)
        param_idx += 1

    # 關鍵字搜尋
    if filter.search:
        conditions.append(f"(title ILIKE ${param_idx} OR content ILIKE ${param_idx})")
        params.append(f"%{filter.search}%")
        param_idx += 1

    # 已讀狀態過濾
    if filter.is_read is not None:
        conditions.append(f"is_read = ${param_idx}")
        params.append(filter.is_read)
        param_idx += 1

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    async with get_connection() as conn:
        # 計算總數
        count_row = await conn.fetchrow(
            f"SELECT COUNT(*) as total FROM messages WHERE {where_clause}",
            *params,
        )
        total = count_row["total"]

        # 計算分頁
        offset = (filter.page - 1) * filter.limit
        total_pages = math.ceil(total / filter.limit) if total > 0 else 1

        # 查詢資料
        rows = await conn.fetch(
            f"""
            SELECT id, created_at, severity, source, category, title, is_read
            FROM messages
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """,
            *params,
            filter.limit,
            offset,
        )

        items = [
            MessageListItem(
                id=row["id"],
                created_at=row["created_at"],
                severity=MessageSeverity(row["severity"]),
                source=MessageSource(row["source"]),
                category=row["category"],
                title=row["title"],
                is_read=row["is_read"],
            )
            for row in rows
        ]

        return MessageListResponse(
            items=items,
            total=total,
            page=filter.page,
            limit=filter.limit,
            total_pages=total_pages,
        )


async def get_unread_count(user_id: int | None = None) -> int:
    """取得未讀訊息數量

    Args:
        user_id: 使用者 ID（可選，若不指定則計算全部）

    Returns:
        未讀數量
    """
    async with get_connection() as conn:
        if user_id:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) as count
                FROM messages
                WHERE is_read = FALSE AND (user_id = $1 OR user_id IS NULL)
                """,
                user_id,
            )
        else:
            row = await conn.fetchrow(
                "SELECT COUNT(*) as count FROM messages WHERE is_read = FALSE"
            )
        return row["count"]


async def mark_as_read(
    ids: list[int] | None = None,
    mark_all: bool = False,
    user_id: int | None = None,
) -> int:
    """標記訊息為已讀

    Args:
        ids: 訊息 ID 列表
        mark_all: 是否標記全部
        user_id: 使用者 ID（用於 mark_all）

    Returns:
        標記的訊息數量
    """
    async with get_connection() as conn:
        if mark_all:
            if user_id:
                result = await conn.execute(
                    """
                    UPDATE messages SET is_read = TRUE
                    WHERE is_read = FALSE AND (user_id = $1 OR user_id IS NULL)
                    """,
                    user_id,
                )
            else:
                result = await conn.execute(
                    "UPDATE messages SET is_read = TRUE WHERE is_read = FALSE"
                )
        elif ids:
            placeholders = ", ".join(f"${i+1}" for i in range(len(ids)))
            result = await conn.execute(
                f"UPDATE messages SET is_read = TRUE WHERE id IN ({placeholders})",
                *ids,
            )
        else:
            return 0

        # 解析 UPDATE 結果取得影響列數
        # asyncpg 返回格式: "UPDATE {count}"
        count = int(result.split()[-1])
        return count


async def get_messages_grouped_by_date(
    user_id: int | None = None,
    limit: int = 50,
) -> dict[str, list[MessageListItem]]:
    """取得訊息並依日期分組（今天、昨天、更早）

    Args:
        user_id: 使用者 ID
        limit: 最大筆數

    Returns:
        依日期分組的訊息字典
    """
    async with get_connection() as conn:
        if user_id:
            rows = await conn.fetch(
                """
                SELECT id, created_at, severity, source, category, title, is_read
                FROM messages
                WHERE user_id = $1 OR user_id IS NULL
                ORDER BY created_at DESC
                LIMIT $2
                """,
                user_id,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, created_at, severity, source, category, title, is_read
                FROM messages
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )

    today = date.today()
    yesterday = date.today().replace(day=today.day - 1) if today.day > 1 else today

    groups = {"today": [], "yesterday": [], "earlier": []}

    for row in rows:
        item = MessageListItem(
            id=row["id"],
            created_at=row["created_at"],
            severity=MessageSeverity(row["severity"]),
            source=MessageSource(row["source"]),
            category=row["category"],
            title=row["title"],
            is_read=row["is_read"],
        )
        msg_date = row["created_at"].date()
        if msg_date == today:
            groups["today"].append(item)
        elif msg_date == yesterday:
            groups["yesterday"].append(item)
        else:
            groups["earlier"].append(item)

    return groups
