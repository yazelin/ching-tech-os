"""AI Log 依用戶篩選（migration 029）測試。

涵蓋：model 欄位、create_log 的 INSERT 參數、每個呼叫端帶入的 user_id 來源、
get_logs／get_log_stats 的 where 子句（user_id=5 與 user_id=0 兩種語意）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ching_tech_os.models.ai import AiLogCreate, AiLogFilter, AiLogListItem, AiLogResponse
from ching_tech_os.services import ai_manager


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log_row(**over) -> dict:
    row = {
        "id": uuid4(),
        "agent_id": None,
        "prompt_id": None,
        "context_type": "web-chat",
        "context_id": "c1",
        "input_prompt": "in",
        "system_prompt": None,
        "allowed_tools": None,
        "raw_response": "ok",
        "parsed_response": None,
        "model": "m",
        "success": True,
        "error_message": None,
        "duration_ms": 1,
        "input_tokens": 1,
        "output_tokens": 2,
        "user_id": 7,
        "created_at": _now(),
    }
    row.update(over)
    return row


# ============================================================
# 1. Model 欄位
# ============================================================


def test_ai_log_create_has_optional_user_id() -> None:
    assert AiLogCreate(input_prompt="x").user_id is None
    assert AiLogCreate(input_prompt="x", user_id=5).user_id == 5


def test_ai_log_response_and_list_item_have_user_fields() -> None:
    detail = AiLogResponse(
        id=uuid4(),
        agent_id=None,
        prompt_id=None,
        context_type=None,
        context_id=None,
        input_prompt="in",
        raw_response=None,
        parsed_response=None,
        model=None,
        success=True,
        error_message=None,
        duration_ms=None,
        input_tokens=None,
        output_tokens=None,
        created_at=_now(),
    )
    assert detail.user_id is None and detail.username is None

    item = AiLogListItem(
        id=uuid4(),
        agent_id=None,
        agent_name=None,
        context_type=None,
        success=True,
        duration_ms=None,
        input_tokens=None,
        output_tokens=None,
        created_at=_now(),
        user_id=9,
        username="alice",
    )
    assert item.user_id == 9 and item.username == "alice"


def test_ai_log_filter_has_user_id() -> None:
    assert AiLogFilter().user_id is None
    assert AiLogFilter(user_id=0).user_id == 0


# ============================================================
# 2. create_log 帶入 user_id
# ============================================================


@pytest.mark.asyncio
async def test_create_log_passes_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_log_row(user_id=42))
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    result = await ai_manager.create_log(AiLogCreate(input_prompt="in", user_id=42))

    sql = conn.fetchrow.await_args.args[0]
    assert "user_id" in sql
    # user_id 是最後一個 INSERT 參數
    assert conn.fetchrow.await_args.args[-1] == 42
    assert result["user_id"] == 42


@pytest.mark.asyncio
async def test_create_log_user_id_defaults_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_log_row(user_id=None))
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    await ai_manager.create_log(AiLogCreate(input_prompt="in"))
    assert conn.fetchrow.await_args.args[-1] is None


# ============================================================
# 3. 讀端：LEFT JOIN users 取 username、where 子句
# ============================================================


@pytest.mark.asyncio
async def test_get_logs_selects_username(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"total": 1})
    conn.fetch = AsyncMock(return_value=[
        {
            "id": uuid4(),
            "agent_id": None,
            "agent_name": None,
            "context_type": "web-chat",
            "model": "m",
            "input_prompt": "p",
            "allowed_tools": None,
            "parsed_response": None,
            "success": True,
            "duration_ms": 1,
            "input_tokens": 1,
            "output_tokens": 2,
            "user_id": 7,
            "username": "alice",
            "created_at": _now(),
        }
    ])
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    items, total = await ai_manager.get_logs(AiLogFilter(), page=1, page_size=10)

    list_sql = conn.fetch.await_args.args[0]
    assert "LEFT JOIN users u ON l.user_id = u.id" in list_sql
    assert "u.username" in list_sql
    assert total == 1
    assert items[0]["user_id"] == 7 and items[0]["username"] == "alice"


@pytest.mark.asyncio
async def test_get_log_detail_selects_username(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_log_row(agent_name=None, username="bob"))
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    detail = await ai_manager.get_log(uuid4())

    sql = conn.fetchrow.await_args.args[0]
    assert "LEFT JOIN users u ON l.user_id = u.id" in sql
    assert "u.username" in sql
    assert detail["username"] == "bob"


@pytest.mark.asyncio
async def test_get_logs_filters_by_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"total": 0})
    conn.fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    await ai_manager.get_logs(AiLogFilter(user_id=5), page=1, page_size=10)

    count_call = conn.fetchrow.await_args
    assert "l.user_id = $1" in count_call.args[0]
    assert count_call.args[1] == 5


@pytest.mark.asyncio
async def test_get_logs_user_id_zero_means_null(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"total": 0})
    conn.fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    await ai_manager.get_logs(AiLogFilter(user_id=0), page=1, page_size=10)

    count_call = conn.fetchrow.await_args
    assert "l.user_id IS NULL" in count_call.args[0]
    # 不應該把 0 當成參數送出去（只有 limit/offset 會進 fetch）
    assert len(count_call.args) == 1


@pytest.mark.asyncio
async def test_get_log_stats_filters_by_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={
        "total_calls": 2,
        "success_count": 1,
        "failure_count": 1,
        "avg_duration_ms": 5.0,
        "total_input_tokens": 1,
        "total_output_tokens": 2,
    })
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    await ai_manager.get_log_stats(user_id=5)
    call = conn.fetchrow.await_args
    assert "user_id = $1" in call.args[0]
    assert call.args[1] == 5


@pytest.mark.asyncio
async def test_get_log_stats_user_id_zero_means_null(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={
        "total_calls": 0,
        "success_count": 0,
        "failure_count": 0,
        "avg_duration_ms": None,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    })
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    await ai_manager.get_log_stats(user_id=0)
    call = conn.fetchrow.await_args
    assert "user_id IS NULL" in call.args[0]
    assert len(call.args) == 1


# ============================================================
# 4. 每個呼叫端帶入的 user_id 來源
# ============================================================


class _FakeSio:
    """Socket.IO 假 server：連線身分由 connect 存進 session。"""

    def __init__(self) -> None:
        self.handlers: dict = {}
        self.emit = AsyncMock()
        self.disconnect = AsyncMock()

    def event(self, fn):
        self.handlers[fn.__name__] = fn
        return fn

    async def get_session(self, _sid):
        return {"user_id": 77, "role": "user", "app_permissions": {}, "token": "tok"}


def _stub_socket_session(monkeypatch, user_id: int = 77):
    """web-chat 兩個事件進入時都會重新解析一次 token，身分以它為準。"""
    import ching_tech_os.api.auth as auth_api
    from ching_tech_os.models.auth import SessionData

    now = _now()
    session = SessionData(
        username="tester",
        password="x",
        nas_host="localhost",
        user_id=user_id,
        created_at=now,
        expires_at=now,
        role="user",
        app_permissions={},
        read_only=False,
    )
    monkeypatch.setattr(auth_api, "_resolve_session", AsyncMock(return_value=session))
    return session


def _ai_response(success: bool = True, message: str = "ok", error: str | None = None):
    from ching_tech_os.services.ai_provider import AIResponse

    return AIResponse(
        success=success,
        message=message,
        error=error,
        tool_calls=[],
        input_tokens=1,
        output_tokens=2,
        provider="claude",
        actual_model="claude-sonnet",
    )


def _patch_web_chat(monkeypatch, ai_api, *, chat_id, success: bool = True):
    monkeypatch.setattr(
        ai_api.ai_chat,
        "get_chat",
        AsyncMock(return_value={
            "id": chat_id,
            "user_id": 77,
            "title": "對話",
            "prompt_name": "agent-a",
            "messages": [],
        }),
    )
    monkeypatch.setattr(ai_api.ai_chat, "get_agent_system_prompt", AsyncMock(return_value="sys"))
    monkeypatch.setattr(
        ai_api.ai_chat,
        "get_agent_config",
        AsyncMock(return_value={"id": uuid4(), "tools": None}),
    )
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_messages", AsyncMock())
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_title", AsyncMock())
    monkeypatch.setattr(
        ai_api,
        "call_ai",
        AsyncMock(return_value=_ai_response(success=success, error=None if success else "忙碌")),
    )
    monkeypatch.setattr(ai_api, "log_message", AsyncMock())
    create_log = AsyncMock()
    monkeypatch.setattr(ai_api.ai_manager, "create_log", create_log)
    return create_log


@pytest.mark.parametrize("success", [True, False])
@pytest.mark.asyncio
async def test_web_chat_log_uses_socket_identity(
    monkeypatch: pytest.MonkeyPatch, success: bool
) -> None:
    """api/ai.py web-chat：user_id 來自 Socket.IO 連線身分（#186 後重新解析的 session）。"""
    from ching_tech_os.api import ai as ai_api

    sio = _FakeSio()
    ai_api.register_events(sio)
    _stub_socket_session(monkeypatch, user_id=77)
    chat_id = uuid4()
    create_log = _patch_web_chat(monkeypatch, ai_api, chat_id=chat_id, success=success)

    await sio.handlers["ai_chat_event"](
        "sid-1", {"chatId": str(chat_id), "message": "嗨", "model": "claude-sonnet"}
    )

    create_log.assert_awaited_once()
    assert create_log.await_args.args[0].user_id == 77


@pytest.mark.asyncio
async def test_compress_chat_log_uses_socket_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """api/ai.py compress：user_id 同樣來自連線身分。"""
    from ching_tech_os.api import ai as ai_api

    sio = _FakeSio()
    ai_api.register_events(sio)
    _stub_socket_session(monkeypatch, user_id=77)
    chat_id = uuid4()

    messages = [{"role": "user", "content": f"m{i}", "timestamp": i} for i in range(14)]
    monkeypatch.setattr(
        ai_api.ai_chat,
        "get_chat",
        AsyncMock(return_value={"id": chat_id, "user_id": 77, "messages": messages}),
    )
    monkeypatch.setattr(ai_api.ai_chat, "update_chat_messages", AsyncMock())
    monkeypatch.setattr(
        ai_api.ai_manager, "get_prompt_by_name", AsyncMock(return_value={"id": uuid4()})
    )
    monkeypatch.setattr(
        ai_api, "summarize_messages", AsyncMock(return_value=_ai_response(message="摘要"))
    )
    create_log = AsyncMock()
    monkeypatch.setattr(ai_api.ai_manager, "create_log", create_log)

    await sio.handlers["compress_chat"]("sid-1", {"chatId": str(chat_id)})

    create_log.assert_awaited_once()
    assert create_log.await_args.args[0].user_id == 77


@pytest.mark.asyncio
async def test_call_agent_and_test_agent_carry_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """agent test：user_id 由 router 從呼叫者 session 傳下來。"""
    agent_id = uuid4()
    monkeypatch.setattr(
        ai_manager,
        "get_agent_by_name",
        AsyncMock(return_value={
            "id": agent_id,
            "name": "agent",
            "model": "claude-sonnet",
            "is_active": True,
            "tools": None,
            "system_prompt": None,
        }),
    )
    monkeypatch.setattr(
        ai_manager, "get_agent", AsyncMock(return_value={"id": agent_id, "name": "agent"})
    )
    monkeypatch.setattr(ai_manager, "call_ai", AsyncMock(return_value=_ai_response()))
    create_log = AsyncMock(return_value={"id": uuid4()})
    monkeypatch.setattr(ai_manager, "create_log", create_log)

    await ai_manager.call_agent("agent", "hi", user_id=31)
    assert create_log.await_args.args[0].user_id == 31

    create_log.reset_mock()
    await ai_manager.test_agent(agent_id, "hi", user_id=31)
    assert create_log.await_args.args[0].user_id == 31

    # 沒帶就是 None，不猜
    create_log.reset_mock()
    await ai_manager.call_agent("agent", "hi")
    assert create_log.await_args.args[0].user_id is None


@pytest.mark.asyncio
async def test_ai_test_endpoint_passes_session_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/ai/test 把呼叫者 session 的 user_id 交給 test_agent。"""
    from ching_tech_os.api import ai_management
    from ching_tech_os.models.ai import AiTestRequest

    test_agent = AsyncMock(return_value={"success": True, "log_id": uuid4()})
    monkeypatch.setattr(ai_management.ai_manager, "test_agent", test_agent)

    agent_id = uuid4()
    session = SimpleNamespace(user_id=88, username="tester")
    await ai_management.test_agent(AiTestRequest(agent_id=agent_id, message="hi"), session)

    assert test_agent.await_args.kwargs["user_id"] == 88


@pytest.mark.asyncio
async def test_scheduler_agent_task_log_uses_created_by(monkeypatch: pytest.MonkeyPatch) -> None:
    """scheduler agent 模式：user_id = executor_config.ctos_user_id，沒有就用 created_by。"""
    from ching_tech_os.services import task_scheduler

    monkeypatch.setattr(
        "ching_tech_os.services.ai_manager.get_agent_by_name",
        AsyncMock(return_value={"id": uuid4(), "model": "sonnet", "tools": None, "system_prompt": None}),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.claude_agent.call_claude",
        AsyncMock(return_value=SimpleNamespace(success=True, message="done", error=None)),
    )
    create_log = AsyncMock()
    monkeypatch.setattr("ching_tech_os.services.ai_manager.create_log", create_log)

    await task_scheduler._execute_agent_task("每日盤點", {"agent_name": "bot", "prompt": "p"}, 12)
    assert create_log.await_args.args[0].user_id == 12

    create_log.reset_mock()
    await task_scheduler._execute_agent_task(
        "每日盤點", {"agent_name": "bot", "prompt": "p", "ctos_user_id": 34}, 12
    )
    assert create_log.await_args.args[0].user_id == 34


@pytest.mark.asyncio
async def test_scheduler_script_task_log_uses_created_by(monkeypatch: pytest.MonkeyPatch) -> None:
    """scheduler skill_script 模式：user_id = scheduled_tasks.created_by。"""
    from pathlib import Path

    from ching_tech_os.services import task_scheduler

    class _SM:
        async def get_skill(self, _n):
            return SimpleNamespace(name="s")

        async def has_scripts(self, _n):
            return True

        async def get_script_path(self, _s, _c):
            return Path("/tmp/fake.py")

        async def get_skill_dir(self, _n):
            return Path("/tmp/s")

        def get_skill_env_overrides(self, _s):
            return {}

    class _Runner:
        def __init__(self, _d):
            pass

        async def execute_path(self, *_a, **_k):
            return {"success": True, "output": "ok", "error": None, "duration_ms": 3}

    monkeypatch.setattr("ching_tech_os.skills.get_skill_manager", lambda: _SM())
    monkeypatch.setattr("ching_tech_os.skills.script_runner.ScriptRunner", _Runner)
    create_log = AsyncMock()
    monkeypatch.setattr("ching_tech_os.services.ai_manager.create_log", create_log)

    await task_scheduler._execute_skill_script_task(
        "每日報表", {"skill": "s", "script": "r", "input": "{}"}, 12
    )
    assert create_log.await_args.args[0].user_id == 12


@pytest.mark.asyncio
async def test_log_linebot_ai_call_passes_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """linebot／telegram：已綁定 CTOS 帳號用 bot_users.user_id，未綁定留 None。"""
    from ching_tech_os.services import linebot_ai

    monkeypatch.setattr(linebot_ai.ai_manager, "get_agent_by_name", AsyncMock(return_value=None))
    create_log = AsyncMock()
    monkeypatch.setattr(linebot_ai.ai_manager, "create_log", create_log)

    common = dict(
        message_uuid=None,
        line_group_id=None,
        is_group=False,
        input_prompt="p",
        history=None,
        system_prompt="sys",
        allowed_tools=None,
        model="m",
        response=_ai_response(),
        duration_ms=1,
    )

    await linebot_ai.log_linebot_ai_call(**common, user_id=123)
    assert create_log.await_args.args[0].user_id == 123

    create_log.reset_mock()
    await linebot_ai.log_linebot_ai_call(**common)
    assert create_log.await_args.args[0].user_id is None


@pytest.mark.asyncio
async def test_bot_debug_command_log_uses_ctx_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """/debug 指令：user_id 來自 CommandContext.ctos_user_id。"""
    from ching_tech_os.services.bot import command_handlers
    from ching_tech_os.services.bot.commands import CommandContext

    monkeypatch.setattr(
        "ching_tech_os.services.ai_manager.get_agent_by_name",
        AsyncMock(return_value={"system_prompt": {"content": "sys"}, "tools": ["run_skill_script"]}),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.claude_agent.call_claude",
        AsyncMock(return_value=_ai_response(message="診斷完成")),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.bot.ai.parse_ai_response",
        lambda text: (text, [], []),
    )
    log_call = AsyncMock()
    monkeypatch.setattr("ching_tech_os.services.linebot_ai.log_linebot_ai_call", log_call)

    ctx = CommandContext(
        platform_type="line",
        platform_user_id="U1",
        bot_user_id=str(uuid4()),
        ctos_user_id=55,
        is_admin=True,
        is_group=False,
        group_id=None,
        reply_token=None,
        raw_args="狀態如何",
    )
    await command_handlers._handle_debug(ctx)

    assert log_call.await_args.kwargs["user_id"] == 55


@pytest.mark.asyncio
async def test_skill_script_log_uses_ctos_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """skill script：user_id 用 framework 注入的 ctos_user_id，LLM 偽造不了。"""
    from pathlib import Path

    from ching_tech_os.services.mcp import skill_script_tools

    class _SM:
        async def get_skill(self, _n):
            return SimpleNamespace(name="s", requires_app=None)

        async def has_scripts(self, _n):
            return True

        async def get_script_path(self, _s, _c):
            return Path("/tmp/fake.py")

        async def get_skill_dir(self, _n):
            return Path("/tmp/s")

        def get_skill_env_overrides(self, _s):
            return {}

        async def get_script_fallback_map(self, _n):
            return {}

    class _Runner:
        def __init__(self, _d):
            pass

        async def execute_path(self, *_a, **_k):
            return {"success": True, "output": "{}", "error": "", "duration_ms": 3}

    async def _noop():
        return None

    monkeypatch.setattr(skill_script_tools, "ensure_db_connection", _noop)
    monkeypatch.setattr("ching_tech_os.skills.get_skill_manager", lambda: _SM())
    monkeypatch.setattr("ching_tech_os.skills.script_runner.ScriptRunner", _Runner)
    create_log = AsyncMock()
    monkeypatch.setattr("ching_tech_os.services.ai_manager.create_log", create_log)

    await skill_script_tools.run_skill_script(
        skill="s", script="r", input="{}", ctos_user_id=66
    )
    assert create_log.await_args.args[0].user_id == 66
