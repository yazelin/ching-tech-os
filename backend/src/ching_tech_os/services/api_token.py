"""API Token（PAT）服務

提供長效 personal access token 的建立、驗證、列表與撤銷，
供 CLI 與自動化工具以 `Authorization: Bearer ctos_pat_xxx` 存取 API。

安全設計：
- 資料庫僅儲存 token 的 SHA-256 hash，原始 token 只在建立時回傳一次
- 驗證時合成的 SessionData 一律 role="user"（即使擁有者是 admin），
  不帶 SMB 密碼，無法操作 NAS 或 admin 端點
- scopes 限縮可存取的 app，並與使用者當下實際權限取交集
"""

import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..database import get_connection
from ..models.auth import ApiTokenInfo, SessionData

logger = logging.getLogger(__name__)

TOKEN_PREFIX = "ctos_pat_"

# last_used_at 更新節流（秒），避免高頻請求每次都寫 DB
_LAST_USED_UPDATE_INTERVAL = 60


def hash_token(token: str) -> str:
    """計算 token 的 SHA-256 hash（hex）"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token() -> str:
    """產生新的 PAT token 字串"""
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def _parse_scopes(raw) -> list[str]:
    """解析 DB 回傳的 scopes 欄位（JSONB 可能是 list 或 JSON 字串）"""
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return []
    if isinstance(raw, list):
        return [s for s in raw if isinstance(s, str)]
    return []


async def create_api_token(
    user_id: int,
    name: str,
    scopes: list[str] | None = None,
    expires_days: int | None = 180,
    read_only: bool = True,
) -> tuple[str, ApiTokenInfo]:
    """建立 API token

    Args:
        user_id: 使用者 ID
        name: token 名稱（用途說明，如 "yaze-laptop CLI"）
        scopes: 允許存取的 app id 清單，空清單代表使用者全部 app 權限
        expires_days: 有效天數，None 代表永不過期
        read_only: 是否唯讀

    Returns:
        (原始 token 字串, ApiTokenInfo)
    """
    token = generate_token()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=expires_days)
        if expires_days is not None
        else None
    )
    scopes = scopes or []

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO api_tokens (user_id, token_hash, name, scopes, read_only, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, name, scopes, read_only, expires_at, last_used_at, created_at
            """,
            user_id,
            hash_token(token),
            name,
            scopes,  # database.py 已註冊 JSONB codec，直接傳 list
            read_only,
            expires_at,
        )

    info = ApiTokenInfo(
        id=row["id"],
        name=row["name"],
        scopes=_parse_scopes(row["scopes"]),
        read_only=row["read_only"],
        expires_at=row["expires_at"],
        last_used_at=row["last_used_at"],
        created_at=row["created_at"],
    )
    logger.info("建立 API token：user_id=%s name=%s scopes=%s", user_id, name, scopes)
    return token, info


async def list_api_tokens(user_id: int) -> list[ApiTokenInfo]:
    """列出使用者的所有 API token（不含 token 本體）"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, scopes, read_only, expires_at, last_used_at, created_at
            FROM api_tokens
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id,
        )
    return [
        ApiTokenInfo(
            id=row["id"],
            name=row["name"],
            scopes=_parse_scopes(row["scopes"]),
            read_only=row["read_only"],
            expires_at=row["expires_at"],
            last_used_at=row["last_used_at"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


async def revoke_api_token(user_id: int, token_id: int) -> bool:
    """撤銷 API token（僅能撤銷自己的）

    Returns:
        是否成功刪除
    """
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM api_tokens WHERE id = $1 AND user_id = $2",
            token_id,
            user_id,
        )
    return result == "DELETE 1"


async def verify_api_token(token: str) -> SessionData | None:
    """驗證 PAT 並合成 SessionData

    Args:
        token: 完整 token 字串（含 ctos_pat_ 前綴）

    Returns:
        SessionData（auth_type="pat"）或 None（無效/過期/使用者停用）
    """
    if not token.startswith(TOKEN_PREFIX):
        return None

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT t.id, t.user_id, t.scopes, t.read_only, t.expires_at,
                   t.last_used_at, t.created_at,
                   u.username, u.is_active
            FROM api_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.token_hash = $1
            """,
            hash_token(token),
        )

        if row is None:
            return None

        now = datetime.now(timezone.utc)
        if row["expires_at"] is not None and row["expires_at"] < now:
            return None
        if not row["is_active"]:
            return None

        # 節流更新 last_used_at
        last_used = row["last_used_at"]
        if last_used is None or (now - last_used).total_seconds() > _LAST_USED_UPDATE_INTERVAL:
            await conn.execute(
                "UPDATE api_tokens SET last_used_at = NOW() WHERE id = $1",
                row["id"],
            )

    # 取使用者當下實際的 app 權限，再以 scopes 取交集
    from .permissions import get_user_app_permissions

    user_perms = await get_user_app_permissions(row["user_id"])
    scopes = _parse_scopes(row["scopes"])
    if scopes:
        app_permissions = {app: user_perms.get(app, False) for app in scopes}
    else:
        app_permissions = user_perms

    return SessionData(
        username=row["username"],
        password="",  # PAT 不帶 SMB 密碼
        nas_host=settings.nas_host,
        user_id=row["user_id"],
        created_at=row["created_at"],
        expires_at=row["expires_at"] or (now + timedelta(days=365 * 100)),
        role="user",  # PAT 一律降為 user，不可操作 admin 端點
        app_permissions=app_permissions,
        auth_type="pat",
        read_only=row["read_only"],
    )
