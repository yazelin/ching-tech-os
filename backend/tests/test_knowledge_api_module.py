"""knowledge API 模組測試。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from ching_tech_os.api import knowledge as knowledge_api
from ching_tech_os.models.auth import SessionData
from ching_tech_os.models.knowledge import (
    AttachmentUpdate,
    KnowledgeAttachment,
    KnowledgeCreate,
    KnowledgeListItem,
    KnowledgeListResponse,
    KnowledgeResponse,
    KnowledgeTags,
    KnowledgeUpdate,
    KnowledgeSource,
    TagsResponse,
)
from ching_tech_os.services.knowledge import KnowledgeError, KnowledgeNotFoundError


def _session() -> SessionData:
    now = datetime.now()
    return SessionData(
        username="u1",
        password="pw",
        nas_host="h",
        user_id=1,
        role="user",
        app_permissions={"knowledge-base": True},
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


def _knowledge(kb_id: str = "kb-1", scope: str = "personal", owner: str | None = "u1") -> KnowledgeResponse:
    return KnowledgeResponse(
        id=kb_id,
        title="標題",
        type="knowledge",
        category="technical",
        scope=scope,
        owner=owner,
        project_id=None,
        tags=KnowledgeTags(),
        source=KnowledgeSource(),
        related=[],
        attachments=[KnowledgeAttachment(type="image", path="../assets/images/a.png")],
        author="u1",
        created_at=date.today(),
        updated_at=date.today(),
        content="內容",
    )


@pytest.mark.asyncio
async def test_list_tags_rebuild_and_assets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session = _session()
    list_resp = KnowledgeListResponse(
        items=[
            KnowledgeListItem(
                id="kb-1",
                title="A",
                type="knowledge",
                category="technical",
                scope="global",
                owner=None,
                project_id=None,
                tags=KnowledgeTags(),
                author="u1",
                updated_at=date.today(),
            )
        ],
        total=1,
        query=None,
    )
    tags_resp = TagsResponse(
        projects=["p1"],
        types=["knowledge"],
        categories=["technical"],
        roles=["all"],
        levels=["beginner"],
        topics=["x"],
    )

    monkeypatch.setattr(knowledge_api, "search_knowledge", lambda **_kwargs: list_resp)
    monkeypatch.setattr(knowledge_api, "get_all_tags", AsyncMock(return_value=tags_resp))
    monkeypatch.setattr(knowledge_api, "rebuild_index", lambda: {"ok": True})
    monkeypatch.setattr(knowledge_api, "get_nas_attachment", lambda _p: b"img")

    assert (await knowledge_api.list_knowledge(session=session)).total == 1
    assert (await knowledge_api.get_tags(session=session)).projects == ["p1"]
    assert (await knowledge_api.rebuild_knowledge_index(session=session))["ok"] is True
    att = await knowledge_api.get_attachment("images/x.png")
    assert att.body == b"img"

    monkeypatch.setattr(knowledge_api, "search_knowledge", lambda **_kwargs: (_ for _ in ()).throw(KnowledgeError("x")))
    with pytest.raises(HTTPException) as e1:
        await knowledge_api.list_knowledge(session=session)
    assert e1.value.status_code == 500

    monkeypatch.setattr(knowledge_api, "get_all_tags", AsyncMock(side_effect=KnowledgeError("x")))
    with pytest.raises(HTTPException):
        await knowledge_api.get_tags(session=session)

    monkeypatch.setattr(knowledge_api, "rebuild_index", lambda: (_ for _ in ()).throw(KnowledgeError("x")))
    with pytest.raises(HTTPException):
        await knowledge_api.rebuild_knowledge_index(session=session)

    monkeypatch.setattr(knowledge_api, "get_nas_attachment", lambda _p: (_ for _ in ()).throw(KnowledgeError("missing")))
    with pytest.raises(HTTPException) as e2:
        await knowledge_api.get_attachment("missing.png")
    assert e2.value.status_code == 404

    # get_local_asset 成功 / 防穿越 / not found / 讀取失敗
    assets_base = tmp_path / "assets" / "images"
    assets_base.mkdir(parents=True, exist_ok=True)
    f = assets_base / "demo.png"
    f.write_bytes(b"demo")
    monkeypatch.setattr(knowledge_api.settings, "knowledge_data_path", str(tmp_path))
    ok = await knowledge_api.get_local_asset("images/demo.png", session=session)
    assert ok.body == b"demo"

    with pytest.raises(HTTPException) as e3:
        await knowledge_api.get_local_asset("../secret", session=session)
    assert e3.value.status_code == 400

    with pytest.raises(HTTPException) as e4:
        await knowledge_api.get_local_asset("images/notfound.png", session=session)
    assert e4.value.status_code == 404

    original_read_bytes = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda _self: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(HTTPException) as e5:
        await knowledge_api.get_local_asset("images/demo.png", session=session)
    assert e5.value.status_code == 500
    monkeypatch.setattr(Path, "read_bytes", original_read_bytes)


@pytest.mark.asyncio
async def test_get_create_update_delete_history_version(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    kb = _knowledge()

    monkeypatch.setattr(knowledge_api, "get_knowledge", lambda _id: kb)
    assert (await knowledge_api.get_single_knowledge("kb-1", session=session)).id == "kb-1"

    monkeypatch.setattr(knowledge_api, "get_knowledge", lambda _id: (_ for _ in ()).throw(KnowledgeNotFoundError("x")))
    with pytest.raises(HTTPException) as e1:
        await knowledge_api.get_single_knowledge("kb-x", session=session)
    assert e1.value.status_code == 404

    monkeypatch.setattr(knowledge_api, "get_knowledge", lambda _id: (_ for _ in ()).throw(KnowledgeError("x")))
    with pytest.raises(HTTPException):
        await knowledge_api.get_single_knowledge("kb-x", session=session)

    # create: global 權限拒絕
    monkeypatch.setattr(knowledge_api, "get_user_preferences", AsyncMock(return_value={}))
    monkeypatch.setattr(knowledge_api, "check_knowledge_permission_async", AsyncMock(return_value=False))
    with pytest.raises(HTTPException) as e2:
        await knowledge_api.create_new_knowledge(
            KnowledgeCreate(title="t", content="c", scope="global"),
            session=session,
        )
    assert e2.value.status_code == 403

    # create: success + log_message 失敗不影響
    monkeypatch.setattr(knowledge_api, "check_knowledge_permission_async", AsyncMock(return_value=True))
    monkeypatch.setattr(knowledge_api, "create_knowledge", lambda _d, owner=None: _knowledge(owner=owner))
    monkeypatch.setattr(knowledge_api, "log_message", AsyncMock(side_effect=RuntimeError("ignore")))
    created = await knowledge_api.create_new_knowledge(
        KnowledgeCreate(title="t", content="c", scope="global"),
        session=session,
    )
    assert created.owner == "u1"

    monkeypatch.setattr(knowledge_api, "create_knowledge", lambda *_a, **_k: (_ for _ in ()).throw(KnowledgeError("x")))
    with pytest.raises(HTTPException):
        await knowledge_api.create_new_knowledge(KnowledgeCreate(title="t", content="c"), session=session)

    # update: not found / no permission / success / error
    monkeypatch.setattr(knowledge_api, "get_knowledge", lambda _id: (_ for _ in ()).throw(KnowledgeNotFoundError("x")))
    with pytest.raises(HTTPException) as e3:
        await knowledge_api.update_existing_knowledge("kb-x", KnowledgeUpdate(title="u"), session=session)
    assert e3.value.status_code == 404

    monkeypatch.setattr(knowledge_api, "get_knowledge", lambda _id: _knowledge(scope="personal", owner="other"))
    monkeypatch.setattr(knowledge_api, "check_knowledge_permission_async", AsyncMock(return_value=False))
    with pytest.raises(HTTPException) as e4:
        await knowledge_api.update_existing_knowledge("kb-1", KnowledgeUpdate(title="u"), session=session)
    assert e4.value.status_code == 403

    monkeypatch.setattr(knowledge_api, "check_knowledge_permission_async", AsyncMock(return_value=True))
    monkeypatch.setattr(knowledge_api, "update_knowledge", lambda _id, _d: _knowledge(kb_id=_id))
    monkeypatch.setattr(knowledge_api, "log_message", AsyncMock(side_effect=RuntimeError("ignore")))
    assert (await knowledge_api.update_existing_knowledge("kb-1", KnowledgeUpdate(title="u"), session=session)).id == "kb-1"

    monkeypatch.setattr(knowledge_api, "update_knowledge", lambda *_a, **_k: (_ for _ in ()).throw(KnowledgeError("x")))
    with pytest.raises(HTTPException):
        await knowledge_api.update_existing_knowledge("kb-1", KnowledgeUpdate(title="u"), session=session)

    # delete: not found / no permission / success / error
    monkeypatch.setattr(knowledge_api, "get_knowledge", lambda _id: (_ for _ in ()).throw(KnowledgeNotFoundError("x")))
    with pytest.raises(HTTPException):
        await knowledge_api.delete_existing_knowledge("kb-x", session=session)

    monkeypatch.setattr(knowledge_api, "get_knowledge", lambda _id: _knowledge(scope="global", owner=None))
    monkeypatch.setattr(knowledge_api, "check_knowledge_permission_async", AsyncMock(return_value=False))
    with pytest.raises(HTTPException):
        await knowledge_api.delete_existing_knowledge("kb-1", session=session)

    monkeypatch.setattr(knowledge_api, "check_knowledge_permission_async", AsyncMock(return_value=True))
    monkeypatch.setattr(knowledge_api, "delete_knowledge", lambda _id: None)
    monkeypatch.setattr(knowledge_api, "log_message", AsyncMock(side_effect=RuntimeError("ignore")))
    await knowledge_api.delete_existing_knowledge("kb-1", session=session)

    monkeypatch.setattr(knowledge_api, "delete_knowledge", lambda _id: (_ for _ in ()).throw(KnowledgeError("x")))
    with pytest.raises(HTTPException):
        await knowledge_api.delete_existing_knowledge("kb-1", session=session)

    # history/version
    monkeypatch.setattr(knowledge_api, "get_history", lambda _id: {"id": _id, "entries": []})
    monkeypatch.setattr(knowledge_api, "get_version", lambda _id, _c: {"id": _id, "commit": _c, "content": "x"})
    assert (await knowledge_api.get_knowledge_history("kb-1", session=session))["id"] == "kb-1"
    assert (await knowledge_api.get_knowledge_version("kb-1", "abc", session=session))["commit"] == "abc"

    monkeypatch.setattr(knowledge_api, "get_history", lambda _id: (_ for _ in ()).throw(KnowledgeNotFoundError("x")))
    with pytest.raises(HTTPException):
        await knowledge_api.get_knowledge_history("kb-x", session=session)
    monkeypatch.setattr(knowledge_api, "get_version", lambda _id, _c: (_ for _ in ()).throw(KnowledgeError("x")))
    with pytest.raises(HTTPException):
        await knowledge_api.get_knowledge_version("kb-x", "abc", session=session)


@pytest.mark.asyncio
async def test_attachment_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    monkeypatch.setattr(knowledge_api, "get_knowledge", lambda _id: _knowledge(kb_id=_id))

    upload = UploadFile(file=BytesIO(b"abc"), filename="a.txt")
    monkeypatch.setattr(knowledge_api, "upload_attachment", lambda *_args, **_kwargs: KnowledgeAttachment(type="file", path="p", description="d"))
    resp = await knowledge_api.upload_knowledge_attachment("kb-1", upload, description="d", session=session)
    assert resp["success"] is True and resp["attachment"]["path"] == "p"

    monkeypatch.setattr(knowledge_api, "get_knowledge", lambda _id: (_ for _ in ()).throw(KnowledgeNotFoundError("x")))
    upload2 = UploadFile(file=BytesIO(b"abc"), filename="a.txt")
    with pytest.raises(HTTPException) as e1:
        await knowledge_api.upload_knowledge_attachment("kb-x", upload2, session=session)
    assert e1.value.status_code == 404

    monkeypatch.setattr(knowledge_api, "get_knowledge", lambda _id: _knowledge(kb_id=_id))
    monkeypatch.setattr(knowledge_api, "upload_attachment", lambda *_args, **_kwargs: (_ for _ in ()).throw(KnowledgeError("x")))
    upload3 = UploadFile(file=BytesIO(b"abc"), filename="a.txt")
    with pytest.raises(HTTPException) as e2:
        await knowledge_api.upload_knowledge_attachment("kb-1", upload3, session=session)
    assert e2.value.status_code == 500

    # delete attachment
    monkeypatch.setattr(knowledge_api, "delete_attachment", lambda _id, _idx: None)
    await knowledge_api.delete_knowledge_attachment("kb-1", 0, session=session)
    monkeypatch.setattr(knowledge_api, "delete_attachment", lambda _id, _idx: (_ for _ in ()).throw(KnowledgeError("x")))
    with pytest.raises(HTTPException) as e3:
        await knowledge_api.delete_knowledge_attachment("kb-1", 0, session=session)
    assert e3.value.status_code == 400

    # update attachment
    monkeypatch.setattr(
        knowledge_api,
        "update_attachment",
        lambda _id, _idx, description=None, attachment_type=None: KnowledgeAttachment(type=attachment_type or "file", path="p2", description=description),
    )
    updated = await knowledge_api.update_knowledge_attachment(
        "kb-1",
        0,
        AttachmentUpdate(type="image", description="new"),
        session=session,
    )
    assert updated.type == "image"

    monkeypatch.setattr(knowledge_api, "update_attachment", lambda *_a, **_k: (_ for _ in ()).throw(KnowledgeError("x")))
    with pytest.raises(HTTPException) as e4:
        await knowledge_api.update_knowledge_attachment("kb-1", 0, AttachmentUpdate(type="file"), session=session)
    assert e4.value.status_code == 400
