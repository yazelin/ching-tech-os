"""share API 路由測試。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ching_tech_os.api import share as share_api
from ching_tech_os.models.share import (
    PasswordRequiredResponse,
    PublicResourceResponse,
    ShareLinkListResponse,
    ShareLinkResponse,
)
from ching_tech_os.services.share import (
    NasFileAccessDenied,
    NasFileNotFoundError,
    PasswordIncorrectError,
    ResourceNotFoundError,
    ShareError,
    ShareLinkExpiredError,
    ShareLinkLockedError,
    ShareLinkNotFoundError,
)


def _build_app(session: SimpleNamespace) -> FastAPI:
    app = FastAPI()
    app.include_router(share_api.router)
    app.include_router(share_api.public_router)
    app.dependency_overrides[share_api.get_current_session] = lambda: session
    return app


def _sample_link() -> ShareLinkResponse:
    now = datetime.now(timezone.utc)
    return ShareLinkResponse(
        token="abc123",
        url="/s/abc123",
        full_url="https://example.com/s/abc123",
        resource_type="content",
        resource_id="",
        resource_title="內容",
        expires_at=None,
        created_at=now,
    )


@pytest.mark.asyncio
async def test_create_link_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(role="admin", username="admin", user_id=1)
    app = _build_app(session)
    transport = ASGITransport(app=app)

    monkeypatch.setattr(share_api, "create_share_link", AsyncMock(return_value=_sample_link()))
    monkeypatch.setattr(share_api, "get_knowledge", lambda _rid: SimpleNamespace(owner="admin", scope="private"))
    monkeypatch.setattr(share_api, "get_user_preferences", AsyncMock(return_value={}))
    monkeypatch.setattr(share_api, "check_knowledge_permission", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(share_api, "validate_nas_file_path", lambda _p: Path("/tmp/ok"))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # content 成功
        resp = await client.post("/api/share", json={"resource_type": "content", "content": "hello", "filename": "a.txt"})
        assert resp.status_code == 201

        # content 缺少 content
        resp = await client.post("/api/share", json={"resource_type": "content"})
        assert resp.status_code == 400

        # knowledge 成功
        resp = await client.post("/api/share", json={"resource_type": "knowledge", "resource_id": "kb1"})
        assert resp.status_code == 201

        # nas_file 成功
        resp = await client.post("/api/share", json={"resource_type": "nas_file", "resource_id": "path/file.txt"})
        assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_link_error_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(role="user", username="u1", user_id=1)
    app = _build_app(session)
    transport = ASGITransport(app=app)

    monkeypatch.setattr(share_api, "get_knowledge", lambda _rid: SimpleNamespace(owner="other", scope="private"))
    monkeypatch.setattr(share_api, "get_user_preferences", AsyncMock(return_value={}))
    monkeypatch.setattr(share_api, "check_knowledge_permission", lambda *_args, **_kwargs: False)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/share", json={"resource_type": "knowledge", "resource_id": "kb1"})
        assert resp.status_code == 403

    monkeypatch.setattr(share_api, "validate_nas_file_path", lambda _p: (_ for _ in ()).throw(NasFileNotFoundError("missing")))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/share", json={"resource_type": "nas_file", "resource_id": "bad"})
        assert resp.status_code == 404

    monkeypatch.setattr(share_api, "validate_nas_file_path", lambda _p: (_ for _ in ()).throw(NasFileAccessDenied("deny")))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/share", json={"resource_type": "nas_file", "resource_id": "bad"})
        assert resp.status_code == 403

    monkeypatch.setattr(share_api, "create_share_link", AsyncMock(side_effect=ResourceNotFoundError("missing")))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/share", json={"resource_type": "content", "content": "x"})
        assert resp.status_code == 404

    monkeypatch.setattr(share_api, "create_share_link", AsyncMock(side_effect=ShareError("oops")))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/share", json={"resource_type": "content", "content": "x"})
        assert resp.status_code == 500


@pytest.mark.asyncio
async def test_list_and_delete_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = SimpleNamespace(role="admin", username="admin", user_id=1)
    app = _build_app(admin)
    transport = ASGITransport(app=app)

    monkeypatch.setattr(share_api, "list_all_links", AsyncMock(return_value=ShareLinkListResponse(links=[_sample_link()])))
    monkeypatch.setattr(share_api, "list_my_links", AsyncMock(return_value=ShareLinkListResponse(links=[_sample_link()])))
    monkeypatch.setattr(share_api, "revoke_link", AsyncMock(return_value=None))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/share?view=all")
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True

        resp = await client.delete("/api/share/abc123")
        assert resp.status_code == 204

    # 刪除錯誤分支
    monkeypatch.setattr(share_api, "revoke_link", AsyncMock(side_effect=ShareLinkNotFoundError()))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete("/api/share/missing")
        assert resp.status_code == 404

    monkeypatch.setattr(share_api, "revoke_link", AsyncMock(side_effect=ShareError("forbidden")))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete("/api/share/x")
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_public_get_resource_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _build_app(SimpleNamespace(role="user", username="u", user_id=1))
    transport = ASGITransport(app=app)

    monkeypatch.setattr(
        share_api,
        "get_public_resource",
        AsyncMock(return_value=PublicResourceResponse(
            type="content",
            data={"content": "hello"},
            shared_by="admin",
            shared_at=datetime.now(timezone.utc),
            expires_at=None,
        )),
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/public/abc")
        assert resp.status_code == 200

    monkeypatch.setattr(share_api, "get_public_resource", AsyncMock(return_value=PasswordRequiredResponse()))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/public/abc")
        assert resp.status_code == 401

    monkeypatch.setattr(share_api, "get_public_resource", AsyncMock(side_effect=ShareLinkNotFoundError()))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/public/abc")).status_code == 404

    monkeypatch.setattr(share_api, "get_public_resource", AsyncMock(side_effect=ShareLinkExpiredError()))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/public/abc")).status_code == 410

    monkeypatch.setattr(share_api, "get_public_resource", AsyncMock(side_effect=ShareLinkLockedError()))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/public/abc")).status_code == 423

    monkeypatch.setattr(share_api, "get_public_resource", AsyncMock(side_effect=PasswordIncorrectError()))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/public/abc")).status_code == 401

    monkeypatch.setattr(share_api, "get_public_resource", AsyncMock(side_effect=ResourceNotFoundError()))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/public/abc")).status_code == 404

    monkeypatch.setattr(share_api, "get_public_resource", AsyncMock(side_effect=ShareError("x")))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/public/abc")).status_code == 500


@pytest.mark.asyncio
async def test_public_attachment_and_download_routes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _build_app(SimpleNamespace(role="user", username="u", user_id=1))
    transport = ASGITransport(app=app)

    monkeypatch.setattr(share_api, "get_link_info", AsyncMock(return_value={"resource_type": "knowledge", "resource_id": "kb1"}))
    monkeypatch.setattr(share_api.settings, "knowledge_data_path", str(tmp_path))

    # 本機附件
    file_path = tmp_path / "assets" / "images" / "kb1-photo.png"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"pngdata")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/public/tok/attachments/local/images/kb1-photo.png")
        assert resp.status_code == 200
        assert resp.content == b"pngdata"

        # 路徑穿越
        resp = await client.get("/api/public/tok/attachments/../../etc/passwd")
        assert resp.status_code in (400, 404)

    # 下載：nas_file
    nas_file = tmp_path / "demo.txt"
    nas_file.write_bytes(b"hello")
    monkeypatch.setattr(share_api, "get_link_info", AsyncMock(return_value={"resource_type": "nas_file", "resource_id": "x"}))
    monkeypatch.setattr(share_api, "validate_nas_file_path", lambda _p: nas_file)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/public/tok/download")
        assert resp.status_code == 200
        assert resp.content == b"hello"

    # 下載：project_attachment
    aid = uuid4()
    monkeypatch.setattr(share_api, "get_link_info", AsyncMock(return_value={"resource_type": "project_attachment", "resource_id": str(aid)}))
    from ching_tech_os.services import share as share_service
    from ching_tech_os.services import project as project_service

    monkeypatch.setattr(share_service, "get_project_attachment_info", AsyncMock(return_value={"project_id": uuid4()}))
    monkeypatch.setattr(project_service, "get_attachment_content", AsyncMock(return_value=(b"att", "a.pdf")))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/public/tok/download")
        assert resp.status_code == 200
        assert resp.content == b"att"

    # 下載：不支援類型
    monkeypatch.setattr(share_api, "get_link_info", AsyncMock(return_value={"resource_type": "content", "resource_id": ""}))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/public/tok/download")
        assert resp.status_code == 500
