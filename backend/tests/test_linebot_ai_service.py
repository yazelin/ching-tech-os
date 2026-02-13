"""linebot_ai 服務流程測試。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from linebot.v3.messaging import TextMessage

from ching_tech_os.services import linebot_ai
from ching_tech_os.services.mcp import nas_tools as mcp_nas_tools


@pytest.mark.asyncio
async def test_auto_prepare_generated_images_basic_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        linebot_ai,
        "extract_generated_images_from_tool_calls",
        lambda _calls: ["/tmp/ching-tech-os-cli/nanobanana-output/a.jpg", "/tmp/normal/b.jpg"],
    )
    monkeypatch.setattr(
        mcp_nas_tools,
        "prepare_file_message",
        AsyncMock(side_effect=[
            '[FILE_MESSAGE:{"type":"image","url":"https://example.com/a.jpg","name":"a.jpg"}]',
            "prepare failed",
        ]),
    )

    raw = (
        "完成處理\n"
        "[FILE_MESSAGE:{\"type\":\"image\",\"url\":\"https://example.com/b.jpg\",\"name\":\"b.jpg\"}]\n"
        "[FILE_MESSAGE:/tmp/invalid-path.jpg]"
    )
    processed = await linebot_ai.auto_prepare_generated_images(raw, tool_calls=[])

    assert "a.jpg" in processed
    assert "[FILE_MESSAGE:/tmp/invalid-path.jpg]" not in processed
    mcp_nas_tools.prepare_file_message.assert_awaited_with("nanobanana-output/a.jpg")


@pytest.mark.asyncio
async def test_auto_prepare_generated_images_no_files_or_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(linebot_ai, "extract_generated_images_from_tool_calls", lambda _calls: [])
    assert await linebot_ai.auto_prepare_generated_images("hello", tool_calls=[]) == "hello"

    monkeypatch.setattr(
        linebot_ai,
        "extract_generated_images_from_tool_calls",
        lambda _calls: ["/tmp/ching-tech-os-cli/nanobanana-output/x.jpg"],
    )
    monkeypatch.setattr(
        mcp_nas_tools,
        "prepare_file_message",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    assert await linebot_ai.auto_prepare_generated_images("hello", tool_calls=[]) == "hello"


def test_append_text_to_first_message_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        linebot_ai,
        "create_text_message_with_mention",
        lambda text, user_id: TextMessage(text=f"@{user_id}:{text}"),
    )

    messages = [TextMessage(text="原文")]
    linebot_ai._append_text_to_first_message(messages, "補充", mention_line_user_id=None)
    assert messages[0].text == "原文\n\n補充"

    messages = [TextMessage(text=f"{linebot_ai.MENTION_PLACEHOLDER}Hi")]
    linebot_ai._append_text_to_first_message(messages, "補充", mention_line_user_id="U1")
    assert messages[0].text == "@U1:Hi\n\n補充"

    messages = []
    linebot_ai._append_text_to_first_message(messages, "新增", mention_line_user_id="U2")
    assert messages[0].text == "@U2:新增"


@pytest.mark.asyncio
async def test_send_ai_response_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        linebot_ai,
        "create_text_message_with_mention",
        lambda text, _uid: TextMessage(text=text),
    )
    reply_messages = AsyncMock(return_value=["m1", "m2"])
    monkeypatch.setattr(linebot_ai, "reply_messages", reply_messages)

    # 空訊息直接返回
    assert await linebot_ai.send_ai_response("token", "", [], None) == []
    reply_messages.assert_not_called()

    # 圖片超過 5 則時，應裁切並把超出圖片改成連結文字
    image_files = [
        {"type": "image", "url": f"https://example.com/{i}.jpg"}
        for i in range(1, 7)
    ]
    sent_ids = await linebot_ai.send_ai_response(
        reply_token="token",
        text="主訊息",
        file_messages=image_files,
        mention_line_user_id=None,
    )
    assert sent_ids == ["m1", "m2"]
    called_messages = reply_messages.await_args.args[1]
    assert len(called_messages) == 5
    assert isinstance(called_messages[0], TextMessage)
    assert "其他圖片連結" in called_messages[0].text

    # 純檔案連結時，應產生文字訊息
    reply_messages.reset_mock()
    file_only = [{
        "type": "file",
        "url": "https://example.com/file.pdf",
        "name": "file.pdf",
        "size": "1KB",
    }]
    await linebot_ai.send_ai_response(
        reply_token="token",
        text="",
        file_messages=file_only,
        mention_line_user_id=None,
    )
    called_messages = reply_messages.await_args.args[1]
    assert len(called_messages) == 1
    assert "📎 file.pdf（1KB）" in called_messages[0].text


@pytest.mark.asyncio
async def test_log_linebot_ai_call_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    create_log = AsyncMock()
    monkeypatch.setattr(linebot_ai.ai_manager, "create_log", create_log)
    monkeypatch.setattr(
        linebot_ai.ai_manager,
        "get_agent_by_name",
        AsyncMock(return_value={"id": uuid4(), "system_prompt": {"id": uuid4()}}),
    )
    monkeypatch.setattr(
        linebot_ai,
        "compose_prompt_with_history",
        lambda history, prompt: f"HISTORY={len(history)}::{prompt}",
    )

    response = SimpleNamespace(
        tool_calls=[SimpleNamespace(id="tc1", name="tool", input={"a": 1}, output="ok")],
        tool_timings={"tool": 123},
        success=True,
        message="AI OK",
        error=None,
        input_tokens=10,
        output_tokens=20,
    )
    await linebot_ai.log_linebot_ai_call(
        message_uuid=uuid4(),
        line_group_id=uuid4(),
        is_group=True,
        input_prompt="prompt",
        history=[{"role": "user", "content": "q"}],
        system_prompt="sys",
        allowed_tools=["Read"],
        model="sonnet",
        response=response,
        duration_ms=321,
        tool_routing={"policy": "script-first"},
    )

    log_data = create_log.await_args.args[0]
    assert log_data.context_type == "linebot-group"
    assert log_data.success is True
    assert log_data.input_prompt.startswith("HISTORY=1::")
    assert log_data.parsed_response["tool_calls"][0]["name"] == "tool"

    monkeypatch.setattr(
        linebot_ai.ai_manager,
        "get_agent_by_name",
        AsyncMock(return_value=None),
    )
    response = SimpleNamespace(
        tool_calls=[],
        tool_timings={},
        success=False,
        message="",
        error="timeout",
        input_tokens=None,
        output_tokens=None,
    )
    await linebot_ai.log_linebot_ai_call(
        message_uuid=uuid4(),
        line_group_id=None,
        is_group=False,
        input_prompt="prompt2",
        history=None,
        system_prompt="sys2",
        allowed_tools=None,
        model="opus",
        response=response,
        duration_ms=999,
        context_type_override="telegram-personal",
    )
    log_data = create_log.await_args.args[0]
    assert log_data.context_type == "telegram-personal"
    assert log_data.success is False
    assert log_data.error_message == "timeout"


@pytest.mark.asyncio
async def test_log_linebot_ai_call_handles_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        linebot_ai.ai_manager,
        "get_agent_by_name",
        AsyncMock(side_effect=RuntimeError("db down")),
    )
    warning = MagicMock()
    monkeypatch.setattr(linebot_ai.logger, "warning", warning)

    response = SimpleNamespace(
        tool_calls=[],
        tool_timings={},
        success=True,
        message="ok",
        error=None,
        input_tokens=1,
        output_tokens=1,
    )
    await linebot_ai.log_linebot_ai_call(
        message_uuid=uuid4(),
        line_group_id=None,
        is_group=False,
        input_prompt="x",
        history=None,
        system_prompt="sys",
        allowed_tools=[],
        model="sonnet",
        response=response,
        duration_ms=1,
    )
    warning.assert_called_once()


@pytest.mark.asyncio
async def test_handle_text_message(monkeypatch: pytest.MonkeyPatch) -> None:
    process = AsyncMock()
    monkeypatch.setattr(linebot_ai, "process_message_with_ai", process)
    monkeypatch.setattr(
        linebot_ai,
        "get_line_user_record",
        AsyncMock(side_effect=[{"display_name": "小明"}, None]),
    )

    message_uuid = uuid4()
    await linebot_ai.handle_text_message(
        message_id="m1",
        message_uuid=message_uuid,
        content="hello",
        line_user_id="U1",
        line_group_id=None,
        reply_token="r1",
        quoted_message_id="q1",
    )
    assert process.await_args.kwargs["user_display_name"] == "小明"

    await linebot_ai.handle_text_message(
        message_id="m2",
        message_uuid=uuid4(),
        content="hello2",
        line_user_id="U2",
        line_group_id=None,
        reply_token="r2",
    )
    assert process.await_args.kwargs["user_display_name"] is None


@pytest.mark.asyncio
async def test_process_message_with_ai_reset_group_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(linebot_ai, "is_reset_command", lambda _content: True)
    result = await linebot_ai.process_message_with_ai(
        message_uuid=uuid4(),
        content="/reset",
        line_group_id=uuid4(),
        line_user_id="U1",
        reply_token="r1",
    )
    assert result is None


@pytest.mark.asyncio
async def test_process_message_with_ai_reset_reply_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(linebot_ai, "is_reset_command", lambda _content: True)
    monkeypatch.setattr(linebot_ai, "reset_conversation", AsyncMock(return_value=True))
    monkeypatch.setattr(linebot_ai, "save_bot_response", AsyncMock(return_value=uuid4()))
    reply_text = AsyncMock(return_value="m1")
    push_text = AsyncMock(return_value=("m2", None))
    monkeypatch.setattr(linebot_ai, "reply_text", reply_text)
    monkeypatch.setattr(linebot_ai, "push_text", push_text)

    result = await linebot_ai.process_message_with_ai(
        message_uuid=uuid4(),
        content="/reset",
        line_group_id=None,
        line_user_id="U1",
        reply_token="r1",
    )
    assert "已清除對話歷史" in (result or "")
    reply_text.assert_awaited_once()
    push_text.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_with_ai_reset_push_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(linebot_ai, "is_reset_command", lambda _content: True)
    monkeypatch.setattr(linebot_ai, "reset_conversation", AsyncMock(return_value=True))
    monkeypatch.setattr(linebot_ai, "save_bot_response", AsyncMock(return_value=uuid4()))
    monkeypatch.setattr(linebot_ai, "reply_text", AsyncMock(side_effect=RuntimeError("expired")))
    push_text = AsyncMock(return_value=("m2", None))
    monkeypatch.setattr(linebot_ai, "push_text", push_text)

    result = await linebot_ai.process_message_with_ai(
        message_uuid=uuid4(),
        content="/新對話",
        line_group_id=None,
        line_user_id="U1",
        reply_token="r1",
    )
    assert "已清除對話歷史" in (result or "")
    push_text.assert_awaited_once()
