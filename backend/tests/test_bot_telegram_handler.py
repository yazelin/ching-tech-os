"""bot_telegram.handler 測試。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ching_tech_os.services.bot_telegram import handler


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_ensure_user_group_and_save_message_paths() -> None:
    conn = AsyncMock()

    # user: 已存在且名稱變更
    conn.fetchrow = AsyncMock(return_value={"id": "u1", "display_name": "old"})
    user_id = await handler._ensure_bot_user(SimpleNamespace(id=1, full_name="new"), conn)
    assert user_id == "u1"
    conn.execute.assert_awaited_once()

    # user: 不存在，新建
    conn.fetchrow = AsyncMock(side_effect=[None, {"id": "u2"}])
    user_id = await handler._ensure_bot_user(SimpleNamespace(id=2, full_name="user2"), conn)
    assert user_id == "u2"

    # group: 已存在
    conn.fetchrow = AsyncMock(return_value={"id": "g1", "name": "群組A"})
    group_id = await handler._ensure_bot_group(SimpleNamespace(id=-1, title="群組A"), conn)
    assert group_id == "g1"

    # group: 不存在，新建
    conn.fetchrow = AsyncMock(side_effect=[None, {"id": "g2"}])
    group_id = await handler._ensure_bot_group(SimpleNamespace(id=-2, title="群組B"), conn)
    assert group_id == "g2"

    conn.fetchrow = AsyncMock(return_value={"id": "m1"})
    msg_id = await handler._save_message(
        conn,
        message_id="tg_1",
        bot_user_id="u1",
        bot_group_id=None,
        message_type="text",
        content="hello",
        is_from_bot=False,
    )
    assert msg_id == "m1"


def test_should_respond_prefix_and_strip_paths() -> None:
    reply_message = SimpleNamespace(from_user=SimpleNamespace(is_bot=True))
    m1 = SimpleNamespace(reply_to_message=reply_message, entities=None, text="hi")
    assert handler._should_respond_in_group(m1, bot_username="ctos_bot") is True

    mention_entity = SimpleNamespace(type="mention", offset=0, length=9)
    m2 = SimpleNamespace(reply_to_message=None, entities=[mention_entity], text="@ctos_bot hi")
    assert handler._should_respond_in_group(m2, bot_username="CTOS_BOT") is True

    m3 = SimpleNamespace(reply_to_message=None, entities=None, text="hello")
    assert handler._should_respond_in_group(m3, bot_username="ctos_bot") is False

    assert handler._prefix_user("x", SimpleNamespace(full_name="小明")) == "user[小明]: x"
    assert handler._prefix_user("x", None) == "x"
    assert handler._strip_bot_mention("@Ctos_Bot 幫我", "ctos_bot") == "幫我"


@pytest.mark.asyncio
async def test_extract_reply_from_message_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    # 圖片下載成功
    file_obj = SimpleNamespace(download_to_drive=AsyncMock())
    bot = SimpleNamespace(get_file=AsyncMock(return_value=file_obj))
    reply = SimpleNamespace(
        photo=[SimpleNamespace(file_id="f1", file_unique_id="u1")],
        document=None,
        caption=None,
        text=None,
    )
    result = await handler._extract_reply_from_message(reply, bot=bot)
    assert "[回覆圖片:" in result

    # 圖片下載失敗
    bot_fail = SimpleNamespace(get_file=AsyncMock(side_effect=RuntimeError("x")))
    result = await handler._extract_reply_from_message(reply, bot=bot_fail)
    assert result.startswith("[回覆圖片]")

    # 檔案可讀取
    monkeypatch.setattr(
        "ching_tech_os.services.bot.media.is_readable_file",
        lambda _name: True,
    )
    reply_doc = SimpleNamespace(
        photo=None,
        document=SimpleNamespace(file_id="d1", file_unique_id="du1", file_name="a.txt"),
        caption=None,
        text=None,
    )
    result = await handler._extract_reply_from_message(reply_doc, bot=bot)
    assert "[回覆檔案:" in result

    # 檔案不可讀取 + caption/text 截斷
    monkeypatch.setattr(
        "ching_tech_os.services.bot.media.is_readable_file",
        lambda _name: False,
    )
    reply_doc.caption = "c" * 700
    result = await handler._extract_reply_from_message(reply_doc, bot=bot)
    assert "不支援讀取的格式" in result
    assert "[附文:" in result

    reply_text = SimpleNamespace(
        photo=None,
        document=None,
        caption=None,
        text="t" * 700,
    )
    result = await handler._extract_reply_from_message(reply_text, bot=bot)
    assert "[回覆訊息:" in result


@pytest.mark.asyncio
async def test_get_reply_context_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    # 無回覆訊息
    msg = SimpleNamespace(reply_to_message=None)
    assert await handler._get_reply_context(msg) == ""

    # DB 查不到，fallback 到直接解析
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    monkeypatch.setattr(handler, "get_connection", lambda: _CM(conn))
    fallback = AsyncMock(return_value="[fallback]\n")
    monkeypatch.setattr(handler, "_extract_reply_from_message", fallback)
    msg = SimpleNamespace(reply_to_message=SimpleNamespace(message_id=1))
    assert await handler._get_reply_context(msg) == "[fallback]\n"

    # 圖片
    conn.fetchrow = AsyncMock(return_value={"message_type": "image", "nas_path": "nas/a.jpg", "file_name": None, "content": None})
    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.ensure_temp_image",
        AsyncMock(return_value="/tmp/a.jpg"),
    )
    assert "[回覆圖片: /tmp/a.jpg]" in await handler._get_reply_context(msg)

    # 檔案
    conn.fetchrow = AsyncMock(return_value={"message_type": "file", "nas_path": "nas/a.txt", "file_name": "a.txt", "content": None})
    monkeypatch.setattr(
        "ching_tech_os.services.bot.media.is_readable_file",
        lambda _name: True,
    )
    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.ensure_temp_file",
        AsyncMock(return_value="/tmp/a.txt"),
    )
    assert "[回覆檔案: /tmp/a.txt]" in await handler._get_reply_context(msg)

    # 文字
    conn.fetchrow = AsyncMock(return_value={"message_type": "text", "nas_path": None, "file_name": None, "content": "hello"})
    assert await handler._get_reply_context(msg) == "[回覆訊息: hello]\n"

    # DB 例外
    conn.fetchrow = AsyncMock(side_effect=RuntimeError("db"))
    assert await handler._get_reply_context(msg) == ""


@pytest.mark.asyncio
async def test_handle_update_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = SimpleNamespace(
        bot_username="ctos_bot",
        ensure_bot_info=AsyncMock(),
        bot=SimpleNamespace(),
    )
    handle_text = AsyncMock()
    handle_media = AsyncMock()
    monkeypatch.setattr(handler, "_handle_text", handle_text)
    monkeypatch.setattr(handler, "_handle_media", handle_media)

    # 無 message
    await handler.handle_update(SimpleNamespace(update_id=1, message=None), adapter)
    adapter.ensure_bot_info.assert_not_called()

    # 群組文字：未觸發
    monkeypatch.setattr(handler, "_should_respond_in_group", lambda *_args, **_kwargs: False)
    message = SimpleNamespace(
        chat=SimpleNamespace(id=-1, type="group"),
        from_user=SimpleNamespace(full_name="A"),
        text="hello",
        photo=None,
        document=None,
        reply_to_message=None,
        message_id=10,
    )
    await handler.handle_update(SimpleNamespace(update_id=2, message=message), adapter)
    handle_text.assert_not_called()

    # 群組文字：觸發後呼叫 _handle_text
    monkeypatch.setattr(handler, "_should_respond_in_group", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(handler, "_strip_bot_mention", lambda _text, _bot: "處理內容")
    await handler.handle_update(SimpleNamespace(update_id=3, message=message), adapter)
    handle_text.assert_awaited()

    # 群組圖片：非回覆 bot 不處理
    handle_media.reset_mock()
    message_photo = SimpleNamespace(
        chat=SimpleNamespace(id=-1, type="group"),
        from_user=SimpleNamespace(full_name="A"),
        text=None,
        photo=[SimpleNamespace()],
        document=None,
        reply_to_message=None,
        message_id=11,
    )
    await handler.handle_update(SimpleNamespace(update_id=4, message=message_photo), adapter)
    handle_media.assert_not_called()

    # 群組圖片：回覆 bot 觸發
    message_photo.reply_to_message = SimpleNamespace(from_user=SimpleNamespace(is_bot=True))
    await handler.handle_update(SimpleNamespace(update_id=5, message=message_photo), adapter)
    handle_media.assert_awaited()


@pytest.mark.asyncio
async def test_handle_text_command_and_access_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    monkeypatch.setattr(handler, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(handler, "_ensure_bot_user", AsyncMock(return_value="u1"))
    monkeypatch.setattr(handler, "_ensure_bot_group", AsyncMock(return_value="g1"))
    monkeypatch.setattr(handler, "_get_reply_context", AsyncMock(return_value="[回覆]\n"))
    ai_handle = AsyncMock()
    monkeypatch.setattr(handler, "_handle_text_with_ai", ai_handle)
    monkeypatch.setattr(handler, "check_line_access", AsyncMock(return_value=(True, None)))
    monkeypatch.setattr(handler, "is_binding_code_format", AsyncMock(return_value=False))

    adapter = SimpleNamespace(send_text=AsyncMock(), bot=SimpleNamespace())
    message = SimpleNamespace(message_id=1)
    chat = SimpleNamespace(id=100, type="private")
    user = SimpleNamespace(id=9, full_name="小明")

    # 確保 CommandRouter 已註冊指令
    from ching_tech_os.services.bot import commands as bot_commands
    from ching_tech_os.services.bot import command_handlers
    from ching_tech_os.services.bot.command_handlers import register_builtin_commands, get_welcome_message

    register_builtin_commands()
    # mock get_command_user_context 避免 DB 查詢
    monkeypatch.setattr(bot_commands, "get_command_user_context", AsyncMock(return_value=(None, False)))

    # /start（現在走 CommandRouter）
    await handler._handle_text(message, "/start", "100", chat, user, False, adapter)
    adapter.send_text.assert_awaited_with("100", get_welcome_message())

    # /help（現在走 CommandRouter）
    adapter.send_text.reset_mock()
    await handler._handle_text(message, "/help", "100", chat, user, False, adapter)
    help_text = adapter.send_text.await_args.args[1]
    assert "指令列表" in help_text
    assert "/start" in help_text
    monkeypatch.setattr(command_handlers, "reset_conversation", AsyncMock())
    # mock get_user_role_and_permissions 避免 DB 查詢
    monkeypatch.setattr(
        handler, "get_user_role_and_permissions",
        AsyncMock(return_value={"role": "user"}),
    )
    adapter.send_text.reset_mock()
    await handler._handle_text(message, "/reset", "100", chat, user, False, adapter)
    adapter.send_text.assert_awaited_once()
    assert "對話" in adapter.send_text.await_args.args[1] or "清除" in adapter.send_text.await_args.args[1]

    # 綁定碼
    monkeypatch.setattr(handler, "is_binding_code_format", AsyncMock(return_value=True))
    monkeypatch.setattr(handler, "verify_binding_code", AsyncMock(return_value=(True, "綁定成功")))
    adapter.send_text.reset_mock()
    await handler._handle_text(message, "123456", "100", chat, user, False, adapter)
    adapter.send_text.assert_awaited_with("100", "綁定成功")

    # 未綁定拒絕
    monkeypatch.setattr(handler, "check_line_access", AsyncMock(return_value=(False, "user_not_bound")))
    monkeypatch.setattr(handler, "is_binding_code_format", AsyncMock(return_value=False))
    adapter.send_text.reset_mock()
    await handler._handle_text(message, "hi", "100", chat, user, False, adapter)
    assert "請先在 CTOS 系統綁定" in adapter.send_text.await_args.args[1]

    # 正常進 AI
    monkeypatch.setattr(handler, "check_line_access", AsyncMock(return_value=(True, None)))
    await handler._handle_text(message, "hello", "100", chat, user, False, adapter)
    assert ai_handle.await_args.args[0].startswith("[回覆]\nuser[小明]: hello")

    # AI 失敗 fallback
    monkeypatch.setattr(handler, "_handle_text_with_ai", AsyncMock(side_effect=RuntimeError("x")))
    adapter.send_text.reset_mock()
    await handler._handle_text(message, "hello", "100", chat, user, False, adapter)
    adapter.send_text.assert_awaited_with("100", "抱歉，處理訊息時發生錯誤，請稍後再試。")


@pytest.mark.asyncio
async def test_restricted_mode_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    """測試 Telegram 受限模式：指令攔截（頂層）+ AI 處理 + 錯誤處理"""
    conn = AsyncMock()
    monkeypatch.setattr(handler, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(handler, "_ensure_bot_user", AsyncMock(return_value="u1"))
    monkeypatch.setattr(handler, "_save_message", AsyncMock(return_value="msg-r1"))
    monkeypatch.setattr(handler, "is_binding_code_format", AsyncMock(return_value=False))

    # 未綁定用戶，restricted 策略
    monkeypatch.setattr(
        handler, "check_line_access",
        AsyncMock(return_value=(False, "user_not_bound")),
    )

    adapter = SimpleNamespace(send_text=AsyncMock(), bot=SimpleNamespace())
    message = SimpleNamespace(message_id=1)
    chat = SimpleNamespace(id=100, type="private")
    user = SimpleNamespace(id=9, full_name="小明", username="xm")

    # 註冊內建指令
    from ching_tech_os.services.bot import command_handlers
    from ching_tech_os.services.bot.command_handlers import register_builtin_commands
    register_builtin_commands()
    monkeypatch.setattr(command_handlers, "reset_conversation", AsyncMock())

    # --- 1. 斜線指令由頂層 CommandRouter 攔截（不到 restricted 分支）---
    from ching_tech_os.services.bot.identity_router import UnboundRouteResult
    monkeypatch.setattr(
        "ching_tech_os.services.bot.identity_router.route_unbound",
        lambda **kw: UnboundRouteResult(action="restricted"),
    )
    adapter.send_text.reset_mock()
    await handler._handle_text(message, "/reset", "100", chat, user, False, adapter)
    adapter.send_text.assert_awaited_once()
    assert "對話" in adapter.send_text.await_args.args[1]

    # --- 2. 受限模式 AI 處理成功（含 message_uuid 傳遞）---
    mock_restricted = AsyncMock(return_value="受限模式回覆")
    monkeypatch.setattr(
        "ching_tech_os.services.bot.identity_router.handle_restricted_mode",
        mock_restricted,
    )
    adapter.send_text.reset_mock()
    await handler._handle_text(message, "你好", "100", chat, user, False, adapter)
    adapter.send_text.assert_awaited_with("100", "受限模式回覆")
    # 確認 message_uuid 和 str(bot_user_id) 有傳入
    call_kwargs = mock_restricted.call_args.kwargs
    assert call_kwargs["message_uuid"] == "msg-r1"
    assert call_kwargs["bot_user_id"] == "u1"

    # --- 3. 受限模式 AI 回傳 None → 不送訊息 ---
    monkeypatch.setattr(
        "ching_tech_os.services.bot.identity_router.handle_restricted_mode",
        AsyncMock(return_value=None),
    )
    adapter.send_text.reset_mock()
    await handler._handle_text(message, "你好", "100", chat, user, False, adapter)
    adapter.send_text.assert_not_awaited()

    # --- 4. 受限模式 AI 拋出例外 → 錯誤訊息 ---
    monkeypatch.setattr(
        "ching_tech_os.services.bot.identity_router.handle_restricted_mode",
        AsyncMock(side_effect=RuntimeError("AI boom")),
    )
    adapter.send_text.reset_mock()
    await handler._handle_text(message, "你好", "100", chat, user, False, adapter)
    assert "發生錯誤" in adapter.send_text.await_args.args[1]

    # --- 5. silent 路由（群組）→ 不送訊息 ---
    monkeypatch.setattr(
        "ching_tech_os.services.bot.identity_router.route_unbound",
        lambda **kw: UnboundRouteResult(action="silent"),
    )
    adapter.send_text.reset_mock()
    await handler._handle_text(message, "你好", "100", chat, user, True, adapter)
    adapter.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_media_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    monkeypatch.setattr(handler, "get_connection", lambda: _CM(conn))
    monkeypatch.setattr(handler, "_ensure_bot_user", AsyncMock(return_value="u1"))
    monkeypatch.setattr(handler, "_ensure_bot_group", AsyncMock(return_value=None))
    monkeypatch.setattr(handler, "check_line_access", AsyncMock(return_value=(True, None)))
    monkeypatch.setattr(handler, "_save_message", AsyncMock(return_value="m1"))
    ai_handle = AsyncMock()
    monkeypatch.setattr(handler, "_handle_text_with_ai", ai_handle)

    adapter = SimpleNamespace(bot=SimpleNamespace(), send_text=AsyncMock())
    chat = SimpleNamespace(id=100, type="private")
    user = SimpleNamespace(id=9, full_name="小明")

    # 圖片成功
    message = SimpleNamespace(
        message_id=1,
        caption="請分析",
        photo=[SimpleNamespace()],
        document=None,
    )
    monkeypatch.setattr(handler, "download_telegram_photo", AsyncMock(return_value="nas/img.jpg"))
    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.ensure_temp_image",
        AsyncMock(return_value="/tmp/img.jpg"),
    )
    await handler._handle_media(message, "image", "100", chat, user, False, adapter)
    assert "[上傳圖片: /tmp/img.jpg]" in ai_handle.await_args.args[0]

    # 圖片暫存失敗
    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.ensure_temp_image",
        AsyncMock(return_value=None),
    )
    adapter.send_text.reset_mock()
    await handler._handle_media(message, "image", "100", chat, user, False, adapter)
    adapter.send_text.assert_awaited_with("100", "圖片處理失敗。")

    # 檔案不可讀
    message_file = SimpleNamespace(
        message_id=2,
        caption="",
        photo=None,
        document=SimpleNamespace(file_name="a.bin", file_size=10),
    )
    monkeypatch.setattr(handler, "download_telegram_document", AsyncMock(return_value="nas/a.bin"))
    monkeypatch.setattr(
        "ching_tech_os.services.bot.media.is_readable_file",
        lambda _name: False,
    )
    adapter.send_text.reset_mock()
    await handler._handle_media(message_file, "file", "100", chat, user, False, adapter)
    assert "無法由 AI 讀取" in adapter.send_text.await_args.args[1]

    # 檔案可讀但暫存失敗
    monkeypatch.setattr(
        "ching_tech_os.services.bot.media.is_readable_file",
        lambda _name: True,
    )
    monkeypatch.setattr(
        "ching_tech_os.services.bot_line.ensure_temp_file",
        AsyncMock(return_value=None),
    )
    adapter.send_text.reset_mock()
    await handler._handle_media(message_file, "file", "100", chat, user, False, adapter)
    adapter.send_text.assert_awaited_with("100", "檔案處理失敗。")


@pytest.mark.asyncio
async def test_handle_text_with_ai_success(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"user_id": 1})
    monkeypatch.setattr(handler, "get_connection", lambda: _CM(conn))

    save_message = AsyncMock(side_effect=["msg-user", "msg-bot", "msg-img"])
    monkeypatch.setattr(handler, "_save_message", save_message)
    monkeypatch.setattr(handler, "get_conversation_context", AsyncMock(return_value=([{"role": "user", "content": "h"}], [], [])))
    monkeypatch.setattr(
        handler,
        "get_linebot_agent",
        AsyncMock(return_value={"model": "claude-sonnet", "system_prompt": {"content": "你是助理"}, "tools": ["WebSearch"]}),
    )
    monkeypatch.setattr(handler, "get_user_role_and_permissions", AsyncMock(return_value={"role": "admin", "permissions": [], "user_data": {}}))
    monkeypatch.setattr(handler, "get_user_app_permissions_sync", lambda *_args, **_kwargs: {"knowledge-base": True})
    monkeypatch.setattr(handler, "build_system_prompt", AsyncMock(return_value="sys"))
    monkeypatch.setattr(handler, "get_mcp_tool_names", AsyncMock(return_value=["Read", "search_knowledge"]))
    monkeypatch.setattr(handler, "get_mcp_tools_for_user", lambda *_args: ["Read", "search_knowledge"])
    monkeypatch.setattr(handler, "get_tool_routing_for_user", AsyncMock(return_value={}))
    monkeypatch.setattr(handler, "get_tools_for_user", AsyncMock(return_value=["create_share_link"]))
    monkeypatch.setattr(handler, "get_mcp_servers_for_user", AsyncMock(return_value=["ching-tech-os"]))
    monkeypatch.setattr(handler, "log_linebot_ai_call", AsyncMock())
    monkeypatch.setattr(handler, "auto_prepare_generated_images", AsyncMock(return_value="ai-response"))
    monkeypatch.setattr(
        handler,
        "parse_ai_response",
        lambda _msg: (
            "AI 回覆",
            [{"type": "image", "url": "https://img", "nas_path": "nas/img.jpg", "name": "img.jpg"}],
        ),
    )
    monkeypatch.setattr(handler, "save_file_record", AsyncMock())

    # 用遞增時間確保 progress update 節流分支被覆蓋
    ticks = iter([0.0, 1.2, 2.5, 3.8, 5.0, 6.2, 7.4, 8.6])
    monkeypatch.setattr(handler.time, "time", lambda: next(ticks))

    async def _fake_call_claude(**kwargs):
        await kwargs["on_tool_start"]("search_knowledge", {"query": "abc"})
        await kwargs["on_tool_end"]("search_knowledge", {"duration_ms": 1200})
        return SimpleNamespace(success=True, message="ok", tool_calls=[], error=None)

    monkeypatch.setattr(handler, "call_claude", _fake_call_claude)

    adapter = SimpleNamespace(
        bot=SimpleNamespace(send_chat_action=AsyncMock()),
        send_text=AsyncMock(return_value=SimpleNamespace(message_id="101")),
        send_image=AsyncMock(return_value=SimpleNamespace(message_id="202")),
        send_file=AsyncMock(return_value=SimpleNamespace(message_id="303")),
        send_progress=AsyncMock(return_value=SimpleNamespace(message_id="p1")),
        update_progress=AsyncMock(return_value=None),
        finish_progress=AsyncMock(return_value=None),
    )

    await handler._handle_text_with_ai(
        text="hello",
        chat_id="100",
        user=SimpleNamespace(id=9),
        message_id=88,
        bot_user_id="u1",
        bot_group_id=None,
        is_group=False,
        adapter=adapter,
    )

    adapter.send_progress.assert_awaited_once()
    adapter.update_progress.assert_awaited()
    adapter.finish_progress.assert_awaited_once()
    adapter.send_text.assert_awaited()
    adapter.send_image.assert_awaited_once()
    assert save_message.await_count == 3


@pytest.mark.asyncio
async def test_handle_text_with_ai_failure_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(handler, "get_conversation_context", AsyncMock(return_value=([], [], [])))
    monkeypatch.setattr(handler, "_save_message", AsyncMock(return_value="msg-user"))
    monkeypatch.setattr(handler, "get_connection", lambda: _CM(AsyncMock(fetchrow=AsyncMock(return_value=None))))

    adapter = SimpleNamespace(
        bot=SimpleNamespace(send_chat_action=AsyncMock(side_effect=RuntimeError("typing failed"))),
        send_text=AsyncMock(return_value=SimpleNamespace(message_id="101")),
        send_progress=AsyncMock(return_value=SimpleNamespace(message_id="p1")),
        update_progress=AsyncMock(return_value=None),
        finish_progress=AsyncMock(return_value=None),
    )

    # Agent 不存在
    monkeypatch.setattr(handler, "get_linebot_agent", AsyncMock(return_value=None))
    await handler._handle_text_with_ai(
        text="hello",
        chat_id="100",
        user=SimpleNamespace(id=9),
        message_id=1,
        bot_user_id="u1",
        bot_group_id=None,
        is_group=False,
        adapter=adapter,
    )
    assert "尚未設定 AI Agent" in adapter.send_text.await_args.args[1]

    # Agent 沒有 system_prompt
    adapter.send_text.reset_mock()
    monkeypatch.setattr(
        handler,
        "get_linebot_agent",
        AsyncMock(return_value={"model": "claude-sonnet", "system_prompt": {}, "tools": []}),
    )
    await handler._handle_text_with_ai(
        text="hello",
        chat_id="100",
        user=SimpleNamespace(id=9),
        message_id=1,
        bot_user_id="u1",
        bot_group_id=None,
        is_group=False,
        adapter=adapter,
    )
    assert "AI 設定錯誤" in adapter.send_text.await_args.args[1]

    # Claude 失敗
    adapter.send_text.reset_mock()
    monkeypatch.setattr(
        handler,
        "get_linebot_agent",
        AsyncMock(return_value={"model": "claude-sonnet", "system_prompt": {"content": "ok"}, "tools": []}),
    )
    monkeypatch.setattr(handler, "get_user_app_permissions_sync", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(handler, "build_system_prompt", AsyncMock(return_value="sys"))
    monkeypatch.setattr(handler, "get_mcp_tool_names", AsyncMock(return_value=[]))
    monkeypatch.setattr(handler, "get_mcp_tools_for_user", lambda *_args: [])
    monkeypatch.setattr(handler, "get_tool_routing_for_user", AsyncMock(return_value={}))
    monkeypatch.setattr(handler, "get_tools_for_user", AsyncMock(return_value=[]))
    monkeypatch.setattr(handler, "get_mcp_servers_for_user", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        handler,
        "call_claude",
        AsyncMock(return_value=SimpleNamespace(success=False, message="", tool_calls=[], error="timeout")),
    )
    monkeypatch.setattr(handler, "log_linebot_ai_call", AsyncMock())
    await handler._handle_text_with_ai(
        text="hello",
        chat_id="100",
        user=SimpleNamespace(id=9),
        message_id=1,
        bot_user_id="u1",
        bot_group_id=None,
        is_group=False,
        adapter=adapter,
    )
    assert adapter.send_text.await_args.args[1] == "AI 回應失敗，請稍後再試。"
