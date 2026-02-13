"""NAS 連線管理服務測試。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from ching_tech_os.services import nas_connection
from ching_tech_os.services.smb import SMBAuthError, SMBConnectionError


class _DummySMB:
    def __init__(self, host: str, username: str, password: str) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.auth_checked = False

    def test_auth(self) -> None:
        self.auth_checked = True


def test_nas_connection_lazy_smb_and_extend() -> None:
    conn = nas_connection.NASConnection(
        host="1.2.3.4",
        username="u",
        password="p",
        user_id=1,
        created_at=datetime.now(),
        expires_at=datetime.now(),
        last_used_at=datetime.now(),
    )
    conn._smb_service = _DummySMB("1.2.3.4", "u", "p")
    smb = conn.get_smb_service()
    assert smb.host == "1.2.3.4"

    old = conn.expires_at
    conn.extend_expiry(minutes=1)
    assert conn.expires_at > old


def test_connection_manager_basic_operations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nas_connection, "SMBService", _DummySMB)
    monkeypatch.setattr(nas_connection.secrets, "token_urlsafe", lambda _n: "tok1")

    mgr = nas_connection.NASConnectionManager(default_timeout_minutes=1)
    token = mgr.create_connection("1.2.3.4", "u", "p", user_id=7)
    assert token == "tok1"
    assert mgr.active_connection_count == 1

    conn = mgr.get_connection("tok1")
    assert conn is not None
    assert mgr.get_smb_service("tok1") is not None
    assert mgr.get_smb_service("missing") is None

    assert len(mgr.get_user_connections(7)) == 1
    assert mgr.close_connection("tok1") is True
    assert mgr.close_connection("tok1") is False


def test_connection_manager_create_connection_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class _AuthFailSMB(_DummySMB):
        def test_auth(self) -> None:
            raise SMBAuthError("bad")

    class _ConnFailSMB(_DummySMB):
        def test_auth(self) -> None:
            raise SMBConnectionError("down")

    mgr = nas_connection.NASConnectionManager()

    monkeypatch.setattr(nas_connection, "SMBService", _AuthFailSMB)
    with pytest.raises(SMBAuthError):
        mgr.create_connection("h", "u", "p")

    monkeypatch.setattr(nas_connection, "SMBService", _ConnFailSMB)
    with pytest.raises(SMBConnectionError):
        mgr.create_connection("h", "u", "p")


def test_cleanup_and_user_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nas_connection, "SMBService", _DummySMB)
    tokens = iter(["tok-a", "tok-b"])
    monkeypatch.setattr(nas_connection.secrets, "token_urlsafe", lambda _n: next(tokens))

    mgr = nas_connection.NASConnectionManager(default_timeout_minutes=1)
    t1 = mgr.create_connection("h1", "u1", "p1", user_id=1)
    t2 = mgr.create_connection("h2", "u2", "p2", user_id=2)
    assert t1 and t2

    # 手動設為過期
    mgr._connections[t1].expires_at = datetime.now() - timedelta(seconds=1)  # noqa: SLF001
    cleaned = mgr.cleanup_expired()
    assert cleaned == 1

    closed = mgr.close_user_connections(2)
    assert closed == 1
    assert mgr.active_connection_count == 0


@pytest.mark.asyncio
async def test_cleanup_background_task(monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = nas_connection.NASConnectionManager()

    class _DummyTask:
        def __init__(self) -> None:
            self.cancelled = False

        def cancel(self) -> None:
            self.cancelled = True

        def __await__(self):
            async def _done():
                raise asyncio.CancelledError()
            return _done().__await__()

    dummy_task = _DummyTask()

    def _fake_create_task(_coro):
        _coro.close()
        return dummy_task

    monkeypatch.setattr(asyncio, "create_task", _fake_create_task)
    await mgr.start_cleanup_task(interval_minutes=1)
    assert mgr._cleanup_task is dummy_task  # noqa: SLF001

    # 再次啟動不應覆蓋
    await mgr.start_cleanup_task(interval_minutes=1)
    assert mgr._cleanup_task is dummy_task  # noqa: SLF001

    await mgr.stop_cleanup_task()
    assert mgr._cleanup_task is None  # noqa: SLF001
