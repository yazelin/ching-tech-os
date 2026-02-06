"""Session 管理服務（PostgreSQL 持久化）

將 session 資料儲存於 PostgreSQL，server 重啟後 session 不失效。
SMB 密碼以 AES-256-GCM 加密儲存。
"""

import asyncio
import logging
import time
import uuid as uuid_lib
from typing import Optional

from ..config import settings
from ..database import get_connection
from ..models.auth import SessionData
from ..utils.crypto import encrypt_credential, decrypt_credential

logger = logging.getLogger(__name__)

# Session cache TTL（秒）— 減少高頻 DB 查詢
_CACHE_TTL = 30


class _SessionCache:
    """簡易 TTL cache（不需外部套件）

    儲存 token → (SessionData, expire_time) 的對應。
    """

    def __init__(self, ttl: int = _CACHE_TTL):
        self._store: dict[str, tuple[SessionData, float]] = {}
        self._ttl = ttl

    def get(self, token: str) -> SessionData | None:
        entry = self._store.get(token)
        if entry is None:
            return None
        data, expire_at = entry
        if time.monotonic() > expire_at:
            del self._store[token]
            return None
        return data

    def set(self, token: str, data: SessionData) -> None:
        self._store[token] = (data, time.monotonic() + self._ttl)

    def delete(self, token: str) -> None:
        self._store.pop(token, None)

    def clear(self) -> None:
        self._store.clear()


class SessionManager:
    """Session 管理器（PostgreSQL 持久化）

    將 session 資料儲存於 PostgreSQL sessions 表，
    SMB 密碼以 AES-256-GCM 加密。
    get_session 搭配 TTL cache 減少 DB 查詢次數。
    """

    def __init__(self):
        self._cleanup_task: asyncio.Task | None = None
        self._cache = _SessionCache()

    async def create_session(
        self,
        username: str,
        password: str,
        nas_host: str | None = None,
        user_id: int | None = None,
        role: str = "user",
        app_permissions: dict[str, bool] | None = None,
    ) -> str:
        """建立新 session

        Args:
            username: 使用者帳號
            password: 使用者密碼（供 SMB 操作使用）
            nas_host: NAS 主機位址
            user_id: 資料庫中的使用者 ID
            role: 用戶角色（admin, user）
            app_permissions: App 權限設定

        Returns:
            session token (UUID)
        """
        token = str(uuid_lib.uuid4())

        # 加密密碼
        password_enc = encrypt_credential(password) if password else ""

        async with get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO sessions (token, user_id, username, password_enc, nas_host, role, app_permissions, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW() + $8 * INTERVAL '1 hour')
                """,
                token,
                user_id,
                username,
                password_enc,
                nas_host or settings.nas_host,
                role,
                app_permissions or {},
                float(settings.session_ttl_hours),
            )

        return token

    async def get_session(self, token: str) -> Optional[SessionData]:
        """取得 session 資料

        優先從 TTL cache 取得，cache miss 時查 DB 並更新 last_accessed_at。

        Args:
            token: session token

        Returns:
            SessionData 或 None（若不存在或已過期）
        """
        # 先查 cache
        cached = self._cache.get(token)
        if cached is not None:
            return cached

        # Cache miss → 查 DB 並更新 last_accessed_at
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                UPDATE sessions SET last_accessed_at = NOW()
                WHERE token = $1 AND expires_at > NOW()
                RETURNING username, password_enc, nas_host, user_id,
                          created_at, expires_at, role, app_permissions
                """,
                token,
            )

        if row is None:
            return None

        # 解密密碼
        password = decrypt_credential(row["password_enc"]) if row["password_enc"] else ""

        session = SessionData(
            username=row["username"],
            password=password,
            nas_host=row["nas_host"],
            user_id=row["user_id"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            role=row["role"],
            app_permissions=row["app_permissions"] or {},
        )

        # 寫入 cache
        self._cache.set(token, session)
        return session

    async def delete_session(self, token: str) -> bool:
        """刪除 session

        Args:
            token: session token

        Returns:
            是否成功刪除
        """
        self._cache.delete(token)
        async with get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM sessions WHERE token = $1",
                token,
            )
        return result == "DELETE 1"

    async def cleanup_expired(self) -> int:
        """清理過期的 session

        Returns:
            清理的 session 數量
        """
        async with get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM sessions WHERE expires_at < NOW()"
            )
        # result is like "DELETE 5"
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError):
            return 0

    async def start_cleanup_task(self):
        """啟動背景清理任務"""
        if self._cleanup_task is not None:
            return

        async def cleanup_loop():
            interval = settings.session_cleanup_interval_minutes * 60
            while True:
                await asyncio.sleep(interval)
                try:
                    count = await self.cleanup_expired()
                    if count > 0:
                        logger.info("Cleaned up %d expired sessions", count)
                except Exception as e:
                    logger.error("Session cleanup failed: %s", e)

        self._cleanup_task = asyncio.create_task(cleanup_loop())

    async def stop_cleanup_task(self):
        """停止背景清理任務"""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def get_active_session_count(self) -> int:
        """目前活躍的 session 數量"""
        async with get_connection() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM sessions WHERE expires_at > NOW()"
            )
        return count or 0


# 全域 session manager 實例
session_manager = SessionManager()
