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
        "call_claude",
        AsyncMock(return_value=SimpleNamespace(success=True, message="ok", error=None)),
    )
    monkeypatch.setattr(ai_manager, "compose_prompt_with_history", lambda _h, m: f"H::{m}")
    monkeypatch.setattr(ai_manager, "create_log", AsyncMock(return_value={"id": uuid4()}))
    ok = await ai_manager.call_agent("agent-a", "hi", history=[{"role": "user", "content": "x"}])
    assert ok["success"] is True and ok["response"] == "ok"

    # 失敗路徑
    monkeypatch.setattr(
        ai_manager,
        "call_claude",
        AsyncMock(return_value=SimpleNamespace(success=False, message=None, error="boom")),
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
async def test_ensure_log_partitions(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AsyncMock()
    monkeypatch.setattr(ai_manager, "get_connection", lambda: _CM(conn))
    await ai_manager.ensure_log_partitions()
    conn.execute.assert_awaited_once()
