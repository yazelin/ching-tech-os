"""Session 管理器測試

測試 Phase 4 + 4-issue fix 的功能：
- _SessionCache TTL 快取
- SessionManager（PostgreSQL 持久化）CRUD
- get_session 快取命中 / cache miss 行為
- delete_session 同時清除快取
- create_session 使用 DB-side 時間
"""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ching_tech_os.services.session import _SessionCache, SessionManager
from ching_tech_os.models.auth import SessionData

_NOW = datetime.now()
_LATER = _NOW + timedelta(hours=24)


def _make_session_data(**overrides) -> SessionData:
    """建立測試用 SessionData（含必填欄位預設值）"""
    defaults = dict(
        username="test",
        password="",
        nas_host="10.0.0.1",
        user_id=1,
        created_at=_NOW,
        expires_at=_LATER,
        role="user",
        app_permissions={},
    )
    defaults.update(overrides)
    return SessionData(**defaults)


# ============================================================
# _SessionCache 測試
# ============================================================

class TestSessionCache:
    """TTL cache 基本功能測試"""

    def test_set_and_get(self):
        """設定後應能取得"""
        cache = _SessionCache(ttl=10)
        data = _make_session_data(username="alice")
        cache.set("token-1", data)
        result = cache.get("token-1")
        assert result is not None
        assert result.username == "alice"

    def test_get_nonexistent(self):
        """不存在的 token 應回傳 None"""
        cache = _SessionCache(ttl=10)
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        """超過 TTL 後應回傳 None"""
        cache = _SessionCache(ttl=0)  # 立即過期
        data = _make_session_data(username="bob", user_id=2)
        cache.set("token-2", data)
        # TTL=0 → monotonic() 已超過 expire_at
        time.sleep(0.01)
        assert cache.get("token-2") is None

    def test_delete(self):
        """刪除後應取不到"""
        cache = _SessionCache(ttl=60)
        data = _make_session_data(username="charlie", user_id=3)
        cache.set("token-3", data)
        cache.delete("token-3")
        assert cache.get("token-3") is None

    def test_delete_nonexistent(self):
        """刪除不存在的 token 不應報錯"""
        cache = _SessionCache(ttl=60)
        cache.delete("nonexistent")  # 不應拋出例外

    def test_clear(self):
        """清空所有快取"""
        cache = _SessionCache(ttl=60)
        data = _make_session_data(username="dave", user_id=4)
        cache.set("t1", data)
        cache.set("t2", data)
        cache.clear()
        assert cache.get("t1") is None
        assert cache.get("t2") is None


# ============================================================
# SessionManager 測試（mock DB）
# ============================================================

def _make_mock_connection():
    """建立 mock DB connection + context manager"""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="DELETE 1")
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=0)

    class _CM:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, *args):
            pass

    return conn, _CM()


@pytest.fixture
def session_manager():
    """建立乾淨的 SessionManager"""
    return SessionManager()


class TestSessionManagerCreate:
    """create_session 測試"""

    @pytest.mark.asyncio
    async def test_create_returns_token(self, session_manager):
        """應回傳 UUID token"""
        conn, cm = _make_mock_connection()
        with patch("ching_tech_os.services.session.get_connection", return_value=cm):
            with patch("ching_tech_os.services.session.encrypt_credential", return_value="enc-pw"):
                token = await session_manager.create_session(
                    username="alice",
                    password="secret",
                    user_id=1,
                )
        assert isinstance(token, str)
        assert len(token) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_create_uses_db_side_time(self, session_manager):
        """INSERT SQL 應使用 NOW() + INTERVAL（非 Python datetime）"""
        conn, cm = _make_mock_connection()
        with patch("ching_tech_os.services.session.get_connection", return_value=cm):
            with patch("ching_tech_os.services.session.encrypt_credential", return_value="enc"):
                await session_manager.create_session(
                    username="alice",
                    password="pw",
                    user_id=1,
                )
        # 檢查 SQL 中包含 NOW() + ... INTERVAL
        sql = conn.execute.call_args[0][0]
        assert "NOW()" in sql
        assert "INTERVAL" in sql

    @pytest.mark.asyncio
    async def test_create_passes_ttl_as_float(self, session_manager):
        """expires_at 參數應為 float（小時數）"""
        conn, cm = _make_mock_connection()
        with patch("ching_tech_os.services.session.get_connection", return_value=cm):
            with patch("ching_tech_os.services.session.encrypt_credential", return_value="enc"):
                await session_manager.create_session(
                    username="alice",
                    password="pw",
                    user_id=1,
                )
        # 第 8 個參數（$8）應為 float
        args = conn.execute.call_args[0]
        ttl_arg = args[8]  # 0=sql, 1=token, 2=user_id, ..., 8=ttl
        assert isinstance(ttl_arg, float)


class TestSessionManagerGet:
    """get_session 測試"""

    @pytest.mark.asyncio
    async def test_cache_hit(self, session_manager):
        """快取命中時不應查 DB"""
        data = _make_session_data(username="alice")
        session_manager._cache.set("cached-token", data)

        with patch("ching_tech_os.services.session.get_connection") as mock_gc:
            result = await session_manager.get_session("cached-token")

        assert result is not None
        assert result.username == "alice"
        mock_gc.assert_not_called()  # 不應查 DB

    @pytest.mark.asyncio
    async def test_cache_miss_queries_db(self, session_manager):
        """快取未命中時應查 DB 並更新 last_accessed_at"""
        now = datetime.now()
        row = {
            "username": "bob",
            "password_enc": "enc-data",
            "nas_host": "10.0.0.2",
            "user_id": 2,
            "created_at": now,
            "expires_at": now,
            "role": "admin",
            "app_permissions": {"file-manager": True},
        }
        conn, cm = _make_mock_connection()
        conn.fetchrow = AsyncMock(return_value=row)

        with patch("ching_tech_os.services.session.get_connection", return_value=cm):
            with patch("ching_tech_os.services.session.decrypt_credential", return_value="decrypted-pw"):
                result = await session_manager.get_session("db-token")

        assert result is not None
        assert result.username == "bob"
        assert result.role == "admin"
        assert result.password == "decrypted-pw"

        # SQL 應為 UPDATE ... SET last_accessed_at = NOW() ... RETURNING
        sql = conn.fetchrow.call_args[0][0]
        assert "UPDATE" in sql
        assert "last_accessed_at" in sql
        assert "RETURNING" in sql

    @pytest.mark.asyncio
    async def test_cache_miss_populates_cache(self, session_manager):
        """DB 查詢後應寫入快取"""
        now = datetime.now()
        row = {
            "username": "charlie",
            "password_enc": "",
            "nas_host": "10.0.0.3",
            "user_id": 3,
            "created_at": now,
            "expires_at": now,
            "role": "user",
            "app_permissions": {},
        }
        conn, cm = _make_mock_connection()
        conn.fetchrow = AsyncMock(return_value=row)

        with patch("ching_tech_os.services.session.get_connection", return_value=cm):
            await session_manager.get_session("new-token")

        # 第二次取應命中快取
        cached = session_manager._cache.get("new-token")
        assert cached is not None
        assert cached.username == "charlie"

    @pytest.mark.asyncio
    async def test_expired_returns_none(self, session_manager):
        """過期或不存在的 token 應回傳 None"""
        conn, cm = _make_mock_connection()
        conn.fetchrow = AsyncMock(return_value=None)

        with patch("ching_tech_os.services.session.get_connection", return_value=cm):
            result = await session_manager.get_session("expired-token")

        assert result is None


class TestSessionManagerDelete:
    """delete_session 測試"""

    @pytest.mark.asyncio
    async def test_delete_clears_cache(self, session_manager):
        """刪除 session 應同時清除快取"""
        data = _make_session_data(username="alice")
        session_manager._cache.set("del-token", data)

        conn, cm = _make_mock_connection()
        with patch("ching_tech_os.services.session.get_connection", return_value=cm):
            result = await session_manager.delete_session("del-token")

        assert result is True
        assert session_manager._cache.get("del-token") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, session_manager):
        """刪除不存在的 session 應回傳 False"""
        conn, cm = _make_mock_connection()
        conn.execute = AsyncMock(return_value="DELETE 0")
        with patch("ching_tech_os.services.session.get_connection", return_value=cm):
            result = await session_manager.delete_session("nonexistent")
        assert result is False


# ============================================================
# nas_connect 非阻塞測試
# ============================================================

class TestNasConnectNonBlocking:
    """nas_connect 應使用 run_in_smb_pool（不阻塞 event loop）"""

    @pytest.mark.asyncio
    async def test_nas_connect_uses_worker_pool(self):
        """nas_connect 應透過 run_in_smb_pool 呼叫 create_connection"""
        from unittest.mock import patch, AsyncMock, MagicMock

        mock_session = _make_session_data(
            username="admin", password="pw", role="admin",
            app_permissions={"file-manager": True},
        )

        with patch("ching_tech_os.api.nas.run_in_smb_pool", new_callable=AsyncMock, return_value="fake-token") as mock_pool:
            with patch("ching_tech_os.api.nas.require_app_permission", return_value=lambda: mock_session):
                from ching_tech_os.api.nas import nas_connection_manager
                # 直接呼叫 endpoint 函式
                from ching_tech_os.api.nas import nas_connect, NASConnectRequest
                request = NASConnectRequest(host="10.0.0.1", username="user", password="pw")
                result = await nas_connect(request, session=mock_session)

        assert result.success is True
        assert result.token == "fake-token"
        # 關鍵：確認使用了 run_in_smb_pool
        mock_pool.assert_called_once()
        # 第一個參數應為 create_connection 方法
        call_args = mock_pool.call_args
        assert call_args.kwargs["host"] == "10.0.0.1"
        assert call_args.kwargs["username"] == "user"
