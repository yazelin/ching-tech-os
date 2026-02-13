"""terminal API 事件測試。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ching_tech_os.api import terminal as terminal_api


class _FakeSio:
    def __init__(self) -> None:
        self.handlers = {}
        self.emit = AsyncMock()

    def on(self, event: str):
        def _decorator(fn):
            self.handlers[event] = fn
            return fn
        return _decorator


class _FakeSession:
    def __init__(self, session_id: str, websocket_sid: str | None = None) -> None:
        self.session_id = session_id
        self.websocket_sid = websocket_sid
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.written: list[str] = []
        self.resized: list[tuple[int, int]] = []

    def write(self, data: str) -> None:
        self.written.append(data)

    def resize(self, rows: int, cols: int) -> None:
        self.resized.append((rows, cols))

    def get_cwd(self) -> str:
        return "/tmp"


class _FakeTerminalService:
    def __init__(self) -> None:
        self.output_cb = None
        self.sessions: dict[str, _FakeSession] = {}
        self.detached_by_sid: dict[str, list[str]] = {"sid-disconnect": ["s1"]}

    def set_output_callback(self, cb) -> None:
        self.output_cb = cb

    async def create_session(self, websocket_sid: str, user_id=None, cols=80, rows=24):
        s = _FakeSession("s1", websocket_sid=websocket_sid)
        self.sessions[s.session_id] = s
        return s

    def get_session(self, session_id: str):
        return self.sessions.get(session_id)

    def close_session(self, session_id: str) -> bool:
        return self.sessions.pop(session_id, None) is not None

    def get_detached_sessions(self, user_id=None):
        return [s for s in self.sessions.values() if s.websocket_sid is None and (user_id is None or user_id == 1)]

    def reattach_websocket(self, session_id: str, sid: str) -> bool:
        s = self.sessions.get(session_id)
        if s and s.websocket_sid is None:
            s.websocket_sid = sid
            return True
        return False

    def detach_websocket(self, sid: str):
        for s in self.sessions.values():
            if s.websocket_sid == sid:
                s.websocket_sid = None
        return self.detached_by_sid.get(sid, [])


@pytest.mark.asyncio
async def test_terminal_event_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio()
    service = _FakeTerminalService()
    monkeypatch.setattr(terminal_api, "terminal_service", service)

    terminal_api.register_events(sio)
    assert service.output_cb is not None

    # output callback
    service.sessions["s1"] = _FakeSession("s1", websocket_sid="sid1")
    await service.output_cb("s1", b"hello")
    sio.emit.assert_awaited()

    # create
    result = await sio.handlers["terminal:create"]("sid1", {"cols": 100, "rows": 20, "user_id": 1})
    assert result["success"] is True
    assert result["session_id"] == "s1"

    # input: 缺參數 -> ignore
    await sio.handlers["terminal:input"]("sid1", {"session_id": "", "data": ""})

    # input: 正常
    await sio.handlers["terminal:input"]("sid1", {"session_id": "s1", "data": "ls\n"})
    assert service.sessions["s1"].written[-1] == "ls\n"

    # input: 寫入錯誤分支
    bad_session = _FakeSession("s2", websocket_sid="sid1")
    bad_session.write = lambda _d: (_ for _ in ()).throw(RuntimeError("write failed"))  # type: ignore[method-assign]
    service.sessions["s2"] = bad_session
    await sio.handlers["terminal:input"]("sid1", {"session_id": "s2", "data": "x"})

    # resize
    await sio.handlers["terminal:resize"]("sid1", {"session_id": "s1", "cols": 120, "rows": 30})
    assert service.sessions["s1"].resized[-1] == (30, 120)

    # close
    no_id = await sio.handlers["terminal:close"]("sid1", {})
    assert no_id["success"] is False
    ok = await sio.handlers["terminal:close"]("sid1", {"session_id": "s1"})
    assert ok["success"] is True
    bad = await sio.handlers["terminal:close"]("sid1", {"session_id": "missing"})
    assert bad["success"] is False

    # list
    detached = _FakeSession("d1", websocket_sid=None)
    detached.created_at = datetime.now()
    detached.last_activity = datetime.now()
    service.sessions["d1"] = detached
    listed = await sio.handlers["terminal:list"]("sid1", {"user_id": 1})
    assert listed["sessions"][0]["session_id"] == "d1"

    # reconnect
    missing_id = await sio.handlers["terminal:reconnect"]("sid1", {})
    assert missing_id["success"] is False
    reconnect_ok = await sio.handlers["terminal:reconnect"]("sid2", {"session_id": "d1"})
    assert reconnect_ok["success"] is True
    reconnect_bad = await sio.handlers["terminal:reconnect"]("sid2", {"session_id": "none"})
    assert reconnect_bad["success"] is False

    # disconnect
    await sio.handlers["disconnect"]("sid-disconnect")


@pytest.mark.asyncio
async def test_terminal_create_error_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio()
    service = _FakeTerminalService()

    async def _raise_create(*_args, **_kwargs):
        raise RuntimeError("boom")

    service.create_session = _raise_create  # type: ignore[method-assign]
    monkeypatch.setattr(terminal_api, "terminal_service", service)
    terminal_api.register_events(sio)

    result = await sio.handlers["terminal:create"]("sid1", {})
    assert result["success"] is False
