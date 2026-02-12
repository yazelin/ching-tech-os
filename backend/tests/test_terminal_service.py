"""終端機服務測試。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.services import terminal


class _DummyTask:
    def __init__(self, done: bool = False) -> None:
        self._done = done
        self.cancelled = False

    def done(self) -> bool:
        return self._done

    def cancel(self) -> None:
        self.cancelled = True


class _DummyPty:
    def __init__(self) -> None:
        self.pid = 1234
        self._alive = True
        self.writes: list[bytes] = []
        self.sizes: list[tuple[int, int]] = []
        self._reads = [b"hello", EOFError()]

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def setwinsize(self, rows: int, cols: int) -> None:
        self.sizes.append((rows, cols))

    def isalive(self) -> bool:
        return self._alive

    def terminate(self, force: bool = False) -> None:
        self._alive = False

    def read(self, _size: int) -> bytes:
        value = self._reads.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


@pytest.mark.asyncio
async def test_terminal_session_basic_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    pty = _DummyPty()
    session = terminal.TerminalSession(session_id="s1", pty=pty)
    old_activity = session.last_activity

    session.write("ls\n")
    assert pty.writes[-1] == b"ls\n"
    assert session.last_activity >= old_activity

    session.resize(24, 80)
    assert pty.sizes[-1] == (24, 80)

    monkeypatch.setattr(terminal.os, "readlink", lambda _: "/tmp/demo")
    assert session.get_cwd() == "/tmp/demo"

    monkeypatch.setattr(terminal.os, "readlink", lambda _: (_ for _ in ()).throw(FileNotFoundError()))
    assert session.get_cwd() is None


@pytest.mark.asyncio
async def test_terminal_session_read_loop_and_close(monkeypatch: pytest.MonkeyPatch) -> None:
    pty = _DummyPty()
    session = terminal.TerminalSession(session_id="s2", pty=pty)
    received: list[tuple[str, bytes]] = []

    async def _cb(session_id: str, data: bytes) -> None:
        received.append((session_id, data))

    class _Loop:
        async def run_in_executor(self, _executor, fn):
            return fn()

    monkeypatch.setattr(terminal.asyncio, "get_event_loop", lambda: _Loop())
    await session._read_loop()  # 讀到 EOFError 會結束
    assert received == []

    # 設定 callback 後再跑一次（重新建立讀取資料）
    pty._reads = [b"world", EOFError()]
    pty._alive = True
    session._output_callback = _cb
    await session._read_loop()
    assert received == [("s2", b"world")]

    session._read_task = _DummyTask(done=False)  # type: ignore[assignment]
    session.close()
    assert session._read_task.cancelled is True
    assert pty.isalive() is False


@pytest.mark.asyncio
async def test_terminal_service_session_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    service = terminal.TerminalService()
    service.set_output_callback(lambda *_: None)

    pty = _DummyPty()
    monkeypatch.setattr(terminal.uuid, "uuid4", lambda: "fixed-session-id")
    monkeypatch.setattr(
        terminal.ptyprocess.PtyProcess,
        "spawn",
        lambda *_args, **_kwargs: pty,
    )
    start_reading_mock = AsyncMock()
    monkeypatch.setattr(terminal.TerminalSession, "start_reading", start_reading_mock)

    session = await service.create_session(websocket_sid="ws1", user_id=99, cols=100, rows=30)
    assert session.session_id == "fixed-session-id"
    assert service.get_session("fixed-session-id") is session
    start_reading_mock.assert_awaited_once()

    assert service.get_session_by_websocket("ws1") == [session]
    detached = service.detach_websocket("ws1")
    assert detached == ["fixed-session-id"]
    assert session.websocket_sid is None

    assert service.reattach_websocket("fixed-session-id", "ws2") is True
    assert service.reattach_websocket("fixed-session-id", "ws3") is False

    assert service.get_detached_sessions() == []
    service.detach_websocket("ws2")
    assert service.get_detached_sessions(user_id=99) == [session]
    assert service.get_detached_sessions(user_id=100) == []

    assert service.close_session("fixed-session-id") is True
    assert service.close_session("fixed-session-id") is False


@pytest.mark.asyncio
async def test_terminal_service_cleanup_and_background_task(monkeypatch: pytest.MonkeyPatch) -> None:
    service = terminal.TerminalService()
    now = datetime.now()

    old_session = terminal.TerminalSession(session_id="old", pty=_DummyPty(), websocket_sid=None)
    old_session.last_activity = now - terminal.TerminalService.SESSION_TIMEOUT - timedelta(seconds=1)
    new_session = terminal.TerminalSession(session_id="new", pty=_DummyPty(), websocket_sid=None)
    new_session.last_activity = now
    attached_session = terminal.TerminalSession(session_id="attached", pty=_DummyPty(), websocket_sid="ws")
    attached_session.last_activity = now - timedelta(days=1)

    service._sessions = {  # noqa: SLF001
        "old": old_session,
        "new": new_session,
        "attached": attached_session,
    }

    await service._cleanup_expired_sessions()
    assert "old" not in service._sessions  # noqa: SLF001
    assert "new" in service._sessions  # noqa: SLF001
    assert "attached" in service._sessions  # noqa: SLF001

    # 測試 start/stop cleanup task
    async def _never_loop() -> None:
        await asyncio.sleep(10)

    monkeypatch.setattr(service, "_cleanup_loop", _never_loop)
    await service.start_cleanup_task()
    assert service._cleanup_task is not None  # noqa: SLF001
    await service.stop_cleanup_task()

    # 測試 close_all
    service._sessions = {  # noqa: SLF001
        "a": terminal.TerminalSession(session_id="a", pty=_DummyPty()),
        "b": terminal.TerminalSession(session_id="b", pty=_DummyPty()),
    }
    service.close_all()
    assert service._sessions == {}  # noqa: SLF001


@pytest.mark.asyncio
async def test_terminal_session_start_reading_and_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    session = terminal.TerminalSession(session_id="s3", pty=_DummyPty())
    loop_task = _DummyTask(done=False)

    def _fake_create_task(coro):
        coro.close()
        return loop_task

    monkeypatch.setattr(terminal.asyncio, "create_task", _fake_create_task)
    await session.start_reading(AsyncMock())
    assert session._read_task is loop_task  # noqa: SLF001

    async def _cancelled_executor(self, _executor, _fn):
        raise asyncio.CancelledError()

    class _Loop:
        run_in_executor = _cancelled_executor

    session._output_callback = AsyncMock()
    monkeypatch.setattr(terminal.asyncio, "get_event_loop", lambda: _Loop())
    await session._read_loop()  # 不應拋出
