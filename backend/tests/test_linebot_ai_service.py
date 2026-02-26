"""linebot_ai 服務流程測試。"""

from __future__ import annotations

import importlib
import json
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


def test_extract_research_tool_feedback_start_and_completed() -> None:
    start_output = json.dumps(
        {
            "success": True,
            "output": json.dumps(
                {"success": True, "job_id": "a1b2c3d4", "status": "started"},
                ensure_ascii=False,
            ),
            "error": "",
            "duration_ms": 32,
        },
        ensure_ascii=False,
    )
    start_call = SimpleNamespace(
        name="mcp__ching-tech-os__run_skill_script",
        input={"skill": "research-skill", "script": "start-research"},
        output=start_output,
    )
    start_feedback = linebot_ai._extract_research_tool_feedback([start_call])
    assert start_feedback is not None
    assert start_feedback["script"] == "start-research"
    assert start_feedback["job_id"] == "a1b2c3d4"
    assert "a1b2c3d4" in start_feedback["message"]

    check_output = json.dumps(
        {
            "success": True,
            "output": json.dumps(
                {
                    "success": True,
                    "job_id": "a1b2c3d4",
                    "status": "completed",
                    "final_summary": "研究完成摘要",
                    "sources": [{"title": "來源 A", "url": "https://example.com/a"}],
                },
                ensure_ascii=False,
            ),
            "error": "",
            "duration_ms": 45,
        },
        ensure_ascii=False,
    )
    check_call = SimpleNamespace(
        name="mcp__ching-tech-os__run_skill_script",
        input={"skill": "research-skill", "script": "check-research"},
        output=check_output,
    )
    check_feedback = linebot_ai._extract_research_tool_feedback([check_call])
    assert check_feedback is not None
    assert check_feedback["script"] == "check-research"
    assert "研究完成摘要" in check_feedback["message"]
    assert "來源 A" in check_feedback["message"]


def test_research_check_mode_detection_helpers() -> None:
    assert linebot_ai._extract_research_job_id_from_text("查詢研究進度 c904b40d") == "c904b40d"
    assert linebot_ai._should_force_research_check_mode("查詢研究進度 c904b40d")
    assert not linebot_ai._should_force_research_check_mode("請幫我查今天天氣 c904b40d")


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
        AsyncMock(side_effect=[{"id": "bot-user-1", "user_id": None, "display_name": "小明"}, None]),
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
async def test_process_message_with_ai_not_triggered(monkeypatch: pytest.MonkeyPatch) -> None:
    is_bot_message = AsyncMock(return_value=False)
    monkeypatch.setattr(linebot_ai, "is_bot_message", is_bot_message)
    monkeypatch.setattr(linebot_ai, "should_trigger_ai", lambda *_args, **_kwargs: False)

    result = await linebot_ai.process_message_with_ai(
        message_uuid=uuid4(),
        content="一般聊天",
        line_group_id=uuid4(),
        line_user_id="U1",
        reply_token="r1",
        quoted_message_id="q1",
    )
    assert result is None
    is_bot_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_with_ai_agent_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(linebot_ai, "should_trigger_ai", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(linebot_ai, "get_linebot_agent", AsyncMock(return_value=None))
    reply_text = AsyncMock()
    monkeypatch.setattr(linebot_ai, "reply_text", reply_text)

    result = await linebot_ai.process_message_with_ai(
        message_uuid=uuid4(),
        content="hello",
        line_group_id=None,
        line_user_id="U1",
        reply_token="r1",
    )
    assert result is not None and "Agent 'linebot-personal' 不存在" in result
    reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_with_ai_missing_system_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(linebot_ai, "should_trigger_ai", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        linebot_ai,
        "get_linebot_agent",
        AsyncMock(return_value={"model": "claude-sonnet", "system_prompt": "bad", "tools": []}),
    )
    reply_text = AsyncMock()
    warning = MagicMock()
    monkeypatch.setattr(linebot_ai, "reply_text", reply_text)
    monkeypatch.setattr(linebot_ai.logger, "warning", warning)

    result = await linebot_ai.process_message_with_ai(
        message_uuid=uuid4(),
        content="hello",
        line_group_id=None,
        line_user_id="U1",
        reply_token="r1",
    )
    assert result is not None and "沒有設定 system_prompt" in result
    reply_text.assert_awaited_once()
    warning.assert_called_once()


def _mock_claude_response(
    *,
    success: bool = True,
    message: str = "AI回覆",
    error: str | None = None,
    tool_calls: list | None = None,
):
    return SimpleNamespace(
        success=success,
        message=message,
        error=error,
        tool_calls=tool_calls or [],
        tool_timings={},
        input_tokens=1,
        output_tokens=2,
    )


def _patch_process_base(monkeypatch: pytest.MonkeyPatch) -> dict:
    user_module = importlib.import_module("ching_tech_os.services.user")
    permissions_module = importlib.import_module("ching_tech_os.services.permissions")
    linebot_agents_module = importlib.import_module("ching_tech_os.services.linebot_agents")
    mcp_module = importlib.import_module("ching_tech_os.services.mcp")

    monkeypatch.setattr(linebot_ai, "is_bot_message", AsyncMock(return_value=True))
    monkeypatch.setattr(linebot_ai, "should_trigger_ai", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        linebot_ai,
        "get_linebot_agent",
        AsyncMock(
            return_value={
                "model": "claude-sonnet",
                "system_prompt": {"content": "BASE"},
                "tools": ["WebSearch"],
            }
        ),
    )
    monkeypatch.setattr(linebot_ai, "build_system_prompt", AsyncMock(return_value="SYS"))
    monkeypatch.setattr(linebot_ai, "get_conversation_context", AsyncMock(return_value=([], [], [])))
    monkeypatch.setattr(linebot_ai, "get_image_info_by_line_message_id", AsyncMock(return_value=None))
    monkeypatch.setattr(linebot_ai, "get_file_info_by_line_message_id", AsyncMock(return_value=None))
    monkeypatch.setattr(
        user_module,
        "get_user_role_and_permissions",
        AsyncMock(return_value={"role": "admin", "permissions": {"apps": {}}}),
    )
    monkeypatch.setattr(
        permissions_module,
        "get_user_app_permissions_sync",
        lambda *_args, **_kwargs: {"knowledge-base": True},
    )
    monkeypatch.setattr(
        permissions_module,
        "get_mcp_tools_for_user",
        lambda _role, _permissions, tools: tools,
    )
    monkeypatch.setattr(
        mcp_module,
        "get_mcp_tool_names",
        AsyncMock(return_value=["mcp__ching-tech-os__create_share_link"]),
    )
    monkeypatch.setattr(
        linebot_agents_module,
        "get_tool_routing_for_user",
        AsyncMock(return_value={"suppressed_mcp_tools": ["mcp__ching-tech-os__create_share_link"]}),
    )
    monkeypatch.setattr(
        linebot_agents_module,
        "get_tools_for_user",
        AsyncMock(return_value=["mcp__erpnext__list_documents"]),
    )
    monkeypatch.setattr(
        linebot_agents_module,
        "get_mcp_servers_for_user",
        AsyncMock(return_value={"ching-tech-os"}),
    )
    monkeypatch.setattr(linebot_ai, "log_linebot_ai_call", AsyncMock())
    monkeypatch.setattr(linebot_ai, "mark_message_ai_processed", AsyncMock())
    monkeypatch.setattr(linebot_ai, "extract_nanobanana_error", lambda _calls: None)
    monkeypatch.setattr(linebot_ai, "check_nanobanana_timeout", lambda _calls: False)
    monkeypatch.setattr(linebot_ai, "auto_prepare_generated_images", AsyncMock(side_effect=lambda text, _calls: text))
    monkeypatch.setattr(linebot_ai, "save_bot_response", AsyncMock(side_effect=[uuid4(), uuid4(), uuid4()]))
    monkeypatch.setattr(linebot_ai, "save_file_record", AsyncMock())
    monkeypatch.setattr(linebot_ai, "reply_text", AsyncMock())
    monkeypatch.setattr(linebot_ai, "push_text", AsyncMock())

    get_line_user_record = AsyncMock(return_value={"user_id": 123})
    monkeypatch.setattr(linebot_ai, "get_line_user_record", get_line_user_record)

    return {"get_line_user_record": get_line_user_record}


@pytest.mark.asyncio
async def test_process_message_with_ai_success_push_fallback_and_quote_text(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_process_base(monkeypatch)
    monkeypatch.setattr(
        linebot_ai,
        "get_message_content_by_line_message_id",
        AsyncMock(return_value={"content": "X" * 2105, "display_name": "小明", "is_from_bot": False}),
    )
    monkeypatch.setattr(linebot_ai, "call_claude", AsyncMock(return_value=_mock_claude_response()))
    monkeypatch.setattr(
        linebot_ai,
        "parse_ai_response",
        lambda _text: (
            "文字回覆",
            [{
                "type": "image",
                "url": "https://example.com/a.jpg",
                "original_url": "https://example.com/a.jpg",
                "preview_url": "https://example.com/a.jpg",
                "name": "圖1.jpg",
                "nas_path": "ai-images/a.jpg",
            }],
        ),
    )

    send_ai_response = AsyncMock(side_effect=RuntimeError("reply token expired"))
    push_messages = AsyncMock(return_value=(["m-text", "m-img"], None))
    monkeypatch.setattr(linebot_ai, "send_ai_response", send_ai_response)
    monkeypatch.setattr(linebot_ai, "get_line_group_external_id", AsyncMock(return_value="C123"))
    monkeypatch.setattr(linebot_ai, "push_messages", push_messages)

    result = await linebot_ai.process_message_with_ai(
        message_uuid=uuid4(),
        content="幫我處理",
        line_group_id=uuid4(),
        line_user_id="U1",
        reply_token="r1",
        user_display_name="發問者",
        quoted_message_id="q1",
    )

    assert result == "文字回覆"
    send_ai_response.assert_awaited_once()
    push_messages.assert_awaited_once()
    assert linebot_ai.save_file_record.await_count == 1

    prompt_arg = linebot_ai.call_claude.await_args.kwargs["prompt"]
    assert "[回覆 小明 的訊息" in prompt_arg
    assert "user[發問者]: 幫我處理" in prompt_arg
    tools_arg = linebot_ai.call_claude.await_args.kwargs["tools"]
    assert "mcp__ching-tech-os__create_share_link" not in tools_arg
    assert "mcp__erpnext__list_documents" in tools_arg


@pytest.mark.asyncio
async def test_process_message_with_ai_start_research_appends_job_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_process_base(monkeypatch)
    monkeypatch.setattr(linebot_ai, "get_message_content_by_line_message_id", AsyncMock(return_value=None))

    tool_output = json.dumps(
        {
            "success": True,
            "output": json.dumps(
                {"success": True, "job_id": "z9y8x7w6", "status": "started"},
                ensure_ascii=False,
            ),
            "error": "",
            "duration_ms": 12,
        },
        ensure_ascii=False,
    )
    tool_call = SimpleNamespace(
        id="tc-research",
        name="mcp__ching-tech-os__run_skill_script",
        input={"skill": "research-skill", "script": "start-research"},
        output=tool_output,
    )
    monkeypatch.setattr(
        linebot_ai,
        "call_claude",
        AsyncMock(
            return_value=_mock_claude_response(
                success=True,
                message="已開始處理研究需求。",
                tool_calls=[tool_call],
            )
        ),
    )
    monkeypatch.setattr(linebot_ai, "parse_ai_response", lambda text: (text, []))
    send_ai_response = AsyncMock(return_value=["mid"])
    monkeypatch.setattr(linebot_ai, "send_ai_response", send_ai_response)

    result = await linebot_ai.process_message_with_ai(
        message_uuid=uuid4(),
        content="幫我研究這個主題",
        line_group_id=None,
        line_user_id="U1",
        reply_token="r1",
    )

    assert result is not None
    assert "z9y8x7w6" in result
    assert "job_id" in send_ai_response.await_args.kwargs["text"]


@pytest.mark.asyncio
async def test_process_message_with_ai_research_check_disables_web_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_process_base(monkeypatch)
    monkeypatch.setattr(linebot_ai, "get_message_content_by_line_message_id", AsyncMock(return_value=None))
    call_claude = AsyncMock(return_value=_mock_claude_response(success=True, message="進度查詢完成"))
    monkeypatch.setattr(linebot_ai, "call_claude", call_claude)
    monkeypatch.setattr(linebot_ai, "parse_ai_response", lambda text: (text, []))
    monkeypatch.setattr(linebot_ai, "send_ai_response", AsyncMock(return_value=["mid"]))

    await linebot_ai.process_message_with_ai(
        message_uuid=uuid4(),
        content="請查詢研究進度 job_id c904b40d",
        line_group_id=None,
        line_user_id="U1",
        reply_token="r1",
    )

    tools_arg = call_claude.await_args.kwargs["tools"]
    assert "WebSearch" not in tools_arg
    assert "WebFetch" not in tools_arg
    assert "mcp__erpnext__list_documents" in tools_arg


@pytest.mark.asyncio
async def test_process_message_with_ai_check_research_feedback_overrides_model_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_process_base(monkeypatch)
    monkeypatch.setattr(linebot_ai, "get_message_content_by_line_message_id", AsyncMock(return_value=None))

    check_output = json.dumps(
        {
            "success": True,
            "output": json.dumps(
                {
                    "success": True,
                    "job_id": "c904b40d",
                    "status": "completed",
                    "final_summary": "研究完成摘要（來自 worker）",
                    "sources": [{"title": "來源 A", "url": "https://example.com/a"}],
                },
                ensure_ascii=False,
            ),
            "error": "",
            "duration_ms": 45,
        },
        ensure_ascii=False,
    )
    check_call = SimpleNamespace(
        id="tc-check",
        name="mcp__ching-tech-os__run_skill_script",
        input={"skill": "research-skill", "script": "check-research"},
        output=check_output,
    )
    webfetch_call = SimpleNamespace(
        id="tc-webfetch",
        name="WebFetch",
        input={"url": "https://example.com"},
        output="抓到更多內容",
    )
    monkeypatch.setattr(
        linebot_ai,
        "call_claude",
        AsyncMock(
            return_value=_mock_claude_response(
                success=True,
                message="研究報告太簡單，我再去抓網頁整理。",
                tool_calls=[check_call, webfetch_call],
            )
        ),
    )
    monkeypatch.setattr(linebot_ai, "parse_ai_response", lambda text: (text, []))
    send_ai_response = AsyncMock(return_value=["mid"])
    monkeypatch.setattr(linebot_ai, "send_ai_response", send_ai_response)

    result = await linebot_ai.process_message_with_ai(
        message_uuid=uuid4(),
        content="查詢研究進度 c904b40d",
        line_group_id=None,
        line_user_id="U1",
        reply_token="r1",
    )

    assert "研究完成摘要（來自 worker）" in result
    assert "研究報告太簡單" not in result
    assert "來源 A" in send_ai_response.await_args.kwargs["text"]


@pytest.mark.asyncio
async def test_process_message_with_ai_nanobanana_fallback_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_process_base(monkeypatch)
    monkeypatch.setattr(linebot_ai, "get_message_content_by_line_message_id", AsyncMock(return_value=None))
    monkeypatch.setattr(linebot_ai, "call_claude", AsyncMock(return_value=_mock_claude_response(tool_calls=[SimpleNamespace()])))
    monkeypatch.setattr(linebot_ai, "extract_nanobanana_error", lambda _calls: "overloaded")
    monkeypatch.setattr(linebot_ai, "check_nanobanana_timeout", lambda _calls: False)
    monkeypatch.setattr(linebot_ai, "extract_nanobanana_prompt", lambda _calls: "draw a cat")
    monkeypatch.setattr(
        linebot_ai,
        "generate_image_with_fallback",
        AsyncMock(return_value=("ai-images/cat.jpg", "flux", None)),
    )
    monkeypatch.setattr(linebot_ai, "get_fallback_notification", lambda _service: "（已切換備援）")
    monkeypatch.setattr(
        mcp_nas_tools,
        "prepare_file_message",
        AsyncMock(
            return_value='[FILE_MESSAGE:{"type":"image","url":"https://example.com/cat.jpg","original_url":"https://example.com/cat.jpg","name":"cat.jpg","nas_path":"ai-images/cat.jpg"}]'
        ),
    )
    monkeypatch.setattr(
        linebot_ai,
        "parse_ai_response",
        lambda _text: (
            "圖片已生成",
            [{
                "type": "image",
                "url": "https://example.com/cat.jpg",
                "original_url": "https://example.com/cat.jpg",
                "name": "cat.jpg",
                "nas_path": "ai-images/cat.jpg",
            }],
        ),
    )
    monkeypatch.setattr(linebot_ai, "send_ai_response", AsyncMock(return_value=["mid1", "mid2"]))

    result = await linebot_ai.process_message_with_ai(
        message_uuid=uuid4(),
        content="幫我生成圖片",
        line_group_id=None,
        line_user_id="U1",
        reply_token="r1",
    )
    assert result == "圖片已生成"
    linebot_ai.generate_image_with_fallback.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_with_ai_failed_response_with_generated_images(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_process_base(monkeypatch)
    monkeypatch.setattr(linebot_ai, "get_message_content_by_line_message_id", AsyncMock(return_value=None))
    monkeypatch.setattr(
        linebot_ai,
        "call_claude",
        AsyncMock(return_value=_mock_claude_response(success=False, error="timeout", tool_calls=[SimpleNamespace(id="x")])),
    )
    monkeypatch.setattr(linebot_ai, "extract_nanobanana_error", lambda _calls: None)
    monkeypatch.setattr(linebot_ai, "check_nanobanana_timeout", lambda _calls: False)
    monkeypatch.setattr(linebot_ai, "extract_generated_images_from_tool_calls", lambda _calls: ["img1"])
    monkeypatch.setattr(linebot_ai, "auto_prepare_generated_images", AsyncMock(return_value="補救訊息"))
    monkeypatch.setattr(linebot_ai, "parse_ai_response", lambda _text: ("補救文字", []))
    monkeypatch.setattr(linebot_ai, "send_ai_response", AsyncMock(return_value=["mid"]))

    result = await linebot_ai.process_message_with_ai(
        message_uuid=uuid4(),
        content="生成失敗也要回覆",
        line_group_id=None,
        line_user_id="U1",
        reply_token="r1",
    )
    assert result == "補救文字"


@pytest.mark.asyncio
async def test_process_message_with_ai_failed_response_without_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_process_base(monkeypatch)
    monkeypatch.setattr(linebot_ai, "get_message_content_by_line_message_id", AsyncMock(return_value=None))
    monkeypatch.setattr(
        linebot_ai,
        "call_claude",
        AsyncMock(return_value=_mock_claude_response(success=False, error="timeout", tool_calls=[])),
    )
    monkeypatch.setattr(linebot_ai, "extract_nanobanana_error", lambda _calls: None)
    monkeypatch.setattr(linebot_ai, "check_nanobanana_timeout", lambda _calls: False)

    result = await linebot_ai.process_message_with_ai(
        message_uuid=uuid4(),
        content="失敗且無工具",
        line_group_id=None,
        line_user_id="U1",
        reply_token="r1",
    )
    # 超時/失敗時現在會回覆錯誤提示，不再 return None
    assert result == "AI回覆"
