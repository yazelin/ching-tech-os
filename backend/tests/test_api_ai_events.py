"""ai Socket.IO 事件測試。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ching_tech_os.api import ai as ai_api


class _FakeSio:
    def __init__(self) -> None:
        self.handlers = {}
        self.emit = AsyncMock()

    def event(self, fn):
        self.handlers[fn.__name__] = fn
        return fn


def _response(
    *,
    success: bool,
    message: str = "",
    error: str | None = None,
    tool_calls: list | None = None,
    input_tokens: int = 1,
    output_tokens: int = 2,
):
    return SimpleNamespace(
        success=success,
        message=message,
        error=error,
        tool_calls=tool_calls or [],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


@pytest.mark.asyncio
async def test_ai_chat_event_validation_and_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio()
    ai_api.register_events(sio)

    await sio.handlers["ai_chat_event"]("sid-1", {"chatId": "", "message": ""})
    await sio.handlers["ai_chat_event"]("sid-1", {"chatId": "bad-uuid", "message": "hi"})

    monkeypatch.setattr(ai_api.ai_chat, "get_chat", AsyncMock(return_value=None))
    await sio.handlers["ai_chat_event"]("sid-1", {"chatId": str(uuid4()), "message": "hi"})

    events = [call.args[0] for call in sio.emit.await_args_list]
    assert events == ["ai_error", "ai_error", "ai_error"]


@pytest.mark.asyncio
async def test_ai_chat_event_success(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio()
    ai_api.register_events(sio)

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

    tool_call = SimpleNamespace(id="tc1", name="search_knowledge", input={"query": "x"}, output="ok")
    monkeypatch.setattr(
        ai_api,
        "call_claude",
        AsyncMock(return_value=_response(success=True, message="AI 回覆", tool_calls=[tool_call])),
    )

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


@pytest.mark.asyncio
async def test_ai_chat_event_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio()
    ai_api.register_events(sio)

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
        "call_claude",
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
async def test_compress_chat_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    sio = _FakeSio()
    ai_api.register_events(sio)
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
        "call_claude_for_summary",
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
        "call_claude_for_summary",
        AsyncMock(return_value=_response(success=False, error="摘要失敗")),
    )
    monkeypatch.setattr(ai_api.ai_manager, "create_log", AsyncMock())
    await handler("sid-1", {"chatId": str(chat_id)})
    events = [call.args[0] for call in sio.emit.await_args_list]
    assert "compress_error" in events
