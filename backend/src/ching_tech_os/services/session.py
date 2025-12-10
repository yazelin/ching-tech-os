"""Session 管理服務"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional

from ..config import settings
from ..models.auth import SessionData


class SessionManager:
    """Session 管理器

    以記憶體儲存 session 資料，server 重啟後 session 失效。
    """

    def __init__(self):
        self._sessions: dict[str, SessionData] = {}
        self._cleanup_task: asyncio.Task | None = None

    def create_session(
        self, username: str, password: str, nas_host: str | None = None
    ) -> str:
        """建立新 session

        Args:
            username: 使用者帳號
            password: 使用者密碼（供 SMB 操作使用）
            nas_host: NAS 主機位址

        Returns:
            session token (UUID)
        """
        token = str(uuid.uuid4())
        now = datetime.now()
        expires_at = now + timedelta(hours=settings.session_ttl_hours)

        self._sessions[token] = SessionData(
            username=username,
            password=password,
            nas_host=nas_host or settings.nas_host,
            created_at=now,
            expires_at=expires_at,
        )

        return token

    def get_session(self, token: str) -> Optional[SessionData]:
        """取得 session 資料

        Args:
            token: session token

        Returns:
            SessionData 或 None（若不存在或已過期）
        """
        session = self._sessions.get(token)
        if session is None:
            return None

        if datetime.now() > session.expires_at:
            self.delete_session(token)
            return None

        return session

    def delete_session(self, token: str) -> bool:
        """刪除 session

        Args:
            token: session token

        Returns:
            是否成功刪除
        """
        if token in self._sessions:
            del self._sessions[token]
            return True
        return False

    def cleanup_expired(self) -> int:
        """清理過期的 session

        Returns:
            清理的 session 數量
        """
        now = datetime.now()
        expired_tokens = [
            token
            for token, session in self._sessions.items()
            if now > session.expires_at
        ]

        for token in expired_tokens:
            del self._sessions[token]

        return len(expired_tokens)

    async def start_cleanup_task(self):
        """啟動背景清理任務"""
        if self._cleanup_task is not None:
            return

        async def cleanup_loop():
            interval = settings.session_cleanup_interval_minutes * 60
            while True:
                await asyncio.sleep(interval)
                count = self.cleanup_expired()
                if count > 0:
                    print(f"Cleaned up {count} expired sessions")

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

    @property
    def active_session_count(self) -> int:
        """目前活躍的 session 數量"""
        return len(self._sessions)


# 全域 session manager 實例
session_manager = SessionManager()
