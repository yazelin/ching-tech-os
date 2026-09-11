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


# ============================================================
# 5. API 篩選參數
# ============================================================


@pytest.mark.asyncio
async def test_list_logs_endpoint_passes_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    from ching_tech_os.api import ai_management

    get_logs = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(ai_management.ai_manager, "get_logs", get_logs)
    session = SimpleNamespace(user_id=1, username="tester")

    await ai_management.list_logs(
        agent_id=None,
        context_type=None,
        success=None,
        start_date=None,
        end_date=None,
        user_id=5,
        page=1,
        page_size=50,
        session=session,
    )
    assert get_logs.await_args.args[0].user_id == 5

    # 0 = 未記錄使用者，要原封不動傳下去（不能被當成 falsy 丟掉）
    get_logs.reset_mock()
    await ai_management.list_logs(
        agent_id=None,
        context_type=None,
        success=None,
        start_date=None,
        end_date=None,
        user_id=0,
        page=1,
        page_size=50,
        session=session,
    )
    assert get_logs.await_args.args[0].user_id == 0


@pytest.mark.asyncio
async def test_log_stats_endpoint_passes_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    from ching_tech_os.api import ai_management

    stats = AsyncMock(return_value={})
    monkeypatch.setattr(ai_management.ai_manager, "get_log_stats", stats)
    session = SimpleNamespace(user_id=1, username="tester")

    await ai_management.get_log_stats(
        agent_id=None, start_date=None, end_date=None, user_id=0, session=session
    )
    assert stats.await_args.kwargs["user_id"] == 0


def _closure_app_ids(checker) -> list[str]:
    """從 require_app_permission 回傳的 checker 取出它閉包裡的 app_id。

    只比 __qualname__ 會放過「換成別的 app 權限」這種改動，所以要看字串本身。
    """
    code = getattr(checker, "__code__", None)
    closure = getattr(checker, "__closure__", None)
    if code is None or closure is None:
        return []
    return [
        cell.cell_contents
        for name, cell in zip(code.co_freevars, closure)
        if name == "app_id"
    ]


def test_log_endpoints_keep_ai_log_permission() -> None:
    """權限不變：三個 log 端點維持 require_app_permission("ai-log")。"""
    from fastapi.routing import APIRoute

    from ching_tech_os.api import ai_management

    routes = {
        r.path: r
        for r in ai_management.router.routes
        if isinstance(r, APIRoute)
    }
    for path in ("/api/ai/logs", "/api/ai/logs/stats", "/api/ai/logs/{log_id}"):
        route = routes[path]
        app_ids = [
            app_id
            for d in route.dependant.dependencies
            if getattr(d.call, "__qualname__", "").startswith("require_app_permission")
            for app_id in _closure_app_ids(d.call)
        ]
        assert app_ids == ["ai-log"], f"{path} 的 app 權限是 {app_ids}"


def test_require_app_permission_closure_probe_actually_works() -> None:
    """負控制：上面那支取值法真的取得到，換成別的 app id 會看得出來。"""
    from ching_tech_os.services.permissions import require_app_permission

    assert _closure_app_ids(require_app_permission("ai-log")) == ["ai-log"]
    assert _closure_app_ids(require_app_permission("agent-settings")) == ["agent-settings"]


def test_user_id_zero_semantics_documented() -> None:
    """0 的語意要寫在 docstring 裡，不然前端會猜。"""
    from ching_tech_os.api import ai_management

    assert "0" in (ai_management.list_logs.__doc__ or "")
    assert "未記錄使用者" in (ai_management.list_logs.__doc__ or "")
    assert "未記錄使用者" in (ai_management.get_log_stats.__doc__ or "")


# ============================================================
# 6. 邊界與失敗路徑
# ============================================================


def _log_api_client(monkeypatch):
    """只掛 ai_management router 的最小 app，權限用 admin session 蓋過去。"""
    from datetime import timedelta

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from ching_tech_os.api import ai_management
    from ching_tech_os.api.auth import get_current_session
    from ching_tech_os.models.auth import SessionData

    app = FastAPI()
    app.include_router(ai_management.router)

    async def _session():
        now = _now()
        return SessionData(
            username="admin",
            password="x",
            nas_host="localhost",
            user_id=1,
            created_at=now,
            expires_at=now + timedelta(hours=1),
            role="admin",
        )

    app.dependency_overrides[get_current_session] = _session
    return TestClient(app)


def test_list_logs_rejects_negative_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """user_id 是 ge=0：負數沒有語意，要被擋在 422，不能靜默當成沒帶。"""
    from ching_tech_os.api import ai_management

    get_logs = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(ai_management.ai_manager, "get_logs", get_logs)
    client = _log_api_client(monkeypatch)

    assert client.get("/api/ai/logs?user_id=-1").status_code == 422
    get_logs.assert_not_awaited()

    # 負控制：0 與正數都放行，證明 422 是 ge=0 擋的，不是路由本身壞掉
    assert client.get("/api/ai/logs?user_id=0").status_code == 200
    assert client.get("/api/ai/logs?user_id=1").status_code == 200


def test_log_stats_rejects_negative_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    from ching_tech_os.api import ai_management

    monkeypatch.setattr(
        ai_management.ai_manager,
        "get_log_stats",
        AsyncMock(return_value={
            "total_calls": 0,
            "success_count": 0,
            "failure_count": 0,
            "success_rate": 0.0,
            "avg_duration_ms": None,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }),
    )
    client = _log_api_client(monkeypatch)

    assert client.get("/api/ai/logs/stats?user_id=-1").status_code == 422
    assert client.get("/api/ai/logs/stats?user_id=0").status_code == 200


@pytest.mark.asyncio
async def test_no_user_filter_leaves_sql_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    """沒帶 user_id 就完全不該出現在 where 條件裡（count SQL 沒有 JOIN，最好驗）。"""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"total": 0})
    conn.fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    await ai_manager.get_logs(AiLogFilter(), page=1, page_size=10)
    count_sql = conn.fetchrow.await_args.args[0]
    assert "user_id" not in count_sql
    assert "WHERE" not in count_sql
    assert len(conn.fetchrow.await_args.args) == 1

    # stats 同理
    conn.fetchrow = AsyncMock(return_value={
        "total_calls": 0,
        "success_count": 0,
        "failure_count": 0,
        "avg_duration_ms": None,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    })
    await ai_manager.get_log_stats()
    stats_sql = conn.fetchrow.await_args.args[0]
    assert "user_id" not in stats_sql
    # stats 的 SELECT 本來就有 FILTER (WHERE ...)，所以只驗 FROM 後面沒有接 where 子句
    assert "FROM ai_logs\n" in stats_sql
    assert stats_sql.split("FROM ai_logs", 1)[1].strip() == ""
    assert len(conn.fetchrow.await_args.args) == 1


@pytest.mark.asyncio
async def test_call_agent_survives_create_log_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """寫 log 失敗不該讓 Agent 呼叫失敗：回 success=True、log_id=None。"""
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
    monkeypatch.setattr(ai_manager, "call_ai", AsyncMock(return_value=_ai_response()))
    monkeypatch.setattr(
        ai_manager, "create_log", AsyncMock(side_effect=RuntimeError("DB 掛了"))
    )

    result = await ai_manager.call_agent("agent", "hi", user_id=31)
    assert result["success"] is True
    assert result["response"] == "ok"
    assert result["log_id"] is None


def test_ai_test_endpoint_still_200_when_create_log_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/ai/test：create_log 丟例外，端點仍要 200。"""
    from ching_tech_os.api import ai_management
    from ching_tech_os.services import ai_manager as svc

    agent_id = uuid4()
    monkeypatch.setattr(svc, "get_agent", AsyncMock(return_value={"id": agent_id, "name": "agent"}))
    monkeypatch.setattr(
        svc,
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
    monkeypatch.setattr(svc, "call_ai", AsyncMock(return_value=_ai_response()))
    monkeypatch.setattr(svc, "create_log", AsyncMock(side_effect=RuntimeError("DB 掛了")))
    monkeypatch.setattr(ai_management.ai_manager, "test_agent", svc.test_agent)

    client = _log_api_client(monkeypatch)
    resp = client.post("/api/ai/test", json={"agent_id": str(agent_id), "message": "hi"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True and body["log_id"] is None


@pytest.mark.asyncio
async def test_scheduler_retries_log_without_user_on_fk_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """executor_config.ctos_user_id 是管理員手填的，指到不存在的使用者會違反外鍵。

    這時重試一次 user_id=None，log 還是留得下來；第二次再失敗就只 warning。
    """
    from ching_tech_os.services import task_scheduler

    monkeypatch.setattr(
        "ching_tech_os.services.ai_manager.get_agent_by_name",
        AsyncMock(return_value={"id": uuid4(), "model": "sonnet", "tools": None, "system_prompt": None}),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.claude_agent.call_claude",
        AsyncMock(return_value=SimpleNamespace(success=True, message="done", error=None)),
    )

    calls: list = []

    async def _create_log(data):
        calls.append(data)
        if data.user_id is not None:
            raise RuntimeError('violates foreign key constraint "fk_ai_logs_user_id"')
        return {"id": uuid4()}

    monkeypatch.setattr("ching_tech_os.services.ai_manager.create_log", _create_log)

    out = await task_scheduler._execute_agent_task(
        "每日盤點", {"agent_name": "bot", "prompt": "p", "ctos_user_id": 999999}, None
    )

    assert out == "done"  # 排程本身沒有被 log 拖垮
    assert [c.user_id for c in calls] == [999999, None]
    # 重試那筆除了 user_id 之外內容一樣
    assert calls[1].input_prompt == calls[0].input_prompt
    assert calls[1].context_id == calls[0].context_id


@pytest.mark.asyncio
async def test_scheduler_gives_up_after_one_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """重試那次也失敗就放棄，只 warning，不再往下退讓，也不能炸掉排程。"""
    from ching_tech_os.services import task_scheduler

    monkeypatch.setattr(
        "ching_tech_os.services.ai_manager.get_agent_by_name",
        AsyncMock(return_value={"id": uuid4(), "model": "sonnet", "tools": None, "system_prompt": None}),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.claude_agent.call_claude",
        AsyncMock(return_value=SimpleNamespace(success=True, message="done", error=None)),
    )
    create_log = AsyncMock(side_effect=RuntimeError("DB 掛了"))
    monkeypatch.setattr("ching_tech_os.services.ai_manager.create_log", create_log)

    out = await task_scheduler._execute_agent_task(
        "每日盤點", {"agent_name": "bot", "prompt": "p", "ctos_user_id": 999999}, None
    )

    assert out == "done"
    assert create_log.await_count == 2  # 原始一次 + 重試一次，不再更多


@pytest.mark.asyncio
async def test_scheduler_does_not_retry_when_user_id_already_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """負控制：本來就沒有 user_id 時不該多打一次。"""
    from ching_tech_os.services import task_scheduler

    monkeypatch.setattr(
        "ching_tech_os.services.ai_manager.get_agent_by_name",
        AsyncMock(return_value={"id": uuid4(), "model": "sonnet", "tools": None, "system_prompt": None}),
    )
    monkeypatch.setattr(
        "ching_tech_os.services.claude_agent.call_claude",
        AsyncMock(return_value=SimpleNamespace(success=True, message="done", error=None)),
    )
    create_log = AsyncMock(side_effect=RuntimeError("DB 掛了"))
    monkeypatch.setattr("ching_tech_os.services.ai_manager.create_log", create_log)

    out = await task_scheduler._execute_agent_task(
        "每日盤點", {"agent_name": "bot", "prompt": "p"}, None
    )

    assert out == "done"
    assert create_log.await_count == 1
