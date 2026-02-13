"""ai_chat 與 AI API 路由測試。"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from ching_tech_os.api import ai_management, ai_router
from ching_tech_os.models.ai import ChatCreate, ChatUpdate
from ching_tech_os.models.auth import SessionData
from ching_tech_os.services import ai_chat


class _CM:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return None


def _now() -> datetime:
    return datetime.now()


def _session() -> SessionData:
    now = _now()
    return SessionData(
        username="admin",
        password="x",
        nas_host="h",
        user_id=1,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        role="admin",
    )


def _prompt_dict(pid) -> dict:
    return {
        "id": pid,
        "name": "prompt-a",
        "display_name": "Prompt A",
        "category": "system",
        "content": "sys",
        "description": None,
        "variables": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


def _agent_dict(aid, pid) -> dict:
    return {
        "id": aid,
        "name": "agent-a",
        "display_name": "Agent A",
        "description": None,
        "model": "claude-sonnet",
        "system_prompt_id": pid,
        "is_active": True,
        "tools": ["search_knowledge"],
        "settings": {"temperature": 0.2},
        "created_at": _now(),
        "updated_at": _now(),
    }


def _log_dict(lid, aid) -> dict:
    return {
        "id": lid,
        "agent_id": aid,
        "agent_name": "agent-a",
        "prompt_id": None,
        "context_type": "web",
        "context_id": "ctx",
        "input_prompt": "hello",
        "system_prompt": None,
        "allowed_tools": ["search_knowledge"],
        "raw_response": "ok",
        "parsed_response": {"tool_calls": []},
        "model": "claude-sonnet",
        "success": True,
        "error_message": None,
        "duration_ms": 12,
        "input_tokens": 3,
        "output_tokens": 5,
        "created_at": _now(),
    }


@pytest.mark.asyncio
async def test_ai_chat_service_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    chat_id = uuid4()
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[
        [{"id": uuid4(), "name": "agent-a", "display_name": "A", "description": None, "model": "m", "is_active": True}],  # get_available_agents
        [{"id": chat_id, "user_id": 1, "title": "t", "model": "m", "prompt_name": "p", "created_at": _now(), "updated_at": _now()}],  # get_user_chats
    ])
    conn.fetchrow = AsyncMock(side_effect=[
        {"content": "sys"},  # get_agent_system_prompt
        {"id": uuid4(), "name": "agent-a", "display_name": "A", "model": "m", "is_active": True, "tools": '["t"]', "settings": '{"x":1}', "system_prompt": "sys"},  # get_agent_config
        {"id": chat_id, "user_id": 1, "title": "new", "model": "claude-sonnet", "prompt_name": "default", "messages": "[]", "created_at": _now(), "updated_at": _now()},  # create_chat
        {"id": chat_id, "user_id": 1, "title": "new", "model": "claude-sonnet", "prompt_name": "default", "messages": '[{"role":"user","content":"x","timestamp":1}]', "created_at": _now(), "updated_at": _now()},  # get_chat
        {"id": chat_id, "user_id": 1, "title": "u", "model": "m2", "prompt_name": "p2", "messages": "[]", "created_at": _now(), "updated_at": _now()},  # update_chat
        {"id": chat_id, "user_id": 1, "title": "u", "model": "m2", "prompt_name": "p2", "messages": '[{"role":"assistant","content":"ok","timestamp":2}]', "created_at": _now(), "updated_at": _now()},  # update_chat_messages
        {"id": chat_id, "user_id": 1, "title": "u", "model": "m2", "prompt_name": "p2", "messages": "[]", "created_at": _now(), "updated_at": _now()},  # get_chat for append
        {"id": chat_id, "user_id": 1, "title": "u", "model": "m2", "prompt_name": "p2", "messages": '[{"role":"user","content":"new","timestamp":3}]', "created_at": _now(), "updated_at": _now()},  # update_chat_messages for append
    ])
    conn.execute = AsyncMock(side_effect=["DELETE 1", "UPDATE 1"])
    monkeypatch.setattr(ai_chat, "get_connection", lambda: _CM(conn))

    agents = await ai_chat.get_available_agents()
    assert agents[0]["name"] == "agent-a"
    assert await ai_chat.get_agent_system_prompt("agent-a") == "sys"
    config = await ai_chat.get_agent_config("agent-a")
    assert config["tools"] == ["t"] and config["settings"]["x"] == 1
    assert len(await ai_chat.get_user_chats(1)) == 1
    assert (await ai_chat.create_chat(1))["messages"] == []
    assert (await ai_chat.get_chat(chat_id, 1))["messages"][0]["content"] == "x"
    assert await ai_chat.delete_chat(chat_id, 1) is True
    assert (await ai_chat.update_chat(chat_id, 1, title="u"))["title"] == "u"
    assert (await ai_chat.update_chat_messages(chat_id, [{"role": "assistant", "content": "ok", "timestamp": 2}], 1))["messages"][0]["role"] == "assistant"
    appended = await ai_chat.append_message(chat_id, "user", "new", 1)
    assert appended is not None and appended["messages"][0]["content"] == "new"
    assert await ai_chat.update_chat_title(chat_id, "t2", 1) is True

    # update_chat 無更新欄位
    monkeypatch.setattr(ai_chat, "get_chat", AsyncMock(return_value={"id": chat_id, "title": "fallback"}))
    assert (await ai_chat.update_chat(chat_id, 1))["title"] == "fallback"


@pytest.mark.asyncio
async def test_ai_router_routes_and_auth_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(ai_router.router)
    app.dependency_overrides[ai_router.get_current_user_id] = lambda: 1
    client = TestClient(app)

    chat_id = uuid4()
    chat_detail = {
        "id": str(chat_id),
        "user_id": 1,
        "title": "chat",
        "model": "claude-sonnet",
        "prompt_name": "default",
        "messages": [],
        "created_at": _now().isoformat(),
        "updated_at": _now().isoformat(),
    }

    monkeypatch.setattr(ai_router.ai_chat, "get_user_chats", AsyncMock(return_value=[{
        "id": str(chat_id),
        "user_id": 1,
        "title": "chat",
        "model": "claude-sonnet",
        "prompt_name": "default",
        "created_at": _now().isoformat(),
        "updated_at": _now().isoformat(),
    }]))
    monkeypatch.setattr(ai_router.ai_chat, "create_chat", AsyncMock(return_value=chat_detail))
    monkeypatch.setattr(ai_router.ai_chat, "get_chat", AsyncMock(side_effect=[chat_detail, None]))
    monkeypatch.setattr(ai_router.ai_chat, "delete_chat", AsyncMock(side_effect=[True, False]))
    monkeypatch.setattr(ai_router.ai_chat, "update_chat", AsyncMock(side_effect=[chat_detail, None]))

    assert client.get("/api/ai/chats").status_code == 200
    assert client.post("/api/ai/chats", json=ChatCreate().model_dump()).status_code == 200
    assert client.get(f"/api/ai/chats/{chat_id}").status_code == 200
    assert client.get(f"/api/ai/chats/{uuid4()}").status_code == 404
    assert client.delete(f"/api/ai/chats/{chat_id}").status_code == 200
    assert client.delete(f"/api/ai/chats/{uuid4()}").status_code == 404
    assert client.patch(f"/api/ai/chats/{chat_id}", json=ChatUpdate(title="x").model_dump()).status_code == 200
    assert client.patch(f"/api/ai/chats/{uuid4()}", json=ChatUpdate(title="x").model_dump()).status_code == 404

    # get_current_user_id: 無 cookie
    scope = {"type": "http", "headers": [], "query_string": b""}
    req = Request(scope)
    assert await ai_router.get_current_user_id(req) == 1

    # 有 cookie 且 session 有效
    req2 = Request({"type": "http", "headers": [(b"cookie", b"session_token=abc")], "query_string": b""})
    monkeypatch.setattr(ai_router.session_manager, "get_session", AsyncMock(return_value=SimpleNamespace(username="u1")))
    assert isinstance(await ai_router.get_current_user_id(req2), int)

    # session 失效
    monkeypatch.setattr(ai_router.session_manager, "get_session", AsyncMock(return_value=None))
    with pytest.raises(Exception):
        await ai_router.get_current_user_id(req2)


@pytest.mark.asyncio
async def test_ai_management_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(ai_management.router)
    app.dependency_overrides[ai_management.get_current_session] = _session
    client = TestClient(app)

    pid = uuid4()
    aid = uuid4()
    lid = uuid4()
    prompt = _prompt_dict(pid)
    agent = _agent_dict(aid, pid)
    log_item = _log_dict(lid, aid)

    monkeypatch.setattr(ai_management.ai_manager, "get_prompts", AsyncMock(return_value=[prompt]))
    monkeypatch.setattr(ai_management.ai_manager, "create_prompt", AsyncMock(return_value=prompt))
    monkeypatch.setattr(ai_management.ai_manager, "get_prompt", AsyncMock(side_effect=[prompt, None]))
    monkeypatch.setattr(ai_management.ai_manager, "get_prompt_referencing_agents", AsyncMock(return_value=[{"id": aid, "name": "agent-a", "display_name": "Agent A"}]))
    monkeypatch.setattr(ai_management.ai_manager, "update_prompt", AsyncMock(side_effect=[prompt, None]))
    monkeypatch.setattr(ai_management.ai_manager, "delete_prompt", AsyncMock(side_effect=[(True, None), (False, "used"), (False, None)]))

    monkeypatch.setattr(ai_management.ai_manager, "get_agents", AsyncMock(return_value=[agent]))
    monkeypatch.setattr(ai_management.ai_manager, "create_agent", AsyncMock(return_value=agent))
    monkeypatch.setattr(ai_management.ai_manager, "get_agent_by_name", AsyncMock(side_effect=[agent, None]))
    monkeypatch.setattr(ai_management.ai_manager, "get_agent", AsyncMock(side_effect=[agent, None]))
    monkeypatch.setattr(ai_management.ai_manager, "update_agent", AsyncMock(side_effect=[agent, None]))
    monkeypatch.setattr(ai_management.ai_manager, "delete_agent", AsyncMock(side_effect=[True, False]))

    monkeypatch.setattr(ai_management.ai_manager, "get_logs", AsyncMock(return_value=([{
        "id": lid,
        "agent_id": aid,
        "agent_name": "agent-a",
        "context_type": "web",
        "allowed_tools": ["search_knowledge"],
        "used_tools": ["search_knowledge"],
        "success": True,
        "duration_ms": 12,
        "input_tokens": 3,
        "output_tokens": 5,
        "created_at": _now().isoformat(),
    }], 1)))
    monkeypatch.setattr(
        ai_management.ai_manager,
        "get_log_stats",
        AsyncMock(return_value={
            "total_calls": 10,
            "success_count": 8,
            "failure_count": 2,
            "success_rate": 80.0,
            "avg_duration_ms": 123.4,
            "total_input_tokens": 100,
            "total_output_tokens": 200,
        }),
    )
    monkeypatch.setattr(ai_management.ai_manager, "get_log", AsyncMock(side_effect=[log_item, None]))
    monkeypatch.setattr(
        ai_management.ai_manager,
        "test_agent",
        AsyncMock(return_value={"success": True, "response": "ok", "error": None, "duration_ms": 12, "log_id": lid}),
    )

    assert client.get("/api/ai/prompts").status_code == 200
    assert client.post("/api/ai/prompts", json={"name": "p", "content": "c"}).status_code == 200
    assert client.get(f"/api/ai/prompts/{pid}").status_code == 200
    assert client.get(f"/api/ai/prompts/{uuid4()}").status_code == 404
    assert client.put(f"/api/ai/prompts/{pid}", json={"content": "x"}).status_code == 200
    assert client.put(f"/api/ai/prompts/{uuid4()}", json={"content": "x"}).status_code == 500
    assert client.delete(f"/api/ai/prompts/{pid}").status_code == 200
    assert client.delete(f"/api/ai/prompts/{pid}").status_code == 400
    assert client.delete(f"/api/ai/prompts/{pid}").status_code == 404

    assert client.get("/api/ai/agents").status_code == 200
    assert client.post("/api/ai/agents", json={"name": "a", "model": "claude-sonnet"}).status_code == 200
    assert client.get("/api/ai/agents/by-name/agent-a").status_code == 200
    assert client.get("/api/ai/agents/by-name/notfound").status_code == 404
    assert client.get(f"/api/ai/agents/{aid}").status_code == 200
    assert client.get(f"/api/ai/agents/{uuid4()}").status_code == 404
    assert client.put(f"/api/ai/agents/{aid}", json={"is_active": False}).status_code == 200
    assert client.put(f"/api/ai/agents/{uuid4()}", json={"is_active": False}).status_code == 500
    assert client.delete(f"/api/ai/agents/{aid}").status_code == 200
    assert client.delete(f"/api/ai/agents/{aid}").status_code == 404

    assert client.get("/api/ai/logs").status_code == 200
    assert client.get("/api/ai/logs/stats").status_code == 200
    assert client.get(f"/api/ai/logs/{lid}").status_code == 200
    assert client.get(f"/api/ai/logs/{uuid4()}").status_code == 404
    assert client.post("/api/ai/test", json={"agent_id": str(aid), "message": "hi"}).status_code == 200

    # duplicate key 分支
    monkeypatch.setattr(ai_management.ai_manager, "create_prompt", AsyncMock(side_effect=Exception("duplicate key")))
    assert client.post("/api/ai/prompts", json={"name": "dup", "content": "c"}).status_code == 400
    monkeypatch.setattr(ai_management.ai_manager, "create_agent", AsyncMock(side_effect=Exception("duplicate key")))
    assert client.post("/api/ai/agents", json={"name": "dup", "model": "claude-sonnet"}).status_code == 400
