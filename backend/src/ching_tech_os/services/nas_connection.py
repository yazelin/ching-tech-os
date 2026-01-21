"""NAS 連線管理服務

管理使用者的 NAS 連線，包含：
- 連線池（Connection Pool）
- 連線 Token 產生/驗證
- 自動逾時清理
"""

import asyncio
import secrets
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Any

from .smb import SMBService, SMBAuthError, SMBConnectionError, SMBError


@dataclass
class NASConnection:
    """NAS 連線資訊"""
    host: str
    username: str
    password: str
    user_id: int | None
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime
    _smb_service: SMBService | None = None

    def get_smb_service(self) -> SMBService:
        """取得或建立 SMB 服務"""
        if self._smb_service is None:
            self._smb_service = SMBService(
                host=self.host,
                username=self.username,
                password=self.password,
            )
        return self._smb_service

    def extend_expiry(self, minutes: int = 30) -> None:
        """延長過期時間"""
        self.expires_at = datetime.now() + timedelta(minutes=minutes)
        self.last_used_at = datetime.now()


class NASConnectionManager:
    """NAS 連線池管理器

    管理所有 NAS 連線，提供 Token 驗證和自動清理功能。
    """

    def __init__(self, default_timeout_minutes: int = 30):
        self._connections: dict[str, NASConnection] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._default_timeout = default_timeout_minutes

    def create_connection(
        self,
        host: str,
        username: str,
        password: str,
        user_id: int | None = None,
        timeout_minutes: int | None = None,
    ) -> str:
        """建立新的 NAS 連線

        Args:
            host: NAS 主機 IP
            username: NAS 帳號
            password: NAS 密碼
            user_id: 使用者 ID（用於關聯）
            timeout_minutes: 連線逾時（分鐘）

        Returns:
            連線 Token

        Raises:
            SMBAuthError: NAS 認證失敗
            SMBConnectionError: 無法連線 NAS
        """
        # 先測試連線
        smb = SMBService(host=host, username=username, password=password)
        try:
            smb.test_auth()
        except SMBAuthError:
            raise SMBAuthError("NAS 帳號或密碼錯誤")
        except SMBConnectionError:
            raise SMBConnectionError(f"無法連線至 NAS {host}")

        # 產生 Token
        token = secrets.token_urlsafe(32)
        now = datetime.now()
        timeout = timeout_minutes or self._default_timeout

        self._connections[token] = NASConnection(
            host=host,
            username=username,
            password=password,
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(minutes=timeout),
            last_used_at=now,
        )

        return token

    def get_connection(self, token: str) -> NASConnection | None:
        """取得連線

        Args:
            token: 連線 Token

        Returns:
            NASConnection 或 None（若不存在或已過期）
        """
        conn = self._connections.get(token)
        if conn is None:
            return None

        # 檢查是否過期
        if datetime.now() > conn.expires_at:
            self.close_connection(token)
            return None

        # 延長過期時間
        conn.extend_expiry(self._default_timeout)
        return conn

    def get_smb_service(self, token: str) -> SMBService | None:
        """取得 SMB 服務

        Args:
            token: 連線 Token

        Returns:
            SMBService 或 None
        """
        conn = self.get_connection(token)
        if conn is None:
            return None
        return conn.get_smb_service()

    def close_connection(self, token: str) -> bool:
        """關閉連線

        Args:
            token: 連線 Token

        Returns:
            是否成功關閉
        """
        if token in self._connections:
            del self._connections[token]
            return True
        return False

    def close_user_connections(self, user_id: int) -> int:
        """關閉使用者的所有連線

        Args:
            user_id: 使用者 ID

        Returns:
            關閉的連線數量
        """
        tokens_to_remove = [
            token for token, conn in self._connections.items()
            if conn.user_id == user_id
        ]
        for token in tokens_to_remove:
            del self._connections[token]
        return len(tokens_to_remove)

    def cleanup_expired(self) -> int:
        """清理過期的連線

        Returns:
            清理的連線數量
        """
        now = datetime.now()
        expired_tokens = [
            token for token, conn in self._connections.items()
            if now > conn.expires_at
        ]
        for token in expired_tokens:
            del self._connections[token]
        return len(expired_tokens)

    async def start_cleanup_task(self, interval_minutes: int = 5) -> None:
        """啟動背景清理任務"""
        if self._cleanup_task is not None:
            return

        async def cleanup_loop():
            interval = interval_minutes * 60
            while True:
                await asyncio.sleep(interval)
                count = self.cleanup_expired()
                if count > 0:
                    print(f"[NAS] Cleaned up {count} expired connections")

        self._cleanup_task = asyncio.create_task(cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        """停止背景清理任務"""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    @property
    def active_connection_count(self) -> int:
        """目前活躍的連線數量"""
        return len(self._connections)

    def get_user_connections(self, user_id: int) -> list[dict[str, Any]]:
        """取得使用者的所有連線資訊

        Args:
            user_id: 使用者 ID

        Returns:
            連線資訊列表
        """
        return [
            {
                "token": token,
                "host": conn.host,
                "username": conn.username,
                "created_at": conn.created_at.isoformat(),
                "expires_at": conn.expires_at.isoformat(),
                "last_used_at": conn.last_used_at.isoformat(),
            }
            for token, conn in self._connections.items()
            if conn.user_id == user_id
        ]


# 全域 NAS 連線管理器實例
nas_connection_manager = NASConnectionManager()
