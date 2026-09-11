"""分享連結工具與端點的存取檢查（issue #205）。

背景與 #201／#204／#207 同一個根因：這套權限設計假設呼叫者是已綁定的自己人，
但 bot 對外開放。`create_share_link`／`share_knowledge_attachment` 原本在
`TOOL_APP_MAPPING` 對到 `None`（等同不檢查），`services/share.py` 的
`get_resource_title()` 又只驗「資源存在」——knowledge 不看 scope／owner／is_public、
nas_file 沒帶 `source_permissions`——任何呼叫者都能把別人的知識條目或 NAS 檔案
變成公開連結。

本檔驗證：
- 兩支工具對到 `share-manager`，`share-manager` 進 `APPS_REQUIRE_BOUND_USER`：
  未綁定一律拒絕，且 share service 完全沒被 await。
- 已綁定但沒有 `share-manager` 權限：回功能權限不足。
- 真正的資源存取檢查（`services/share.py` 的 `check_resource_access()`，REST 與
  MCP 共用那層）：knowledge 走與 `get_knowledge_item` 相同的
  `check_knowledge_permission_async(..., action="read")`、nas_file 走與
  `read_document`／`send_nas_file` 相同的 `validate_nas_file_path(...,
  source_permissions=...)`；沒權限就不建連結。
- REST `POST /api/share` 同樣經過那層：已登入者也不能分享自己讀不到的資源。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ching_tech_os.api.share import router as share_router
from ching_tech_os.api.auth import get_current_session
from ching_tech_os.models.auth import SessionData
from ching_tech_os.services import permissions as permissions_module
from ching_tech_os.services import share as share_service
from ching_tech_os.services.mcp import knowledge_tools
from ching_tech_os.services.mcp import server as mcp_server
from ching_tech_os.services.mcp import share_tools


class _ConnCtx:
    """最小 async context manager，包一個假的 connection。"""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


def _item(**kwargs):
    """假的 KnowledgeResponse（只用到存取檢查會看的欄位）。"""
    base = {
        "id": "kb-001",
        "title": "測試知識",
        "scope": "global",
        "is_public": True,
        "owner": None,
        "project_id": None,
        "category": "note",
        "content": "內容",
        "tags": SimpleNamespace(topics=[], projects=[], roles=[], level=None),
        "attachments": [],
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def _user_row(username="yaze", role="user", preferences=None):
    return {
        "id": 1,
        "username": username,
        "role": role,
        "preferences": preferences if preferences is not None else {},
    }


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch):
    """不碰真的資料庫、知識庫與 NAS。"""
    monkeypatch.delenv("CTOS_USER_ID", raising=False)
    monkeypatch.setattr(share_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(mcp_server, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(knowledge_tools, "ensure_db_connection", AsyncMock())
    monkeypatch.setattr(
        share_service,
        "_resolve_source_permissions",
        AsyncMock(return_value={"library": True}),
    )


@pytest.fixture
def _bound_user(monkeypatch: pytest.MonkeyPatch):
    """已綁定的一般使用者（users 查得到）。"""
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value=_user_row()))
    monkeypatch.setattr(share_service, "get_connection", lambda: _ConnCtx(conn))
    monkeypatch.setattr(mcp_server, "get_connection", lambda: _ConnCtx(conn))
    monkeypatch.setattr(knowledge_tools, "get_connection", lambda: _ConnCtx(conn))
    return conn


@pytest.fixture
def _no_link_created(monkeypatch: pytest.MonkeyPatch):
    """存取檢查之後才會呼叫的東西，全部炸開＝證明連結沒被建立。"""
    title = AsyncMock(side_effect=AssertionError("不該走到建立連結"))
    monkeypatch.setattr(share_service, "get_resource_title", title)
    return title


# ============================================================
# 1. registry：兩支工具對到 share-manager，且 share-manager 需綁定
# ============================================================


def test_share_tools_mapped_to_share_manager() -> None:
    assert permissions_module.TOOL_APP_MAPPING["create_share_link"] == "share-manager"
    assert (
        permissions_module.TOOL_APP_MAPPING["share_knowledge_attachment"]
        == "share-manager"
    )


def test_share_manager_requires_bound_user() -> None:
    assert "share-manager" in permissions_module.APPS_REQUIRE_BOUND_USER


def test_share_manager_default_permission_unchanged() -> None:
    """預設值不動（交付第 1 點）：已綁定者預設有 share-manager。"""
    assert permissions_module.DEFAULT_APP_PERMISSIONS["share-manager"] is True


# ============================================================
# 2. 未綁定：兩支工具都拒絕，share service 沒被 await
# ============================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["create_share_link", "share_knowledge_attachment"])
async def test_unbound_denied_by_tool_permission(tool_name: str) -> None:
    allowed, message = await mcp_server.check_mcp_tool_permission(tool_name, None)
    assert allowed is False
    assert message == permissions_module.BOUND_USER_REQUIRED_MESSAGE


@pytest.mark.asyncio
async def test_create_share_link_unbound_denied_and_service_not_awaited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boom = AsyncMock(side_effect=AssertionError("share service 不該被呼叫"))
    monkeypatch.setattr(share_service, "create_share_link", boom)

    result = await share_tools.create_share_link(
        resource_type="knowledge", resource_id="kb-001", ctos_user_id=None
    )

    assert result == f"❌ {permissions_module.BOUND_USER_REQUIRED_MESSAGE}"
    boom.assert_not_awaited()


@pytest.mark.asyncio
async def test_share_knowledge_attachment_unbound_denied_and_service_not_awaited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boom = AsyncMock(side_effect=AssertionError("share service 不該被呼叫"))
    monkeypatch.setattr(share_service, "create_share_link", boom)
    monkeypatch.setattr(
        share_service,
        "check_resource_access",
        AsyncMock(side_effect=AssertionError("不該走到資源檢查")),
    )

    result = await share_tools.share_knowledge_attachment(
        kb_id="kb-001", attachment_idx=0, ctos_user_id=None
    )

    assert result == f"❌ {permissions_module.BOUND_USER_REQUIRED_MESSAGE}"
    boom.assert_not_awaited()


# ============================================================
# 3. 已綁定但沒有 share-manager 權限
# ============================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["create_share_link", "share_knowledge_attachment"])
async def test_bound_user_without_share_manager_denied(
    monkeypatch: pytest.MonkeyPatch, tool_name: str
) -> None:
    conn = SimpleNamespace(
        fetchrow=AsyncMock(
            return_value={
                "role": "user",
                "preferences": {"permissions": {"apps": {"share-manager": False}}},
            }
        )
    )
    monkeypatch.setattr(mcp_server, "get_connection", lambda: _ConnCtx(conn))

    allowed, message = await mcp_server.check_mcp_tool_permission(tool_name, 1)

    assert allowed is False
    assert message == "您沒有「分享管理」功能權限，無法使用此工具"


@pytest.mark.asyncio
async def test_create_share_link_tool_reports_missing_app_permission(
    monkeypatch: pytest.MonkeyPatch, _no_link_created
) -> None:
    conn = SimpleNamespace(
        fetchrow=AsyncMock(
            return_value={
                "role": "user",
                "preferences": {"permissions": {"apps": {"share-manager": False}}},
            }
        )
    )
    monkeypatch.setattr(mcp_server, "get_connection", lambda: _ConnCtx(conn))

    result = await share_tools.create_share_link(
        resource_type="knowledge", resource_id="kb-001", ctos_user_id=1
    )

    assert result == "❌ 您沒有「分享管理」功能權限，無法使用此工具"
    _no_link_created.assert_not_awaited()


# ============================================================
# 4. 資源存取檢查：knowledge
# ============================================================


@pytest.mark.asyncio
async def test_check_resource_access_denies_personal_item_of_others(
    monkeypatch: pytest.MonkeyPatch, _bound_user
) -> None:
    monkeypatch.setattr(
        share_service, "get_knowledge", lambda kb_id: _item(scope="personal", owner="other")
    )

    with pytest.raises(share_service.ShareAccessDenied):
        await share_service.check_resource_access(
            "knowledge", "kb-001", share_service.ShareActor.from_ctos_user_id(1)
        )


@pytest.mark.asyncio
async def test_check_resource_access_allows_own_personal_item(
    monkeypatch: pytest.MonkeyPatch, _bound_user
) -> None:
    monkeypatch.setattr(
        share_service, "get_knowledge", lambda kb_id: _item(scope="personal", owner="yaze")
    )

    await share_service.check_resource_access(
        "knowledge", "kb-001", share_service.ShareActor.from_ctos_user_id(1)
    )


@pytest.mark.asyncio
async def test_check_resource_access_knowledge_missing_is_not_found(
    monkeypatch: pytest.MonkeyPatch, _bound_user
) -> None:
    from ching_tech_os.services.knowledge import KnowledgeNotFoundError

    def _missing(kb_id):
        raise KnowledgeNotFoundError("不存在")

    monkeypatch.setattr(share_service, "get_knowledge", _missing)

    with pytest.raises(share_service.ResourceNotFoundError):
        await share_service.check_resource_access(
            "knowledge", "kb-404", share_service.ShareActor.from_ctos_user_id(1)
        )


@pytest.mark.asyncio
async def test_create_share_link_tool_denies_personal_item_of_others(
    monkeypatch: pytest.MonkeyPatch, _bound_user, _no_link_created
) -> None:
    monkeypatch.setattr(
        share_service, "get_knowledge", lambda kb_id: _item(scope="personal", owner="other")
    )

    result = await share_tools.create_share_link(
        resource_type="knowledge", resource_id="kb-001", ctos_user_id=1
    )

    assert "錯誤" in result
    assert "權限" in result
    _no_link_created.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_share_link_tool_creates_link_when_readable(
    monkeypatch: pytest.MonkeyPatch, _bound_user
) -> None:
    """對照組：有權限且讀得到就照常建立。"""
    monkeypatch.setattr(share_service, "get_knowledge", lambda kb_id: _item())
    monkeypatch.setattr(
        share_service, "get_resource_title", AsyncMock(return_value="測試知識")
    )
    created = AsyncMock(
        return_value=SimpleNamespace(
            full_url="https://example.com/s/abc123",
            token="abc123",
            resource_title="測試知識",
            expires_at=None,
            password=None,
        )
    )
    monkeypatch.setattr(share_service, "create_share_link", created)

    result = await share_tools.create_share_link(
        resource_type="knowledge", resource_id="kb-001", ctos_user_id=1
    )

    assert "https://example.com/s/abc123" in result
    created.assert_awaited()
    actor = created.await_args.kwargs["actor"]
    assert actor.user_id == 1 and actor.is_bound is True


# ============================================================
# 5. 資源存取檢查：nas_file（帶 source_permissions）
# ============================================================


@pytest.mark.asyncio
async def test_check_resource_access_nas_file_passes_source_permissions(
    monkeypatch: pytest.MonkeyPatch, _bound_user
) -> None:
    seen = {}

    def _validate(file_path, source_permissions=None):
        seen["source_permissions"] = source_permissions
        return Path("/mnt/nas/ok.txt")

    monkeypatch.setattr(share_service, "validate_nas_file_path", _validate)

    await share_service.check_resource_access(
        "nas_file", "shared://library/ok.txt", share_service.ShareActor.from_ctos_user_id(1)
    )

    assert seen["source_permissions"] == {"library": True}


@pytest.mark.asyncio
async def test_check_resource_access_nas_file_denied(
    monkeypatch: pytest.MonkeyPatch, _bound_user
) -> None:
    def _validate(file_path, source_permissions=None):
        raise share_service.NasFileAccessDenied("權限不足：無法存取此 shared 來源")

    monkeypatch.setattr(share_service, "validate_nas_file_path", _validate)

    with pytest.raises(share_service.ShareAccessDenied):
        await share_service.check_resource_access(
            "nas_file",
            "shared://projects/secret.pdf",
            share_service.ShareActor.from_ctos_user_id(1),
        )


@pytest.mark.asyncio
async def test_create_share_link_tool_denies_nas_file_without_permission(
    monkeypatch: pytest.MonkeyPatch, _bound_user, _no_link_created
) -> None:
    def _validate(file_path, source_permissions=None):
        raise share_service.NasFileAccessDenied("權限不足：無法存取此 shared 來源")

    monkeypatch.setattr(share_service, "validate_nas_file_path", _validate)

    result = await share_tools.create_share_link(
        resource_type="nas_file", resource_id="shared://projects/secret.pdf", ctos_user_id=1
    )

    assert "錯誤" in result
    assert "權限不足" in result
    _no_link_created.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_resource_access_nas_file_denied_for_unbound() -> None:
    with pytest.raises(share_service.ShareAccessDenied):
        await share_service.check_resource_access(
            "nas_file", "shared://library/ok.txt", share_service.ShareActor()
        )


# ============================================================
# 6. share_knowledge_attachment 也走同一層
# ============================================================


@pytest.mark.asyncio
async def test_share_knowledge_attachment_denies_unreadable_item(
    monkeypatch: pytest.MonkeyPatch, _bound_user
) -> None:
    from ching_tech_os.services import knowledge as kb_service

    monkeypatch.setattr(
        share_service, "get_knowledge", lambda kb_id: _item(scope="personal", owner="other")
    )
    monkeypatch.setattr(
        kb_service,
        "get_knowledge",
        lambda kb_id: (_ for _ in ()).throw(AssertionError("不該讀到附件")),
    )
    boom = AsyncMock(side_effect=AssertionError("不該建立連結"))
    monkeypatch.setattr(share_service, "create_share_link", boom)

    result = await share_tools.share_knowledge_attachment(
        kb_id="kb-001", attachment_idx=0, ctos_user_id=1
    )

    assert "錯誤" in result
    assert "權限" in result
    boom.assert_not_awaited()


# ============================================================
# 7. 與 get_knowledge_item 同一條路（逐格比對，不只嘴上說「共用」）
# ============================================================


_ITEM_MATRIX = [
    ("global", True, None),
    ("global", False, None),
    ("personal", False, "yaze"),
    ("personal", False, "other"),
    ("personal", True, "other"),
    ("project", True, None),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("scope, is_public, owner", _ITEM_MATRIX)
@pytest.mark.parametrize("ctos_user_id", [None, 1])
async def test_share_knowledge_decision_matches_get_knowledge_item(
    monkeypatch: pytest.MonkeyPatch,
    _bound_user,
    scope: str,
    is_public: bool,
    owner: str | None,
    ctos_user_id: int | None,
) -> None:
    """分享的 knowledge 判斷要與 `get_knowledge_item` 的條目層級一致。"""
    from ching_tech_os.services import knowledge as kb_service

    item = _item(scope=scope, is_public=is_public, owner=owner)
    monkeypatch.setattr(share_service, "get_knowledge", lambda kb_id: item)
    monkeypatch.setattr(kb_service, "get_knowledge", lambda kb_id: item)

    tool_err = await knowledge_tools._check_item_access(item, ctos_user_id, "read")
    tool_allows = tool_err is None

    try:
        await share_service.check_resource_access(
            "knowledge", "kb-001", share_service.ShareActor.from_ctos_user_id(ctos_user_id)
        )
        share_allows = True
    except share_service.ShareAccessDenied:
        share_allows = False

    assert share_allows is tool_allows


# ============================================================
# 8. REST：已登入者也不能分享自己讀不到的資源
# ============================================================


def _rest_app(session: SessionData):
    app = FastAPI()
    app.include_router(share_router)
    app.dependency_overrides[get_current_session] = lambda: session
    return app


def _session(role="user", username="yaze", user_id=1):
    now = datetime.now(timezone.utc)
    return SessionData(
        username=username,
        password="test-password",
        nas_host="127.0.0.1",
        user_id=user_id,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        role=role,
    )


def test_rest_create_link_denies_knowledge_user_cannot_read(
    monkeypatch: pytest.MonkeyPatch, _bound_user
) -> None:
    """就算路由的舊檢查放行，service 那層也要擋下讀不到的條目。"""
    import ching_tech_os.api.share as share_api

    monkeypatch.setattr(
        share_api, "get_knowledge", lambda kb_id: _item(scope="personal", owner="other")
    )
    monkeypatch.setattr(
        share_api, "get_user_preferences", AsyncMock(return_value={})
    )
    monkeypatch.setattr(share_api, "check_knowledge_permission", lambda *a, **k: True)
    monkeypatch.setattr(
        share_service, "get_knowledge", lambda kb_id: _item(scope="personal", owner="other")
    )
    monkeypatch.setattr(
        share_service,
        "get_resource_title",
        AsyncMock(side_effect=AssertionError("不該走到建立連結")),
    )

    client = TestClient(_rest_app(_session()))
    resp = client.post("/api/share", json={"resource_type": "knowledge", "resource_id": "kb-001"})

    assert resp.status_code == 403


def test_rest_create_link_denies_nas_file_without_source_permission(
    monkeypatch: pytest.MonkeyPatch, _bound_user
) -> None:
    """路由那層的舊檢查沒帶 `source_permissions`（放行），service 那層要擋下來。"""
    import ching_tech_os.api.share as share_api

    def _legacy_validate(file_path, source_permissions=None):
        return Path("/mnt/nas/projects/x.pdf")

    def _validate(file_path, source_permissions=None):
        raise share_service.NasFileAccessDenied("權限不足：無法存取此 shared 來源")

    monkeypatch.setattr(share_api, "validate_nas_file_path", _legacy_validate)
    monkeypatch.setattr(share_service, "validate_nas_file_path", _validate)
    monkeypatch.setattr(
        share_service,
        "get_resource_title",
        AsyncMock(side_effect=AssertionError("不該走到建立連結")),
    )

    client = TestClient(_rest_app(_session()))
    resp = client.post(
        "/api/share", json={"resource_type": "nas_file", "resource_id": "shared://projects/x.pdf"}
    )

    assert resp.status_code == 403


def test_rest_create_link_allows_readable_knowledge(
    monkeypatch: pytest.MonkeyPatch, _bound_user
) -> None:
    """對照組：讀得到就照常建立（201）。"""
    import ching_tech_os.api.share as share_api
    from ching_tech_os.models.share import ShareLinkResponse

    monkeypatch.setattr(share_api, "get_knowledge", lambda kb_id: _item())
    monkeypatch.setattr(share_api, "get_user_preferences", AsyncMock(return_value={}))
    monkeypatch.setattr(share_api, "check_knowledge_permission", lambda *a, **k: True)
    monkeypatch.setattr(
        share_api,
        "create_share_link",
        AsyncMock(
            return_value=ShareLinkResponse(
                token="abc123",
                url="/s/abc123",
                full_url="https://example.com/s/abc123",
                resource_type="knowledge",
                resource_id="kb-001",
                resource_title="測試知識",
                expires_at=None,
                created_at=datetime.now(timezone.utc),
            )
        ),
    )

    client = TestClient(_rest_app(_session()))
    resp = client.post("/api/share", json={"resource_type": "knowledge", "resource_id": "kb-001"})

    assert resp.status_code == 201
    actor = share_api.create_share_link.await_args.kwargs["actor"]
    assert actor.username == "yaze" and actor.is_bound is True


# ============================================================
# 9. check_resource_access 的其餘分支
# ============================================================


@pytest.mark.asyncio
async def test_check_resource_access_skips_content_type() -> None:
    """content 類型的內容由呼叫端自己提供，沒有別人的資源可洩漏。"""
    await share_service.check_resource_access("content", "", share_service.ShareActor())


@pytest.mark.asyncio
async def test_check_resource_access_rejects_unsupported_type() -> None:
    with pytest.raises(share_service.ShareAccessDenied):
        await share_service.check_resource_access(
            "project", "P-1", share_service.ShareActor.from_ctos_user_id(1)
        )


@pytest.mark.asyncio
async def test_check_resource_access_denies_when_account_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ctos_user_id 有值但帳號已不在資料庫＝等同未綁定。"""
    conn = SimpleNamespace(fetchrow=AsyncMock(return_value=None))
    monkeypatch.setattr(share_service, "get_connection", lambda: _ConnCtx(conn))
    monkeypatch.setattr(share_service, "get_knowledge", lambda kb_id: _item())

    with pytest.raises(share_service.ShareAccessDenied):
        await share_service.check_resource_access(
            "knowledge", "kb-001", share_service.ShareActor.from_ctos_user_id(999999)
        )


@pytest.mark.asyncio
async def test_check_resource_access_nas_file_missing_is_not_found(
    monkeypatch: pytest.MonkeyPatch, _bound_user
) -> None:
    def _validate(file_path, source_permissions=None):
        raise share_service.NasFileNotFoundError("檔案不存在：/x.txt")

    monkeypatch.setattr(share_service, "validate_nas_file_path", _validate)

    with pytest.raises(share_service.ResourceNotFoundError):
        await share_service.check_resource_access(
            "nas_file", "/x.txt", share_service.ShareActor.from_ctos_user_id(1)
        )


@pytest.mark.asyncio
async def test_prefilled_actor_does_not_query_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REST 的 session 已經有 username／role，補齊過的 actor 不該再查一次資料庫。"""
    monkeypatch.setattr(
        share_service,
        "get_connection",
        lambda: (_ for _ in ()).throw(AssertionError("不該查 users")),
    )
    monkeypatch.setattr(
        share_service, "get_knowledge", lambda kb_id: _item(scope="personal", owner="yaze")
    )

    await share_service.check_resource_access(
        "knowledge",
        "kb-001",
        share_service.ShareActor(
            user_id=1, username="yaze", role="user", preferences={}, is_bound=True
        ),
    )


@pytest.mark.asyncio
async def test_resolve_source_permissions_uses_user_shared_mounts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """nas_file 的來源權限與 `read_document`／`send_nas_file` 同一條路。"""
    monkeypatch.undo()  # 解除 autouse fixture 對 _resolve_source_permissions 的替換
    monkeypatch.delenv("CTOS_USER_ID", raising=False)

    from ching_tech_os.services import path_manager as path_manager_module
    from ching_tech_os.services import shared_source_permissions as ssp

    monkeypatch.setattr(
        path_manager_module.path_manager,
        "get_shared_mounts",
        lambda: {"library": "/mnt/nas/library", "projects": "/mnt/nas/projects"},
    )
    monkeypatch.setattr(
        ssp,
        "get_allowed_shared_mounts_for_user",
        AsyncMock(return_value={"library": "/mnt/nas/library"}),
    )

    assert await share_service._resolve_source_permissions(1) == {"library": True}
