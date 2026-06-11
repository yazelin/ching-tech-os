"""知識庫條目層級讀取權限測試（API 層）

personal 條目僅 owner（與 admin）可讀，非 owner 一律 404（不洩漏存在）。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from ching_tech_os.api import knowledge as knowledge_api
from ching_tech_os.models.auth import SessionData
from ching_tech_os.models.knowledge import (
    KnowledgeResponse,
    KnowledgeSource,
    KnowledgeTags,
)


def _session(username: str = "u1", role: str = "user") -> SessionData:
    now = datetime.now()
    return SessionData(
        username=username,
        password="",
        nas_host="h",
        user_id=1,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        role=role,
        app_permissions={"knowledge-base": True},
    )


def _kb(kb_id: str = "kb-9", scope: str = "global", owner: str | None = None) -> KnowledgeResponse:
    return KnowledgeResponse(
        id=kb_id,
        title="t",
        type="note",
        category="technical",
        scope=scope,
        owner=owner,
        tags=KnowledgeTags(),
        source=KnowledgeSource(),
        related=[],
        attachments=[],
        author="a",
        created_at=date.today(),
        updated_at=date.today(),
        content="祕密內容",
    )


@pytest.fixture(autouse=True)
def _no_db(monkeypatch: pytest.MonkeyPatch):
    """讀取權限走真實的 check_knowledge_permission_async，只擋掉 DB 查詢"""
    monkeypatch.setattr(
        knowledge_api, "get_user_preferences", AsyncMock(return_value={})
    )


@pytest.mark.asyncio
async def test_personal_entry_hidden_from_non_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        knowledge_api, "get_knowledge", lambda _id: _kb(scope="personal", owner="jayho")
    )

    # 非 owner：404（與「不存在」相同訊息，不洩漏存在）
    with pytest.raises(HTTPException) as e:
        await knowledge_api.get_single_knowledge("kb-9", session=_session("yazelin"))
    assert e.value.status_code == 404
    assert "不存在" in e.value.detail

    # owner：可讀
    got = await knowledge_api.get_single_knowledge("kb-9", session=_session("jayho"))
    assert got.content == "祕密內容"

    # admin：可讀（與 check_knowledge_permission_async 既有語意一致）
    got = await knowledge_api.get_single_knowledge(
        "kb-9", session=_session("boss", role="admin")
    )
    assert got.id == "kb-9"


@pytest.mark.asyncio
async def test_global_and_project_entries_readable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(knowledge_api, "get_knowledge", lambda _id: _kb(scope="global"))
    assert (await knowledge_api.get_single_knowledge("kb-9", session=_session())).id == "kb-9"

    monkeypatch.setattr(
        knowledge_api, "get_knowledge", lambda _id: _kb(scope="project", owner=None)
    )
    assert (await knowledge_api.get_single_knowledge("kb-9", session=_session())).id == "kb-9"


@pytest.mark.asyncio
async def test_history_and_version_blocked_for_non_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        knowledge_api, "get_knowledge", lambda _id: _kb(scope="personal", owner="jayho")
    )
    history_mock = AsyncMock()
    monkeypatch.setattr(knowledge_api, "get_history", history_mock)
    monkeypatch.setattr(knowledge_api, "get_version", history_mock)

    with pytest.raises(HTTPException) as e:
        await knowledge_api.get_knowledge_history("kb-9", session=_session("yazelin"))
    assert e.value.status_code == 404

    with pytest.raises(HTTPException) as e:
        await knowledge_api.get_knowledge_version("kb-9", "abc123", session=_session("yazelin"))
    assert e.value.status_code == 404

    # 完全沒碰到底層 git 函數
    history_mock.assert_not_called()


@pytest.mark.asyncio
async def test_attachment_paths_check_owning_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        knowledge_api, "get_knowledge", lambda _id: _kb(kb_id=_id, scope="personal", owner="jayho")
    )

    # NAS 附件：路徑第一段是 kb id → 非 owner 404
    with pytest.raises(HTTPException) as e:
        await knowledge_api.get_attachment("kb-9/secret.pdf", session=_session("yazelin"))
    assert e.value.status_code == 404

    # 本機 asset：檔名以 kb id 開頭 → 非 owner 404
    with pytest.raises(HTTPException) as e:
        await knowledge_api.get_local_asset(
            "images/kb-9-secret.png", session=_session("yazelin")
        )
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_attachment_orphan_files_keep_old_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """找不到對應知識條目（孤兒檔案）時不擋，由檔案層自然 404"""
    from ching_tech_os.services.knowledge import KnowledgeNotFoundError

    monkeypatch.setattr(
        knowledge_api,
        "get_knowledge",
        lambda _id: (_ for _ in ()).throw(KnowledgeNotFoundError("x")),
    )
    monkeypatch.setattr(
        knowledge_api, "get_nas_attachment", lambda _p: b"orphan-bytes"
    )
    resp = await knowledge_api.get_attachment("kb-9/orphan.pdf", session=_session("yazelin"))
    assert resp.body == b"orphan-bytes"
