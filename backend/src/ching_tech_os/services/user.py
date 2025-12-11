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


def _parse_preferences(value) -> dict:
    """解析偏好設定值

    Args:
        value: 可能是 dict、str 或 None

    Returns:
        偏好設定 dict
    """
    import json

    if value is None:
        return {"theme": "dark"}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {"theme": "dark"}
    return {"theme": "dark"}


async def get_user_preferences(user_id: int) -> dict:
    """取得使用者偏好設定

    Args:
        user_id: 使用者 ID

    Returns:
        使用者偏好設定（JSONB），若無則回傳預設值
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT preferences FROM users WHERE id = $1",
            user_id,
        )
        if row and row["preferences"]:
            return _parse_preferences(row["preferences"])
        return {"theme": "dark"}


async def update_user_preferences(user_id: int, preferences: dict) -> dict:
    """更新使用者偏好設定

    Args:
        user_id: 使用者 ID
        preferences: 要更新的偏好設定（會與現有設定合併）

    Returns:
        更新後的完整偏好設定
    """
    import json

    async with get_connection() as conn:
        # 使用 jsonb_concat (||) 合併現有與新的偏好設定
        row = await conn.fetchrow(
            """
            UPDATE users
            SET preferences = COALESCE(preferences, '{}'::jsonb) || $2::jsonb
            WHERE id = $1
            RETURNING preferences
            """,
            user_id,
            json.dumps(preferences),
        )
        if row and row["preferences"]:
            return _parse_preferences(row["preferences"])
        return {"theme": "dark"}
