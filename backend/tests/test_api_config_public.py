"""config_public API 測試。"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ching_tech_os.api import auth as auth_api
from ching_tech_os.api import config_public
from ching_tech_os.models.auth import SessionData


def _session() -> SessionData:
    now = datetime.now()
    return SessionData(
        username="u1",
        password="",
        nas_host="h",
        user_id=1,
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


def _build_app():
    app = FastAPI()
    app.include_router(config_public.router)
    return app


@pytest.mark.asyncio
async def test_config_health_public() -> None:
    """/health 不需要登入。"""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health = await client.get("/api/config/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_config_apps_requires_login(monkeypatch) -> None:
    """/apps 會洩露已裝模組清單，未登入應 401，帶 token（header 或 query）才 200。"""
    app = _build_app()
    monkeypatch.setattr(
        config_public,
        "get_enabled_app_manifests",
        lambda: [{"id": "knowledge-base", "name": "知識庫", "icon": "mdi-book-open-page-variant"}],
    )
    monkeypatch.setattr(auth_api.session_manager, "get_session", AsyncMock(return_value=_session()))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 無 token → 401
        no_token = await client.get("/api/config/apps")
        assert no_token.status_code == 401

        # Authorization header → 200
        with_header = await client.get(
            "/api/config/apps", headers={"Authorization": "Bearer good-token"}
        )
        assert with_header.status_code == 200
        assert with_header.json()[0]["id"] == "knowledge-base"

        # ?token= query（舊桌面 <script>/<link> 無法帶 header 時使用）→ 200
        with_query = await client.get("/api/config/apps", params={"token": "good-token"})
        assert with_query.status_code == 200
        assert with_query.json()[0]["id"] == "knowledge-base"


@pytest.mark.asyncio
async def test_config_apps_invalid_token_rejected(monkeypatch) -> None:
    """負控制：token 存在但驗證不過（session 查無資料）仍是 401，不是「有帶就放行」。"""
    app = _build_app()
    monkeypatch.setattr(config_public, "get_enabled_app_manifests", lambda: [])
    monkeypatch.setattr(auth_api.session_manager, "get_session", AsyncMock(return_value=None))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/config/apps", headers={"Authorization": "Bearer bad-token"}
        )
        assert resp.status_code == 401
