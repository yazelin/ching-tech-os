"""presentation API 測試。"""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
import pytest
from unittest.mock import AsyncMock

from ching_tech_os.api import presentation as presentation_api


@pytest.mark.asyncio
async def test_presentation_generate_success_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(presentation_api.router)
    transport = ASGITransport(app=app)

    monkeypatch.setattr(
        presentation_api,
        "generate_html_presentation",
        AsyncMock(
            return_value={
                "title": "Demo",
                "slides_count": 5,
                "nas_path": "ai-presentations/demo.html",
                "filename": "demo.html",
                "format": "html",
            }
        ),
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/presentation/generate", json={"topic": "AI"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # topic 與 outline_json 都缺少
        resp = await client.post("/api/presentation/generate", json={})
        assert resp.status_code == 400

        # 無效主題
        resp = await client.post("/api/presentation/generate", json={"topic": "AI", "theme": "bad"})
        assert resp.status_code == 400

        # 無效輸出格式
        resp = await client.post("/api/presentation/generate", json={"topic": "AI", "output_format": "doc"})
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_presentation_generate_error_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(presentation_api.router)
    transport = ASGITransport(app=app)

    monkeypatch.setattr(
        presentation_api,
        "generate_html_presentation",
        AsyncMock(side_effect=ValueError("bad input")),
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/presentation/generate", json={"topic": "AI"})
        assert resp.status_code == 400

    monkeypatch.setattr(
        presentation_api,
        "generate_html_presentation",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/presentation/generate", json={"topic": "AI"})
        assert resp.status_code == 500
