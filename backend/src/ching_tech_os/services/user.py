"""使用者服務"""

from datetime import datetime
from uuid import UUID

from ..config import settings, DEFAULT_TENANT_UUID
from ..database import get_connection


async def upsert_user(username: str, tenant_id: UUID | str | None = None) -> int:
    """建立或更新使用者記錄

    如果使用者不存在，建立新記錄；否則更新最後登入時間。
    使用者唯一性在租戶範圍內驗證（同租戶不能有重複帳號）。

    Args:
        username: 使用者帳號
        tenant_id: 租戶 UUID（可選，預設使用預設租戶）

    Returns:
        使用者 ID
    """
    # 處理 tenant_id
    if tenant_id is None:
        tenant_id = UUID(settings.default_tenant_id)
    elif isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        # 嘗試插入或更新（使用 tenant_id + username 的複合唯一鍵）
        result = await conn.fetchrow(
            """
            INSERT INTO users (username, tenant_id, last_login_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (tenant_id, username) DO UPDATE
            SET last_login_at = $3
            RETURNING id
            """,
            username,
            tenant_id,
            datetime.now(),
        )
        return result["id"]


async def get_user_by_username(
    username: str,
    tenant_id: UUID | str | None = None,
) -> dict | None:
    """根據帳號取得使用者資料

    Args:
        username: 使用者帳號
        tenant_id: 租戶 UUID（可選，預設使用預設租戶）

    Returns:
        使用者資料或 None
    """
    # 處理 tenant_id
    if tenant_id is None:
        tenant_id = UUID(settings.default_tenant_id)
    elif isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, username, display_name, created_at, last_login_at,
                   preferences, tenant_id, role
            FROM users
            WHERE username = $1 AND tenant_id = $2
            """,
            username,
            tenant_id,
        )
        if row:
            return dict(row)
        return None


async def get_all_users(tenant_id: UUID | str | None = None) -> list[dict]:
    """取得所有使用者列表

    Args:
        tenant_id: 租戶 UUID（可選，預設使用預設租戶）

    Returns:
        使用者列表
    """
    # 處理 tenant_id
    if tenant_id is None:
        tenant_id = UUID(settings.default_tenant_id)
    elif isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, username, display_name, created_at, last_login_at,
                   preferences, tenant_id, role
            FROM users
            WHERE tenant_id = $1
            ORDER BY created_at DESC
            """,
            tenant_id,
        )
        return [dict(row) for row in rows]


async def get_user_by_id(user_id: int) -> dict | None:
    """根據 ID 取得使用者資料

    Args:
        user_id: 使用者 ID

    Returns:
        使用者資料或 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, display_name, created_at, last_login_at, preferences FROM users WHERE id = $1",
            user_id,
        )
        if row:
            return dict(row)
        return None


async def update_user_permissions(user_id: int, permissions: dict) -> dict:
    """更新使用者權限

    Args:
        user_id: 使用者 ID
        permissions: 要更新的權限（會與現有權限合併）

    Returns:
        更新後的完整偏好設定
    """
    import json

    async with get_connection() as conn:
        # 先取得現有偏好設定
        row = await conn.fetchrow(
            "SELECT preferences FROM users WHERE id = $1",
            user_id,
        )
        if row is None:
            raise ValueError(f"使用者 {user_id} 不存在")

        current_prefs = _parse_preferences(row["preferences"])
        current_perms = current_prefs.get("permissions", {})

        # 深度合併權限
        if "apps" in permissions:
            if "apps" not in current_perms:
                current_perms["apps"] = {}
            current_perms["apps"].update(permissions["apps"])

        if "knowledge" in permissions:
            if "knowledge" not in current_perms:
                current_perms["knowledge"] = {}
            current_perms["knowledge"].update(permissions["knowledge"])

        current_prefs["permissions"] = current_perms

        # 更新資料庫
        row = await conn.fetchrow(
            """
            UPDATE users
            SET preferences = $2::jsonb
            WHERE id = $1
            RETURNING preferences
            """,
            user_id,
            json.dumps(current_prefs),
        )
        if row and row["preferences"]:
            return _parse_preferences(row["preferences"])
        return current_prefs


async def update_user_display_name(
    username: str,
    display_name: str,
    tenant_id: UUID | str | None = None,
) -> dict | None:
    """更新使用者顯示名稱

    Args:
        username: 使用者帳號
        display_name: 新的顯示名稱
        tenant_id: 租戶 UUID（可選，預設使用預設租戶）

    Returns:
        更新後的使用者資料或 None
    """
    # 處理 tenant_id
    if tenant_id is None:
        tenant_id = UUID(settings.default_tenant_id)
    elif isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE users SET display_name = $2
            WHERE username = $1 AND tenant_id = $3
            RETURNING id, username, display_name, created_at, last_login_at,
                      preferences, tenant_id, role
            """,
            username,
            display_name,
            tenant_id,
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
