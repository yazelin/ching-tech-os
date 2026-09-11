"""Socket.IO 連線驗證與事件身分測試（#185）。

- connect：沒帶 token、token 無效 → 拒絕連線；有效 → 把身分存進 sio session。
- ai_chat_event／compress_chat：以連線身分取對話，不是自己的 → 回錯誤且不呼叫 AI。
- terminal:create：用連線身分的 user_id，沒有 terminal 權限就拒絕。
- join_user_room：加入的是連線身分的房間，忽略 payload 的 userId。

事件處理直接呼叫註冊好的 coroutine，sio 用假物件（save_session／get_session／
emit／enter_room／leave_room 都是 AsyncMock）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from socketio.exceptions import ConnectionRefusedError as SioConnectionRefused

import ching_tech_os.api.auth as auth_api
import ching_tech_os.main as main_module
from ching_tech_os.api import ai as ai_api
from ching_tech_os.api import message_events, terminal as terminal_api
from ching_tech_os.models.auth import SessionData
from ching_tech_os.services import socket_auth


# ============================================================
# 共用假物件
# ============================================================


class _FakeSio:
    """假的 Socket.IO server：記下 handler 與 session。"""

    def __init__(self, identity: dict | None = None) -> None:
        self.handlers: dict = {}
        self.identity = identity
        self.save_session = AsyncMock()
        self.emit = AsyncMock()
        self.enter_room = AsyncMock()
        self.leave_room = AsyncMock()

    def event(self, fn):
        self.handlers[fn.__name__] = fn
        return fn

    def on(self, event: str):
        def _decorator(fn):
            self.handlers[event] = fn
            return fn
        return _decorator

    async def get_session(self, sid):
        return self.identity


def _session_data(role: str = "user", app_permissions: dict | None = None) -> SessionData:
    now = datetime.now(timezone.utc)
    return SessionData(
        username="tester",
        password="xxx",
        nas_host="localhost",
        user_id=7,
        created_at=now,
        expires_at=now,
        role=role,
        app_permissions=app_permissions if app_permissions is not None else {"terminal": True},
        auth_type="session",
    )


# ============================================================
# extract_token
# ============================================================


def test_extract_token_prefers_auth_dict() -> None:
    assert socket_auth.extract_token({"token": " abc "}, {"QUERY_STRING": "token=zzz"}) == "abc"


def test_extract_token_falls_back_to_query_string() -> None:
    assert socket_auth.extract_token(None, {"QUERY_STRING": "EIO=4&token=qs-token"}) == "qs-token"


def test_extract_token_missing() -> None:
    assert socket_auth.extract_token(None, {}) is None
    assert socket_auth.extract_token({"token": "   "}, {"QUERY_STRING": ""}) is None


@pytest.mark.asyncio
async def test_get_socket_identity_tolerates_missing_get_session() -> None:
    class _NoSession:
        pass

    assert await socket_auth.get_socket_identity(_NoSession(), "sid") is None
    assert await socket_auth.get_socket_user_id(_NoSession(), "sid") is None


@pytest.mark.asyncio
async def test_get_socket_identity_tolerates_error() -> None:
    class _Boom:
        async def get_session(self, sid):
            raise KeyError(sid)

    assert await socket_auth.get_socket_identity(_Boom(), "sid") is None


# ============================================================
# main.connect
# ============================================================


@pytest.mark.asyncio
async def test_connect_without_token_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sio = _FakeSio()
    monkeypatch.setattr(main_module, "sio", fake_sio)
    resolve = AsyncMock(return_value=_session_data())
    monkeypatch.setattr(auth_api, "_resolve_session", resolve)

    with pytest.raises(SioConnectionRefused):
        await main_module.connect("sid-1", {"QUERY_STRING": ""}, None)

    resolve.assert_not_awaited()
    fake_sio.save_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_connect_invalid_token_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sio = _FakeSio()
    monkeypatch.setattr(main_module, "sio", fake_sio)
    monkeypatch.setattr(auth_api, "_resolve_session", AsyncMock(return_value=None))

    with pytest.raises(SioConnectionRefused):
        await main_module.connect("sid-1", {"QUERY_STRING": ""}, {"token": "bad"})

    fake_sio.save_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_connect_valid_token_saves_session(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sio = _FakeSio()
    monkeypatch.setattr(main_module, "sio", fake_sio)
    session = _session_data(role="admin", app_permissions={"terminal": True})
    monkeypatch.setattr(auth_api, "_resolve_session", AsyncMock(return_value=session))

    await main_module.connect("sid-1", {"QUERY_STRING": ""}, {"token": "good"})

    fake_sio.save_session.assert_awaited_once()
    sid, stored = fake_sio.save_session.await_args.args
    assert sid == "sid-1"
    assert stored == {
        "user_id": 7,
        "username": "tester",
        "role": "admin",
        "app_permissions": {"terminal": True},
        "auth_type": "session",
    }


@pytest.mark.asyncio
async def test_connect_accepts_query_string_token(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sio = _FakeSio()
    monkeypatch.setattr(main_module, "sio", fake_sio)
    resolve = AsyncMock(return_value=_session_data())
    monkeypatch.setattr(auth_api, "_resolve_session", resolve)

    await main_module.connect("sid-2", {"QUERY_STRING": "EIO=4&token=from-query"}, None)

    resolve.assert_awaited_once_with("from-query")
    fake_sio.save_session.assert_awaited_once()


# ============================================================
# ai_chat_event / compress_chat 用連線身分
# ============================================================


@pytest.mark.asyncio
async def test_ai_chat_event_foreign_chat_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """別人的 chat_id → get_chat 帶 user_id 查不到 → 回 ai_error 且不呼叫 AI"""
    sio = _FakeSio(identity={"user_id": 7, "role": "user", "app_permissions": {}})
    ai_api.register_events(sio)

    get_chat = AsyncMock(return_value=None)
    monkeypatch.setattr(ai_api.ai_chat, "get_chat", get_chat)
    call_ai = AsyncMock()
    monkeypatch.setattr(ai_api, "call_ai", call_ai)

    chat_id = uuid4()
    await sio.handlers["ai_chat_event"](
        "sid-1", {"chatId": str(chat_id), "message": "hi", "model": "claude-sonnet"}
    )

    get_chat.assert_awaited_once_with(chat_id, 7)
    call_ai.assert_not_awaited()
    events = [call.args[0] for call in sio.emit.await_args_list]
    assert events == ["ai_error"]
    assert sio.emit.await_args.args[1]["error"] == "對話不存在或無權限"


@pytest.mark.asyncio
async def test_ai_chat_event_without_identity_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """連線身分取不到（例如未驗證）→ 回 ai_error，不查 DB、不呼叫 AI"""
    sio = _FakeSio(identity=None)
    ai_api.register_events(sio)

    get_chat = AsyncMock()
    monkeypatch.setattr(ai_api.ai_chat, "get_chat", get_chat)
    call_ai = AsyncMock()
    monkeypatch.setattr(ai_api, "call_ai", call_ai)

    await sio.handlers["ai_chat_event"](
        "sid-1", {"chatId": str(uuid4()), "message": "hi"}
    )

    get_chat.assert_not_awaited()
    call_ai.assert_not_awaited()
    assert [call.args[0] for call in sio.emit.await_args_list] == ["ai_error"]


@pytest.mark.asyncio
async def test_ai_chat_event_own_chat_proceeds(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio(identity={"user_id": 7, "role": "user", "app_permissions": {}})
    ai_api.register_events(sio)

    chat_id = uuid4()
    monkeypatch.setattr(
        ai_api.ai_chat,
        "get_chat",
        AsyncMock(return_value={"id": chat_id, "user_id": 7, "title": "我的對話", "messages": []}),
    )
    monkeypatch.setattr(ai_api.ai_chat, "get_agent_system_prompt", AsyncMock(return_value="sys"))
    monkeypatch.setattr(ai_api.ai_chat, "get_agent_config", AsyncMock(return_value=None))
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_messages", AsyncMock())
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_title", AsyncMock())
    monkeypatch.setattr(ai_api, "log_message", AsyncMock())

    from ching_tech_os.services.ai_provider import AIResponse

    call_ai = AsyncMock(
        return_value=AIResponse(
            success=True,
            message="回覆",
            input_tokens=1,
            output_tokens=2,
            provider="claude",
            route_reason="forced_claude",
        )
    )
    monkeypatch.setattr(ai_api, "call_ai", call_ai)

    await sio.handlers["ai_chat_event"](
        "sid-1", {"chatId": str(chat_id), "message": "hi", "model": "claude-sonnet"}
    )

    call_ai.assert_awaited_once()
    events = [call.args[0] for call in sio.emit.await_args_list]
    assert "ai_response" in events
    assert "ai_error" not in events


@pytest.mark.asyncio
async def test_compress_chat_foreign_chat_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio(identity={"user_id": 7, "role": "user", "app_permissions": {}})
    ai_api.register_events(sio)

    get_chat = AsyncMock(return_value=None)
    monkeypatch.setattr(ai_api.ai_chat, "get_chat", get_chat)
    summarize = AsyncMock()
    monkeypatch.setattr(ai_api, "summarize_messages", summarize)

    chat_id = uuid4()
    await sio.handlers["compress_chat"]("sid-1", {"chatId": str(chat_id)})

    get_chat.assert_awaited_once_with(chat_id, 7)
    summarize.assert_not_awaited()
    assert [call.args[0] for call in sio.emit.await_args_list] == ["compress_error"]


# ============================================================
# terminal:create 用連線身分 + terminal 權限
# ============================================================


class _FakeTerminalSession:
    def __init__(self, session_id: str, user_id: int | None) -> None:
        self.session_id = session_id
        self.user_id = user_id


class _FakeTerminalService:
    def __init__(self) -> None:
        self.created_user_ids: list = []

    def set_output_callback(self, cb) -> None:
        self.output_cb = cb

    async def create_session(self, websocket_sid: str, user_id=None, cols=80, rows=24):
        self.created_user_ids.append(user_id)
        return _FakeTerminalSession("term-1", user_id)

    def get_session(self, session_id: str):
        return None

    def get_detached_sessions(self, user_id=None):
        return []

    def detach_websocket(self, sid: str):
        return []

    def reattach_websocket(self, session_id: str, sid: str):
        return False


@pytest.mark.asyncio
async def test_terminal_create_uses_session_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """忽略 payload 的 user_id，一律用連線身分"""
    service = _FakeTerminalService()
    monkeypatch.setattr(terminal_api, "terminal_service", service)
    sio = _FakeSio(identity={"user_id": 7, "role": "user", "app_permissions": {"terminal": True}})
    terminal_api.register_events(sio)

    result = await sio.handlers["terminal:create"]("sid-1", {"cols": 80, "rows": 24, "user_id": 999})

    assert result["success"] is True
    assert service.created_user_ids == [7]


@pytest.mark.asyncio
async def test_terminal_create_denied_without_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeTerminalService()
    monkeypatch.setattr(terminal_api, "terminal_service", service)
    sio = _FakeSio(identity={"user_id": 7, "role": "user", "app_permissions": {"terminal": False}})
    terminal_api.register_events(sio)

    result = await sio.handlers["terminal:create"]("sid-1", {"user_id": 7})

    assert result["success"] is False
    assert service.created_user_ids == []


@pytest.mark.asyncio
async def test_terminal_create_denied_without_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeTerminalService()
    monkeypatch.setattr(terminal_api, "terminal_service", service)
    sio = _FakeSio(identity=None)
    terminal_api.register_events(sio)

    result = await sio.handlers["terminal:create"]("sid-1", {"user_id": 7})

    assert result["success"] is False
    assert service.created_user_ids == []


# ============================================================
# join_user_room / leave_user_room 用連線身分
# ============================================================


@pytest.mark.asyncio
async def test_join_user_room_ignores_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio(identity={"user_id": 7, "role": "user", "app_permissions": {}})
    monkeypatch.setattr(message_events, "get_unread_count", AsyncMock(return_value=3))
    message_events.register_events(sio)

    await sio.handlers["join_user_room"]("sid-1", {"userId": 999})
    sio.enter_room.assert_awaited_once_with("sid-1", "user:7")

    await sio.handlers["leave_user_room"]("sid-1", {"userId": 999})
    sio.leave_room.assert_awaited_once_with("sid-1", "user:7")


@pytest.mark.asyncio
async def test_join_user_room_without_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio(identity=None)
    monkeypatch.setattr(message_events, "get_unread_count", AsyncMock(return_value=0))
    message_events.register_events(sio)

    await sio.handlers["join_user_room"]("sid-1", {"userId": 999})
    sio.enter_room.assert_not_awaited()
