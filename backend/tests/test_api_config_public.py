"""config_public API 測試。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ching_tech_os.api import config_public


@pytest.mark.asyncio
async def test_config_health_and_apps(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(config_public.router)
    monkeypatch.setattr(
        config_public,
        "get_enabled_app_manifests",
        lambda: [{"id": "knowledge-base", "name": "知識庫", "icon": "mdi-book-open-page-variant"}],
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health = await client.get("/api/config/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        apps = await client.get("/api/config/apps")
        assert apps.status_code == 200
        assert apps.json()[0]["id"] == "knowledge-base"
