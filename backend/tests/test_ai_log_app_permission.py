"""AI log 端點 app 權限測試（GET /logs、/logs/stats、/logs/{id}）。

驗證三個端點已套用 require_app_permission("ai-log")：
- admin 一律放行。
- 一般使用者、無覆寫 → 依預設權限（False）拒絕。
- 一般使用者、preferences.permissions.apps["ai-log"] = True → 放行。

以 httpx ASGITransport 掛載 ai_management.router，並覆寫
ching_tech_os.api.auth.get_current_session（require_app_permission 內部依賴的
同一個函式物件）。service 層以 AsyncMock 隔離。
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


async def _get(app: FastAPI, url: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(url)


# ============================================================
# GET /api/ai/logs
# ============================================================


@pytest.mark.asyncio
async def test_list_logs_admin_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ai_management_api.ai_manager, "get_logs", AsyncMock(return_value=([], 0))
    )
    resp = await _get(_app(_session(role="admin")), "/api/ai/logs")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_logs_user_default_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """一般使用者、無覆寫 → 預設關閉，403"""
    monkeypatch.setattr(
        ai_management_api.ai_manager, "get_logs", AsyncMock(return_value=([], 0))
    )
    resp = await _get(_app(_session(role="user")), "/api/ai/logs")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_logs_user_with_override_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """一般使用者、preferences.permissions.apps["ai-log"] = True → 放行"""
    monkeypatch.setattr(
        ai_management_api.ai_manager, "get_logs", AsyncMock(return_value=([], 0))
    )
    session = _session(role="user", app_permissions={"ai-log": True})
    resp = await _get(_app(session), "/api/ai/logs")
    assert resp.status_code == 200


# ============================================================
# GET /api/ai/logs/stats
# ============================================================


@pytest.mark.asyncio
async def test_get_log_stats_admin_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ai_management_api.ai_manager,
        "get_log_stats",
        AsyncMock(
            return_value={
                "total_calls": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "avg_duration_ms": None,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            }
        ),
    )
    resp = await _get(_app(_session(role="admin")), "/api/ai/logs/stats")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_log_stats_user_default_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ai_management_api.ai_manager, "get_log_stats", AsyncMock(return_value={})
    )
    resp = await _get(_app(_session(role="user")), "/api/ai/logs/stats")
    assert resp.status_code == 403


# ============================================================
# GET /api/ai/logs/{log_id}
# ============================================================


@pytest.mark.asyncio
async def test_get_log_admin_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    log_id = uuid4()
    monkeypatch.setattr(
        ai_management_api.ai_manager,
        "get_log",
        AsyncMock(
            return_value={
                "id": log_id,
                "agent_id": None,
                "prompt_id": None,
                "context_type": "chat",
                "context_id": None,
                "input_prompt": "hello",
                "raw_response": None,
                "parsed_response": None,
                "model": None,
                "success": True,
                "error_message": None,
                "duration_ms": None,
                "input_tokens": None,
                "output_tokens": None,
                "created_at": datetime.now(timezone.utc),
            }
        ),
    )
    resp = await _get(_app(_session(role="admin")), f"/api/ai/logs/{log_id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_log_user_default_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    log_id = uuid4()
    monkeypatch.setattr(
        ai_management_api.ai_manager, "get_log", AsyncMock(return_value=None)
    )
    resp = await _get(_app(_session(role="user")), f"/api/ai/logs/{log_id}")
    assert resp.status_code == 403
