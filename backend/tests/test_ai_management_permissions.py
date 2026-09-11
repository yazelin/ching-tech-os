"""AI 管理寫入端點的 app 權限測試（prompts / agents / test）。

驗證既有缺口已補上：
- prompts 的 POST/PUT/DELETE 套 require_app_permission("prompt-editor")。
- agents 的 POST/PUT/DELETE 與 POST /test 套 require_app_permission("agent-settings")。
- GET 端點維持登入即可（AI 助手選 agent、AI Log 篩選、排程 UI 都要讀）。

作法與 test_ai_log_app_permission.py 相同：以 httpx ASGITransport 掛載
ai_management.router，覆寫 ching_tech_os.api.auth.get_current_session，
service 層以 AsyncMock 隔離。
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import ching_tech_os.api.ai_management as ai_management_api
import ching_tech_os.api.auth as auth_api
from ching_tech_os.models.auth import SessionData
from ching_tech_os.services.permissions import DEFAULT_APP_PERMISSIONS, has_app_permission


def _session(role: str = "user", app_permissions: dict[str, bool] | None = None) -> SessionData:
    now = datetime.now(timezone.utc)
    return SessionData(
        username="tester",
        password="xxx",
        nas_host="localhost",
        user_id=1,
        created_at=now,
        expires_at=now,
        role=role,
        app_permissions=app_permissions or {},
    )


def _app(session: SessionData) -> FastAPI:
    app = FastAPI()
    app.include_router(ai_management_api.router)
    app.dependency_overrides[auth_api.get_current_session] = lambda: session
    return app


async def _request(app: FastAPI, method: str, url: str, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, url, **kwargs)


def _agent(agent_id) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": agent_id,
        "name": "web-chat-default",
        "display_name": "網頁對話",
        "description": None,
        "model": "claude-sonnet",
        "system_prompt_id": None,
        "system_prompt": None,
        "is_active": True,
        "tools": [],
        "settings": None,
        "created_at": now,
        "updated_at": now,
    }


def _prompt(prompt_id) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": prompt_id,
        "name": "summarizer",
        "display_name": "摘要",
        "category": "task",
        "content": "summarize",
        "description": None,
        "variables": None,
        "created_at": now,
        "updated_at": now,
    }


# ============================================================
# PUT /api/ai/agents/{id}
# ============================================================


@pytest.mark.asyncio
async def test_update_agent_user_explicit_false_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """一般使用者、明確關閉 → 403，且不會呼叫 service"""
    agent_id = uuid4()
    update = AsyncMock(return_value=_agent(agent_id))
    monkeypatch.setattr(ai_management_api.ai_manager, "update_agent", update)

    resp = await _request(
        _app(_session(role="user", app_permissions={"agent-settings": False})),
        "PUT",
        f"/api/ai/agents/{agent_id}",
        json={"display_name": "改過的名字"},
    )
    assert resp.status_code == 403
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_agent_user_empty_permissions_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """app_permissions 是空 dict → 回退到預設值（agent-settings 預設關閉）→ 403"""
    agent_id = uuid4()
    update = AsyncMock(return_value=_agent(agent_id))
    monkeypatch.setattr(ai_management_api.ai_manager, "update_agent", update)

    resp = await _request(
        _app(_session(role="user", app_permissions={})),
        "PUT",
        f"/api/ai/agents/{agent_id}",
        json={"display_name": "改過的名字"},
    )
    assert resp.status_code == 403
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_agent_user_other_app_permission_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """app_permissions 有值但沒帶 agent-settings → 一樣回退到預設值 → 403

    （checker 以前遇到非空 dict 缺 key 會直接 403，現在與 has_app_permission 一致）
    """
    agent_id = uuid4()
    update = AsyncMock(return_value=_agent(agent_id))
    monkeypatch.setattr(ai_management_api.ai_manager, "update_agent", update)

    resp = await _request(
        _app(_session(role="user", app_permissions={"other-app": True})),
        "PUT",
        f"/api/ai/agents/{agent_id}",
        json={"display_name": "改過的名字"},
    )
    assert resp.status_code == 403
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_checker_falls_back_to_default_for_missing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非空 dict 缺 key 時要回退到預設值，預設開放的 app 就該放行"""
    monkeypatch.setattr(ai_management_api.ai_manager, "get_agents", AsyncMock(return_value=[]))
    # knowledge-base 預設開放；session 的權限快取只帶了別的 app
    from ching_tech_os.services.permissions import require_app_permission

    checker = require_app_permission("knowledge-base")
    session = _session(role="user", app_permissions={"other-app": True})

    class _Req:
        method = "GET"

    assert await checker(request=_Req(), session=session) is session


@pytest.mark.asyncio
async def test_update_agent_admin_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    agent_id = uuid4()
    monkeypatch.setattr(
        ai_management_api.ai_manager, "update_agent", AsyncMock(return_value=_agent(agent_id))
    )
    resp = await _request(
        _app(_session(role="admin")),
        "PUT",
        f"/api/ai/agents/{agent_id}",
        json={"display_name": "改過的名字"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_agent_user_with_override_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """一般使用者、preferences.permissions.apps["agent-settings"] = True → 放行"""
    agent_id = uuid4()
    monkeypatch.setattr(
        ai_management_api.ai_manager, "update_agent", AsyncMock(return_value=_agent(agent_id))
    )
    resp = await _request(
        _app(_session(role="user", app_permissions={"agent-settings": True})),
        "PUT",
        f"/api/ai/agents/{agent_id}",
        json={"display_name": "改過的名字"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_agent_user_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    agent_id = uuid4()
    delete = AsyncMock(return_value=True)
    monkeypatch.setattr(ai_management_api.ai_manager, "delete_agent", delete)
    resp = await _request(
        _app(_session(role="user", app_permissions={"agent-settings": False})),
        "DELETE",
        f"/api/ai/agents/{agent_id}",
    )
    assert resp.status_code == 403
    delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_agent_user_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    create = AsyncMock(return_value=_agent(uuid4()))
    monkeypatch.setattr(ai_management_api.ai_manager, "create_agent", create)
    resp = await _request(
        _app(_session(role="user", app_permissions={"agent-settings": False})),
        "POST",
        "/api/ai/agents",
        json={"name": "x", "display_name": "x", "system_prompt": "x"},
    )
    assert resp.status_code == 403
    create.assert_not_awaited()


# ============================================================
# POST /api/ai/test
# ============================================================


@pytest.mark.asyncio
async def test_test_agent_user_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    run = AsyncMock(return_value={"success": True, "response": "ok"})
    monkeypatch.setattr(ai_management_api.ai_manager, "test_agent", run)
    resp = await _request(
        _app(_session(role="user", app_permissions={"agent-settings": False})),
        "POST",
        "/api/ai/test",
        json={"agent_id": str(uuid4()), "message": "hi"},
    )
    assert resp.status_code == 403
    run.assert_not_awaited()


# ============================================================
# Prompt 寫入端點
# ============================================================


@pytest.mark.asyncio
async def test_create_prompt_user_default_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    create = AsyncMock(return_value=_prompt(uuid4()))
    monkeypatch.setattr(ai_management_api.ai_manager, "create_prompt", create)
    resp = await _request(
        _app(_session(role="user", app_permissions={"prompt-editor": False})),
        "POST",
        "/api/ai/prompts",
        json={"name": "p1", "category": "task", "content": "hello"},
    )
    assert resp.status_code == 403
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_prompt_admin_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ai_management_api.ai_manager, "create_prompt", AsyncMock(return_value=_prompt(uuid4()))
    )
    resp = await _request(
        _app(_session(role="admin")),
        "POST",
        "/api/ai/prompts",
        json={"name": "p1", "category": "task", "content": "hello"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_prompt_user_with_override_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ai_management_api.ai_manager, "create_prompt", AsyncMock(return_value=_prompt(uuid4()))
    )
    resp = await _request(
        _app(_session(role="user", app_permissions={"prompt-editor": True})),
        "POST",
        "/api/ai/prompts",
        json={"name": "p1", "category": "task", "content": "hello"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_prompt_user_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    delete = AsyncMock(return_value=True)
    monkeypatch.setattr(ai_management_api.ai_manager, "delete_prompt", delete)
    resp = await _request(
        _app(_session(role="user", app_permissions={"prompt-editor": False})),
        "DELETE",
        f"/api/ai/prompts/{uuid4()}",
    )
    assert resp.status_code == 403
    delete.assert_not_awaited()


# ============================================================
# GET 端點維持登入即可
# ============================================================


@pytest.mark.asyncio
async def test_list_agents_user_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_management_api.ai_manager, "get_agents", AsyncMock(return_value=[]))
    resp = await _request(
        _app(_session(role="user", app_permissions={"agent-settings": False})),
        "GET",
        "/api/ai/agents",
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_prompts_user_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_management_api.ai_manager, "get_prompts", AsyncMock(return_value=[]))
    resp = await _request(
        _app(_session(role="user", app_permissions={"prompt-editor": False})),
        "GET",
        "/api/ai/prompts",
    )
    assert resp.status_code == 200


# ============================================================
# 預設權限（F8：兩個 app 改為預設關閉）
# ============================================================


def test_prompt_editor_and_agent_settings_default_closed() -> None:
    """ai_prompts / ai_agents 是全域表，預設關閉、由管理員逐人開放"""
    assert DEFAULT_APP_PERMISSIONS["prompt-editor"] is False
    assert DEFAULT_APP_PERMISSIONS["agent-settings"] is False


def test_has_app_permission_defaults_for_two_apps() -> None:
    for app_id in ("prompt-editor", "agent-settings"):
        assert has_app_permission("user", None, app_id) is False
        assert has_app_permission("admin", None, app_id) is True
