"""ai_manager 服務測試。"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ching_tech_os.models.ai import (
    AiAgentCreate,
    AiAgentUpdate,
    AiLogCreate,
    AiLogFilter,
    AiPromptCreate,
    AiPromptUpdate,
)
from ching_tech_os.services import ai_manager
from ching_tech_os.services.ai_provider import AIResponse


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_prompt_crud_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    pid = uuid4()
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[
        [{"id": pid, "name": "a"}],  # get_prompts(category)
        [{"id": pid, "name": "b"}],  # get_prompts(all)
        [{"id": pid, "name": "agent-a"}],  # get_prompt_referencing_agents
    ])
    conn.fetchrow = AsyncMock(side_effect=[
        {  # get_prompt
            "id": pid,
            "name": "p1",
            "display_name": "P1",
            "category": "system",
            "content": "hello",
            "description": None,
            "variables": '{"x":"y"}',
            "created_at": _now(),
            "updated_at": _now(),
        },
        {  # get_prompt_by_name
            "id": pid,
            "name": "p1",
            "display_name": "P1",
            "category": "system",
            "content": "hello",
            "description": None,
            "variables": '{"k":1}',
            "created_at": _now(),
            "updated_at": _now(),
        },
        {  # create_prompt
            "id": pid,
            "name": "p2",
            "display_name": "P2",
            "category": "task",
            "content": "world",
            "description": "desc",
            "variables": '{"v":"x"}',
            "created_at": _now(),
            "updated_at": _now(),
        },
        {  # update_prompt
            "id": pid,
            "name": "p3",
            "display_name": "P3",
            "category": "system",
            "content": "updated",
            "description": None,
            "variables": '{"done":true}',
            "created_at": _now(),
            "updated_at": _now(),
        },
    ])
    conn.execute = AsyncMock(return_value="DELETE 1")
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    assert (await ai_manager.get_prompts("system"))[0]["name"] == "a"
    assert (await ai_manager.get_prompts())[0]["name"] == "b"
    assert (await ai_manager.get_prompt(pid))["variables"]["x"] == "y"
    assert (await ai_manager.get_prompt_by_name("p1"))["variables"]["k"] == 1
    created = await ai_manager.create_prompt(
        AiPromptCreate(name="n", content="c", display_name="d", category="system", variables={"v": "x"})
    )
    assert created["variables"]["v"] == "x"
    updated = await ai_manager.update_prompt(pid, AiPromptUpdate(content="updated"))
    assert updated["variables"]["done"] is True
    refs = await ai_manager.get_prompt_referencing_agents(pid)
    assert refs[0]["name"] == "agent-a"

    # delete_prompt: 被引用
    conn.fetch = AsyncMock(return_value=[{"name": "agent-x"}])
    ok, err = await ai_manager.delete_prompt(pid)
    assert ok is False and "agent-x" in (err or "")

    # delete_prompt: 正常刪除
    conn.fetch = AsyncMock(return_value=[])
    ok, err = await ai_manager.delete_prompt(pid)
    assert ok is True and err is None


@pytest.mark.asyncio
async def test_agent_crud_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    aid = uuid4()
    pid = uuid4()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[
        {"id": aid, "name": "agent", "display_name": "A", "model": "m", "is_active": True, "tools": '["t1"]', "updated_at": _now()},
    ])
    conn.fetchrow = AsyncMock(side_effect=[
        {  # get_agent
            "id": aid,
            "name": "agent",
            "display_name": "A",
            "description": "desc",
            "model": "claude-sonnet",
            "system_prompt_id": pid,
            "is_active": True,
            "tools": '["tool1"]',
            "settings": '{"temperature":0.2}',
            "created_at": _now(),
            "updated_at": _now(),
            "prompt_id": pid,
            "prompt_name": "p",
            "prompt_display_name": "P",
            "prompt_category": "system",
            "prompt_content": "sys",
            "prompt_description": None,
            "prompt_variables": '{"a":1}',
            "prompt_created_at": _now(),
            "prompt_updated_at": _now(),
        },
        {  # get_agent_by_name
            "id": aid,
            "name": "agent",
            "display_name": "A",
            "description": "desc",
            "model": "claude-sonnet",
            "system_prompt_id": pid,
            "is_active": True,
            "tools": '["tool2"]',
            "settings": '{"debug":true}',
            "created_at": _now(),
            "updated_at": _now(),
            "prompt_id": None,
            "prompt_name": None,
            "prompt_display_name": None,
            "prompt_category": None,
            "prompt_content": None,
            "prompt_description": None,
            "prompt_variables": None,
            "prompt_created_at": None,
            "prompt_updated_at": None,
        },
        {  # create_agent
            "id": aid,
            "name": "agent",
            "display_name": "A",
            "description": "desc",
            "model": "claude-sonnet",
            "system_prompt_id": pid,
            "is_active": True,
            "tools": '["t"]',
            "settings": '{"x":1}',
            "created_at": _now(),
            "updated_at": _now(),
        },
        {  # update_agent
            "id": aid,
            "name": "agent2",
            "display_name": "A2",
            "description": "d2",
            "model": "claude-haiku",
            "system_prompt_id": None,
            "is_active": False,
            "tools": '["t2"]',
            "settings": '{"y":2}',
            "created_at": _now(),
            "updated_at": _now(),
        },
    ])
    conn.execute = AsyncMock(return_value="DELETE 1")
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    assert (await ai_manager.get_agents())[0]["tools"] == ["t1"]
    detail = await ai_manager.get_agent(aid)
    assert detail["settings"]["temperature"] == 0.2
    assert detail["system_prompt"]["variables"]["a"] == 1
    by_name = await ai_manager.get_agent_by_name("agent")
    assert by_name["system_prompt"] is None and by_name["tools"] == ["tool2"]
    created = await ai_manager.create_agent(
        AiAgentCreate(name="a", model="claude-sonnet", tools=["t"], settings={"x": 1})
    )
    assert created["tools"] == ["t"]
    updated = await ai_manager.update_agent(aid, AiAgentUpdate(name="agent2", model="claude-haiku", is_active=False))
    assert updated["name"] == "agent2" and updated["settings"]["y"] == 2
    assert await ai_manager.delete_agent(aid) is True

    # update_agent: 無更新欄位 -> fallback get_agent
    monkeypatch.setattr(ai_manager, "get_agent", AsyncMock(return_value={"id": aid, "name": "fallback"}))
    assert (await ai_manager.update_agent(aid, AiAgentUpdate()))["name"] == "fallback"


@pytest.mark.asyncio
async def test_log_and_stats_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    lid = uuid4()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[
        {  # create_log
            "id": lid,
            "agent_id": uuid4(),
            "prompt_id": None,
            "context_type": "web",
            "context_id": "c1",
            "input_prompt": "in",
            "system_prompt": None,
            "allowed_tools": '["a","b"]',
            "raw_response": "ok",
            "parsed_response": '{"tool_calls":[{"name":"a"}]}',
            "model": "m",
            "success": True,
            "error_message": None,
            "duration_ms": 10,
            "input_tokens": 1,
            "output_tokens": 2,
            "created_at": _now(),
        },
        {"total": 1},  # get_logs count
        {  # get_log
            "id": lid,
            "agent_id": None,
            "agent_name": None,
            "prompt_id": None,
            "context_type": "web",
            "context_id": "c1",
            "input_prompt": "in",
            "system_prompt": None,
            "allowed_tools": '["a"]',
            "raw_response": "ok",
            "parsed_response": '{"x":1}',
            "model": "m",
            "success": True,
            "error_message": None,
            "duration_ms": 10,
            "input_tokens": 1,
            "output_tokens": 2,
            "created_at": _now(),
        },
        {  # get_log_stats
            "total_calls": 4,
            "success_count": 3,
            "failure_count": 1,
            "avg_duration_ms": 12.345,
            "total_input_tokens": 10,
            "total_output_tokens": 20,
        },
    ])
    conn.fetch = AsyncMock(return_value=[
        {
            "id": lid,
            "agent_id": None,
            "agent_name": None,
            "context_type": "web",
            "allowed_tools": '["a","b"]',
            "parsed_response": '{"tool_calls":[{"name":"a"},{"name":"a"},{"name":"b"}]}',
            "input_prompt": "test prompt",
            "success": True,
            "duration_ms": 10,
            "input_tokens": 1,
            "output_tokens": 2,
            "created_at": _now(),
        }
    ])
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    created = await ai_manager.create_log(
        AiLogCreate(
            input_prompt="in",
            model="m",
            success=True,
            parsed_response={"tool_calls": [{"name": "a"}]},
            allowed_tools=["a", "b"],
        )
    )
    assert created["allowed_tools"] == ["a", "b"]

    logs, total = await ai_manager.get_logs(
        AiLogFilter(context_type="web", success=True),
        page=1,
        page_size=20,
    )
    assert total == 1 and sorted(logs[0]["used_tools"]) == ["a", "b"]
    assert await ai_manager.get_log(uuid4()) is not None
    stats = await ai_manager.get_log_stats()
    assert stats["success_rate"] == 75.0 and stats["avg_duration_ms"] == 12.35

    # get_log: 查無資料
    conn.fetchrow = AsyncMock(return_value=None)
    assert await ai_manager.get_log(uuid4()) is None


@pytest.mark.asyncio
async def test_call_agent_and_test_agent_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    agent_id = uuid4()

    # agent 不存在
    monkeypatch.setattr(ai_manager, "get_agent_by_name", AsyncMock(return_value=None))
    missing = await ai_manager.call_agent("missing", "hello")
    assert missing["success"] is False and "不存在" in (missing["error"] or "")

    # agent 停用
    monkeypatch.setattr(ai_manager, "get_agent_by_name", AsyncMock(return_value={"is_active": False}))
    disabled = await ai_manager.call_agent("disabled", "hello")
    assert disabled["success"] is False and "停用" in (disabled["error"] or "")

    # 成功路徑
    monkeypatch.setattr(
        ai_manager,
        "get_agent_by_name",
        AsyncMock(
            return_value={
                "id": agent_id,
                "name": "agent-a",
                "is_active": True,
                "model": "claude-sonnet",
                "tools": ["search_knowledge"],
                "system_prompt": {"id": uuid4(), "content": "sys"},
            }
        ),
    )
    monkeypatch.setattr(
        ai_manager,
        "call_ai",
        AsyncMock(return_value=AIResponse(success=True, message="ok")),
    )
    monkeypatch.setattr(ai_manager, "compose_prompt_with_history", lambda _h, m: f"H::{m}")
    monkeypatch.setattr(ai_manager, "create_log", AsyncMock(return_value={"id": uuid4()}))
    ok = await ai_manager.call_agent("agent-a", "hi", history=[{"role": "user", "content": "x"}])
    assert ok["success"] is True and ok["response"] == "ok"

    # 失敗路徑
    monkeypatch.setattr(
        ai_manager,
        "call_ai",
        AsyncMock(return_value=AIResponse(success=False, message="", error="boom")),
    )
    fail = await ai_manager.call_agent("agent-a", "hi")
    assert fail["success"] is False and fail["error"] == "boom"

    # test_agent: 不存在
    monkeypatch.setattr(ai_manager, "get_agent", AsyncMock(return_value=None))
    not_found = await ai_manager.test_agent(agent_id, "x")
    assert not_found["success"] is False and "不存在" in (not_found["error"] or "")

    # test_agent: 走 call_agent
    monkeypatch.setattr(ai_manager, "get_agent", AsyncMock(return_value={"name": "agent-a"}))
    monkeypatch.setattr(ai_manager, "call_agent", AsyncMock(return_value={"success": True, "response": "ok"}))
    tested = await ai_manager.test_agent(agent_id, "x")
    assert tested["success"] is True


@pytest.mark.asyncio
async def test_call_agent_routes_via_call_ai_with_routing_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """8.1：internal test-agent 走 call_ai，帶 routing context 並記錄 routing metadata。"""
    agent_id = uuid4()
    monkeypatch.setattr(
        ai_manager,
        "get_agent_by_name",
        AsyncMock(
            return_value={
                "id": agent_id,
                "name": "test-agent",
                "is_active": True,
                "model": "sonnet",
                "tools": ["mcp__ching-tech-os__search_knowledge"],
                "system_prompt": None,
            }
        ),
    )
    captured: dict = {}

    async def fake_call_ai(**kwargs):
        captured.update(kwargs)
        return AIResponse(
            success=True,
            message="ok",
            provider="claude",
            route_reason="forced_claude",
            requested_role="sonnet",
        )

    monkeypatch.setattr(ai_manager, "call_ai", fake_call_ai)
    logged: dict = {}

    async def fake_create_log(data):
        logged["data"] = data
        return {"id": uuid4()}

    monkeypatch.setattr(ai_manager, "create_log", fake_create_log)

    result = await ai_manager.call_agent(
        "test-agent", "hi", context_type="test", context_id="cid-1"
    )
    assert result["success"] is True
    # routing context 以 caller 事實為準，不受 LLM 影響
    routing_context = captured["routing_context"]
    assert routing_context.context_type == "test"
    assert routing_context.agent_name == "test-agent"
    assert captured["tools"] == ["mcp__ching-tech-os__search_knowledge"]
    # ai_logs.parsed_response 記錄 routing metadata；model 欄位保留 requested role
    assert logged["data"].parsed_response["routing"]["provider"] == "claude"
    assert logged["data"].parsed_response["routing"]["route_reason"] == "forced_claude"
    assert logged["data"].model == "sonnet"


@pytest.mark.asyncio
async def test_call_agent_without_context_type_has_no_routing_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ai_manager,
        "get_agent_by_name",
        AsyncMock(
            return_value={
                "id": uuid4(),
                "name": "agent-a",
                "is_active": True,
                "model": "sonnet",
                "tools": None,
                "system_prompt": None,
            }
        ),
    )
    captured: dict = {}

    async def fake_call_ai(**kwargs):
        captured.update(kwargs)
        return AIResponse(success=True, message="ok")

    monkeypatch.setattr(ai_manager, "call_ai", fake_call_ai)
    monkeypatch.setattr(ai_manager, "create_log", AsyncMock(return_value={"id": uuid4()}))

    await ai_manager.call_agent("agent-a", "hi")
    # 沒有可信 context 就不進 canary scope（is_canary_allowed(None) 為 False）
    assert captured["routing_context"] is None


@pytest.mark.asyncio
async def test_ensure_log_partitions(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))
    await ai_manager.ensure_log_partitions()
    conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_prompt_not_found_and_update_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prompt 查無資料與 update_prompt 各欄位分支。"""
    pid = uuid4()
    conn = AsyncMock()
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    # get_prompt / get_prompt_by_name：查無資料
    conn.fetchrow = AsyncMock(return_value=None)
    assert await ai_manager.get_prompt(pid) is None
    assert await ai_manager.get_prompt_by_name("missing") is None

    # update_prompt：所有欄位都更新（覆蓋 name/display_name/category/description/variables 分支）
    conn.fetchrow = AsyncMock(return_value={
        "id": pid,
        "name": "full",
        "display_name": "Full",
        "category": "task",
        "content": "c",
        "description": "d",
        "variables": '{"all":1}',
        "created_at": _now(),
        "updated_at": _now(),
    })
    updated = await ai_manager.update_prompt(
        pid,
        AiPromptUpdate(
            name="full",
            display_name="Full",
            category="task",
            content="c",
            description="d",
            variables={"all": 1},
        ),
    )
    assert updated is not None and updated["variables"]["all"] == 1

    # update_prompt：無任何欄位 -> fallback get_prompt
    monkeypatch.setattr(ai_manager, "get_prompt", AsyncMock(return_value={"id": pid, "name": "fb"}))
    assert (await ai_manager.update_prompt(pid, AiPromptUpdate()))["name"] == "fb"

    # update_prompt：目標不存在 -> 回傳 None
    conn.fetchrow = AsyncMock(return_value=None)
    assert await ai_manager.update_prompt(pid, AiPromptUpdate(content="x")) is None


@pytest.mark.asyncio
async def test_agent_not_found_and_update_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent 查無資料、關聯 Prompt 組裝與 update_agent 各欄位分支。"""
    aid = uuid4()
    pid = uuid4()
    conn = AsyncMock()
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    # get_agent / get_agent_by_name：查無資料
    conn.fetchrow = AsyncMock(return_value=None)
    assert await ai_manager.get_agent(aid) is None
    assert await ai_manager.get_agent_by_name("missing") is None

    # get_agent：無關聯 Prompt（prompt_id 為 None -> system_prompt 為 None）
    conn.fetchrow = AsyncMock(return_value={
        "id": aid,
        "name": "agent",
        "display_name": "A",
        "description": None,
        "model": "claude-sonnet",
        "system_prompt_id": None,
        "is_active": True,
        "tools": None,
        "settings": None,
        "created_at": _now(),
        "updated_at": _now(),
        "prompt_id": None,
        "prompt_name": None,
        "prompt_display_name": None,
        "prompt_category": None,
        "prompt_content": None,
        "prompt_description": None,
        "prompt_variables": None,
        "prompt_created_at": None,
        "prompt_updated_at": None,
    })
    no_prompt = await ai_manager.get_agent(aid)
    assert no_prompt is not None and no_prompt["system_prompt"] is None

    # get_agent_by_name：有關聯 Prompt（組裝 system_prompt dict）
    conn.fetchrow = AsyncMock(return_value={
        "id": aid,
        "name": "agent",
        "display_name": "A",
        "description": None,
        "model": "claude-sonnet",
        "system_prompt_id": pid,
        "is_active": True,
        "tools": None,
        "settings": None,
        "created_at": _now(),
        "updated_at": _now(),
        "prompt_id": pid,
        "prompt_name": "p",
        "prompt_display_name": "P",
        "prompt_category": "system",
        "prompt_content": "sys",
        "prompt_description": None,
        "prompt_variables": '{"v":9}',
        "prompt_created_at": _now(),
        "prompt_updated_at": _now(),
    })
    with_prompt = await ai_manager.get_agent_by_name("agent")
    assert with_prompt["system_prompt"]["variables"]["v"] == 9

    # update_agent：所有欄位都更新（覆蓋 display_name/description/system_prompt_id/tools/settings 分支）
    conn.fetchrow = AsyncMock(return_value={
        "id": aid,
        "name": "n2",
        "display_name": "D2",
        "description": "d2",
        "model": "claude-haiku",
        "system_prompt_id": pid,
        "is_active": True,
        "tools": '["t"]',
        "settings": '{"s":1}',
        "created_at": _now(),
        "updated_at": _now(),
    })
    updated = await ai_manager.update_agent(
        aid,
        AiAgentUpdate(
            name="n2",
            display_name="D2",
            description="d2",
            model="claude-haiku",
            system_prompt_id=pid,
            is_active=True,
            tools=["t"],
            settings={"s": 1},
        ),
    )
    assert updated is not None and updated["tools"] == ["t"] and updated["settings"]["s"] == 1

    # update_agent：目標不存在 -> 回傳 None
    conn.fetchrow = AsyncMock(return_value=None)
    assert await ai_manager.update_agent(aid, AiAgentUpdate(name="x")) is None


@pytest.mark.asyncio
async def test_get_selectable_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    """取得可供 /agent 切換的 Agent 清單。"""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[
        {"id": uuid4(), "name": "sel", "display_name": "S", "description": None, "model": "m", "tools": None},
    ])
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))
    agents = await ai_manager.get_selectable_agents()
    assert agents[0]["name"] == "sel"


@pytest.mark.asyncio
async def test_get_logs_all_filters_and_used_tools_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_logs：agent_id/日期過濾條件與 used_tools、script_label 解析分支。"""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"total": 3})
    conn.fetch = AsyncMock(return_value=[
        {  # run_skill_script（含 skill/script）、無 name 的 tool_call、一般工具
            "id": uuid4(),
            "agent_id": None,
            "agent_name": None,
            "context_type": "web",
            "model": "m",
            "input_prompt": "p1",
            "allowed_tools": None,
            "parsed_response": (
                '{"tool_calls":['
                '{"name":"run_skill_script","input":{"skill":"mail","script":"send"}},'
                '{"name":"run_skill_script","input":{"skill":"mail"}},'
                '{"name":"run_skill_script","input":{"other":1}},'
                '{"input":{"no_name":1}},'
                '{"name":"search_knowledge"}'
                "]}"
            ),
            "success": True,
            "duration_ms": 1,
            "input_tokens": 1,
            "output_tokens": 1,
            "created_at": _now(),
        },
        {  # 無 parsed_response -> used_tools 空；script context -> 解析 script_label
            "id": uuid4(),
            "agent_id": None,
            "agent_name": None,
            "context_type": "script",
            "model": "m",
            "input_prompt": 'mail/send: {"x":1}',
            "allowed_tools": None,
            "parsed_response": None,
            "success": True,
            "duration_ms": 1,
            "input_tokens": 1,
            "output_tokens": 1,
            "created_at": _now(),
        },
        {  # script context 但 input_prompt 沒有冒號 -> script_label 維持 None
            "id": uuid4(),
            "agent_id": None,
            "agent_name": None,
            "context_type": "script",
            "model": "m",
            "input_prompt": "no-colon-format",
            "allowed_tools": None,
            "parsed_response": None,
            "success": False,
            "duration_ms": 1,
            "input_tokens": 1,
            "output_tokens": 1,
            "created_at": _now(),
        },
    ])
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))

    items, total = await ai_manager.get_logs(
        AiLogFilter(agent_id=uuid4(), start_date=_now(), end_date=_now()),
        page=1,
        page_size=10,
    )
    assert total == 3
    # run_skill_script 依 skill/script 展開，沒有 skill 的保留原名，無 name 的忽略
    assert sorted(items[0]["used_tools"]) == [
        "run_skill_script",
        "run_skill_script(mail)",
        "run_skill_script(mail/send)",
        "search_knowledge",
    ]
    assert items[1]["used_tools"] == [] and items[1]["script_label"] == "mail/send"
    assert items[2]["script_label"] is None


@pytest.mark.asyncio
async def test_get_log_stats_filters_and_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_log_stats：agent_id/日期過濾與零筆資料時的統計。"""
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

    stats = await ai_manager.get_log_stats(
        agent_id=uuid4(),
        start_date=_now(),
        end_date=_now(),
    )
    # 零筆資料時 success_rate 為 0、avg_duration_ms 為 None
    assert stats["success_rate"] == 0.0 and stats["avg_duration_ms"] is None
    # WHERE 條件應包含三個過濾參數
    args = conn.fetchrow.await_args.args
    assert "agent_id = $1" in args[0] and "created_at >= $2" in args[0] and "created_at <= $3" in args[0]
