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
        # 嘗試插入或更新（使用 username 唯一鍵）
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
            """
            SELECT id, username, display_name, created_at, last_login_at,
                   preferences, role, password_hash, email,
                   password_changed_at, must_change_password, is_active
            FROM users
            WHERE username = $1
            """,
            username,
        )
        if row:
            return dict(row)
        return None


async def get_user_for_auth(username: str) -> dict | None:
    """取得用於認證的使用者資料（包含密碼雜湊）

    Args:
        username: 使用者帳號

    Returns:
        使用者資料或 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, username, display_name, role,
                   password_hash, must_change_password, is_active
            FROM users
            WHERE username = $1
            """,
            username,
        )
        if row:
            return dict(row)
        return None


async def set_user_password(
    user_id: int,
    password_hash: str,
    must_change: bool = False,
) -> bool:
    """設定使用者密碼

    Args:
        user_id: 使用者 ID
        password_hash: bcrypt 密碼雜湊
        must_change: 是否需要下次登入時變更密碼

    Returns:
        是否成功
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE users
            SET password_hash = $2,
                password_changed_at = NOW(),
                must_change_password = $3
            WHERE id = $1
            """,
            user_id,
            password_hash,
            must_change,
        )
        return "UPDATE 1" in result


async def update_last_login(user_id: int) -> None:
    """更新最後登入時間

    Args:
        user_id: 使用者 ID
    """
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET last_login_at = NOW() WHERE id = $1",
            user_id,
        )


async def clear_must_change_password(user_id: int) -> None:
    """清除強制變更密碼標記

    Args:
        user_id: 使用者 ID
    """
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET must_change_password = false WHERE id = $1",
            user_id,
        )


async def create_user(
    username: str,
    password_hash: str | None = None,
    display_name: str | None = None,
    email: str | None = None,
    role: str = "user",
    must_change_password: bool = False,
) -> int:
    """建立新使用者

    Args:
        username: 使用者帳號
        password_hash: bcrypt 密碼雜湊（可選）
        display_name: 顯示名稱
        email: Email（可選）
        role: 角色（user, admin）
        must_change_password: 是否需要下次登入時變更密碼

    Returns:
        新建使用者 ID

    Raises:
        ValueError: 若帳號已存在
    """
    async with get_connection() as conn:
        try:
            # 判斷是否設定 password_changed_at
            password_changed_at = datetime.now() if password_hash else None

            row = await conn.fetchrow(
                """
                INSERT INTO users (
                    username, password_hash, display_name, email,
                    role, must_change_password, password_changed_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                username,
                password_hash,
                display_name,
                email,
                role,
                must_change_password,
                password_changed_at,
            )
            return row["id"]
        except Exception as e:
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                raise ValueError("此帳號已存在")
            raise


async def deactivate_user(user_id: int) -> bool:
    """停用使用者帳號

    Args:
        user_id: 使用者 ID

    Returns:
        是否成功
    """
    async with get_connection() as conn:
        result = await conn.execute(
            "UPDATE users SET is_active = false WHERE id = $1",
            user_id,
        )
        return "UPDATE 1" in result


async def activate_user(user_id: int) -> bool:
    """啟用使用者帳號

    Args:
        user_id: 使用者 ID

    Returns:
        是否成功
    """
    async with get_connection() as conn:
        result = await conn.execute(
            "UPDATE users SET is_active = true WHERE id = $1",
            user_id,
        )
        return "UPDATE 1" in result


async def get_all_users(
    include_inactive: bool = False,
) -> list[dict]:
    """取得所有使用者列表

    Args:
        include_inactive: 是否包含停用的使用者

    Returns:
        使用者列表
    """
    async with get_connection() as conn:
        query = """
            SELECT u.id, u.username, u.display_name, u.created_at, u.last_login_at,
                   u.preferences, u.is_active, u.role
            FROM users u
        """
        if not include_inactive:
            query += " WHERE u.is_active = true"
        query += " ORDER BY u.created_at DESC"

        rows = await conn.fetch(query)
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
            """
            SELECT id, username, display_name, created_at, last_login_at,
                   preferences, role
            FROM users WHERE id = $1
            """,
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
) -> dict | None:
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
            RETURNING id, username, display_name, created_at, last_login_at,
                      preferences, role
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


async def get_user_role_and_permissions(user_id: int) -> dict:
    """取得使用者的角色和權限設定

    角色直接從 users.role 欄位讀取（admin 或 user）

    Args:
        user_id: 使用者 ID

    Returns:
        包含 role、permissions 和 user_data 的 dict
        - role: 使用者角色（admin/user）
        - permissions: 從 preferences 中提取的 permissions 設定
        - user_data: 完整的使用者資料（供 get_user_app_permissions_sync 使用）
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT role, preferences FROM users WHERE id = $1",
            user_id,
        )
        if not row:
            return {"role": "user", "permissions": None, "user_data": None}

        role = row["role"] or "user"
        preferences = _parse_preferences(row["preferences"])
        permissions = preferences.get("permissions")

        # 建立 user_data 供 get_user_app_permissions_sync 使用
        user_data = {"preferences": preferences}

        return {"role": role, "permissions": permissions, "user_data": user_data}


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


# =============================================================
# 使用者管理函數（供管理員使用）
# =============================================================


async def list_users(
    include_inactive: bool = False,
) -> list[dict]:
    """列出所有使用者

    Args:
        include_inactive: 是否包含停用的使用者

    Returns:
        使用者列表
    """
    async with get_connection() as conn:
        if include_inactive:
            rows = await conn.fetch(
                """
                SELECT id, username, display_name, email, role, is_active,
                       must_change_password, created_at, last_login_at, password_changed_at
                FROM users
                ORDER BY created_at DESC
                """,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, username, display_name, email, role, is_active,
                       must_change_password, created_at, last_login_at, password_changed_at
                FROM users
                WHERE is_active = true
                ORDER BY created_at DESC
                """,
            )
        return [dict(row) for row in rows]


async def get_user_detail(user_id: int) -> dict | None:
    """取得使用者詳細資料（用於管理）

    Args:
        user_id: 使用者 ID

    Returns:
        使用者資料或 None
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, username, display_name, email, is_active,
                   must_change_password, created_at, last_login_at,
                   password_changed_at, preferences, role
            FROM users
            WHERE id = $1
            """,
            user_id,
        )
        if row:
            return dict(row)
        return None


async def update_user_info(
    user_id: int,
    display_name: str | None = None,
    email: str | None = None,
    role: str | None = None,
) -> dict | None:
    """更新使用者資訊（供管理員使用）

    Args:
        user_id: 使用者 ID
        display_name: 新的顯示名稱
        email: 新的 Email
        role: 新的角色

    Returns:
        更新後的使用者資料或 None
    """
    # 驗證角色值
    if role is not None and role not in ("user", "admin"):
        raise ValueError("角色必須是 user 或 admin")

    async with get_connection() as conn:
        # 先驗證使用者存在
        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE id = $1",
            user_id,
        )
        if existing is None:
            return None

        # 建構動態更新
        updates = []
        params = [user_id]
        param_index = 2

        if display_name is not None:
            updates.append(f"display_name = ${param_index}")
            params.append(display_name)
            param_index += 1

        if email is not None:
            updates.append(f"email = ${param_index}")
            params.append(email)
            param_index += 1

        if role is not None:
            updates.append(f"role = ${param_index}")
            params.append(role)
            param_index += 1

        if not updates:
            # 沒有要更新的欄位，直接返回現有資料
            return await get_user_detail(user_id)

        query = f"""
            UPDATE users
            SET {", ".join(updates)}
            WHERE id = $1
            RETURNING id, username, display_name, email, role, is_active,
                      must_change_password, created_at, last_login_at, password_changed_at
        """

        row = await conn.fetchrow(query, *params)
        if row:
            return dict(row)
        return None


async def reset_user_password(
    user_id: int,
    new_password_hash: str,
    must_change: bool = True,
) -> bool:
    """重設使用者密碼（供管理員使用）

    Args:
        user_id: 使用者 ID
        new_password_hash: 新密碼的雜湊值
        must_change: 是否要求下次登入時變更密碼

    Returns:
        是否成功
    """
    async with get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE users
            SET password_hash = $2,
                password_changed_at = NOW(),
                must_change_password = $3
            WHERE id = $1
            """,
            user_id,
            new_password_hash,
            must_change,
        )
        return "UPDATE 1" in result


async def delete_user(user_id: int) -> bool:
    """刪除使用者

    注意：這是永久刪除，建議使用 deactivate_user 代替。

    Args:
        user_id: 使用者 ID

    Returns:
        是否成功
    """
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM users WHERE id = $1",
            user_id,
        )
        return "DELETE 1" in result


async def get_user_role(user_id: int | None) -> str:
    """從資料庫取得使用者的角色

    直接從 users.role 欄位讀取（admin 或 user）

    Args:
        user_id: 使用者 ID

    Returns:
        角色字串：admin / user
    """
    if user_id is None:
        return "user"

    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT role FROM users WHERE id = $1",
            user_id,
        )
        if row:
            return row["role"] or "user"

    return "user"
