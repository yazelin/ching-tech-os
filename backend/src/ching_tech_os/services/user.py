"""使用者服務"""

from datetime import datetime

from ..database import get_connection


async def upsert_user(username: str) -> int:
    """建立或更新使用者記錄

    如果使用者不存在，建立新記錄；否則更新最後登入時間。

    Args:
        username: 使用者帳號

    Returns:
        使用者 ID
    """
    async with get_connection() as conn:
        # 嘗試插入或更新
        result = await conn.fetchrow(
            """
            INSERT INTO users (username, last_login_at)
            VALUES ($1, $2)
            ON CONFLICT (username) DO UPDATE
            SET last_login_at = $2
            RETURNING id
            """,
            username,
            datetime.now(),
        )
        return result["id"]


async def get_user_by_username(username: str) -> dict | None:
    """根據帳號取得使用者資料

    Args:
        username: 使用者帳號

    Returns:
        使用者資料或 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, display_name, created_at, last_login_at FROM users WHERE username = $1",
            username,
        )
        if row:
            return dict(row)
        return None


async def update_user_display_name(username: str, display_name: str) -> dict | None:
    """更新使用者顯示名稱

    Args:
        username: 使用者帳號
        display_name: 新的顯示名稱

    Returns:
        更新後的使用者資料或 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE users SET display_name = $2
            WHERE username = $1
            RETURNING id, username, display_name, created_at, last_login_at
            """,
            username,
            display_name,
        )
        if row:
            return dict(row)
        return None
