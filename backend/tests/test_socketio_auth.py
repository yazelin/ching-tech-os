"""Socket.IO 連線驗證與事件身分測試（#185）。

- connect：沒帶 token、token 無效、解析拋例外 → 拒絕連線；有效 → 把身分存進 sio session。
- token 只認 auth["token"]，query string 不收。
- 高風險事件（ai_chat_event／compress_chat／terminal:create）進入時重新解析 token，
  失敗回錯誤並斷線；唯讀 token 一律拒絕。
- ai_chat_event／compress_chat 以連線身分取對話，不是自己的 → 回錯誤且不呼叫 AI。
- terminal:create 用連線身分的 user_id，沒有 terminal 權限就拒絕；
  terminal:list／terminal:reconnect 只看得到、只能重連自己的 session。
- join_user_room／leave_user_room／get_unread_count_event 一律用連線身分。

事件處理直接呼叫註冊好的 coroutine，sio 用假物件（save_session／get_session／
emit／enter_room／leave_room／disconnect 都是 AsyncMock）。
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
        self.disconnect = AsyncMock()

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


def _session_data(
    role: str = "user",
    app_permissions: dict | None = None,
    user_id: int | None = 7,
    read_only: bool = False,
) -> SessionData:
    now = datetime.now(timezone.utc)
    return SessionData(
        username="tester",
        password="xxx",
        nas_host="localhost",
        user_id=user_id,
        created_at=now,
        expires_at=now,
        role=role,
        app_permissions=app_permissions if app_permissions is not None else {"terminal": True},
        read_only=read_only,
    )


def _identity(**overrides) -> dict:
    """connect 存進 sio session 的那份身分"""
    base = {
        "user_id": 7,
        "username": "tester",
        "role": "user",
        "app_permissions": {"terminal": True},
        "read_only": False,
        "token": "tok",
    }
    base.update(overrides)
    return base


# ============================================================
# extract_token（F7：只認 auth.token）
# ============================================================


def test_extract_token_from_auth_dict() -> None:
    assert socket_auth.extract_token({"token": " abc "}) == "abc"


def test_extract_token_rejects_query_string() -> None:
    """query string 會留在 nginx log 與瀏覽器歷史紀錄，不接受"""
    assert socket_auth.extract_token(None) is None
    assert socket_auth.extract_token({"EIO": "4"}) is None


def test_extract_token_missing() -> None:
    assert socket_auth.extract_token({}) is None
    assert socket_auth.extract_token({"token": "   "}) is None
    assert socket_auth.extract_token("not-a-dict") is None


@pytest.mark.asyncio
async def test_get_socket_identity_tolerates_missing_get_session() -> None:
    class _NoSession:
        pass

    assert await socket_auth.get_socket_identity(_NoSession(), "sid") is None
    assert await socket_auth.get_socket_user_id(_NoSession(), "sid") is None
    assert await socket_auth.revalidate_socket_session(_NoSession(), "sid") is None
    # disconnect 不存在也不應該炸
    await socket_auth.disconnect_socket(_NoSession(), "sid")


@pytest.mark.asyncio
async def test_get_socket_identity_tolerates_error() -> None:
    class _Boom:
        async def get_session(self, sid):
            raise KeyError(sid)

        async def disconnect(self, sid):
            raise RuntimeError("boom")

    assert await socket_auth.get_socket_identity(_Boom(), "sid") is None
    await socket_auth.disconnect_socket(_Boom(), "sid")


@pytest.mark.asyncio
async def test_revalidate_returns_none_when_resolve_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sio = _FakeSio(identity=_identity())
    monkeypatch.setattr(auth_api, "_resolve_session", AsyncMock(side_effect=RuntimeError("db")))
    assert await socket_auth.revalidate_socket_session(sio, "sid-1") is None


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
async def test_connect_query_string_token_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """F7：query string 帶 token 不再被接受"""
    fake_sio = _FakeSio()
    monkeypatch.setattr(main_module, "sio", fake_sio)
    resolve = AsyncMock(return_value=_session_data())
    monkeypatch.setattr(auth_api, "_resolve_session", resolve)

    with pytest.raises(SioConnectionRefused):
        await main_module.connect("sid-1", {"QUERY_STRING": "EIO=4&token=from-query"}, None)

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
async def test_connect_resolve_error_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """F6：_resolve_session 拋例外要拒絕連線，不是讓 500 冒出去"""
    fake_sio = _FakeSio()
    monkeypatch.setattr(main_module, "sio", fake_sio)
    monkeypatch.setattr(
        auth_api, "_resolve_session", AsyncMock(side_effect=RuntimeError("db down"))
    )

    with pytest.raises(SioConnectionRefused):
        await main_module.connect("sid-1", {"QUERY_STRING": ""}, {"token": "whatever"})

    fake_sio.save_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_connect_valid_token_saves_session(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sio = _FakeSio()
    monkeypatch.setattr(main_module, "sio", fake_sio)
    session = _session_data(role="admin", app_permissions={"terminal": True}, read_only=True)
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
        "read_only": True,
        "token": "good",
    }
    # F11：auth_type 沒人讀，不再存
    assert "auth_type" not in stored


# ============================================================
# ai_chat_event / compress_chat
# ============================================================


def _stub_resolve(monkeypatch: pytest.MonkeyPatch, session) -> AsyncMock:
    resolve = AsyncMock(return_value=session)
    monkeypatch.setattr(auth_api, "_resolve_session", resolve)
    return resolve


@pytest.mark.asyncio
async def test_ai_chat_event_foreign_chat_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """別人的 chat_id → get_chat 帶 user_id 查不到 → 回 ai_error 且不呼叫 AI"""
    sio = _FakeSio(identity=_identity())
    ai_api.register_events(sio)
    _stub_resolve(monkeypatch, _session_data())

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
async def test_ai_chat_event_revoked_token_disconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    """F2：連線後 token 被撤銷／登出 → 回錯誤並斷線，不查 DB、不呼叫 AI"""
    sio = _FakeSio(identity=_identity())
    ai_api.register_events(sio)
    _stub_resolve(monkeypatch, None)

    get_chat = AsyncMock()
    monkeypatch.setattr(ai_api.ai_chat, "get_chat", get_chat)
    call_ai = AsyncMock()
    monkeypatch.setattr(ai_api, "call_ai", call_ai)

    await sio.handlers["ai_chat_event"]("sid-1", {"chatId": str(uuid4()), "message": "hi"})

    get_chat.assert_not_awaited()
    call_ai.assert_not_awaited()
    assert [call.args[0] for call in sio.emit.await_args_list] == ["ai_error"]
    sio.disconnect.assert_awaited_once_with("sid-1")


@pytest.mark.asyncio
async def test_ai_chat_event_read_only_token_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """F1：唯讀 PAT 不能跑 AI 對話"""
    sio = _FakeSio(identity=_identity(read_only=True))
    ai_api.register_events(sio)
    _stub_resolve(monkeypatch, _session_data(read_only=True))

    get_chat = AsyncMock()
    monkeypatch.setattr(ai_api.ai_chat, "get_chat", get_chat)
    call_ai = AsyncMock()
    monkeypatch.setattr(ai_api, "call_ai", call_ai)

    await sio.handlers["ai_chat_event"]("sid-1", {"chatId": str(uuid4()), "message": "hi"})

    get_chat.assert_not_awaited()
    call_ai.assert_not_awaited()
    assert [call.args[0] for call in sio.emit.await_args_list] == ["ai_error"]
    assert "唯讀" in sio.emit.await_args.args[1]["error"]
    sio.disconnect.assert_not_awaited()


@pytest.mark.asyncio
async def test_ai_chat_event_without_identity_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """連線身分取不到（例如連線已消失）→ 回 ai_error，不查 DB、不呼叫 AI"""
    sio = _FakeSio(identity=None)
    ai_api.register_events(sio)

    get_chat = AsyncMock()
    monkeypatch.setattr(ai_api.ai_chat, "get_chat", get_chat)
    call_ai = AsyncMock()
    monkeypatch.setattr(ai_api, "call_ai", call_ai)

    await sio.handlers["ai_chat_event"]("sid-1", {"chatId": str(uuid4()), "message": "hi"})

    get_chat.assert_not_awaited()
    call_ai.assert_not_awaited()
    assert [call.args[0] for call in sio.emit.await_args_list] == ["ai_error"]


@pytest.mark.asyncio
async def test_ai_chat_event_own_chat_proceeds(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio(identity=_identity())
    ai_api.register_events(sio)
    _stub_resolve(monkeypatch, _session_data())

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
    sio = _FakeSio(identity=_identity())
    ai_api.register_events(sio)
    _stub_resolve(monkeypatch, _session_data())

    get_chat = AsyncMock(return_value=None)
    monkeypatch.setattr(ai_api.ai_chat, "get_chat", get_chat)
    summarize = AsyncMock()
    monkeypatch.setattr(ai_api, "summarize_messages", summarize)

    chat_id = uuid4()
    await sio.handlers["compress_chat"]("sid-1", {"chatId": str(chat_id)})

    get_chat.assert_awaited_once_with(chat_id, 7)
    summarize.assert_not_awaited()
    assert [call.args[0] for call in sio.emit.await_args_list] == ["compress_error"]


@pytest.mark.asyncio
async def test_compress_chat_revoked_token_disconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio(identity=_identity())
    ai_api.register_events(sio)
    _stub_resolve(monkeypatch, None)

    get_chat = AsyncMock()
    monkeypatch.setattr(ai_api.ai_chat, "get_chat", get_chat)
    summarize = AsyncMock()
    monkeypatch.setattr(ai_api, "summarize_messages", summarize)

    await sio.handlers["compress_chat"]("sid-1", {"chatId": str(uuid4())})

    get_chat.assert_not_awaited()
    summarize.assert_not_awaited()
    assert [call.args[0] for call in sio.emit.await_args_list] == ["compress_error"]
    sio.disconnect.assert_awaited_once_with("sid-1")


@pytest.mark.asyncio
async def test_compress_chat_read_only_token_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio(identity=_identity(read_only=True))
    ai_api.register_events(sio)
    _stub_resolve(monkeypatch, _session_data(read_only=True))

    get_chat = AsyncMock()
    monkeypatch.setattr(ai_api.ai_chat, "get_chat", get_chat)
    summarize = AsyncMock()
    monkeypatch.setattr(ai_api, "summarize_messages", summarize)

    await sio.handlers["compress_chat"]("sid-1", {"chatId": str(uuid4())})

    get_chat.assert_not_awaited()
    summarize.assert_not_awaited()
    assert "唯讀" in sio.emit.await_args.args[1]["error"]
    sio.disconnect.assert_not_awaited()


# ============================================================
# terminal 事件
# ============================================================


class _FakeTerminalSession:
    def __init__(self, session_id: str, user_id: int | None) -> None:
        self.session_id = session_id
        self.user_id = user_id


class _FakeTerminalService:
    def __init__(self, sessions: dict | None = None) -> None:
        self.created_user_ids: list = []
        self.sessions = sessions or {}
        self.reattached: list = []

    def set_output_callback(self, cb) -> None:
        self.output_cb = cb

    async def create_session(self, websocket_sid: str, user_id=None, cols=80, rows=24):
        self.created_user_ids.append(user_id)
        return _FakeTerminalSession("term-1", user_id)

    def get_session(self, session_id: str):
        return self.sessions.get(session_id)

    def get_detached_sessions(self, user_id=None):
        return []

    def detach_websocket(self, sid: str):
        return []

    def reattach_websocket(self, session_id: str, sid: str):
        self.reattached.append(session_id)
        return True


@pytest.mark.asyncio
async def test_terminal_create_uses_session_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """忽略 payload 的 user_id，一律用重新解析出來的連線身分"""
    service = _FakeTerminalService()
    monkeypatch.setattr(terminal_api, "terminal_service", service)
    _stub_resolve(monkeypatch, _session_data(app_permissions={"terminal": True}))
    sio = _FakeSio(identity=_identity())
    terminal_api.register_events(sio)

    result = await sio.handlers["terminal:create"]("sid-1", {"cols": 80, "rows": 24, "user_id": 999})

    assert result["success"] is True
    assert service.created_user_ids == [7]


@pytest.mark.asyncio
async def test_terminal_create_denied_without_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeTerminalService()
    monkeypatch.setattr(terminal_api, "terminal_service", service)
    _stub_resolve(monkeypatch, _session_data(app_permissions={"terminal": False}))
    sio = _FakeSio(identity=_identity(app_permissions={"terminal": False}))
    terminal_api.register_events(sio)

    result = await sio.handlers["terminal:create"]("sid-1", {"user_id": 7})

    assert result["success"] is False
    assert service.created_user_ids == []


@pytest.mark.asyncio
async def test_terminal_create_denied_by_default_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """app_permissions 沒帶 terminal → 回退到預設值（terminal 預設關閉）"""
    service = _FakeTerminalService()
    monkeypatch.setattr(terminal_api, "terminal_service", service)
    _stub_resolve(monkeypatch, _session_data(app_permissions={}))
    sio = _FakeSio(identity=_identity(app_permissions={}))
    terminal_api.register_events(sio)

    result = await sio.handlers["terminal:create"]("sid-1", {})

    assert result["success"] is False
    assert service.created_user_ids == []


@pytest.mark.asyncio
async def test_terminal_create_revoked_token_disconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    """F2：連線後 token 被撤銷 → 拒絕並斷線"""
    service = _FakeTerminalService()
    monkeypatch.setattr(terminal_api, "terminal_service", service)
    _stub_resolve(monkeypatch, None)
    sio = _FakeSio(identity=_identity())
    terminal_api.register_events(sio)

    result = await sio.handlers["terminal:create"]("sid-1", {})

    assert result["success"] is False
    assert service.created_user_ids == []
    sio.disconnect.assert_awaited_once_with("sid-1")


@pytest.mark.asyncio
async def test_terminal_create_read_only_token_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """F1：唯讀 PAT 不能開終端機"""
    service = _FakeTerminalService()
    monkeypatch.setattr(terminal_api, "terminal_service", service)
    _stub_resolve(monkeypatch, _session_data(read_only=True))
    sio = _FakeSio(identity=_identity(read_only=True))
    terminal_api.register_events(sio)

    result = await sio.handlers["terminal:create"]("sid-1", {})

    assert result["success"] is False
    assert "唯讀" in result["error"]
    assert service.created_user_ids == []
    sio.disconnect.assert_not_awaited()


@pytest.mark.asyncio
async def test_terminal_create_denied_without_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeTerminalService()
    monkeypatch.setattr(terminal_api, "terminal_service", service)
    sio = _FakeSio(identity=None)
    terminal_api.register_events(sio)

    result = await sio.handlers["terminal:create"]("sid-1", {"user_id": 7})

    assert result["success"] is False
    assert service.created_user_ids == []


@pytest.mark.asyncio
async def test_terminal_list_requires_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """F5：沒有連線身分就不列任何 session"""
    service = _FakeTerminalService()
    monkeypatch.setattr(terminal_api, "terminal_service", service)
    sio = _FakeSio(identity=_identity(user_id=None))
    terminal_api.register_events(sio)

    assert await sio.handlers["terminal:list"]("sid-1", {"user_id": 999}) == {"sessions": []}


@pytest.mark.asyncio
async def test_terminal_reconnect_rejects_foreign_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F10：別人的 session 不能重連"""
    service = _FakeTerminalService(sessions={"term-other": _FakeTerminalSession("term-other", 99)})
    monkeypatch.setattr(terminal_api, "terminal_service", service)
    sio = _FakeSio(identity=_identity())
    terminal_api.register_events(sio)

    result = await sio.handlers["terminal:reconnect"]("sid-1", {"session_id": "term-other"})

    assert result["success"] is False
    assert service.reattached == []


@pytest.mark.asyncio
async def test_terminal_reconnect_allows_own_session(monkeypatch: pytest.MonkeyPatch) -> None:
    own = _FakeTerminalSession("term-mine", 7)
    own.created_at = datetime.now(timezone.utc)
    service = _FakeTerminalService(sessions={"term-mine": own})
    monkeypatch.setattr(terminal_api, "terminal_service", service)
    sio = _FakeSio(identity=_identity())
    terminal_api.register_events(sio)

    result = await sio.handlers["terminal:reconnect"]("sid-1", {"session_id": "term-mine"})

    assert result["success"] is True
    assert service.reattached == ["term-mine"]


@pytest.mark.asyncio
async def test_terminal_reconnect_requires_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """F5：user_id 是 None 直接拒絕，不會變成「比對 None 剛好相等」"""
    orphan = _FakeTerminalSession("term-orphan", None)
    service = _FakeTerminalService(sessions={"term-orphan": orphan})
    monkeypatch.setattr(terminal_api, "terminal_service", service)
    sio = _FakeSio(identity=_identity(user_id=None))
    terminal_api.register_events(sio)

    result = await sio.handlers["terminal:reconnect"]("sid-1", {"session_id": "term-orphan"})

    assert result["success"] is False
    assert service.reattached == []


# ============================================================
# 訊息中心事件
# ============================================================


@pytest.mark.asyncio
async def test_join_user_room_ignores_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio(identity=_identity())
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


@pytest.mark.asyncio
async def test_unread_count_event_uses_session_user(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio(identity=_identity())
    unread = AsyncMock(return_value=5)
    monkeypatch.setattr(message_events, "get_unread_count", unread)
    message_events.register_events(sio)

    await sio.handlers["get_unread_count_event"]("sid-1", {"userId": 999})

    unread.assert_awaited_once_with(7)
    assert sio.emit.await_args.args[1] == {"count": 5}


@pytest.mark.asyncio
async def test_unread_count_event_without_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """F4：取不到連線身分就不回全域未讀數"""
    sio = _FakeSio(identity=None)
    unread = AsyncMock(return_value=42)
    monkeypatch.setattr(message_events, "get_unread_count", unread)
    message_events.register_events(sio)

    await sio.handlers["get_unread_count_event"]("sid-1", {"userId": 999})

    unread.assert_not_awaited()
    sio.emit.assert_not_awaited()
