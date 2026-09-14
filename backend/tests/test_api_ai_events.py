"""ai Socket.IO 事件測試。"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

import ching_tech_os.api.auth as auth_api
from ching_tech_os.api import ai as ai_api
from ching_tech_os.models.auth import SessionData
from ching_tech_os.services.ai_provider import AIResponse, ToolCall


class _FakeSio:
    """連線身分由 connect 存進 sio session，測試直接餵一份。"""

    def __init__(self, identity: dict | None = None) -> None:
        self.handlers = {}
        self.emit = AsyncMock()
        self.disconnect = AsyncMock()
        self.identity = (
            identity
            if identity is not None
            else {"user_id": 1, "role": "user", "app_permissions": {}, "token": "tok"}
        )

    def event(self, fn):
        self.handlers[fn.__name__] = fn
        return fn

    async def get_session(self, sid):
        return self.identity


def _stub_resolve_session(
    monkeypatch: pytest.MonkeyPatch, *, user_id: int = 1, read_only: bool = False
) -> AsyncMock:
    """ai_chat_event／compress_chat 進入時會重新解析一次 token"""
    now = datetime.now(timezone.utc)
    session = SessionData(
        username="tester",
        password="xxx",
        nas_host="localhost",
        user_id=user_id,
        created_at=now,
        expires_at=now,
        role="user",
        app_permissions={},
        read_only=read_only,
    )
    resolve = AsyncMock(return_value=session)
    monkeypatch.setattr(auth_api, "_resolve_session", resolve)
    return resolve


def _response(
    *,
    success: bool,
    message: str = "",
    error: str | None = None,
    tool_calls: list | None = None,
    tool_timings: list | None = None,
    input_tokens: int = 1,
    output_tokens: int = 2,
):
    # 用真實 AIResponse，讓 attach_routing_metadata() 可運作
    return AIResponse(
        success=success,
        message=message,
        error=error,
        tool_calls=tool_calls or [],
        tool_timings=tool_timings or [],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        provider="claude",
        route_reason="forced_claude",
    )


@pytest.mark.asyncio
async def test_ai_chat_event_validation_and_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio()
    ai_api.register_events(sio)
    _stub_resolve_session(monkeypatch)

    await sio.handlers["ai_chat_event"]("sid-1", {"chatId": "", "message": ""})
    await sio.handlers["ai_chat_event"]("sid-1", {"chatId": "bad-uuid", "message": "hi"})

    monkeypatch.setattr(ai_api.ai_chat, "get_chat", AsyncMock(return_value=None))
    await sio.handlers["ai_chat_event"]("sid-1", {"chatId": str(uuid4()), "message": "hi"})

    events = [call.args[0] for call in sio.emit.await_args_list]
    assert events == ["ai_error", "ai_error", "ai_error"]


@pytest.mark.asyncio
async def test_ai_chat_event_prompt_name_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """chat dict 沒有 prompt_name 時，ai_chat_event 要退回 'web-chat-default'

    行為測試：不看原始碼字面（inspect.getsource 太脆，字串一改就假綠），
    直接驅動 ai_chat_event，斷言 get_agent_system_prompt／get_agent_config
    實際收到的 agent_name 引數是 'web-chat-default'。
    """
    sio = _FakeSio()
    ai_api.register_events(sio)
    _stub_resolve_session(monkeypatch)

    chat_id = uuid4()

    monkeypatch.setattr(
        ai_api.ai_chat,
        "get_chat",
        AsyncMock(
            return_value={
                "id": chat_id,
                "user_id": 1,
                "title": "新對話",
                # 沒有 "prompt_name" key（模擬舊資料或未指定）
                "messages": [],
            }
        ),
    )
    get_system_prompt = AsyncMock(return_value="sys")
    get_agent_config = AsyncMock(return_value=None)
    monkeypatch.setattr(ai_api.ai_chat, "get_agent_system_prompt", get_system_prompt)
    monkeypatch.setattr(ai_api.ai_chat, "get_agent_config", get_agent_config)
    monkeypatch.setattr(ai_api, "call_ai", AsyncMock(return_value=_response(success=True, message="ok")))
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_messages", AsyncMock())
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_title", AsyncMock())
    monkeypatch.setattr(ai_api, "log_message", AsyncMock())

    await sio.handlers["ai_chat_event"](
        "sid-1",
        {"chatId": str(chat_id), "message": "hi", "model": "claude-sonnet"},
    )

    get_system_prompt.assert_awaited_once_with("web-chat-default")
    get_agent_config.assert_awaited_once_with("web-chat-default")


@pytest.mark.asyncio
async def test_ai_chat_event_success(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio()
    ai_api.register_events(sio)
    _stub_resolve_session(monkeypatch)

    chat_id = uuid4()
    agent_id = uuid4()

    monkeypatch.setattr(
        ai_api.ai_chat,
        "get_chat",
        AsyncMock(
            return_value={
                "id": chat_id,
                "user_id": 1,
                "title": "新對話",
                "prompt_name": "agent-a",
                "messages": [],
            }
        ),
    )
    monkeypatch.setattr(ai_api.ai_chat, "get_agent_system_prompt", AsyncMock(return_value="sys"))
    monkeypatch.setattr(
        ai_api.ai_chat,
        "get_agent_config",
        AsyncMock(return_value={"id": agent_id, "tools": ["search_knowledge"]}),
    )
    update_messages = AsyncMock()
    update_title = AsyncMock()
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_messages", update_messages)
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_title", update_title)

    tool_call = ToolCall(id="tc1", name="search_knowledge", input={"query": "x"}, output="ok")
    tool_timings = [{"name": "search_knowledge", "duration_ms": 42}]
    call_ai_mock = AsyncMock(
        return_value=_response(
            success=True,
            message="AI 回覆",
            tool_calls=[tool_call],
            tool_timings=tool_timings,
        )
    )
    monkeypatch.setattr(ai_api, "call_ai", call_ai_mock)

    create_log = AsyncMock()
    monkeypatch.setattr(ai_api.ai_manager, "create_log", create_log)
    log_message = AsyncMock()
    monkeypatch.setattr(ai_api, "log_message", log_message)

    await sio.handlers["ai_chat_event"](
        "sid-1",
        {"chatId": str(chat_id), "message": "請幫我整理", "model": "claude-sonnet"},
    )

    events = [call.args[0] for call in sio.emit.await_args_list]
    assert events.count("ai_typing") == 2
    assert "ai_response" in events
    assert "ai_error" not in events
    update_messages.assert_awaited_once()
    update_title.assert_awaited_once()
    create_log.assert_awaited_once()
    log_message.assert_awaited_once()

    # 8.2：web-chat 走 call_ai，routing context 用 caller 端事實
    routing_context = call_ai_mock.await_args.kwargs["routing_context"]
    assert routing_context.context_type == "web-chat"
    assert routing_context.agent_name == "agent-a"
    # issue #231：身分取自這條連線的 session，而且只從 session 取
    assert call_ai_mock.await_args.kwargs["ctos_user_id"] == 1
    # AI log 的 parsed_response 保留 tool_calls 並附加 routing metadata
    log_data = create_log.await_args.args[0]
    assert log_data.parsed_response["routing"]["provider"] == "claude"
    assert log_data.parsed_response["tool_calls"][0]["name"] == "search_knowledge"

    # PR 3b：ai_response payload 帶 toolCalls / toolTimings（camelCase，與 chatId 一致）
    response_call = next(
        call for call in sio.emit.await_args_list if call.args[0] == "ai_response"
    )
    payload = response_call.args[1]
    assert payload["chatId"] == str(chat_id)
    assert payload["message"] == "AI 回覆"
    assert payload["toolCalls"] == [
        {"id": "tc1", "name": "search_knowledge", "input": {"query": "x"}, "output": "ok"}
    ]
    assert payload["toolTimings"] == tool_timings

    # 持久化的 assistant 訊息也帶 tool_calls（與 AI Log parsed_response.tool_calls 同形狀）
    saved_messages = update_messages.await_args.args[1]
    assistant_message = saved_messages[-1]
    assert assistant_message["role"] == "assistant"
    assert assistant_message["tool_calls"] == [
        {"id": "tc1", "name": "search_knowledge", "input": {"query": "x"}, "output": "ok"}
    ]


@pytest.mark.asyncio
async def test_ai_chat_event_success_without_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """沒有工具呼叫時：toolCalls 是空陣列，持久化訊息的 tool_calls 是 None（負控制）"""
    sio = _FakeSio()
    ai_api.register_events(sio)
    _stub_resolve_session(monkeypatch)

    chat_id = uuid4()
    agent_id = uuid4()

    monkeypatch.setattr(
        ai_api.ai_chat,
        "get_chat",
        AsyncMock(
            return_value={
                "id": chat_id,
                "user_id": 1,
                "title": "新對話",
                "prompt_name": "agent-a",
                "messages": [],
            }
        ),
    )
    monkeypatch.setattr(ai_api.ai_chat, "get_agent_system_prompt", AsyncMock(return_value="sys"))
    monkeypatch.setattr(
        ai_api.ai_chat,
        "get_agent_config",
        AsyncMock(return_value={"id": agent_id, "tools": []}),
    )
    update_messages = AsyncMock()
    update_title = AsyncMock()
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_messages", update_messages)
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_title", update_title)

    call_ai_mock = AsyncMock(return_value=_response(success=True, message="沒有用工具的回覆"))
    monkeypatch.setattr(ai_api, "call_ai", call_ai_mock)
    monkeypatch.setattr(ai_api.ai_manager, "create_log", AsyncMock())
    monkeypatch.setattr(ai_api, "log_message", AsyncMock())

    await sio.handlers["ai_chat_event"](
        "sid-1",
        {"chatId": str(chat_id), "message": "普通問題", "model": "claude-sonnet"},
    )

    response_call = next(
        call for call in sio.emit.await_args_list if call.args[0] == "ai_response"
    )
    payload = response_call.args[1]
    assert payload["toolCalls"] == []
    assert payload["toolTimings"] == []

    saved_messages = update_messages.await_args.args[1]
    assistant_message = saved_messages[-1]
    assert assistant_message["tool_calls"] is None


@pytest.mark.asyncio
async def test_ai_chat_event_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio()
    ai_api.register_events(sio)
    _stub_resolve_session(monkeypatch)

    chat_id = uuid4()
    agent_id = uuid4()

    monkeypatch.setattr(
        ai_api.ai_chat,
        "get_chat",
        AsyncMock(
            return_value={
                "id": chat_id,
                "user_id": 1,
                "title": "舊對話",
                "prompt_name": "agent-a",
                "messages": [{"role": "user", "content": "old", "timestamp": 1}],
            }
        ),
    )
    monkeypatch.setattr(ai_api.ai_chat, "get_agent_system_prompt", AsyncMock(return_value="sys"))
    monkeypatch.setattr(
        ai_api.ai_chat,
        "get_agent_config",
        AsyncMock(return_value={"id": agent_id, "tools": ["search_knowledge"]}),
    )
    update_messages = AsyncMock()
    update_title = AsyncMock()
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_messages", update_messages)
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_title", update_title)
    monkeypatch.setattr(
        ai_api,
        "call_ai",
        AsyncMock(return_value=_response(success=False, error="模型忙碌")),
    )
    create_log = AsyncMock()
    monkeypatch.setattr(ai_api.ai_manager, "create_log", create_log)
    log_message = AsyncMock()
    monkeypatch.setattr(ai_api, "log_message", log_message)

    await sio.handlers["ai_chat_event"](
        "sid-1",
        {"chatId": str(chat_id), "message": "失敗測試", "model": "claude-sonnet"},
    )

    events = [call.args[0] for call in sio.emit.await_args_list]
    assert "ai_error" in events
    assert "ai_response" not in events
    update_messages.assert_not_called()
    update_title.assert_not_called()
    create_log.assert_awaited_once()
    log_message.assert_not_called()


@pytest.mark.asyncio
async def test_ai_chat_event_injects_session_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """issue #231：`call_ai` 一定收得到登入者身分，而且身分只能是 session 的。

    這是正式機那個 bug 的回歸測試：沒帶 `ctos_user_id` 時 MCP 子行程沒有
    `CTOS_USER_ID`，`run_skill_script` 走未綁定那支，回「請先綁定 CTOS 帳號」。
    順便把「不從 request body／model 參數取身分」也釘住——data 裡塞別人的
    id 不會改變送進 `call_ai` 的值。
    """
    sio = _FakeSio()
    ai_api.register_events(sio)
    _stub_resolve_session(monkeypatch, user_id=7)

    chat_id = uuid4()
    monkeypatch.setattr(
        ai_api.ai_chat,
        "get_chat",
        AsyncMock(
            return_value={
                "id": chat_id,
                "user_id": 7,
                "title": "新對話",
                "prompt_name": "bot-debug",
                "messages": [],
            }
        ),
    )
    monkeypatch.setattr(ai_api.ai_chat, "get_agent_system_prompt", AsyncMock(return_value="sys"))
    monkeypatch.setattr(
        ai_api.ai_chat,
        "get_agent_config",
        AsyncMock(return_value={"id": uuid4(), "tools": ["run_skill_script"]}),
    )
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_messages", AsyncMock())
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_title", AsyncMock())
    call_ai_mock = AsyncMock(return_value=_response(success=True, message="ok"))
    monkeypatch.setattr(ai_api, "call_ai", call_ai_mock)
    monkeypatch.setattr(ai_api.ai_manager, "create_log", AsyncMock())
    monkeypatch.setattr(ai_api, "log_message", AsyncMock())

    await sio.handlers["ai_chat_event"](
        "sid-1",
        {
            "chatId": str(chat_id),
            "message": "跑一下 check-db-status",
            "model": "claude-sonnet",
            # 冒充嘗試：request body 帶別人的 id，不該影響注入的身分
            "ctos_user_id": 999,
            "userId": 999,
        },
    )

    kwargs = call_ai_mock.await_args.kwargs
    assert kwargs["ctos_user_id"] == 7
    # bot 專屬的平台／群組身分不屬於網頁聊天，不得一起帶
    assert "extra_mcp_env" not in kwargs or kwargs["extra_mcp_env"] is None


@pytest.mark.asyncio
async def test_ai_chat_event_without_user_id_never_calls_ai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """session 沒有 user_id（NAS 帳號還沒 upsert）時不硬造身分。

    這條路在取對話那一關就擋掉了，`call_ai` 根本不會被呼叫——
    也就不會有「猜一個 user_id 送進去」的機會。
    """
    sio = _FakeSio()
    ai_api.register_events(sio)
    _stub_resolve_session(monkeypatch, user_id=None)

    get_chat = AsyncMock(return_value={"id": uuid4(), "messages": []})
    monkeypatch.setattr(ai_api.ai_chat, "get_chat", get_chat)
    call_ai_mock = AsyncMock(return_value=_response(success=True, message="ok"))
    monkeypatch.setattr(ai_api, "call_ai", call_ai_mock)

    await sio.handlers["ai_chat_event"](
        "sid-1", {"chatId": str(uuid4()), "message": "hi", "model": "claude-sonnet"}
    )

    call_ai_mock.assert_not_called()
    get_chat.assert_not_called()
    events = [call.args[0] for call in sio.emit.await_args_list]
    assert events == ["ai_error"]


@pytest.mark.asyncio
async def test_compress_chat_injects_session_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """issue #231：摘要管線同樣帶連線身分（`summarize_messages`）。"""
    sio = _FakeSio()
    ai_api.register_events(sio)
    _stub_resolve_session(monkeypatch, user_id=7)

    long_messages = [
        {"role": "user", "content": f"訊息 {idx}", "timestamp": idx} for idx in range(15)
    ]
    monkeypatch.setattr(
        ai_api.ai_chat, "get_chat", AsyncMock(return_value={"messages": long_messages})
    )
    monkeypatch.setattr(
        ai_api.ai_manager, "get_prompt_by_name", AsyncMock(return_value={"id": uuid4()})
    )
    summarize = AsyncMock(return_value=_response(success=True, message="摘要內容"))
    monkeypatch.setattr(ai_api, "summarize_messages", summarize)
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_messages", AsyncMock())
    monkeypatch.setattr(ai_api.ai_manager, "create_log", AsyncMock())

    await sio.handlers["compress_chat"]("sid-1", {"chatId": str(uuid4())})

    assert summarize.await_args.kwargs["ctos_user_id"] == 7


@pytest.mark.asyncio
async def test_compress_chat_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio()
    ai_api.register_events(sio)
    _stub_resolve_session(monkeypatch)
    handler = sio.handlers["compress_chat"]

    # 缺少 chatId / 格式錯誤 / 對話不存在 / 訊息不足
    await handler("sid-1", {})
    await handler("sid-1", {"chatId": "bad"})
    monkeypatch.setattr(ai_api.ai_chat, "get_chat", AsyncMock(return_value=None))
    await handler("sid-1", {"chatId": str(uuid4())})
    monkeypatch.setattr(ai_api.ai_chat, "get_chat", AsyncMock(return_value={"messages": [{"role": "user", "content": "x"}]}))
    await handler("sid-1", {"chatId": str(uuid4())})

    # 成功壓縮
    chat_id = uuid4()
    long_messages = [
        {"role": "user", "content": f"訊息 {idx}", "timestamp": idx}
        for idx in range(15)
    ]
    monkeypatch.setattr(ai_api.ai_chat, "get_chat", AsyncMock(return_value={"messages": long_messages}))
    monkeypatch.setattr(ai_api.ai_manager, "get_prompt_by_name", AsyncMock(return_value={"id": uuid4()}))
    monkeypatch.setattr(
        ai_api,
        "summarize_messages",
        AsyncMock(return_value=_response(success=True, message="摘要內容")),
    )
    update_messages = AsyncMock()
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_messages", update_messages)
    monkeypatch.setattr(ai_api.ai_manager, "create_log", AsyncMock())
    await handler("sid-1", {"chatId": str(chat_id)})
    update_messages.assert_awaited_once()
    new_messages = update_messages.await_args.args[1]
    assert new_messages[0]["is_summary"] is True
    assert len(new_messages) == 11

    # 壓縮失敗
    sio.emit.reset_mock()
    monkeypatch.setattr(ai_api.ai_chat, "get_chat", AsyncMock(return_value={"messages": long_messages}))
    monkeypatch.setattr(ai_api.ai_manager, "get_prompt_by_name", AsyncMock(return_value={"id": uuid4()}))
    monkeypatch.setattr(
        ai_api,
        "summarize_messages",
        AsyncMock(return_value=_response(success=False, error="摘要失敗")),
    )
    monkeypatch.setattr(ai_api.ai_manager, "create_log", AsyncMock())
    await handler("sid-1", {"chatId": str(chat_id)})
    events = [call.args[0] for call in sio.emit.await_args_list]
    assert "compress_error" in events
